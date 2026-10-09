"""Rattrapage des conversions par page d'atterrissage (landingMonth) sur
l'historique complet.

Meme logique que backfill_rebond.py : le run quotidien (refresh.yml) ne
retraite que les MOIS_RECENTS derniers mois, les mois plus anciens n'ont donc
jamais eu ce champ. Recalcule landingMonth[mois] pour chaque mois de
d["months"] absent de landingMonth, site par site. N'ecrit que landingMonth.

Usage :
  python -m pipeline.backfill_landing                    # tous les sites exploitables
  python -m pipeline.backfill_landing --sites "OPEL FR"
  python -m pipeline.backfill_landing --dry-run
"""

import argparse
import json
from pathlib import Path

from pipeline import funnel, ga4
from pipeline.build import _commit_et_pousse, _configure_git, jour_fiable
from pipeline.sites import exploitables, site as trouve_site

RACINE = Path(__file__).resolve().parent.parent
DATA_DIR = RACINE / "data"


def rattrape_site(cli, s, dry_run=False):
    chemin = DATA_DIR / f"{s.slug}.json"
    if not chemin.exists():
        print(f"{s.nom} : fichier introuvable ({chemin.name}), ignore")
        return None

    d = json.loads(chemin.read_text(encoding="utf-8"))
    d.setdefault("landingMonth", {})
    limite = jour_fiable().replace("-", "")
    a_faire = [m for m in d.get("months", []) if m not in d["landingMonth"]]
    if not a_faire:
        return None

    print(f"{s.nom} : {len(a_faire)} mois a recuperer ({a_faire[0]}..{a_faire[-1]})")
    recuperes = 0
    for m in a_faire:
        deb, fin, _ = ga4.bornes(m)
        if deb.replace("-", "") > limite:
            print(f"  {s.nom} {m} : hors plage fiable GA4, laisse absent")
            continue
        f_num = min(fin.replace("-", ""), limite)
        f_iso = f"{f_num[:4]}-{f_num[4:6]}-{f_num[6:]}"
        try:
            pages = ga4.landing_conversions_par_page(
                cli, s.propriete, s.hote_reprise, deb, f_iso, funnel.EVENEMENT_ESTIMATION)
        except Exception as e:
            print(f"  {s.nom} {m} : echec extraction ({type(e).__name__}: {e}), laisse absent")
            continue
        d["landingMonth"][m] = {"pages": pages}
        recuperes += 1
        print(f"  {s.nom} {m} : {len(pages)} pages d'atterrissage")

    if not recuperes:
        print(f"  {s.nom} : aucun mois recupere (toutes les extractions ont echoue)")
        return None

    if dry_run:
        print(f"  {s.nom} : {recuperes} mois rattrapes (dry-run, rien d'ecrit)")
        return recuperes

    chemin.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ok, detail = _commit_et_pousse(
        [f"data/{chemin.name}"],
        f"Rattrapage pages d'atterrissage — {s.nom}")
    if not ok:
        print(f"  {s.nom} : ECHEC commit/push ({detail}) -- fichier ecrit localement, pas publie")
    else:
        print(f"  {s.nom} : {recuperes} mois rattrapes, publie")
    return recuperes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", nargs="*", help="par defaut : tous les sites exploitables")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not a.dry_run:
        _configure_git()

    cli = ga4.client()
    cibles = [trouve_site(n) for n in a.sites] if a.sites else exploitables()

    resultats = {}
    for s in cibles:
        r = rattrape_site(cli, s, dry_run=a.dry_run)
        if r:
            resultats[s.nom] = r

    print()
    print(f"=== {len(resultats)} site(s) rattrape(s) sur {len(cibles)} passe(s) en revue ===")
    print(f"Total mois recuperes : {sum(resultats.values())}")


if __name__ == "__main__":
    main()
