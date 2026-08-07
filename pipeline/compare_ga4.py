#!/usr/bin/env python3
"""Etape 1 : comparer l'extraction GA4 par API au fichier en production.

N'ecrit rien dans data/. Ne commite rien. Produit un rapport sur la sortie
standard et, sous GitHub Actions, dans le recapitulatif d'execution.

But : verifier que l'API retrouve les chiffres obtenus a la main avant de lui
confier la production des fichiers.

Usage
-----
    python3 -m pipeline.compare_ga4 --site opel-fr
    python3 -m pipeline.compare_ga4 --site opel-fr --mois 2026-04 2026-07
"""

import argparse
import json
import os
import sys
from pathlib import Path

from pipeline import ga4
from pipeline.sites import site as trouve_site

RACINE = Path(__file__).resolve().parent.parent
SEUIL_ALERTE = 1.0     # % d'ecart au-dela duquel on signale
SEUIL_ECHEC = 3.5      # % d'ecart au-dela duquel on considere l'API non validee


def ligne(sortie, txt=""):
    print(txt)
    sortie.append(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--mois", nargs="+", default=["2026-04", "2026-05", "2026-06", "2026-07"])
    a = ap.parse_args()

    s = trouve_site(a.site)
    if not s.acces_api:
        sys.exit(f"{s.nom} : le compte de service n'a pas acces a la propriete {s.propriete}.")
    if not s.verifie:
        print(f"Attention : les hotes de {s.nom} ne sont pas encore verifies dans GA4.")
        print(f"Relever d'abord : python3 -m pipeline.ga4 --propriete {s.propriete} --hotes\n")

    ref_path = RACINE / "data" / f"{s.slug}.json"
    if not ref_path.exists():
        sys.exit(f"fichier de reference absent : {ref_path}")
    ref = json.loads(ref_path.read_text())

    cli = ga4.client()
    sortie = []
    ligne(sortie, f"## Comparaison API GA4 / fichier en production — {s.nom}")
    ligne(sortie)
    ligne(sortie, f"- propriete : `{s.propriete}`")
    ligne(sortie, f"- hote parent : `{s.hote_parent}`")
    ligne(sortie, f"- hote reprise : `{s.hote_reprise}`")
    ligne(sortie)
    ligne(sortie, "| Mois | Source | Fichier | API | Ecart |")
    ligne(sortie, "|---|---|---|---|---|")

    ecarts, pire = [], 0.0
    for m in a.mois:
        bloc = ga4.bloc_mensuel(cli, s, m)
        for etiquette, cle_ref, valeur in (
            ("parent", "trafficMonth", bloc["traffic_total"]),
            ("reprise", "repriseMonth", bloc["reprise_total"]),
        ):
            attendu = ref.get(cle_ref, {}).get(m, {}).get("sessions")
            if attendu is None:
                ligne(sortie, f"| {m} | {etiquette} | absent | {valeur} | — |")
                continue
            e = (valeur - attendu) / attendu * 100 if attendu else 0.0
            pire = max(pire, abs(e))
            marque = "" if abs(e) < SEUIL_ALERTE else (" ⚠" if abs(e) < SEUIL_ECHEC else " ❌")
            ligne(sortie, f"| {m} | {etiquette} | {attendu} | {valeur} | {e:+.2f} %{marque} |")
            ecarts.append((m, etiquette, attendu, valeur, e))

        # signature de trafic automatise, releve au passage
        sess, users = bloc["reprise_sessions"], bloc["reprise_utilisateurs"]
        if users:
            ratio = sess / users
            if ratio > 3:
                ligne(sortie)
                ligne(sortie, f"> **{m}** : {ratio:.1f} sessions par utilisateur sur "
                              f"le site de reprise. Au-dela de 3, un seul client ouvre "
                              f"des centaines de sessions — signature de trafic automatise.")
                ligne(sortie)

    ligne(sortie)
    ligne(sortie, f"**Ecart maximal : {pire:.2f} %**")
    ligne(sortie)
    if pire < SEUIL_ALERTE:
        verdict = "API validee : les chiffres concordent a moins de 1 %."
        code = 0
    elif pire < SEUIL_ECHEC:
        verdict = ("Ecarts faibles, compatibles avec la non-additivite GA4 decrite au "
                   "§5.4 du mode d'emploi. A confirmer mois par mois avant bascule.")
        code = 0
    else:
        verdict = ("Ecart trop important. Verifier le nom d'hote : un prefixe `www.` "
                   "manquant suffit a fausser tout le releve.")
        code = 1
    ligne(sortie, verdict)
    ligne(sortie)
    ligne(sortie, "_Aucun fichier n'a ete modifie, aucun commit n'a ete fait._")

    recap = os.environ.get("GITHUB_STEP_SUMMARY")
    if recap:
        with open(recap, "a", encoding="utf-8") as f:
            f.write("\n".join(sortie) + "\n")

    sys.exit(code)


if __name__ == "__main__":
    main()
