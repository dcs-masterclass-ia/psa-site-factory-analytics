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

from pipeline import detect, discover, funnel, ga4
from pipeline.controls import affiche, controle
from pipeline.sites import SITES, site as trouve_site

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data"
PARIS = timezone(timedelta(hours=2))          # CEST ; l'ecart hiver est assume


def esc_md(t):
    return str(t).replace("|", "\\|").replace("\n", " ")


def mois_a_traiter(jusqu_a=None):
    """Tous les mois depuis avril 2026 jusqu'au mois courant inclus."""
    fin = jusqu_a or datetime.now(PARIS).date()
    liste, an, m = [], 2026, 4
    while (an, m) <= (fin.year, fin.month):
        liste.append(f"{an}-{m:02d}")
        m += 1
        if m > 12:
            an, m = an + 1, 1
    return liste


def jour_fiable():
    """GA4 ne consolide pas avant 24 a 48 h : le dernier jour sur est J-2."""
    return (datetime.now(PARIS).date() - timedelta(days=2)).isoformat()


def assemble(cli, s, mois_liste, existant):
    """Reconstruit la partie GA4 d'un site. Retourne (donnees, journal)."""
    journal = []

    # 1. decouverte des hotes, a chaque execution
    debut = f"{mois_liste[0]}-01"
    fin = jour_fiable()
    liste_hotes = ga4.hotes(cli, s.propriete, debut, fin)
    hote_parent, hote_reprise, jrn = discover.deduire(liste_hotes, s.pays)
    journal += jrn

    d = json.loads(json.dumps(existant))      # copie
    d["daily"] = {"d": [], "u": [], "rep": []}
    d["trafficMonth"], d["repriseMonth"] = {}, {}
    d.setdefault("funnelMonth", {})
    anomalies, ratios, parts = {}, {}, {}
    methodes_funnel = {}

    limite = jour_fiable().replace("-", "")

    for mois in mois_liste:
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
        jours_reels = 0
        for j in range(1, nb + 1):
            cle = f"{an}{m:02d}{j:02d}"
            if cle > limite:
                break
            d["daily"]["d"].append(f"{m:02d}-{j:02d}")
            d["daily"]["u"].append(jp.get(cle, 0))
            d["daily"]["rep"].append(jr.get(cle, 0))
            jours_reels += 1

        d["trafficMonth"][mois] = {"sessions": tp, "tdays": jours_reels}
        d["repriseMonth"][mois] = {"sessions": tr, "rdays": jours_reels}

        a = detect.detecte(jr, prof_jour, s.pays, sess, users)
        if a:
            a["reprise_nette"] = tr - int(a["sessions"])
            a["part_pct"] = round(a["sessions"] / tr * 100, 1) if tr else 0
            anomalies[mois] = a
            journal.append(f"{mois} : {int(a['sessions'])} sessions automatisees "
                           f"({a['part_pct']} %) sur {len(a['jours'])} journees")
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

    if mois_liste and mois_liste[-1] not in d["months"]:
        d["months"] = [m for m in mois_liste if m in d["trafficMonth"]]
    d["periods"] = d["months"] + ["total"]

    cons = [m for m in d["months"] if not d["meta"].get(m, {}).get("provisional")]
    d["trafficMonth"]["total"] = {
        "sessions": sum(d["trafficMonth"][m]["sessions"] for m in cons),
        "tdays": sum(d["trafficMonth"][m]["tdays"] for m in cons)}
    d["repriseMonth"]["total"] = {
        "sessions": sum(d["repriseMonth"][m]["sessions"] for m in cons),
        "rdays": sum(d["repriseMonth"][m]["rdays"] for m in cons)}
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
        existant = json.loads(chemin.read_text())
        try:
            d, journal = assemble(cli, s, mois_liste, existant)
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
    else:
        print("Controle bloquant : aucune donnee ecrite, on garde celles de la veille.")
        ecrit_recap(f"\n**Contrôle bloquant : aucune donnée écrite, celles de la veille sont conservées.**")

    (DATA / "pipeline.json").write_text(
        json.dumps(etat, ensure_ascii=False, indent=1))
    print("ecrit  pipeline.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
