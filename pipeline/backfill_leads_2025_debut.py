"""Rattrapage des leads back-office de janvier a avril 2025 -- periode
JAMAIS couverte par le pipeline (GA4 n'a de donnees que depuis le
09/08/2026... en realite depuis mai 2025 pour tous les sites, voir
data/*.json:daily.d). Confirme le 11/08/2026 via pipeline/_diag_valide.py :
le back-office a bien de vrais leads sur cette periode (35078 leads
valides sur PEUGEOT FR en janvier 2025 seul), donc pas un "vrai zero" a
laisser vide.

IMPORTANT -- n'ecrit QUE d["leads"][mois], jamais d["months"]/d["meta"] :
_decoupe_daily_existant() (pipeline/build.py) utilise d["months"] comme
index pour re-decouper le tableau daily GA4 CONCATENE en tranches par
mois (meta[m]["days"] jours consecutifs par mois, dans l'ordre de
d["months"]). Ajouter janv-avril 2025 a d["months"] sans avoir de vraies
donnees GA4 a prepender au tableau daily decalerait TOUT le reste de
l'historique de trafic au prochain run de build.py -- corruption
silencieuse. d["leads"][mois] est un sous-objet independant (lu par son
propre nom de cle dans index.html, jamais via d["months"]), donc sans
risque d'y ajouter des mois hors de la plage GA4.

Consequence assumee : d["leads"]["total"] (KPI "Leads GCP", donut
Marques reprises, etc., tous scopes a d["months"]) ne bougera PAS -- seul
le module "Leads par pays" (qui lit Object.keys(d.leads) directement)
beneficie de ce rattrapage. Coherent avec le fait que ce KPI a toujours
ete cadre sur la periode GA4 du site, pas sur tout l'historique
back-office disponible.

Usage :
  python -m pipeline.backfill_leads_2025_debut                    # tous les sites SITE_EXTRACT
  python -m pipeline.backfill_leads_2025_debut --sites "OPEL FR"
  python -m pipeline.backfill_leads_2025_debut --dry-run
"""

import argparse
import calendar
import json
import re
from pathlib import Path

from pipeline import leads_extract
from pipeline.build import _commit_et_pousse, _configure_git

RACINE = Path(__file__).resolve().parent.parent
DATA_DIR = RACINE / "data"
MOIS_CIBLES = ["2025-01", "2025-02", "2025-03", "2025-04"]


def _slug(nom):
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", nom.lower()))


def rattrape_site(nom, dry_run=False):
    chemin = DATA_DIR / f"{_slug(nom)}.json"
    if not chemin.exists():
        print(f"{nom} : fichier introuvable ({chemin.name}), ignore")
        return None
    if nom not in leads_extract.SITE_EXTRACT:
        print(f"{nom} : pas dans SITE_EXTRACT, ignore")
        return None

    d = json.loads(chemin.read_text(encoding="utf-8"))
    d.setdefault("leads", {})
    a_faire = [m for m in MOIS_CIBLES if m not in d["leads"]]
    if not a_faire:
        return None

    print(f"{nom} : {len(a_faire)} mois a recuperer ({a_faire[0]}..{a_faire[-1]})")
    total_recupere = 0
    ecrit = False
    for m in a_faire:
        an, mo = int(m[:4]), int(m[5:7])
        jours = calendar.monthrange(an, mo)[1]
        try:
            bloc = leads_extract.bloc_leads_mois(nom, m, jours, jours)
        except Exception as e:
            print(f"  {nom} {m} : echec extraction ({type(e).__name__}: {e}), laisse absent")
            continue
        d["leads"][m] = bloc
        total_recupere += bloc["total"]
        ecrit = True
        print(f"  {nom} {m} : {bloc['total']} leads")

    if not ecrit:
        print(f"  {nom} : aucun mois recupere (toutes les extractions ont echoue)")
        return None

    if dry_run:
        print(f"  {nom} : +{total_recupere} leads recuperes (dry-run, rien d'ecrit)")
        return total_recupere

    chemin.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ok, detail = _commit_et_pousse(
        [f"data/{chemin.name}"],
        f"Rattrapage leads BO janv-avril 2025 — {nom}")
    if not ok:
        print(f"  {nom} : ECHEC commit/push ({detail}) -- fichier ecrit localement, pas publie")
    else:
        print(f"  {nom} : +{total_recupere} leads recuperes, publie")
    return total_recupere


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", nargs="*", help="par defaut : tous ceux couverts par SITE_EXTRACT")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not a.dry_run:
        _configure_git()

    cibles = a.sites or sorted(leads_extract.SITE_EXTRACT.keys())
    resultats = {}
    for nom in cibles:
        r = rattrape_site(nom, dry_run=a.dry_run)
        if r:
            resultats[nom] = r

    print()
    print(f"=== {len(resultats)} site(s) rattrape(s) sur {len(cibles)} passe(s) en revue ===")
    print(f"Total leads recuperes (janv-avril 2025) : {sum(resultats.values())}")


if __name__ == "__main__":
    main()
