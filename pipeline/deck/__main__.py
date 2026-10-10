"""python -m pipeline.deck --brief brief.json --sortie presentation.pptx [--hist data/history]"""

import argparse
import json

from .construit import construit
from .donnees import HIST, Donnees


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True)
    ap.add_argument("--sortie", required=True)
    ap.add_argument("--hist", default=str(HIST))
    a = ap.parse_args()
    brief = json.load(open(a.brief, encoding="utf-8"))
    d = Donnees(brief["perimetre"]["pays"], brief["perimetre"].get("marques") or None, hist=a.hist)
    ctx = construit(brief, d, a.sortie)
    print(f"{ctx.n} diapositives -> {a.sortie}")
    for w in ctx.avertissements:
        print("AVERTISSEMENT :", w)


if __name__ == "__main__":
    main()
