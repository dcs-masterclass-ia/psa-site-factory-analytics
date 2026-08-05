#!/usr/bin/env python3
"""Extraction Search Console par l'API Search Analytics.

Aucun etat, aucune ecriture dans data/ : ce module ne fait que lire Search
Console et rendre des structures Python, comme pipeline/ga4.py pour GA4.
L'assemblage dans data/<site>.json viendra dans un second temps, une fois
l'extraction validee contre au moins un site reel.

Contrairement a GA4, l'acces Search Console ne se donne pas au niveau du
compte de service seul : il faut en plus ajouter son adresse e-mail comme
utilisateur (Parametres -> Utilisateurs et autorisations) dans CHAQUE
propriete Search Console concernee. Tant que --sites ne remonte rien pour un
site donne, aucune extraction n'est possible pour lui, quel que soit le code
ecrit ici.

Une propriete est identifiee par son siteUrl exact tel que renvoye par
--sites — jamais reconstruit a partir d'un nom d'hote : un prefixe d'URL
(« https://www.reprise.opel.fr/ ») et un domaine (« sc-domain:opel.fr ») ne
s'adressent pas de la meme facon, et seule l'API le dit avec certitude.

Usage
-----
    python3 -m pipeline.search_console --sites
    python3 -m pipeline.search_console --site-url "https://www.reprise.opel.fr/" \
        --debut 2026-07-01 --fin 2026-07-31
"""

import argparse
import json
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# maximum de lignes autorise par l'API Search Console en une seule requete ;
# largement suffisant pour prendre le top N localement, pas besoin de paginer
# comme pour GA4 (voir ga4._rapport).
LIMITE = 25000


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


def _requete(cli, site_url, debut, fin, dimensions):
    corps = {"startDate": debut, "endDate": fin, "dimensions": dimensions,
             "rowLimit": LIMITE}
    rep = cli.searchanalytics().query(siteUrl=site_url, body=corps).execute()
    return rep.get("rows", [])


def _ligne(r):
    return {"clics": r["clicks"], "impressions": r["impressions"],
            "ctr": round(r["ctr"] * 100, 2), "position": round(r["position"], 1)}


def vue_ensemble_quotidienne(cli, site_url, debut, fin):
    """{'AAAA-MM-JJ': {clics, impressions, ctr, position}}"""
    return {r["keys"][0]: _ligne(r) for r in _requete(cli, site_url, debut, fin, ["date"])}


def top_requetes(cli, site_url, debut, fin, n=20):
    """Requetes de recherche menant au site, triees par clics decroissants."""
    lignes = _requete(cli, site_url, debut, fin, ["query"])
    tri = sorted(lignes, key=lambda r: -r["clicks"])[:n]
    return [{"requete": r["keys"][0], **_ligne(r)} for r in tri]


def top_pages(cli, site_url, debut, fin, n=20):
    """Pages recevant des clics depuis la recherche, triees par clics decroissants."""
    lignes = _requete(cli, site_url, debut, fin, ["page"])
    tri = sorted(lignes, key=lambda r: -r["clicks"])[:n]
    return [{"page": r["keys"][0], **_ligne(r)} for r in tri]


# ---------------------------------------------------------------- ligne de commande

def main():
    ap = argparse.ArgumentParser(description="Lecture Search Console par l'API Search Analytics")
    ap.add_argument("--sites", action="store_true",
                    help="liste les proprietes accessibles au compte de service")
    ap.add_argument("--site-url", help="propriete exacte, telle que renvoyee par --sites")
    ap.add_argument("--debut", default="2026-07-01")
    ap.add_argument("--fin", default="2026-07-31")
    ap.add_argument("--top", type=int, default=20, help="nombre de requetes/pages a afficher")
    a = ap.parse_args()

    if not a.sites and not a.site_url:
        sys.exit("Choisir --sites ou --site-url")

    sortie = []

    def ligne(t=""):
        print(t)
        sortie.append(t)

    email = email_compte_service()
    cli = client()

    if a.sites:
        ligne(f"## Diagnostic Search Console — compte de service `{email}`")
        ligne()
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

    if a.site_url:
        ligne(f"## Extraction Search Console — `{a.site_url}` du {a.debut} au {a.fin}")
        ligne()

        vue = vue_ensemble_quotidienne(cli, a.site_url, a.debut, a.fin)
        tot_clics = sum(v["clics"] for v in vue.values())
        tot_impr = sum(v["impressions"] for v in vue.values())
        ligne(f"**Vue d'ensemble** — {len(vue)} jour(s), "
              f"{tot_clics} clics, {tot_impr} impressions au total.")
        ligne()

        reqs = top_requetes(cli, a.site_url, a.debut, a.fin, a.top)
        ligne(f"### Top {len(reqs)} requetes")
        ligne()
        ligne("| Requete | Clics | Impressions | CTR | Position |")
        ligne("|---|---:|---:|---:|---:|")
        for r in reqs:
            ligne(f"| {r['requete']} | {r['clics']} | {r['impressions']} | "
                  f"{r['ctr']}% | {r['position']} |")
        ligne()

        pages = top_pages(cli, a.site_url, a.debut, a.fin, a.top)
        ligne(f"### Top {len(pages)} pages")
        ligne()
        ligne("| Page | Clics | Impressions | CTR | Position |")
        ligne("|---|---:|---:|---:|---:|")
        for p in pages:
            ligne(f"| {p['page']} | {p['clics']} | {p['impressions']} | "
                  f"{p['ctr']}% | {p['position']} |")

    recap = os.environ.get("GITHUB_STEP_SUMMARY")
    if recap:
        with open(recap, "a", encoding="utf-8") as f:
            f.write("\n".join(sortie) + "\n")


if __name__ == "__main__":
    main()
