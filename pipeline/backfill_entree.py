"""Rattrapage de l'« entrée directe sur la reprise » par canal (entreeMonth) sur l'historique complet.

Alignement Looker (tableau « Traffic landing on Trade In » et anneau « Trade In Entry / Brand Websites »), voir
ga4.entree_directe_par_canal. build.py le calcule pour les mois récents et rattrape 3 mois anciens par passage ; ce module
remplit tout l'historique d'un coup, site par site. N'écrit que entreeMonth.

Usage :
  python -m pipeline.backfill_entree                    # tous les sites exploitables
  python -m pipeline.backfill_entree --sites "OPEL FR"
  python -m pipeline.backfill_entree --dry-run
"""

import argparse
import json
from pathlib import Path

from pipeline import ga4
from pipeline.build import _commit_et_pousse, _configure_git, jour_fiable
from pipeline.sites import exploitables, site as trouve_site

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def rattrape_site(cli, s, dry_run=False):
    chemin = DATA_DIR / f"{s.slug}.json"
    if not chemin.exists():
        print(f"{s.nom} : fichier introuvable, ignoré")
        return None
    d = json.loads(chemin.read_text(encoding="utf-8"))
    d.setdefault("entreeMonth", {})
    hotes = d.get("_hotes") or {}
    reprise = hotes.get("reprise") or s.hote_reprise
    parent = hotes.get("parent") or s.hote_parent
    limite = jour_fiable().replace("-", "")
    a_faire = [m for m in d.get("months", []) if m not in d["entreeMonth"]]
    ecrit = 0
    for m in a_faire:
        deb, fin, _ = ga4.bornes(m)
        if deb.replace("-", "") > limite:
            continue
        f_num = min(fin.replace("-", ""), limite)
        f_iso = f"{f_num[:4]}-{f_num[4:6]}-{f_num[6:]}"
        try:
            ed = ga4.entree_directe_par_canal(cli, s.propriete, reprise, parent, deb, f_iso)
        except Exception as e:
            print(f"  {s.nom} {m} : échec ({type(e).__name__}: {e})")
            continue
        if ed is None:
            continue
        d["entreeMonth"][m] = ed
        ecrit += 1
        print(f"  {s.nom} {m} : entrée directe {ed['total']} (depuis le site marque {ed['marque']})")
    if not ecrit:
        return None
    if dry_run:
        return ecrit
    chemin.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ok, detail = _commit_et_pousse([f"data/{chemin.name}"], f"Entrée directe par canal (alignement Looker) — {s.nom}")
    print(f"  {s.nom} : {ecrit} mois, " + ("publié" if ok else f"ECHEC push ({detail})"))
    return ecrit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.dry_run:
        _configure_git()
    cli = ga4.client()
    cibles = [trouve_site(n) for n in a.sites] if a.sites else exploitables()
    n = 0
    for s in cibles:
        if rattrape_site(cli, s, dry_run=a.dry_run):
            n += 1
    print(f"=== {n} site(s) rattrapé(s) sur {len(cibles)} ===")


if __name__ == "__main__":
    main()
