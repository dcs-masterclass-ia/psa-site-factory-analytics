"""Extraction quotidienne du canal d'acquisition.

Sert le graphique en aires empilees demande (equivalent du "Sessions per
channel over period" de Looker). Impossible a construire sans cette
extraction : les fichiers actuels ne portent le canal qu'en instantane
mensuel, jamais jour par jour.

Le nom de la dimension n'est jamais suppose. "Stellantis Custom Channel
Group" est le libelle affiche dans l'interface GA4, mais un libelle affiche
ne dit pas le nom d'API reel — meme lecon que step_name : on teste des
candidats, on retient celui qui repond, on ne devine pas celui qui echoue.
"""

import argparse
import os
import sys

from pipeline import ga4

CANDIDATS = [
    "sessionDefaultChannelGroup",       # champ standard GA4, present partout
    "customEvent:channel_group",
    "customUser:channel_group",
    "sessionManualCampaignName",        # improbable mais ecarte proprement si faux
]


def _valide(cli, pid, hote, debut, fin, nom):
    """Une dimension valide renvoie plus d'une valeur distincte : un champ
    absent ou vide renvoie zero ligne, ou une seule ligne vide/"(not set)"."""
    try:
        l = ga4._rapport(cli, pid, debut, fin, [nom], ["sessions"], ga4._egal("hostName", hote))
        vraies = [v for v, n in l if v.strip() and v.strip().lower() != "(not set)"]
        return len(set(vraies)) > 1
    except Exception:
        return False


def dimension_canal(cli, pid, hote, debut, fin):
    for c in CANDIDATS:
        if _valide(cli, pid, hote, debut, fin, c):
            return c
    return None


def canal_quotidien(cli, pid, hote, debut, fin):
    """Retourne (dimension_utilisee, {'YYYY-MM-DD': {canal: sessions}}) ou (None, {})."""
    dim = dimension_canal(cli, pid, hote, debut, fin)
    if not dim:
        return None, {}
    lignes = ga4._rapport(cli, pid, debut, fin, ["date", dim], ["sessions"],
                          ga4._egal("hostName", hote))
    par_jour = {}
    for date, canal, sess in lignes:
        if len(date) != 8 or not date.isdigit():
            continue
        # annee incluse (pas seulement "MM-DD") : indispensable des que la
        # fenetre depasse 12 mois, memes raisons que pipeline/build.py.
        ymd = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        par_jour.setdefault(ymd, {})[canal.strip() or "(non défini)"] = int(sess)
    return dim, par_jour


# ---------------------------------------------------------------- ligne de commande

def main():
    ap = argparse.ArgumentParser(description="Teste la decouverte du canal quotidien")
    ap.add_argument("--propriete", required=True)
    ap.add_argument("--hote", required=True)
    ap.add_argument("--debut", default="2026-07-01")
    ap.add_argument("--fin", default="2026-07-31")
    a = ap.parse_args()

    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        sys.exit("GOOGLE_APPLICATION_CREDENTIALS non defini.")
    cli = ga4.client()

    print(f"## Decouverte du canal quotidien — {a.hote}\n")
    print("Candidats testes, dans l'ordre :")
    trouve = None
    for c in CANDIDATS:
        ok = _valide(cli, a.propriete, a.hote, a.debut, a.fin, c)
        print(f"  {'OK ' if ok else 'non'}  {c}")
        if ok and not trouve:
            trouve = c

    if not trouve:
        print("\nAucun candidat valide. Le canal quotidien reste indisponible pour ce site.")
        print("Lancer le workflow de decouverte des metadonnees pour lister les "
              "dimensions reelles de cette propriete et en identifier le nom exact.")
        sys.exit(1)

    print(f"\nDimension retenue : {trouve}\n")
    dim, par_jour = canal_quotidien(cli, a.propriete, a.hote, a.debut, a.fin)
    jours = sorted(par_jour)
    print(f"{len(jours)} jours extraits. Exemple ({jours[0] if jours else '—'}) :")
    if jours:
        for canal, n in sorted(par_jour[jours[0]].items(), key=lambda x: -x[1]):
            print(f"   {canal:<24}{n:>6}")


if __name__ == "__main__":
    main()
