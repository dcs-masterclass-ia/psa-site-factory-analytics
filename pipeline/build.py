#!/usr/bin/env python3
"""Assemblage automatique des fichiers data/<site>.json.

Le pipeline regenere la partie GA4 — series quotidiennes, totaux mensuels,
detection de trafic automatise — et **preserve** la partie leads, qui reste
produite depuis le back-office. Rien n'est efface : ce qui n'est pas
regenerable est repris tel quel du fichier existant.

Aucune ecriture si un controle bloquant echoue -- pour CE site : l'ecriture
est incrementale, site par site, commit et pousse des qu'un site est pret
(voir _commit_et_pousse). Un site en echec de controle ou un push qui rate
ne bloque plus les autres -- perte reelle constatee deux fois le
07-08/08/2026 avec l'ancienne ecriture en un seul bloc a la fin du run :
d'abord un push final en echec qui a fait perdre ~2h de calcul GA4/GSC/leads
pour 52 sites, puis un controle bloquant sur seulement 4 sites qui a annule
l'ecriture des 48 autres, pourtant publiables. L'etat est ecrit dans
data/pipeline.json a chaque execution, succes comme echec, parce que c'est le
canal d'alerte du dashboard : un echec muet serait pire qu'un echec.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from pipeline import channel, detect, discover, funnel, funnel_weekly, ga4, insights, leads_extract, search_console, v2_report
from pipeline.controls import affiche, controle
from pipeline.sites import SITES, site as trouve_site

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data"
PARIS = timezone(timedelta(hours=2))          # CEST ; l'ecart hiver est assume
DECALAGE_GSC = 3   # Search Console publie avec un decalage de 2 a 3 jours,
                   # plus long que GA4 : on se limite a J-3 par prudence.


def esc_md(t):
    return str(t).replace("|", "\\|").replace("\n", " ")


MOIS_HISTORIQUE = 16   # 07/08/2026 : fenetre glissante (etait un debut fixe
                        # a janvier 2025). Search Console ne conserve que les
                        # 16 derniers mois cote Google, quel que soit ce
                        # qu'on demande ; au-dela, GA4 et les leads auraient
                        # plus de recul que Search Console, avec des mois
                        # "Total" qui ne compareraient plus le meme
                        # echantillon d'un rapport a l'autre. Les trois
                        # sources restent donc alignees sur la meme fenetre.

MOIS_RECENTS = 2        # 08/08/2026 : mois reellement retraites a chaque
                         # execution (mois en cours + precedent) — le reste
                         # de l'historique est repris tel quel du fichier
                         # existant. Retraiter les 16 mois chaque jour coute
                         # le meme temps qu'un backfill complet (~3h pour 60+
                         # sites) pour un resultat identique sur des mois deja
                         # consolides cote GA4. 2 mois laisse une marge large
                         # devant le delai de consolidation GA4 (24-48h,
                         # jour_fiable) et d'eventuels correctifs tardifs du
                         # back-office leads sur le mois qui vient de finir.


def mois_a_traiter(jusqu_a=None):
    """Les MOIS_HISTORIQUE derniers mois glissants jusqu'au mois courant
    inclus (meme fenetre que la limite de retention de Search Console)."""
    fin = jusqu_a or datetime.now(PARIS).date()
    an, m = fin.year, fin.month
    for _ in range(MOIS_HISTORIQUE - 1):
        m -= 1
        if m < 1:
            an, m = an - 1, 12
    liste = []
    while (an, m) <= (fin.year, fin.month):
        liste.append(f"{an}-{m:02d}")
        m += 1
        if m > 12:
            an, m = an + 1, 1
    return liste


def jour_fiable():
    """GA4 ne consolide pas avant 24 a 48 h : le dernier jour sur est J-2."""
    return (datetime.now(PARIS).date() - timedelta(days=2)).isoformat()


def jour_fiable_gsc():
    return (datetime.now(PARIS).date() - timedelta(days=DECALAGE_GSC)).isoformat()


def stub_vide(nom):
    """Structure minimale pour un site jamais encore assemble (pas de
    data/<slug>.json existant) : seules les cles que assemble() lit avant de
    les ecrire lui-meme (months/meta/leads) doivent preexister. Le reste
    (daily/trafficMonth/repriseMonth/funnelMonth) est reinitialise par
    assemble() de toute facon."""
    return {
        "site": nom,
        "months": [],
        "meta": {},
        "leads": {"total": {"total": 0, "daily": []}},
        "daily": {"d": [], "u": [], "rep": [], "sc": [], "si": []},
        "trafficMonth": {},
        "repriseMonth": {},
        "funnelMonth": {},
    }


def _decoupe_daily_existant(existant):
    """Reconstruit, a partir des tableaux 'daily' deja ecrits a plat, la part
    de chaque mois — meme decoupage que celui utilise pour les ecrire (les
    jours sont concatenes dans l'ordre de existant['months'], meta[mois]
    ['days'] jours consecutifs par mois)."""
    daily = existant.get("daily") or {}
    cles = ("d", "u", "rep", "sc", "si")
    par_mois = {}
    i = 0
    for m in existant.get("months", []):
        nb_jours = (existant.get("meta", {}).get(m) or {}).get("days", 0)
        par_mois[m] = {c: (daily.get(c) or [])[i:i + nb_jours] for c in cles}
        # migration "MM-DD" (ancien format, 5 caracteres) -> "YYYY-MM-DD" :
        # decouvert le 08/08/2026, une fenetre de 16 mois fait forcement
        # revenir le meme "MM-DD" deux fois (ex. aout 2025 ET aout 2026),
        # ce que le dashboard ne peut pas distinguer sans l'annee. Idempotent
        # (les jours deja au nouveau format ne sont pas retouches) : chaque
        # site se migre tout seul, au premier passage qui reutilise ce mois.
        par_mois[m]["d"] = [v if len(v) == 10 else f"{m[:4]}-{v}" for v in par_mois[m]["d"]]
        i += nb_jours
    return par_mois


def assemble(cli, gsc_cli, gsc_sites, s, mois_liste, existant):
    """Reconstruit la partie GA4 d'un site. Retourne (donnees, journal)."""
    journal = []

    # 1. decouverte des hotes, a chaque execution
    debut = f"{mois_liste[0]}-01"
    fin = jour_fiable()
    liste_hotes = ga4.hotes(cli, s.propriete, debut, fin)
    hote_parent, hote_reprise, jrn = discover.deduire(liste_hotes, s.pays)
    journal += jrn

    # Search Console : propriete deduite du meme hote de reprise que GA4,
    # jamais reconstruite separement. gsc_sites est None si l'API Search
    # Console est indisponible pour toute l'execution (pas seulement ce site).
    gsc_site = search_console.propriete_pour_hote(gsc_sites, hote_reprise) if gsc_sites is not None else None
    if gsc_sites is not None:
        journal.append(f"recherche : propriete `{gsc_site}`" if gsc_site
                       else "recherche : aucune propriete Search Console pour cet hote")

    d = json.loads(json.dumps(existant))      # copie
    d.setdefault("trafficMonth", {})
    d.setdefault("repriseMonth", {})
    d.setdefault("funnelMonth", {})
    d.setdefault("searchMonth", {})
    d.setdefault("audienceMonth", {})
    d.setdefault("rebondMonth", {})
    d.setdefault("convCanalDevice", {})
    d.setdefault("canalQuotidien", {})   # toujours present, meme vide : cle
                                          # attendue par structure_identique,
                                          # remplie plus bas seulement si la
                                          # dimension existe sur la propriete.
    # migration "MM-DD" -> "YYYY-MM-DD", memes raisons que _decoupe_daily_existant
    # ci-dessus : les mois preserves tels quels (non retraites ce run)
    # gardaient sinon indefiniment leurs anciennes cles sans annee.
    for _mois_c, _jours_c in d["canalQuotidien"].items():
        for _jour_c in list(_jours_c):
            if len(_jour_c) == 5:
                _jours_c[f"{_mois_c[:4]}-{_jour_c}"] = _jours_c.pop(_jour_c)
    d.setdefault("meta", {})
    anomalies = dict(d.get("anomaly") or {})
    ratios, parts = {}, {}
    methodes_funnel = {}
    anciens_daily = _decoupe_daily_existant(existant)
    nouveaux_daily = {}

    # voir MOIS_RECENTS : un site jamais assemble n'a rien a conserver et
    # recoit tout l'historique ; sinon, seuls les mois recents bougent
    # encore, le reste est repris tel quel de l'existant (aucun appel API).
    premiere_execution = not existant.get("months")
    if premiere_execution:
        mois_a_retraiter = list(mois_liste)
    else:
        recents = set(mois_liste[-MOIS_RECENTS:])
        # garde-fou : un mois attendu dans la fenetre mais absent des
        # donnees existantes (trou dans l'historique, jamais assemble) est
        # retraite meme s'il est ancien, plutot que de publier un trou.
        mois_manquants = {m for m in mois_liste
                          if m not in anciens_daily or m not in d["trafficMonth"]}
        mois_a_retraiter = [m for m in mois_liste if m in recents or m in mois_manquants]
    conserves = [m for m in mois_liste if m not in mois_a_retraiter]
    journal.append(
        f"mois retraités : {', '.join(mois_a_retraiter)}"
        + (f" — conservés tels quels : {', '.join(conserves)}" if conserves else ""))

    limite = jour_fiable().replace("-", "")
    limite_search = jour_fiable_gsc().replace("-", "")

    for mois in mois_a_retraiter:
        deb, f, nb = ga4.bornes(mois)
        if deb.replace("-", "") > limite:
            continue
        f_effectif = min(f.replace("-", ""), limite)
        f_iso = f"{f_effectif[:4]}-{f_effectif[4:6]}-{f_effectif[6:]}"

        jp = ga4.sessions_par_jour(cli, s.propriete, hote_parent, deb, f_iso)
        jr = ga4.sessions_par_jour(cli, s.propriete, hote_reprise, deb, f_iso)
        tp = ga4.sessions_total(cli, s.propriete, hote_parent, deb, f_iso)
        tr = ga4.sessions_total(cli, s.propriete, hote_reprise, deb, f_iso)
        sess, users = ga4.sessions_et_utilisateurs(cli, s.propriete, hote_reprise, deb, f_iso)

        # taux de rebond (global + par page) sur l'outil de reprise -- meme
        # perimetre que le reste de l'onglet GA4 (sessions/leads/conversion
        # parlent tous de l'outil de reprise, pas du site parent). Demande
        # du 10/08/2026.
        try:
            taux_reb = ga4.taux_rebond(cli, s.propriete, hote_reprise, deb, f_iso)
            pages_reb = ga4.rebond_et_conversion_par_page(
                cli, s.propriete, hote_reprise, deb, f_iso, funnel.EVENEMENT_ESTIMATION)
            d["rebondMonth"][mois] = {"taux": taux_reb, "sessions": tr, "pages": pages_reb}
            journal.append(f"{mois} : taux de rebond {taux_reb} %")
        except Exception as e:
            journal.append(f"{mois} : taux de rebond en erreur ({type(e).__name__})")

        # conversion par canal d'acquisition x type d'appareil -- demande du
        # 10/08/2026, meme evenement GA4 que le reste du Taux de conversion
        # (voir funnel.EVENEMENT_ESTIMATION).
        try:
            d["convCanalDevice"][mois] = funnel.conversion_par_canal_device(cli, s.propriete, hote_reprise, deb, f_iso)
        except Exception as e:
            journal.append(f"{mois} : conversion par canal/device en erreur ({type(e).__name__})")

        # funnel : reconstruit chaque mois, bascule automatique alpha -> repli.
        # on n'ecrase jamais un funnel existant par un echec : si les deux
        # methodes echouent, on garde ce qu'il y avait avant plutot que de
        # publier un trou ou une supposition.
        bloc_f, methode_f = funnel.bloc_funnel(cli, s.propriete, hote_reprise,
                                               deb, f_iso, nb)
        methodes_funnel[mois] = methode_f
        if bloc_f:
            d["funnelMonth"][mois] = bloc_f
            journal.append(f"{mois} : funnel via {methode_f}")
        elif mois not in d["funnelMonth"]:
            journal.append(f"{mois} : funnel indisponible ({methode_f})")

        # canal d'acquisition quotidien, pour le graphique en aires empilees.
        # entierement optionnel : si la dimension n'existe pas sur cette
        # propriete, on continue sans rien publier plutot que de bloquer.
        try:
            dim_canal, par_jour_canal = channel.canal_quotidien(cli, s.propriete, hote_parent, deb, f_iso)
        except Exception as e:
            dim_canal, par_jour_canal = None, {}
            journal.append(f"{mois} : canal quotidien en erreur ({type(e).__name__})")
        if dim_canal:
            d["canalQuotidien"][mois] = par_jour_canal
            journal.append(f"{mois} : canal quotidien via {dim_canal}")
        elif mois in d.get("canalQuotidien", {}):
            pass  # on garde la donnee du mois precedemment reussie

        # Search Console : optionnelle comme le canal quotidien — une
        # propriete absente ou une erreur d'API ne bloque jamais le reste du
        # site. Decalage de publication propre (DECALAGE_GSC), plus prudent
        # que celui de GA4.
        vue_recherche = {}
        if gsc_site and deb.replace("-", "") <= limite_search:
            f_search_effectif = min(f.replace("-", ""), limite_search)
            f_search_iso = f"{f_search_effectif[:4]}-{f_search_effectif[4:6]}-{f_search_effectif[6:]}"
            try:
                vue_recherche = search_console.vue_ensemble_quotidienne(
                    gsc_cli, gsc_site, deb, f_search_iso)
                total_recherche = search_console.total_periode(
                    gsc_cli, gsc_site, deb, f_search_iso)
                d["searchMonth"][mois] = {
                    **total_recherche,
                    "queries": search_console.top_requetes(gsc_cli, gsc_site, deb, f_search_iso, 20),
                    "pages": search_console.top_pages(gsc_cli, gsc_site, deb, f_search_iso, 20),
                }
                journal.append(f"{mois} : recherche {total_recherche['clics']} clics "
                               f"({total_recherche['impressions']} impressions)")
            except Exception as e:
                journal.append(f"{mois} : recherche en erreur ({type(e).__name__})")

        # profils pour la detection, par jour -- meme requete etendue avec
        # newVsReturning + totalUsers pour alimenter aussi "Audience &
        # environnement" cote dashboard (navigateur, nouveaux vs recurrents),
        # jusque-la marques "donnee non disponible" faute de remontee
        # pipeline. Demande le 09/08/2026 : source verifiee dans Looker
        # Studio (connecteur GA4 natif, memes dimensions/metrique
        # _totalUsers_) avant d'ajouter quoi que ce soit ici. Un seul appel
        # API pour les deux usages plutot qu'une requete separee -- prof_jour/
        # prof_mois gardent exactement la meme forme (cle (pays,nav,app) ->
        # sessions) qu'avant pour ne rien casser dans detect.py, qui ne
        # connait pas newVsReturning/totalUsers.
        brut = ga4._rapport(
            cli, s.propriete, deb, f_iso,
            ["date", "countryId", "browser", "deviceCategory", "newVsReturning"],
            ["sessions", "totalUsers"],
            ga4._egal("hostName", hote_reprise))
        prof_jour, prof_mois = {}, {}
        audience_device, audience_navigateur, audience_retour = {}, {}, {}
        # variable nommee jour_iso (pas "date") : ne pas masquer l'import
        # datetime.date, utilise plus loin pour le funnel hebdomadaire
        # glissant -- bug reel du 10/08/2026, provoquait une AttributeError
        # silencieuse ("'str' object has no attribute 'fromisoformat'") sur
        # tous les sites.
        for jour_iso, pays, nav, app, retour, n, u in brut:
            n, u = int(n), int(u)
            prof_jour.setdefault(jour_iso, {})[(pays, nav, app)] = \
                prof_jour.setdefault(jour_iso, {}).get((pays, nav, app), 0) + n
            prof_mois[(pays, nav, app)] = prof_mois.get((pays, nav, app), 0) + n
            for acc, cle in ((audience_device, app), (audience_navigateur, nav), (audience_retour, retour)):
                e = acc.setdefault(cle or "(non défini)", {"sessions": 0, "users": 0})
                e["sessions"] += n
                e["users"] += u
        d["audienceMonth"][mois] = {
            "device": audience_device, "browser": audience_navigateur, "newVsReturning": audience_retour,
        }

        an, m = int(mois[:4]), int(mois[5:7])
        chunk = {"d": [], "u": [], "rep": [], "sc": [], "si": []}
        jours_reels = 0
        for j in range(1, nb + 1):
            cle = f"{an}{m:02d}{j:02d}"
            if cle > limite:
                break
            cle_iso = f"{an}-{m:02d}-{j:02d}"
            # date complete (annee incluse), pas "MM-DD" : indispensable des
            # que la fenetre depasse 12 mois, sinon deux annees partagent le
            # meme "MM-DD" et deviennent indistinguables cote dashboard.
            chunk["d"].append(cle_iso)
            chunk["u"].append(jp.get(cle, 0))
            chunk["rep"].append(jr.get(cle, 0))
            # None (pas 0) au-dela du decalage de publication Search Console :
            # « pas encore connu » n'est pas « zero clic », meme lecon que
            # pour les leads non encore extraits du back-office.
            vr = vue_recherche.get(cle_iso)
            chunk["sc"].append(vr["clics"] if vr else None)
            chunk["si"].append(vr["impressions"] if vr else None)
            jours_reels += 1
        nouveaux_daily[mois] = chunk

        d["trafficMonth"][mois] = {"sessions": tp, "tdays": jours_reels}
        d["repriseMonth"][mois] = {"sessions": tr, "rdays": jours_reels}

        a = detect.detecte(jr, prof_jour, s.pays, sess, users)
        if a:
            a["reprise_nette"] = tr - int(a["sessions"])
            a["part_pct"] = round(a["sessions"] / tr * 100, 1) if tr else 0
            anomalies[mois] = a
            journal.append(f"{mois} : {int(a['sessions'])} sessions automatisees "
                           f"({a['part_pct']} %) sur {len(a['jours'])} journees")
        elif mois in anomalies:
            del anomalies[mois]     # reevalue et infirme sur un mois retraite
        ratios[mois] = round(sess / users, 1) if users else None
        parts[mois] = detect.part_etranger(prof_mois, s.pays)

        # meta : le mois en cours est provisoire
        if mois not in d["meta"]:
            d["meta"][mois] = {}
        d["meta"][mois].update({
            "label": d["meta"][mois].get("label", mois),
            "days": jours_reels,
            "partial": jours_reels < nb,
            "provisional": jours_reels < nb,
        })
        if jours_reels < nb:
            d["meta"][mois]["note"] = (
                f"Mois en cours. Relevé GA4 arrêté au {f_iso}, "
                "les données ne sont consolidées qu'après 24 à 48 heures.")

        # Les leads : extraction automatisee depuis le back-office (meme
        # point d'API que le bouton "Exporter" de l'interface, cf.
        # pipeline/leads_extract.py) pour les sites couverts. Toute panne
        # (token invalide, site absent, reseau) degrade vers les donnees
        # du jour precedent plutot que de publier un mois vide ou tronque.
        if s.nom in leads_extract.SITE_EXTRACT:
            try:
                d["leads"][mois] = leads_extract.bloc_leads_mois(s.nom, mois, nb, jours_reels)
                journal.append(f"{mois} : {d['leads'][mois]['total']} leads extraits "
                               f"automatiquement du back-office")
            except Exception as e:
                journal.append(f"{mois} : extraction leads en erreur "
                               f"({type(e).__name__}: {e}), donnees precedentes conservees")
                d["leads"].setdefault(mois, {"total": 0, "daily": []})
        else:
            # site non couvert par l'extraction automatique : comportement
            # historique, preserve tel quel — jamais 0 qui affirmerait a
            # tort « aucun lead ce jour-la ».
            bloc_leads = d["leads"].setdefault(mois, {"total": 0, "daily": []})
            serie = bloc_leads.setdefault("daily", [])
            if len(serie) < jours_reels:
                manquants = jours_reels - len(serie)
                serie.extend([None] * manquants)
                journal.append(f"{mois} : {manquants} jour(s) de leads non extraits "
                               f"du back-office (site non couvert par l'automatisation)")
            elif len(serie) > jours_reels:
                d["meta"][mois]["days"] = len(serie)

    # trafficMonth/repriseMonth/anomaly n'etaient jamais retraites hors
    # fenetre (mois_a_retraiter ne les touche pas) mais restent copies de
    # l'existant : sans ca ils s'accumuleraient indefiniment au fil des mois
    # qui sortent de la fenetre glissante, contrairement au comportement
    # d'avant (reset complet chaque jour).
    fenetre = set(mois_liste)
    for cle in ("trafficMonth", "repriseMonth", "rebondMonth", "convCanalDevice"):
        d[cle] = {m: v for m, v in d[cle].items() if m in fenetre or m == "total"}
    anomalies = {m: v for m, v in anomalies.items() if m in fenetre}

    # recalcule sans condition : avec l'ancien garde-fou ("seulement si le
    # mois courant manque"), une fenetre glissante qui perd un mois par le
    # DEBUT (pas par la fin) ne redeclenchait jamais le recalcul — 8 sites
    # sur les 59 deja traites sont restes figes a 5 mois affiches alors que
    # trafficMonth en contenait 16 (decouvert le 08/08/2026 en testant ce
    # correctif). Cout negligeable : liste de ~16 cles, aucun appel API.
    d["months"] = [m for m in mois_liste if m in d["trafficMonth"]]
    d["periods"] = d["months"] + ["total"]

    # reconstruction du tableau "daily" a plat : mois retraites depuis
    # nouveaux_daily, mois conserves depuis la decoupe de l'existant — dans
    # l'ordre de d["months"], seul ordre coherent avec meta[m]["days"].
    d["daily"] = {"d": [], "u": [], "rep": [], "sc": [], "si": []}
    for m in d["months"]:
        chunk = nouveaux_daily.get(m) or anciens_daily.get(m)
        if not chunk:
            continue
        for c in ("d", "u", "rep", "sc", "si"):
            d["daily"][c].extend(chunk[c])

    cons = [m for m in d["months"] if not d["meta"].get(m, {}).get("provisional")]
    d["trafficMonth"]["total"] = {
        "sessions": sum(d["trafficMonth"][m]["sessions"] for m in cons),
        "tdays": sum(d["trafficMonth"][m]["tdays"] for m in cons)}
    d["repriseMonth"]["total"] = {
        "sessions": sum(d["repriseMonth"][m]["sessions"] for m in cons),
        "rdays": sum(d["repriseMonth"][m]["rdays"] for m in cons)}
    # taux de rebond global : moyenne ponderee par le volume de sessions de
    # chaque mois, jamais une moyenne simple des pourcentages mensuels (un
    # mois a 10 sessions pese sinon autant qu'un mois a 10000).
    reb_cons = [m for m in cons if m in d["rebondMonth"]]
    reb_sessions = sum(d["rebondMonth"][m]["sessions"] for m in reb_cons)
    d["rebondMonth"]["total"] = {
        "taux": round(sum(d["rebondMonth"][m]["taux"] * d["rebondMonth"][m]["sessions"] for m in reb_cons) / reb_sessions, 2) if reb_sessions else 0.0,
        "sessions": reb_sessions,
    }
    # leads["total"] n'etait ecrit nulle part dans le pipeline (seulement lu,
    # par ce recalcul et par le controle cumul_egale_somme_mois) — reste
    # figee a la valeur de stub_vide (0) indefiniment. Passait inapercu tant
    # que l'ancien bug de d["months"] (voir plus haut) limitait "cons" a une
    # fenetre courte qui, par coincidence, correspondait a l'ancien total
    # fige ; le corriger a immediatement fait echouer cumul_egale_somme_mois
    # sur OPEL FR/CITROEN AT (decouvert le 08/08/2026). Meme perimetre que
    # trafficMonth["total"] : uniquement les mois consolides.
    d["leads"]["total"] = {
        "total": sum(d["leads"][m]["total"] for m in cons if m in d["leads"]),
        "daily": [v for m in cons for v in (d["leads"].get(m, {}).get("daily") or [])],
    }
    # meta["total"]["label"] : sites historiques, saisi a la main, jamais
    # ecrase. "days"/"partial" doivent en revanche suivre leads["total"]
    # recalcule juste au-dessus, sous peine de rompre a leur tour
    # longueur_daily_egale_days (lu pour m="total" aussi).
    d["meta"].setdefault("total", {})
    d["meta"]["total"]["label"] = d["meta"]["total"].get("label", "Total")
    d["meta"]["total"]["days"] = len(d["leads"]["total"]["daily"])
    d["meta"]["total"]["partial"] = len(cons) < len(d["months"])

    # total recalcule via un appel dedie sur la periode entiere, jamais
    # somme des tops mensuels : meme lecon que la vue cumulee des leads,
    # documentee au README — sommer des tops 20 aurait tronque les valeurs
    # sorties du classement certains mois.
    if gsc_site and cons:
        fin_totale = ga4.bornes(cons[-1])[1].replace("-", "")
        fin_totale_eff = min(fin_totale, limite_search)
        if debut.replace("-", "") <= fin_totale_eff:
            fin_totale_iso = f"{fin_totale_eff[:4]}-{fin_totale_eff[4:6]}-{fin_totale_eff[6:]}"
            try:
                total_recherche = search_console.total_periode(gsc_cli, gsc_site, debut, fin_totale_iso)
                d["searchMonth"]["total"] = {
                    **total_recherche,
                    "queries": search_console.top_requetes(gsc_cli, gsc_site, debut, fin_totale_iso, 20),
                    "pages": search_console.top_pages(gsc_cli, gsc_site, debut, fin_totale_iso, 20),
                }
            except Exception as e:
                journal.append(f"total : recherche en erreur ({type(e).__name__})")

    # insights IA : un jeu par rapport (Acquisition/Leads/Parcours toujours
    # tentes, Recherche uniquement s'il y a une propriete Search Console
    # reelle) — jamais invente sur des donnees absentes.
    d["insights"] = insights.genere_tous(s.nom, d, gsc_site)

    # rapport hebdomadaire V2 : sessions/leads recalcules depuis les series
    # deja assemblees ci-dessus, funnel via une requete GA4 par semaine
    # ecoulee depuis la bascule. Ne bloque jamais le site en cas d'echec.
    try:
        v2w = v2_report.rapport_hebdo(cli, s, d, jour_fiable(), hote_reprise)
        if v2w:
            d["v2Weekly"] = v2w
            journal.append(f"V2 hebdo : {len(v2w['weeks'])} semaine(s) depuis le {v2w['v2Date']}")
        elif "v2Weekly" in d:
            journal.append("V2 hebdo : pas assez de recul avant/après la bascule, conservé tel quel")
    except Exception as e:
        journal.append(f"V2 hebdo en erreur ({type(e).__name__}: {e})")
        v2w = None

    # funnel avant/apres V2 (v2steps, carte "Parcours d'estimation" du
    # dashboard) : derive de v2Weekly ci-dessus, jamais une extraction GA4
    # a part. Ne touche jamais un site deja curé manuellement (v2steps deja
    # non vide, sans le marqueur NOTE_AUTO) -- seuls les sites sans donnee ou
    # deja auto-generes sont (re)calcules, pour ameliorer tout seul avec
    # plus de recul au fil des semaines sans ecraser un travail manuel.
    deja_curee = bool(d.get("v2steps")) and (d.get("v2") or {}).get("note") != v2_report.NOTE_AUTO
    if not deja_curee:
        steps = v2_report.v2steps_depuis_hebdo(v2w) if v2w else None
        if steps:
            d["v2steps"] = steps
            pre_label = v2_report.label_plage(v2w["baseline"]["debut"], v2w["baseline"]["fin"])
            post_label = v2_report.label_plage(v2w["weeks"][0]["debut"], v2w["weeks"][-1]["fin"])
            d["v2"] = {"site": s.nom, "is_v2_split": True, "note": v2_report.NOTE_AUTO,
                       "pre_label": pre_label, "post_label": post_label}
            journal.append("V2 funnel avant/après : calculé automatiquement depuis v2Weekly")

    # funnel hebdomadaire glissant (funnelWeekly) : cadre precisement les
    # periodes choisies par l'utilisateur sur le dashboard, complementaire a
    # funnelMonth (mensuel, seul recours au-dela de la fenetre glissante).
    # Cout maitrise : 1 a 3 requetes funnel par site et par jour (semaine en
    # cours + rattrapage court), jamais un backfill de tout l'historique.
    try:
        jour_fiable_d = date.fromisoformat(jour_fiable())
        existantes = d.get("funnelWeekly") or {}
        for deb_s, fin_s in funnel_weekly.semaines_a_calculer(existantes, jour_fiable_d):
            jours_s = (fin_s - deb_s).days + 1
            bloc, _methode = funnel_weekly.bloc_semaine(cli, s.propriete, hote_reprise, deb_s, fin_s, jours_s)
            if bloc:
                existantes[deb_s.isoformat()] = {"debut": deb_s.isoformat(), "fin": fin_s.isoformat(),
                                                  "jours": jours_s, **bloc}
        d["funnelWeekly"] = funnel_weekly.purge_anciennes(existantes, jour_fiable_d)
        if d["funnelWeekly"]:
            journal.append(f"funnel hebdo : {len(d['funnelWeekly'])} semaine(s) en memoire")
    except Exception as e:
        journal.append(f"funnel hebdo en erreur ({type(e).__name__}: {e})")

    d["anomaly"] = anomalies
    d["_ratios_sessions_users"] = ratios
    d["_part_etranger"] = parts
    d["_hotes"] = {"parent": hote_parent, "reprise": hote_reprise}
    d["_methodes_funnel"] = methodes_funnel
    return d, journal


