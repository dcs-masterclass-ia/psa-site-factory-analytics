#!/usr/bin/env python3
"""Diagnostic d'acces a l'API Search Console (etape 0).

Lecture seule : ne configure rien, n'ecrit rien dans data/. Sert uniquement a
verifier ce que le compte de service peut lire avant d'ecrire le moindre
extracteur — meme demarche que pipeline/metadata.py pour GA4 : on releve, on
ne devine pas.

Contrairement a GA4, l'acces Search Console ne se donne pas au niveau du
compte de service seul : il faut en plus ajouter son adresse e-mail comme
utilisateur (Parametres -> Utilisateurs et autorisations) dans CHAQUE
propriete Search Console concernee. Tant que --sites ne remonte rien, aucune
extraction n'est possible, quel que soit le code ecrit ici.

Usage
-----
    python3 -m pipeline.search_console --sites
"""

import argparse
import json
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _chemin_cle():
    chemin = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not chemin:
        sys.exit("GOOGLE_APPLICATION_CREDENTIALS non defini.")
    return chemin


def email_compte_service():
    """Adresse a ajouter manuellement dans chaque propriete Search Console."""
    with open(_chemin_cle(), encoding="utf-8") as f:
        return json.load(f).get("client_email", "?")


def client():
    creds = service_account.Credentials.from_service_account_file(
        _chemin_cle(), scopes=SCOPES)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def sites_accessibles(cli):
    """Proprietes visibles par le compte de service, avec le niveau de droit.

    Une propriete Search Console est soit un prefixe d'URL
    (« https://www.reprise.opel.fr/ »), soit un domaine entier
    (« sc-domain:opel.fr », qui couvre alors tous les sous-domaines et
    protocoles). Le type n'est pas suppose : il se lit dans siteUrl.
    """
    rep = cli.sites().list().execute()
    return sorted(
        ({"site": e["siteUrl"], "droit": e["permissionLevel"]}
         for e in rep.get("siteEntry", [])),
        key=lambda x: x["site"])


def main():
    ap = argparse.ArgumentParser(description="Diagnostic d'acces Search Console")
    ap.add_argument("--sites", action="store_true",
                    help="liste les proprietes accessibles au compte de service")
    a = ap.parse_args()

    if not a.sites:
        sys.exit("Choisir --sites")

    sortie = []

    def ligne(t=""):
        print(t)
        sortie.append(t)

    email = email_compte_service()
    ligne(f"## Diagnostic Search Console — compte de service `{email}`")
    ligne()

    cli = client()
    l = sites_accessibles(cli)

    if not l:
        ligne("**Aucune propriete accessible.**")
        ligne()
        ligne(f"Ajouter `{email}` comme utilisateur dans Search Console "
              "(Parametres -> Utilisateurs et autorisations) pour chaque site "
              "a suivre, puis relancer ce diagnostic.")
    else:
        ligne(f"{len(l)} propriete(s) accessible(s) :")
        ligne()
        ligne("| Propriete | Droit |")
        ligne("|---|---|")
        for e in l:
            ligne(f"| `{e['site']}` | {e['droit']} |")

    recap = os.environ.get("GITHUB_STEP_SUMMARY")
    if recap:
        with open(recap, "a", encoding="utf-8") as f:
            f.write("\n".join(sortie) + "\n")


if __name__ == "__main__":
    main()
