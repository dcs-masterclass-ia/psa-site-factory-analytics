"""Sites « leads back-office seulement » : pas de propriete GA4 dans sites.py.

Fiat Pro (BE, LU, FR, ES, PT), Leapmotor (BE, LU), Fiat PL et Lancia LU ont
des leads dans le back-office (leads_extract.SITE_EXTRACT) mais aucune
propriete GA4 enregistree : build.py ne les traite donc pas, et ils
manquaient au dashboard (9 sites, ~5 100 leads sur 2026 -- trouve le
10/10/2026 en comparant le total BO a l'affichage du dashboard).

Ce module ecrit data/<slug>.json pour chacun, au meme schema que les autres
sites : leads BO reels (meme extraction que build.py, bloc_leads_mois), series
de trafic GA4 a zero, tout le reste vide. Il les declare aussi dans
data/pipeline.json avec le statut "leads_seuls" (c'est cette liste que lit le
dashboard pour construire le selecteur de sites).

Jamais de chiffre GA4 invente : trafic, funnel et Search Console restent
vides tant qu'une propriete n'est pas enregistree dans sites.py. Des qu'un de
ces sites y est ajoute, build.py prend le relais et ce module l'ignore.

Usage :
  python -m pipeline.leads_seuls --dry-run
  python -m pipeline.leads_seuls --ecrire [--sites "FIAT PRO FR" ...]
"""

import argparse
import calendar
import json
import re
import time
import urllib.error
from datetime import datetime, timedelta

from pipeline import leads_extract
from pipeline.build import DATA, PARIS, _commit_et_pousse, _configure_git, mois_a_traiter
from pipeline.sites import SITES

STATUT = "leads_seuls"
MOTIF = "leads back-office seulement (pas de propriété GA4 enregistrée)"


def sites_leads_seuls():
    """Sites connus du back-office mais absents de sites.py, tries."""
    avec_ga4 = {s.nom for s in SITES}
    return sorted(n for n in leads_extract.SITE_EXTRACT if n not in avec_ga4)


def slug(nom):
    # meme regle que le dashboard (index.html, boot) : minuscules, "&" retire,
    # espaces -> "-"
    return re.sub(r"\s+", "-", nom.lower().replace("&", ""))


def _extrait(nom, m, nb, jours_reels, essais=6):
    """bloc_leads_mois avec patience : l'API BO repond 429 quand on enchaine
    trop de requetes (constate le 10/10/2026 sur ce module)."""
    for i in range(essais):
        try:
            return leads_extract.bloc_leads_mois(nom, m, nb, jours_reels)
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == essais - 1:
                raise
            time.sleep(30)


def construit(nom, mois_liste, dernier_jour):
    """Fichier data/<slug>.json complet pour un site leads seuls."""
    d = {
        "site": nom,
        "leads_seuls": True,
        "months": list(mois_liste),
        "meta": {},
        "leads": {},
        "daily": {"d": [], "u": [], "rep": [], "sc": [], "si": []},
        "trafficMonth": {}, "repriseMonth": {}, "funnelMonth": {}, "searchMonth": {},
        "canalQuotidien": {}, "audienceMonth": {}, "rebondMonth": {}, "convCanalDevice": {},
        "landingMonth": {}, "funnelDaily": {}, "funnelWeekly": {},
        "insights": {}, "anomaly": {}, "pagespeed": {}, "gscProperty": "",
    }
    mois_courant = dernier_jour[:7]
    for m in mois_liste:
        an, mm = int(m[:4]), int(m[5:])
        nb = calendar.monthrange(an, mm)[1]
        en_cours = m == mois_courant
        jours = int(dernier_jour[8:]) if en_cours else nb
        if m > mois_courant:          # mois futur : rien a extraire
            continue
        d["meta"][m] = {
            "label": m, "days": jours, "partial": en_cours, "provisional": en_cours,
            **({"note": f"Mois en cours. Relevé arrêté au {dernier_jour}."} if en_cours else {}),
        }
        d["leads"][m] = _extrait(nom, m, nb, jours if en_cours else None)
        time.sleep(1)
        d["daily"]["d"] += [f"{m}-{j:02d}" for j in range(1, jours + 1)]
        for c in ("u", "rep", "sc", "si"):
            d["daily"][c] += [0] * jours
        d["trafficMonth"][m] = {"sessions": 0, "tdays": jours}
        d["repriseMonth"][m] = {"sessions": 0, "rdays": jours}
    d["months"] = [m for m in mois_liste if m in d["meta"]]
    d["periods"] = d["months"] + ["total"]
    cons = [m for m in d["months"] if not d["meta"][m]["provisional"]]
    d["leads"]["total"] = {
        "total": sum(d["leads"][m]["total"] for m in cons),
        "daily": [v for m in cons for v in (d["leads"][m].get("daily") or [])],
    }
    d["meta"]["total"] = {"label": "Total", "days": len(d["leads"]["total"]["daily"]),
                          "partial": len(cons) < len(d["months"])}
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", nargs="*", help="par defaut : tous les sites leads seuls")
    ap.add_argument("--ecrire", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cibles = a.sites or sites_leads_seuls()
    inconnus = [n for n in cibles if n not in sites_leads_seuls()]
    if inconnus:
        raise SystemExit(f"pas des sites « leads seuls » (absents du back-office ou deja dans sites.py) : {inconnus}")
    mois_liste = mois_a_traiter()
    # veille (jamais le jour en cours, partiel) : meme convention que les autres sites
    dernier_jour = (datetime.now(PARIS) - timedelta(days=1)).strftime("%Y-%m-%d")
    if not a.ecrire:
        print(f"Mode simulation. {len(cibles)} site(s) : {', '.join(cibles)}")
    else:
        _configure_git()

    etat_chemin = DATA / "pipeline.json"
    etat = json.loads(etat_chemin.read_text()) if etat_chemin.exists() else {"sites": {}}
    ecrits = []
    for nom in cibles:
        try:
            d = construit(nom, mois_liste, dernier_jour)
        except Exception as e:
            print(f"{nom} : ERREUR extraction ({type(e).__name__}: {e}), site conserve tel quel")
            continue
        total = d["leads"]["total"]["total"]
        print(f"{nom} : {len(d['months'])} mois, {total} leads cumules (mois consolides)")
        if not a.ecrire:
            continue
        chemin = DATA / f"{slug(nom)}.json"
        chemin.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        etat.setdefault("sites", {})[nom] = {"statut": STATUT, "motif": MOTIF}
        ecrits.append(chemin.name)

    if a.ecrire and ecrits:
        etat_chemin.write_text(json.dumps(etat, ensure_ascii=False, indent=1))
        ok, detail = _commit_et_pousse([f"data/{n}" for n in ecrits] + ["data/pipeline.json"],
                                       f"Sites leads seuls — {len(ecrits)} site(s) (BO sans GA4)")
        print("publie" if ok else f"ECHEC commit/push ({detail})")


if __name__ == "__main__":
    main()
