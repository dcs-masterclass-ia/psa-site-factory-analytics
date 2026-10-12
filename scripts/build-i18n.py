"""Génère i18n-en.js (dictionnaire FR -> EN du dashboard) à partir de i18n/en/*.json.

Chaque fichier est un objet { "texte français": "English text" }. Les valeurs variables s'écrivent {0}, {1}… dans la clé
et dans la traduction, dans le même ordre : { "Voir les {0} canaux": "See all {0} channels" }.
Usage : python scripts/build-i18n.py   (puis commiter i18n-en.js)
"""
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def charge():
    d = {}
    for f in sorted((RACINE / "i18n" / "en").glob("*.json")):
        for k, v in json.loads(f.read_text(encoding="utf-8")).items():
            if k in d and d[k] != v:
                print(f"ATTENTION doublon avec traduction différente : {k[:60]!r} ({f.name})", file=sys.stderr)
            d[re.sub(r"\s+", " ", k).strip()] = v
    return d


def verifie(d):
    err = []
    for k, v in d.items():
        a, b = set(re.findall(r"\{\d\}", k)), set(re.findall(r"\{\d\}", v))
        if not b <= a:  # une traduction peut omettre une valeur (pluriel français), jamais en inventer
            err.append(f"valeur {{n}} absente de la clé française : {k[:70]!r}")
    return err


def main():
    d = charge()
    err = verifie(d)
    if err:
        print("\n".join(err), file=sys.stderr)
        return 1
    corps = json.dumps(d, ensure_ascii=False, indent=0, sort_keys=True)
    mots = {}
    f = RACINE / "i18n" / "mots.json"
    if f.exists():
        mots = json.loads(f.read_text(encoding="utf-8"))
        for k, v in list(mots.items()):  # variante avec majuscule initiale (début de phrase, libellés)
            mots.setdefault(k[:1].upper() + k[1:], v[:1].upper() + v[1:])
    (RACINE / "i18n-en.js").write_text(
        "/* GÉNÉRÉ par scripts/build-i18n.py depuis i18n/en/*.json — ne pas modifier à la main. */\n"
        f"window.I18N_EN = {corps};\n"
        f"window.I18N_WORDS = {json.dumps(mots, ensure_ascii=False, indent=0, sort_keys=True)};\n", encoding="utf-8")
    print(f"{len(d)} traductions -> i18n-en.js")
    return 0


if __name__ == "__main__":
    sys.exit(main())
