"""Historique mensuel dérivé de l'historique profond (data/history), servi au dashboard dans data/<site>.json -> histMonth.

Pas de donnée personnelle ni de lead : seulement des totaux mensuels GA4. Permet les vues « même période, années passées » et les
records historiques sans jamais publier data/history lui-même.
  histMonth = { "AAAA-MM": [sessions reprise, sessions site parent, visiteurs accueil (somme des jours), estimations (somme des jours)] }
"""

import csv
import gzip
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
HIST = RACINE / "data" / "history"


def _lignes(chemin):
    if not chemin.exists():
        return
    with gzip.open(chemin, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def mensuel(slug, hist=HIST):
    mois = defaultdict(lambda: [0, 0, 0, 0])
    for r in _lignes(Path(hist) / "ga4_sessions" / f"{slug}.csv.gz"):
        m = r["date"][:7]
        mois[m][0 if r["site"] == "reprise" else 1] += int(r["sessions"] or 0)
    for r in _lignes(Path(hist) / "ga4_funnel" / f"{slug}.csv.gz"):
        m = r["date"][:7]
        mois[m][2] += int(r["accueil"] or 0)
        mois[m][3] += int(r["estimation"] or 0)
    return {m: v for m, v in sorted(mois.items()) if any(v)}
