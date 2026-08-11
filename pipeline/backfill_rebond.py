"""Rattrapage du taux de rebond (rebondMonth) sur l'historique complet.

"Taux de rebond" a ete ajoute au pipeline le 10/08/2026 (voir build.py,
assemble()), mais chaque execution ne retraite que les MOIS_RECENTS (2)
derniers mois -- le reste de l'historique est repris tel quel du fichier
existant (optimisation pour eviter de re-taper GA4 sur 16 mois a chaque
run). Consequence : rebondMonth n'a jamais ete calcule pour les mois plus
anciens que juillet 2026, sur TOUS les sites -- confirme le 11/08/2026 sur
data/opel-fr.json (rebondMonth ne contenait que 2026-07/2026-08/total pour
16 mois de d["months"]).

Recalcule rebondMonth[mois] pour chaque mois de d["months"] absent de
rebondMonth, site par site. Recalcule aussi rebondMonth["total"] a la fin
(meme formule ponderee par les sessions que build.py, cf. sa fonction
assemble()) -- contrairement au rattrapage leads janv-avril 2025, ces mois
font DEJA partie de la fenetre GA4 suivie (d["months"]), ce n'est donc pas
une extension de perimetre mais une correction d'un trou existant : le
total doit refleter les mois rattrapes.

N'ecrit que rebondMonth -- jamais months/meta/daily/trafficMonth/etc.

Usage :
  python -m pipeline.backfill_rebond                    # tous les sites exploitables
  python -m pipeline.backfill_rebond --sites "OPEL FR"
  python -m pipeline.backfill_rebond --dry-run
"""

import argparse
import json
from pathlib import Path

from pipeline import funnel, ga4
from pipeline.build import _commit_et_pousse, _configure_git, jour_fiable
from pipeline.sites import exploitables, site as trouve_site

RACINE = Path(__file__).resolve().parent.parent
DATA_DIR = RACINE / "data"


def _recalcule_total(d):
    cons = [m for m in d["months"] if not d.get("meta", {}).get(m, {}).get("provisional")]
    reb_cons = [m for m in cons if m in d["rebondMonth"]]
    reb_sessions = sum(d["rebondMonth"][m]["sessions"] for m in reb_cons)
    d["rebondMonth"]["total"] = {
        "taux": round(sum(d["rebondMonth"][m]["taux"] * d["rebondMonth"][m]["sessions"] for m in reb_cons) / reb_sessions, 2) if reb_sessions else 0.0,
        "sessions": reb_sessions,
    }


def rattrape_site(cli, s, dry_run=False):
    chemin = DATA_DIR / f"{s.slug}.json"
    if not chemin.exists():
        print(f"{s.nom} : fichier introuvable ({chemin.name}), ignore")
        return None

    d = json.loads(chemin.read_text(encoding="utf-8"))
    d.setdefault("rebondMonth", {})
    limite = jour_fiable().replace("-", "")
    a_faire = [m for m in d.get("months", []) if m not in d["rebondMonth"]]
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
            taux_reb = ga4.taux_rebond(cli, s.propriete, s.hote_reprise, deb, f_iso)
            tr = ga4.sessions_total(cli, s.propriete, s.hote_reprise, deb, f_iso)
            pages_reb = ga4.rebond_et_conversion_par_page(
                cli, s.propriete, s.hote_reprise, deb, f_iso, funnel.EVENEMENT_ESTIMATION)
        except Exception as e:
            print(f"  {s.nom} {m} : echec extraction ({type(e).__name__}: {e}), laisse absent")
            continue
        d["rebondMonth"][m] = {"taux": taux_reb, "sessions": tr, "pages": pages_reb}
        recuperes += 1
        print(f"  {s.nom} {m} : taux {taux_reb} % ({tr} sessions)")

    if not recuperes:
        print(f"  {s.nom} : aucun mois recupere (toutes les extractions ont echoue)")
        return None

    _recalcule_total(d)

    if dry_run:
        print(f"  {s.nom} : {recuperes} mois rattrapes (dry-run, rien d'ecrit)")
        return recuperes

    chemin.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ok, detail = _commit_et_pousse(
        [f"data/{chemin.name}"],
        f"Rattrapage taux de rebond — {s.nom}")
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
