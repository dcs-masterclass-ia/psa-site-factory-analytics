#!/usr/bin/env python3
"""Assemblage automatique des fichiers data/<site>.json.

Le pipeline regenere la partie GA4 — series quotidiennes, totaux mensuels,
detection de trafic automatise — et **preserve** la partie leads, qui reste
produite depuis le back-office. Rien n'est efface : ce qui n'est pas
regenerable est repris tel quel du fichier existant.

Aucune ecriture si un controle bloquant echoue. L'etat est ecrit dans
data/pipeline.json a chaque execution, succes comme echec, parce que c'est le
canal d'alerte du dashboard : un echec muet serait pire qu'un echec.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline import channel, detect, discover, funnel, ga4, insights, leads_extract, search_console, v2_report
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
    d.setdefault("canalQuotidien", {})   # toujours present, meme vide : cle
                                          # attendue par structure_identique,
                                          # remplie plus bas seulement si la
                                          # dimension existe sur la propriete.
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

        # profils pour la detection, par jour
        brut = ga4._rapport(
            cli, s.propriete, deb, f_iso,
            ["date", "countryId", "browser", "deviceCategory"], ["sessions"],
            ga4._egal("hostName", hote_reprise))
        prof_jour, prof_mois = {}, {}
        for date, pays, nav, app, n in brut:
            n = int(n)
            prof_jour.setdefault(date, {})[(pays, nav, app)] = \
                prof_jour.setdefault(date, {}).get((pays, nav, app), 0) + n
            prof_mois[(pays, nav, app)] = prof_mois.get((pays, nav, app), 0) + n

        an, m = int(mois[:4]), int(mois[5:7])
        chunk = {"d": [], "u": [], "rep": [], "sc": [], "si": []}
        jours_reels = 0
        for j in range(1, nb + 1):
            cle = f"{an}{m:02d}{j:02d}"
            if cle > limite:
                break
            cle_iso = f"{an}-{m:02d}-{j:02d}"
            chunk["d"].append(f"{m:02d}-{j:02d}")
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
    for cle in ("trafficMonth", "repriseMonth"):
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
    # meta["total"] n'est ecrit qu'une fois : sites historiques, le libelle a
    # ete saisi a la main et reste tel quel (setdefault ne l'ecrase pas).
    # Pour un site jamais assemble, evite un KeyError dans controle()
    # (longueur_daily_egale_days lit meta[m]["days"] pour m="total" aussi) —
    # "days" doit valoir la longueur reelle de leads["total"]["daily"], pas
    # un total GA4 : ce controle verifie la coherence de la serie leads,
    # jamais maintenue automatiquement pour la periode "total" (voir
    # stub_vide), donc figee a 0 tant qu'aucune extraction leads n'existe.
    d["meta"].setdefault("total", {
        "label": "Total",
        "days": len(d["leads"]["total"]["daily"]),
        "partial": len(cons) < len(d["months"]),
    })

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

    d["anomaly"] = anomalies
    d["_ratios_sessions_users"] = ratios
    d["_part_etranger"] = parts
    d["_hotes"] = {"parent": hote_parent, "reprise": hote_reprise}
    d["_methodes_funnel"] = methodes_funnel
    return d, journal


def nettoie(d):
    """Retire les cles de diagnostic avant ecriture."""
    return {k: v for k, v in d.items() if not k.startswith("_")}


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
    rapports, a_ecrire = [], {}

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
            a_ecrire[chemin] = nettoie(d)

    ecrit_recap("\n### Contrôles\n")
    ecrit_recap("```")
    ecrit_recap(affiche(rapports))
    ecrit_recap("```")
    print(affiche(rapports))

    bloques = [r.site for r in rapports if not r.publiable]
    if bloques:
        etat["statut"] = "echec"
        etat["blocage"] = (f"{len(bloques)} site(s) en echec de controle : "
                           f"{', '.join(bloques)}. Donnees de la veille conservees.")
    elif etat["anomalies"]:
        etat["statut"] = "degrade"

    if not a.ecrire:
        print("\nMode simulation : rien n'a ete ecrit. Ajouter --ecrire pour publier.")
        print(f"statut calcule : {etat['statut']}")
        ecrit_recap(f"\n_Mode simulation : rien n'a été écrit. Statut calculé : **{etat['statut']}**._")
        return 0

    # les donnees ne sont ecrites que si tout passe ; l'etat l'est toujours
    if etat["statut"] != "echec":
        for chemin, contenu in a_ecrire.items():
            chemin.write_text(json.dumps(contenu, ensure_ascii=False, separators=(",", ":")))
            print(f"ecrit  {chemin.name}")

        # data/index.json liste les sites que le dashboard doit charger.
        # Aucun script ne le regenerait jusqu'ici (decouvert le 07/08/2026,
        # reste bloque sur les 8 sites d'origine malgre les 56 ajoutes) :
        # recalcule desormais a chaque ecriture, a partir des fichiers
        # data/<slug>.json reellement presents sur disque, jamais de la
        # seule liste SITES (un site en echec de controle garde son fichier
        # de la veille et doit rester visible, un site jamais publie ne
        # doit pas apparaitre et faire 404 cote dashboard).
        ordre = {s.nom: i for i, s in enumerate(SITES)}
        presents = {s.slug: s.nom for s in SITES}
        noms_index = sorted(
            (presents[f.stem] for f in DATA.glob("*.json") if f.stem in presents),
            key=lambda n: ordre[n])
        (DATA / "index.json").write_text(
            json.dumps({"sites": noms_index}, ensure_ascii=False, separators=(",", ":")))
        print(f"ecrit  index.json ({len(noms_index)} site(s))")
    else:
        print("Controle bloquant : aucune donnee ecrite, on garde celles de la veille.")
        ecrit_recap(f"\n**Contrôle bloquant : aucune donnée écrite, celles de la veille sont conservées.**")

    (DATA / "pipeline.json").write_text(
        json.dumps(etat, ensure_ascii=False, indent=1))
    print("ecrit  pipeline.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
