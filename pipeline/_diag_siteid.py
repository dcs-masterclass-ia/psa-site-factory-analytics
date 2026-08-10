"""Outil ponctuel : identifie le marche/site reel derriere une liste de
(siteId, settings) back-office, en lisant les colonnes du CSV d'extraction
lui-meme -- jamais devine depuis un ordre de collage. Meme methode que celle
documentee dans SITE_EXTRACT (pipeline/leads_extract.py) pour les 64 sites
deja identifies le 07-08/08/2026.

N'imprime que des colonnes non-PII (jamais telephone/nom/commentaire) :
le nom d'hote/domaine si present dans le CSV, sinon l'entete complet pour
reperer a la main la colonne pertinente.

Usage :
    python -m pipeline._diag_siteid 106:2026 66:2026 69:2026 ...
"""

import sys
from datetime import date, timedelta

from pipeline import leads_extract


def main():
    paires = []
    for arg in sys.argv[1:]:
        sid, settings = arg.split(":")
        paires.append((int(sid), int(settings)))

    fin = date.today().isoformat()
    debut = (date.today() - timedelta(days=90)).isoformat()

    for sid, settings in paires:
        print(f"\n=== siteId={sid} settings={settings} ({debut} -> {fin}) ===")
        try:
            lignes = leads_extract._telecharge_un(sid, settings, debut, fin)
        except Exception as e:
            print(f"  ECHEC : {type(e).__name__}: {e}")
            continue
        if not lignes:
            print("  0 ligne sur cette fenetre (essayer une fenetre plus large ?)")
            continue
        entete = list(lignes[0].keys())
        print(f"  {len(lignes)} ligne(s). Colonnes : {entete}")
        # colonnes candidates pour identifier le marche, jamais de PII
        candidats = [c for c in entete if any(
            mot in c.upper() for mot in ("COUNTRY", "SITE", "DOMAIN", "URL", "MARKET", "LANG", "LOCALE"))]
        for c in candidats:
            valeurs = sorted({l.get(c, "") for l in lignes if l.get(c)})
            print(f"  {c} : {valeurs[:5]}")


if __name__ == "__main__":
    main()
