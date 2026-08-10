"""Rattrapage historique des leads back-office (extraction automatique).

leads_extract.py (SITE_EXTRACT) n'a ete branche sur la plupart des sites
qu'en juillet 2026 : le run quotidien (build.py) ne retraite que les
derniers mois a chaque passage, jamais tout l'historique -- les mois
anterieurs a ce branchement sont donc restes a zero indefiniment, jamais
un vrai zero. Trouve le 10/08/2026 : 53 des 64 sites avaient un total de
leads a zero sur mai 2025 - juin 2026, faussant tout calcul agrege sur une
longue periode (le "Taux de conversion"/"Leads" en vue "Tous les sites",
notamment).

Rejoue la MEME extraction reelle (leads_extract.bloc_leads_mois, celle
deja utilisee pour les mois courants) sur les mois consolides dont le
total est a zero -- jamais un chiffre recalcule ou invente, seulement le
meme appel API rejoue sur le passe. Recalcule ensuite leads["total"] avec
la meme logique que build.py (voir son commentaire du 08/08/2026 a ce
sujet), pour rester coherent avec les controles existants
(cumul_egale_somme_mois, longueur_daily_egale_days).

Usage :
  python -m pipeline.backfill_leads                    # tous les sites couverts par SITE_EXTRACT
  python -m pipeline.backfill_leads --sites "OPEL FR" "PEUGEOT FR"
  python -m pipeline.backfill_leads --dry-run           # calcule et affiche, n'ecrit rien
"""

import argparse
import json
import re
from pathlib import Path

from pipeline import leads_extract
from pipeline.build import _commit_et_pousse, _configure_git

RACINE = Path(__file__).resolve().parent.parent
DATA_DIR = RACINE / "data"


def _slug(nom):
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", nom.lower()))


def _mois_a_zero(d):
    """Mois consolides (non provisoires : le mois en cours ne compte pas,
    ce n'est pas une anomalie qu'il soit encore partiel) dont le total de
    leads est a zero -- candidats au rattrapage."""
    cons = [m for m in d.get("months", []) if not d.get("meta", {}).get(m, {}).get("provisional")]
    return [m for m in cons if (d.get("leads", {}).get(m) or {}).get("total", 0) == 0]


def _recalcule_total(d):
    """Meme logique que build.py (voir son commentaire du 08/08/2026) :
    leads["total"] = somme/concatenation des mois consolides uniquement."""
    cons = [m for m in d["months"] if not d["meta"].get(m, {}).get("provisional")]
    d["leads"]["total"] = {
        "total": sum(d["leads"][m]["total"] for m in cons if m in d["leads"]),
        "daily": [v for m in cons for v in (d["leads"].get(m, {}).get("daily") or [])],
    }
    d["meta"].setdefault("total", {})
    d["meta"]["total"]["label"] = d["meta"]["total"].get("label", "Total")
    d["meta"]["total"]["days"] = len(d["leads"]["total"]["daily"])
    d["meta"]["total"]["partial"] = len(cons) < len(d["months"])


def rattrape_site(nom, dry_run=False):
    chemin = DATA_DIR / f"{_slug(nom)}.json"
    if not chemin.exists():
        print(f"{nom} : fichier introuvable ({chemin.name}), ignore")
        return None

    d = json.loads(chemin.read_text(encoding="utf-8"))
    mois = _mois_a_zero(d)
    if not mois:
        return None

    avant = (d.get("leads", {}).get("total") or {}).get("total", 0)
    print(f"{nom} : {len(mois)} mois a zero a rattraper ({mois[0]}..{mois[-1]})")

    ecrit = False
    for m in mois:
        jours = d["meta"][m]["days"]
        try:
            bloc = leads_extract.bloc_leads_mois(nom, m, jours, jours)
        except Exception as e:
            print(f"  {nom} {m} : echec extraction ({type(e).__name__}: {e}), conserve a zero")
            continue
        d["leads"][m] = bloc
        ecrit = True
        print(f"  {nom} {m} : {bloc['total']} leads (etait 0)")

    if not ecrit:
        print(f"  {nom} : aucun mois recupere (toutes les extractions ont echoue)")
        return None

    _recalcule_total(d)
    apres = d["leads"]["total"]["total"]

    if dry_run:
        print(f"  {nom} : {avant} -> {apres} leads cumules (dry-run, rien d'ecrit)")
        return avant, apres

    chemin.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ok, detail = _commit_et_pousse(
        [f"data/{chemin.name}"],
        f"Rattrapage historique des leads BO — {nom}")
    if not ok:
        print(f"  {nom} : ECHEC commit/push ({detail}) -- fichier ecrit localement, pas publie")
    else:
        print(f"  {nom} : {avant} -> {apres} leads cumules, publie")
    return avant, apres


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
    total_avant = sum(v[0] for v in resultats.values())
    total_apres = sum(v[1] for v in resultats.values())
    print(f"Total cumule (sites rattrapes) : {total_avant} -> {total_apres}")


if __name__ == "__main__":
    main()
