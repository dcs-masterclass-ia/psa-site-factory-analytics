"""Diagnostic ponctuel : en-têtes du CSV d'extraction avec leur lettre de colonne Excel (A, B… BC…), et pour
quelques colonnes la répartition des valeurs (top 12) sur une courte fenêtre. Lecture seule, rien n'est écrit.
Sert à repérer la colonne « point de vente » (BC) avant de l'ajouter à l'extraction. Les colonnes qui contiennent
des données personnelles (téléphone, e-mail, nom…) sont listées par leur seul en-tête, jamais par leurs valeurs.

  python -m pipeline._diag_colonnes "OPEL FR" [jours] [LETTRES ex. BC,BD]
"""
import csv
import io
import sys
from collections import Counter
from datetime import date, timedelta

from pipeline import leads_extract as le

PII = ("PHONE", "TEL", "MAIL", "NAME", "NOM", "FIRST", "LAST", "COMMENT", "ADDRESS", "ADRESSE", "ZIP", "POSTAL", "CITY", "VILLE", "PLATE", "VIN")


def lettre(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    nom = sys.argv[1] if len(sys.argv) > 1 else "OPEL FR"
    jours = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    voulues = [x.strip().upper() for x in (sys.argv[3] if len(sys.argv) > 3 else "BC").split(",")]
    fin = date.today() - timedelta(days=1)
    debut = fin - timedelta(days=jours)
    lignes = []
    for site_id, settings in le.SITE_EXTRACT[nom]:
        lignes += le._telecharge_brut(site_id, settings, debut.isoformat(), fin.isoformat())
    if not lignes:
        print("aucune ligne")
        return
    cols = list(lignes[0].keys())
    print(f"{nom} : {len(lignes)} lignes, {len(cols)} colonnes ({debut} -> {fin})")
    for i, c in enumerate(cols):
        print(f"  {lettre(i):>3}  {c}")
    for i, c in enumerate(cols):
        if lettre(i) not in voulues:
            continue
        if any(m in c.upper() for m in PII) and "DEALER" not in c.upper() and "POINT" not in c.upper() and "PDV" not in c.upper():
            print(f"\n{lettre(i)} {c} : colonne potentiellement personnelle, valeurs non affichées")
            continue
        cnt = Counter((l.get(c) or "").strip() for l in lignes)
        print(f"\n{lettre(i)} {c} : {len(cnt)} valeurs distinctes, top 12")
        for v, n in cnt.most_common(12):
            print(f"   {n:5d}  {v[:80]}")


if __name__ == "__main__":
    main()
