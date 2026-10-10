"""Agrege l'historique profond des leads (data/history/leads) en un petit
fichier servi au dashboard : data/leads_mensuel.json.

Format : {"genere": "AAAA-MM-JJ", "sites": {"OPEL FR": {"2021-03": [valides, doublons, tests, preview], ...}}}
Sert a la page Tableau (annee sur annee 2021+, saisonnalite, qualite des
leads : part de doublons/tests par site). Aucune donnee personnelle : ce sont
des compteurs mensuels. data/history lui-meme n'est jamais deploye.

Usage : python -m pipeline.leads_mensuel
"""

import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from pipeline.build import DATA, PARIS, _commit_et_pousse, _configure_git
from pipeline.leads_extract import SITE_EXTRACT

IDX = {"valide": 0, "doublon": 1, "test": 2, "preview": 3}


def slug(nom):
    import re
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", nom.lower()))


def agrege():
    sites = {}
    for nom in sorted(SITE_EXTRACT):
        f = DATA / "history" / "leads" / f"{slug(nom)}.csv.gz"
        if not f.exists():
            continue
        mois = defaultdict(lambda: [0, 0, 0, 0])
        with gzip.open(f, "rt", encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                i = IDX.get(r["statut"])
                if i is not None:
                    mois[r["date"][:7]][i] += int(r["n"])
        if mois:
            sites[nom] = dict(sorted(mois.items()))
    return {"genere": datetime.now(PARIS).strftime("%Y-%m-%d"), "sites": sites}


def main():
    out = agrege()
    chemin = DATA / "leads_mensuel.json"
    chemin.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out['sites'])} sites, {chemin.stat().st_size // 1024} Ko")
    _configure_git()
    ok, detail = _commit_et_pousse(["data/leads_mensuel.json"], "Agrégat mensuel des leads (historique profond)")
    print("publie" if ok else f"ECHEC commit/push ({detail})")


if __name__ == "__main__":
    main()