def nettoie(d):
    """Retire les cles de diagnostic avant ecriture."""
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _git(*args):
    return subprocess.run(["git", *args], cwd=RACINE, capture_output=True, text=True)


def _configure_git():
    _git("config", "user.name", "dcs-masterclass-ia")
    _git("config", "user.email", "m.foureau@autobiz.com")


def _commit_et_pousse(chemins, message):
    """Committe et pousse un petit sous-ensemble de fichiers deja ecrits sur
    disque (chemins relatifs a RACINE, ex. "data/opel-fr.json"). Ne leve
    jamais : un push qui echoue est journalise puis le run continue avec le
    site suivant, jamais un fichier deja ecrit ne doit faire perdre le
    travail des autres sites.

    Retourne (succes: bool, detail: str). "detail" est vide en succes."""
    # branche cible lue dynamiquement (jamais "main" en dur) : GITHUB_REF_NAME
    # est fournie automatiquement par Actions et vaut deja la bonne branche,
    # que le declenchement soit schedule (-> main) ou workflow_dispatch
    # --ref staging (-> staging) -- c'est ce qui permet a un run de pipeline
    # lance depuis la preprod de ne jamais toucher aux donnees de prod.
    branche = os.environ.get("GITHUB_REF_NAME", "main")
    rel = [str(c) for c in chemins]
    r = _git("add", *rel)
    if r.returncode != 0:
        return False, f"git add : {r.stderr.strip()}"
    r = _git("commit", "-m", message)
    if r.returncode != 0:
        if "nothing to commit" in (r.stdout + r.stderr):
            return True, ""
        return False, f"git commit : {r.stderr.strip()}"
    for _tentative in range(3):
        r = _git("push", "origin", f"HEAD:{branche}")
        if r.returncode == 0:
            return True, ""
        _git("fetch", "origin", branche)
        rebase = _git("rebase", f"origin/{branche}")
        if rebase.returncode != 0:
            conflits = [c for c in _git("diff", "--name-only", "--diff-filter=U").stdout.split() if c]
            # "--theirs" pendant un rebase designe le commit rejoue, donc
            # notre travail local -- meme piege/logique que dans
            # refresh.yml. Uniquement s'il n'y a pas d'autre fichier en
            # conflit que ceux de CE commit : sinon, un autre changement
            # imprevu est en jeu, on abandonne plutot que d'ecraser a l'aveugle.
            if conflits and set(conflits) <= set(rel):
                _git("checkout", "--theirs", *conflits)
                _git("add", *conflits)
                if _git("rebase", "--continue").returncode != 0:
                    _git("rebase", "--abort")
                    return False, f"rebase --continue en echec sur {conflits}"
            else:
                _git("rebase", "--abort")
                return False, f"conflit sur {conflits or '(indetermine)'}"
    return False, "push impossible apres 3 tentatives"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", nargs="*", help="par defaut : tous ceux qui ont l'acces API")
    ap.add_argument("--ecrire", action="store_true",
                    help="sans ce drapeau, rien n'est ecrit sur le disque")
    a = ap.parse_args()

    cibles = [trouve_site(x) for x in a.sites] if a.sites else [s for s in SITES if s.acces_api]
    mois_liste = mois_a_traiter()
    modele = json.loads((DATA / "opel-fr.json").read_text())
    cli = ga4.client()

    # Search Console est entierement optionnel : si l'API n'est pas
    # accessible du tout, le pipeline continue sans lui plutot que d'echouer.
    gsc_cli, gsc_sites = None, None
    try:
        gsc_cli = search_console.client()
        gsc_sites = search_console.sites_accessibles(gsc_cli)
        print(f"Search Console : {len(gsc_sites)} propriete(s) accessible(s) au total.")
    except Exception as e:
        print(f"Search Console indisponible pour toute l'execution : {type(e).__name__}: {e}")

    recap = os.environ.get("GITHUB_STEP_SUMMARY")

    def ecrit_recap(texte):
        """Ecrit immediatement, site par site : jamais perdu a une troncature."""
        if recap:
            with open(recap, "a", encoding="utf-8") as f:
                f.write(texte + "\n")

    ecrit_recap(f"## Rafraîchissement automatique — {datetime.now(PARIS).strftime('%d/%m/%Y %H:%M')}\n")
    ecrit_recap(f"Mois traités : {', '.join(mois_liste)} — dernier jour fiable : {jour_fiable()}\n")
    ecrit_recap("### Hôtes découverts\n")
    ecrit_recap("| Site | Parent | Reprise |")
    ecrit_recap("|---|---|---|")

    etat = {
        "derniere_execution": datetime.now(PARIS).isoformat(timespec="seconds"),
        "commit": os.environ.get("GITHUB_SHA", "")[:7],
        "jour_ga4_fiable": jour_fiable(),
        "mois_traites": mois_liste,
        "statut": "ok",
        "sites": {},
        "anomalies": [],
    }
    rapports, sites_ecrits, sites_bloques = [], [], []

    if a.ecrire:
        _configure_git()

    for s in SITES:
        if not s.acces_api:
            etat["sites"][s.nom] = {
                "statut": "indisponible",
                "motif": f"compte de service non autorise sur la propriete {s.propriete}",
            }
            continue
        if s not in cibles:
            continue

        chemin = DATA / f"{s.slug}.json"
        if chemin.exists():
            existant = json.loads(chemin.read_text())
        else:
            existant = stub_vide(s.nom)
            print(f"{s.nom} : premiere execution, aucun {chemin.name} existant — structure vide initialisee")
        try:
            d, journal = assemble(cli, gsc_cli, gsc_sites, s, mois_liste, existant)
        except discover.Ambigu as e:
            etat["sites"][s.nom] = {"statut": "indisponible",
                                    "motif": f"hotes indeterminables : {e}"}
            print(f"{s.nom} : AMBIGU — {e}")
            ecrit_recap(f"| {s.nom} | *ambigu* | {esc_md(str(e))} |")
            continue
        except Exception as e:
            etat["sites"][s.nom] = {"statut": "indisponible",
                                    "motif": f"{type(e).__name__}: {e}"}
            print(f"{s.nom} : ERREUR — {type(e).__name__}: {e}")
            ecrit_recap(f"| {s.nom} | *erreur* | {type(e).__name__} |")
            continue

        h = d["_hotes"]
        ecrit_recap(f"| {s.nom} | `{h['parent']}` | `{h['reprise']}` |")

        r = controle(d, ancien=existant, modele=modele)
        rapports.append(r)
        etat["sites"][s.nom] = {
            "statut": r.statut,
            "hotes": h,
            "ga4_jusqu_au": etat["jour_ga4_fiable"],
            "controles": {"passes": sum(1 for x in r.resultats if x.ok),
                          "total": len(r.resultats)},
        }
        for x in r.avertissements:
            etat["anomalies"].append({"site": s.nom, "controle": x.nom,
                                      "detail": x.detail, "gravite": "avertissement"})
        for x in r.echecs_bloquants:
            etat["anomalies"].append({"site": s.nom, "controle": x.nom,
                                      "detail": x.detail, "gravite": "bloquant"})
        for l in journal:
            print(f"   {s.nom} — {l}")
        if journal:
            ecrit_recap(f"\n<details><summary>{s.nom} — détail</summary>\n\n"
                       + "\n".join(f"- {esc_md(l)}" for l in journal) + "\n\n</details>")
        if r.publiable:
            sites_ecrits.append(s.nom)
            if a.ecrire:
                chemin.write_text(json.dumps(nettoie(d), ensure_ascii=False, separators=(",", ":")))
                ok, detail = _commit_et_pousse(
                    [chemin.relative_to(RACINE).as_posix()],
                    f"Rafraîchissement automatique — {s.nom}")
                if ok:
                    print(f"ecrit+pousse  {chemin.name}")
                else:
                    print(f"{s.nom} : ECRIT MAIS PUSH EN ECHEC — {detail}")
                    etat["anomalies"].append({"site": s.nom, "controle": "push_git",
                                              "detail": detail, "gravite": "avertissement"})
        else:
            sites_bloques.append(s.nom)

    ecrit_recap("\n### Contrôles\n")
    ecrit_recap("```")
    ecrit_recap(affiche(rapports))
    ecrit_recap("```")
    print(affiche(rapports))

    # ecriture desormais incrementale (voir la boucle ci-dessus) : un site
    # bloque ne concerne plus que lui-meme, jamais les autres -- "echec" ne
    # veut donc plus dire "rien n'a ete ecrit", mais "au moins un site ne
    # l'a pas ete". Le detail par site reste dans etat["sites"][nom]["statut"].
    if sites_bloques:
        etat["statut"] = "echec"
        etat["blocage"] = (f"{len(sites_bloques)} site(s) en echec de controle : "
                           f"{', '.join(sites_bloques)}. Donnees de la veille conservees pour ces "
                           f"sites uniquement, les {len(sites_ecrits)} autre(s) mis a jour normalement.")
    elif etat["anomalies"]:
        etat["statut"] = "degrade"

    if not a.ecrire:
        print("\nMode simulation : rien n'a ete ecrit. Ajouter --ecrire pour publier.")
        print(f"statut calcule : {etat['statut']}")
        ecrit_recap(f"\n_Mode simulation : rien n'a été écrit. Statut calculé : **{etat['statut']}**._")
        return 0

    # data/index.json liste les sites que le dashboard doit charger.
    # Recalcule a chaque execution, a partir des fichiers data/<slug>.json
    # reellement presents sur disque, jamais de la seule liste SITES (un
    # site en echec de controle garde son fichier de la veille et doit
    # rester visible, un site jamais publie ne doit pas apparaitre et faire
    # 404 cote dashboard).
    ordre = {s.nom: i for i, s in enumerate(SITES)}
    presents = {s.slug: s.nom for s in SITES}
    noms_index = sorted(
        (presents[f.stem] for f in DATA.glob("*.json") if f.stem in presents),
        key=lambda n: ordre[n])
    chemin_index = DATA / "index.json"
    chemin_index.write_text(json.dumps({"sites": noms_index}, ensure_ascii=False, separators=(",", ":")))
    ok, detail = _commit_et_pousse(["data/index.json"], "Rafraîchissement automatique — index.json")
    print(f"ecrit+pousse  index.json ({len(noms_index)} site(s))" if ok
          else f"index.json : ECRIT MAIS PUSH EN ECHEC — {detail}")

    (DATA / "pipeline.json").write_text(
        json.dumps(etat, ensure_ascii=False, indent=1))
    ok, detail = _commit_et_pousse(["data/pipeline.json"],
                                   f"Rafraîchissement automatique — statut {etat['statut']}")
    print("ecrit+pousse  pipeline.json" if ok
          else f"pipeline.json : ECRIT MAIS PUSH EN ECHEC — {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
