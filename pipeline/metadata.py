#!/usr/bin/env python3
"""Decouverte des metadonnees d'une propriete GA4.

But : arreter de supposer les noms d'API. Le groupe de canaux Stellantis est un
groupe personnalise, l'evenement de lead porte un nom qu'on ne connait pas, et
les dimensions personnalisees varient d'une propriete a l'autre. Ce script les
fait dire par GA4.

C'est la meme lecon que `www.reprise.opel.fr` : on releve, on ne devine pas.

Usage
-----
    python3 -m pipeline.metadata --propriete 276495192
    python3 -m pipeline.metadata --propriete 276495192 --json meta-opel-fr.json
"""

import argparse
import json
import os
import re
import sys

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import GetMetadataRequest

from pipeline import ga4

# ce qu'on cherche a identifier, et les indices qui les trahissent
PISTES = {
    "groupe_canaux": (r"channel.*group", r"canaux"),
    "evenement_lead": (r"lead", r"tradein", r"trade_in", r"reprise", r"retoma",
                       r"estimat", r"valuation"),
    "parcours": (r"funnel", r"journey", r"step", r"etape"),
    "plaque": (r"plate", r"immat", r"matricula", r"registration"),
}


def metadonnees(cli, pid):
    rep = cli.get_metadata(GetMetadataRequest(name=f"properties/{pid}/metadata"))
    dims = [{"api": d.api_name, "libelle": d.ui_name,
             "personnalise": d.custom_definition, "desc": d.description}
            for d in rep.dimensions]
    mets = [{"api": m.api_name, "libelle": m.ui_name,
             "personnalise": m.custom_definition, "desc": m.description}
            for m in rep.metrics]
    return dims, mets


def correspond(champ, motifs):
    texte = f"{champ['api']} {champ['libelle']} {champ.get('desc', '')}".lower()
    return any(re.search(m, texte) for m in motifs)


def evenements(cli, pid, hote, debut, fin, limite=40):
    """Evenements les plus frequents sur un hote, avec leur volume d'evenements cles."""
    lignes = ga4._rapport(cli, pid, debut, fin, ["eventName"],
                          ["eventCount", "keyEvents"], ga4._egal("hostName", hote))
    out = []
    for nom, n, cles in lignes:
        out.append({"evenement": nom, "occurrences": int(n),
                    "evenements_cles": int(cles or 0)})
    return sorted(out, key=lambda x: -x["occurrences"])[:limite]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--propriete", required=True)
    ap.add_argument("--hote", help="pour lister les evenements de cet hote")
    ap.add_argument("--debut", default="2026-07-01")
    ap.add_argument("--fin", default="2026-07-31")
    ap.add_argument("--json")
    a = ap.parse_args()

    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        sys.exit("GOOGLE_APPLICATION_CREDENTIALS non defini.")
    cli = BetaAnalyticsDataClient()

    dims, mets = metadonnees(cli, a.propriete)
    sortie = []

    def ligne(t=""):
        print(t)
        sortie.append(t)

    ligne(f"## Metadonnees de la propriete {a.propriete}")
    ligne()
    ligne(f"- {len(dims)} dimensions, dont "
          f"{sum(1 for d in dims if d['personnalise'])} personnalisees")
    ligne(f"- {len(mets)} metriques, dont "
          f"{sum(1 for m in mets if m['personnalise'])} personnalisees")
    ligne()

    ligne("### Dimensions personnalisees")
    ligne()
    perso = [d for d in dims if d["personnalise"]]
    if perso:
        ligne("| Nom d'API | Libelle |")
        ligne("|---|---|")
        for d in perso:
            ligne(f"| `{d['api']}` | {d['libelle']} |")
    else:
        ligne("_aucune_")
    ligne()

    for cle, motifs in PISTES.items():
        trouves = [d for d in dims if correspond(d, motifs)] + \
                  [m for m in mets if correspond(m, motifs)]
        ligne(f"### Piste « {cle} »")
        ligne()
        if trouves:
            ligne("| Nom d'API | Libelle | Personnalise |")
            ligne("|---|---|---|")
            for t in trouves[:15]:
                ligne(f"| `{t['api']}` | {t['libelle']} | "
                      f"{'oui' if t['personnalise'] else 'non'} |")
        else:
            ligne("_rien trouve_")
        ligne()

    if a.hote:
        ligne(f"### Evenements sur `{a.hote}` du {a.debut} au {a.fin}")
        ligne()
        ev = evenements(cli, a.propriete, a.hote, a.debut, a.fin)
        ligne("| Evenement | Occurrences | Dont evenements cles |")
        ligne("|---|---|---|")
        for e in ev:
            ligne(f"| `{e['evenement']}` | {e['occurrences']} | {e['evenements_cles']} |")
        ligne()
        cles = [e for e in ev if e["evenements_cles"] > 0]
        if cles:
            ligne("**Evenements cles detectes** — c'est parmi eux que se trouve "
                  "le compteur de leads utilise par le Looker :")
            for e in cles:
                ligne(f"- `{e['evenement']}` : {e['evenements_cles']} evenements cles")
        else:
            ligne("_aucun evenement cle sur cet hote : le lead est peut-etre "
                  "compte sur le domaine parent._")

    recap = os.environ.get("GITHUB_STEP_SUMMARY")
    if recap:
        with open(recap, "a", encoding="utf-8") as f:
            f.write("\n".join(sortie) + "\n")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"propriete": a.propriete, "dimensions": dims,
                       "metriques": mets}, f, ensure_ascii=False, indent=1)
        print(f"\nEcrit dans {a.json}")


if __name__ == "__main__":
    main()
