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


def propriete_pour_hote(sites_dispo, hote):
    """Retrouve la propriete Search Console d'un hote parmi celles listees
    par sites_accessibles(). Le compte de service peut voir des dizaines de
    proprietes hors perimetre (portefeuille Stellantis entier) : on ne
    retient que celle qui correspond exactement a l'hote de reprise deja
    decouvert cote GA4, jamais une reconstruction supposee.

    Cherche d'abord le prefixe d'URL exact, puis une propriete de domaine
    qui couvrirait cet hote — sans jamais deviner un format non confirme
    par l'API.
    """
    prefixe = f"https://{hote}/"
    for e in sites_dispo:
        if e["site"] == prefixe:
            return e["site"]
    for e in sites_dispo:
        if e["site"].startswith("sc-domain:") and hote.endswith(e["site"].split(":", 1)[1]):
            return e["site"]
    return None


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


def total_periode(cli, site_url, debut, fin):
    """Total exact de la periode. Ce n'est pas la somme des jours : la
    position et le CTR sont des moyennes ponderees, pas des valeurs
    additives — meme lecon que ga4.sessions_total pour les sessions GA4."""
    lignes = _requete(cli, site_url, debut, fin, [])
    return _ligne(lignes[0]) if lignes else {"clics": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}


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


# ---------------------------------------------------------------- analyses mensuelles (modules SEO du dashboard)

MOTS_MARQUE = {"PEUGEOT": ["peugeot"], "CITROEN": ["citroen", "citroën"], "DS": ["ds automobiles", "dsautomobiles", "ds auto"], "OPEL": ["opel"],
               "ALFA ROMEO": ["alfa romeo", "alfaromeo"], "ABARTH": ["abarth"], "FIAT": ["fiat"], "FIAT PRO": ["fiat professional", "fiat pro"],
               "JEEP": ["jeep"], "LANCIA": ["lancia"], "LEAPMOTOR": ["leapmotor"], "SPOTICAR": ["spoticar"], "STELLANTIS &YOU": ["stellantis"]}
TRANCHES = [("1-3", 0, 3.5), ("4-10", 3.5, 10.5), ("11-20", 10.5, 20.5), ("21+", 20.5, 10 ** 9)]
# CTR attendu par position (courbe de référence du marché) : sert à chiffrer le gain si une requête monte en top 3
CTR_TOP3 = 0.10


def _tranche(pos):
    for nom, a, b in TRANCHES:
        if a < pos <= b:
            return nom
    return "21+"


def analyse_mois(cli, site_url, debut, fin, debut_prec, fin_prec, marque):
    """Analyses SEO d'un mois, calculées sur la liste COMPLÈTE des requêtes (pas seulement le top 20) :
    devices, positions (tranches), marque vs hors marque, gagnants / perdants vs le mois précédent, opportunités (positions 4-15 à fort
    volume et CTR faible), cannibalisation (requêtes servies par plusieurs pages), pages en déclin. Tout est compact (quelques Ko)."""
    mots = MOTS_MARQUE.get(marque, [marque.lower()])
    q_cur = {r["keys"][0]: r for r in _requete(cli, site_url, debut, fin, ["query"])}
    q_prec = {r["keys"][0]: r for r in _requete(cli, site_url, debut_prec, fin_prec, ["query"])} if debut_prec else {}
    out = {}
    # appareils
    out["devices"] = {r["keys"][0].lower(): {"clics": r["clicks"], "impressions": r["impressions"], "position": round(r["position"], 1)}
                      for r in _requete(cli, site_url, debut, fin, ["device"])}
    # distribution des positions (pondérée par impressions) et marque / hors marque
    pos = {n: [0, 0] for n, _, _ in TRANCHES}
    marque_h = {"marque": [0, 0], "hors": [0, 0]}
    for q, r in q_cur.items():
        t = pos[_tranche(r["position"])]
        t[0] += r["clicks"]; t[1] += r["impressions"]
        m = marque_h["marque" if any(w in q.lower() for w in mots) else "hors"]
        m[0] += r["clicks"]; m[1] += r["impressions"]
    out["positions"] = pos
    out["marque"] = marque_h
    # gagnants / perdants (écart de clics)
    delta = []
    for q in set(q_cur) | set(q_prec):
        c, p = q_cur.get(q), q_prec.get(q)
        dc = (c["clicks"] if c else 0) - (p["clicks"] if p else 0)
        if dc:
            delta.append((dc, q, c, p))
    delta.sort(key=lambda x: x[0])
    fmt = lambda q, c, p: {"requete": q, "clics": c["clicks"] if c else 0, "avant": p["clicks"] if p else 0,
                           "impressions": c["impressions"] if c else (p["impressions"] if p else 0),
                           "position": round(c["position"], 1) if c else None, "positionAvant": round(p["position"], 1) if p else None}
    out["gagnants"] = [fmt(q, c, p) for dc, q, c, p in delta[::-1][:8] if dc > 0]
    out["perdants"] = [fmt(q, c, p) for dc, q, c, p in delta[:8] if dc < 0]
    # opportunités : positions 4-15, au moins 100 impressions, gain potentiel si top 3
    opps = []
    for q, r in q_cur.items():
        if 3.5 < r["position"] <= 15.5 and r["impressions"] >= 100:
            gain = r["impressions"] * (CTR_TOP3 - r["ctr"])
            if gain > 0:
                opps.append((gain, q, r))
    opps.sort(key=lambda x: -x[0])
    out["opps"] = [{"requete": q, "clics": r["clicks"], "impressions": r["impressions"], "ctr": round(r["ctr"] * 100, 2),
                    "position": round(r["position"], 1), "gain": round(g)} for g, q, r in opps[:12]]
    # cannibalisation : requêtes (≥ 200 impressions) servies par au moins 2 pages ayant chacune ≥ 5 % des impressions de la requête
    qp = {}
    for r in _requete(cli, site_url, debut, fin, ["query", "page"]):
        qp.setdefault(r["keys"][0], []).append(r)
    cann = []
    for q, lignes in qp.items():
        tot = sum(x["impressions"] for x in lignes)
        if tot < 200:
            continue
        pages = [x for x in lignes if x["impressions"] >= 0.05 * tot]
        if len(pages) >= 2:
            pages.sort(key=lambda x: -x["impressions"])
            cann.append((tot, q, pages))
    cann.sort(key=lambda x: -x[0])
    out["cannib"] = [{"requete": q, "impressions": tot, "pages": [{"page": x["keys"][1], "clics": x["clicks"], "impressions": x["impressions"], "position": round(x["position"], 1)} for x in pages[:3]]}
                     for tot, q, pages in cann[:10]]
    # pages en déclin (clics vs mois précédent)
    p_cur = {r["keys"][0]: r for r in _requete(cli, site_url, debut, fin, ["page"])}
    p_prec = {r["keys"][0]: r for r in _requete(cli, site_url, debut_prec, fin_prec, ["page"])} if debut_prec else {}
    dec = []
    for pg, p in p_prec.items():
        c = p_cur.get(pg)
        dc = (c["clicks"] if c else 0) - p["clicks"]
        if dc < 0 and p["clicks"] >= 10:
            dec.append((dc, pg, c, p))
    dec.sort(key=lambda x: x[0])
    out["pagesDeclin"] = [{"page": pg, "clics": c["clicks"] if c else 0, "avant": p["clicks"], "position": round(c["position"], 1) if c else None,
                           "positionAvant": round(p["position"], 1)} for dc, pg, c, p in dec[:8]]
    return out


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
