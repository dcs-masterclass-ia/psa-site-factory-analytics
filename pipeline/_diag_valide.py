"""Outil ponctuel : quantifie precisement combien de lignes le filtre
_valide() (doublons / tests / hors production, voir leads_extract.py)
retire d'une extraction brute -- pour verifier si l'ecart constate le
11/08/2026 face au report GCP officiel (chiffres bruts) s'explique par ce
filtre, ou par autre chose. Lecture seule, aucune ecriture.

Usage :
    python -m pipeline._diag_valide "PEUGEOT FR" 2026-07-01 2026-07-31
"""

import sys
from collections import Counter

from pipeline import leads_extract


def main():
    site_nom, debut, fin = sys.argv[1], sys.argv[2], sys.argv[3]
    if site_nom not in leads_extract.SITE_EXTRACT:
        print(f"site inconnu dans SITE_EXTRACT : {site_nom}")
        return

    lignes = leads_extract._telecharge(site_nom, debut, fin)
    print(f"\n=== {site_nom} ({debut} -> {fin}) ===")
    print(f"  lignes brutes (toutes, avant tout filtre) : {len(lignes)}")

    doublon_ko = sum(1 for l in lignes if l.get(leads_extract.COL_DOUBLON) != "NO")
    test_ko = sum(1 for l in lignes if l.get(leads_extract.COL_TEST) != "NO")
    test_int_ko = sum(1 for l in lignes if l.get(leads_extract.COL_TEST_INTERNE) != "NO")
    mode_ko = sum(1 for l in lignes if l.get(leads_extract.COL_MODE) != "MODE_PRODUCTION")
    valides = sum(1 for l in lignes if leads_extract._valide(l))

    print(f"  exclues par DOUBLON != NO            : {doublon_ko}")
    print(f"  exclues par TEST != NO                : {test_ko}")
    print(f"  exclues par TEST_INTERNE != NO         : {test_int_ko}")
    print(f"  exclues par MODE != MODE_PRODUCTION    : {mode_ko}")
    print(f"  valides (= ce qui finit dans data/*.json) : {valides}")
    print(f"  ecart brut -> valide                   : {len(lignes) - valides} ({(len(lignes) - valides) / len(lignes) * 100:.1f}% des lignes brutes)" if lignes else "  (0 ligne brute)")

    print("\n  valeurs distinctes observees pour chaque colonne de filtre :")
    for label, col in (("DOUBLON", leads_extract.COL_DOUBLON), ("TEST", leads_extract.COL_TEST),
                        ("TEST_INTERNE", leads_extract.COL_TEST_INTERNE), ("MODE", leads_extract.COL_MODE)):
        valeurs = Counter(l.get(col, "<absent>") for l in lignes)
        print(f"    {label:14s} : {dict(valeurs)}")


if __name__ == "__main__":
    main()
