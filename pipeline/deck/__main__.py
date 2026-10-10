"""python -m pipeline.deck --brief brief.json --sortie presentation.pptx [--hist data/history]

Mode workflow : python -m pipeline.deck --briefs data/presentations/briefs.json --id B-xxx --sortie-dir data/presentations/out
lit le brief par son id, écrit <id>.pptx et met à jour son statut (generee / echec) dans briefs.json."""

import argparse
import json
import os
import time

from .construit import construit
from .donnees import HIST, Donnees


def _maj_statut(chemin, id_, **champs):
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    for b in data.get("briefs", []):
        if b.get("id") == id_:
            b.update(champs)
    data["updatedAt"] = int(time.time() * 1000)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief")
    ap.add_argument("--sortie")
    ap.add_argument("--briefs")
    ap.add_argument("--id")
    ap.add_argument("--sortie-dir")
    ap.add_argument("--echec", action="store_true", help="marque seulement le brief en échec (étape finale du workflow)")
    ap.add_argument("--hist", default=str(HIST))
    a = ap.parse_args()
    if a.briefs:
        if a.echec:
            _maj_statut(a.briefs, a.id, statut="echec", genereeLe=int(time.time() * 1000))
            return
        with open(a.briefs, encoding="utf-8") as f:
            brief = next(b for b in json.load(f)["briefs"] if b["id"] == a.id)
        os.makedirs(a.sortie_dir, exist_ok=True)
        sortie = os.path.join(a.sortie_dir, f"{a.id}.pptx")
    else:
        with open(a.brief, encoding="utf-8") as f:
            brief = json.load(f)
        sortie = a.sortie
    d = Donnees(brief["perimetre"]["pays"], brief["perimetre"].get("marques") or None, hist=a.hist)
    ctx = construit(brief, d, sortie)
    print(f"{ctx.n} diapositives -> {sortie}")
    for w in ctx.avertissements:
        print("AVERTISSEMENT :", w)
    if a.briefs:
        _maj_statut(a.briefs, a.id, statut="generee", fichier=f"presentations/out/{a.id}.pptx", genereeLe=int(time.time() * 1000),
                    diapositives=ctx.n, avertissements=list(ctx.avertissements)[:10])


if __name__ == "__main__":
    main()
