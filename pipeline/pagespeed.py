#!/usr/bin/env python3
"""Performance des outils de reprise via l'API PageSpeed Insights (Lighthouse).

Mesure toujours l'hote de reprise (hote_reprise), jamais le site parent : la
meme logique que le reste du pipeline, qui suit systematiquement l'outil de
reprise plutot que la vitrine (funnel, leads, trafic).

Cle d'API distincte du compte de service GA4/GSC : PageSpeed Insights
s'authentifie avec une simple cle API Google Cloud (PAGESPEED_API_KEY),
pas un compte de service. A creer dans le meme projet GCP (API "PageSpeed
Insights API" a activer separement) puis a deposer comme secret GitHub.

Chaque appel Lighthouse prend 10 a 30 secondes cote Google — bien plus lent
que les rapports GA4/GSC. Volontairement tenu a l'ecart du rafraichissement
quotidien (pipeline/build.py) : la performance d'un site ne bouge pas d'un
jour a l'autre, un releve hebdomadaire suffit et evite d'alourdir encore le
job principal. Voir .github/workflows/pagespeed.yml.

Usage
-----
    python3 -m pipeline.pagespeed --hote reprise.opel.fr
    python3 -m pipeline.pagespeed --tous
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data"
PARIS = timezone(timedelta(hours=2))

BASE = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
STRATEGIES = ("mobile", "desktop")

# id d'audit Lighthouse -> cle de sortie. Ce sont les memes metriques que
# l'onglet "Performance" de l'outil PageSpeed Insights web.
AUDITS = {
    "largest-contentful-paint": "lcp",
    "cumulative-layout-shift": "cls",
    "total-blocking-time": "tbt",
    "first-contentful-paint": "fcp",
    "speed-index": "si",
}

DELAI_ENTRE_APPELS = 1.0   # secondes ; courtoisie envers le quota (25000/jour,
                            # 400/100s par utilisateur), pas une necessite stricte.


def cle_api():
    c = os.environ.get("PAGESPEED_API_KEY")
    if not c:
        sys.exit("PAGESPEED_API_KEY non defini.")
    return c


def _requete(url_cible, strategie, timeout=90):
    params = {
        "url": url_cible, "strategy": strategie,
        "category": "performance", "key": cle_api(),
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def mesure(hote, strategie):
    """Une mesure Lighthouse pour un hote et une strategie donnes.

    Retourne {"score": 0-100, "lcp": ms, "cls": ratio, "tbt": ms, "fcp": ms,
    "si": ms} ou None si l'audit echoue (URL injoignable, quota depasse,
    reponse mal formee) — jamais une exception qui remonte : un site en
    echec ne doit pas bloquer les autres."""
    url_cible = f"https://{hote}/"
    try:
        rep = _requete(url_cible, strategie)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    lh = rep.get("lighthouseResult")
    if not lh:
        return None
    perf = lh.get("categories", {}).get("performance", {}).get("score")
    if perf is None:
        return None

    audits = lh.get("audits", {})
    sortie = {"score": round(perf * 100)}
    for audit_id, cle in AUDITS.items():
        val = audits.get(audit_id, {}).get("numericValue")
        sortie[cle] = round(val) if val is not None else None
    return sortie


def mesure_site(hote):
    """{"mobile": {...} ou None, "desktop": {...} ou None}"""
    sortie = {}
    for i, strategie in enumerate(STRATEGIES):
        if i:
            time.sleep(DELAI_ENTRE_APPELS)
        sortie[strategie] = mesure(hote, strategie)
    return sortie


def _fusionne(chemin, resultat):
    """Ajoute/actualise la cle pagespeed d'un data/<slug>.json existant, sans
    toucher au reste du fichier (pas de passage par les controles de
    build.py : purement additif, aucun risque pour les autres onglets)."""
    d = json.loads(chemin.read_text())
    aujourd_hui = datetime.now(PARIS).date().isoformat()
    bloc = d.setdefault("pagespeed", {"historique": {}})
    bloc["mobile"] = resultat["mobile"]
    bloc["desktop"] = resultat["desktop"]
    bloc["releve"] = aujourd_hui
    bloc["historique"][aujourd_hui] = {
        "mobile": resultat["mobile"]["score"] if resultat["mobile"] else None,
        "desktop": resultat["desktop"]["score"] if resultat["desktop"] else None,
    }
    chemin.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")))


# ---------------------------------------------------------------- ligne de commande

def main():
    ap = argparse.ArgumentParser(description="Mesure PageSpeed Insights d'un hote")
    ap.add_argument("--hote", help="hote de reprise, ex. reprise.opel.fr")
    ap.add_argument("--tous", action="store_true",
                    help="mesure tous les sites exploitables de pipeline.sites")
    ap.add_argument("--sites", nargs="*",
                    help="sous-ensemble de sites (nom ou slug) a mesurer, pour un rafraichissement cible")
    ap.add_argument("--ecrire", action="store_true",
                    help="avec --tous/--sites : ecrit le resultat dans data/<slug>.json")
    a = ap.parse_args()

    if not a.hote and not a.tous and not a.sites:
        sys.exit("Choisir --hote, --tous ou --sites")

    if a.hote:
        r = mesure_site(a.hote)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0

    from pipeline.sites import exploitables, site as trouve_site
    cibles = [trouve_site(x) for x in a.sites] if a.sites else exploitables()
    recap = os.environ.get("GITHUB_STEP_SUMMARY")
    lignes_recap = ["## Performance PageSpeed Insights\n", "| Site | Mobile | Desktop |", "|---|---:|---:|"]
    for s in cibles:
        r = mesure_site(s.hote_reprise)
        m, d = r["mobile"], r["desktop"]
        m_s = str(m["score"]) if m else "?"
        d_s = str(d["score"]) if d else "?"
        print(f"{s.nom:20} mobile={m_s:>4}  desktop={d_s:>4}  ({s.hote_reprise})")
        lignes_recap.append(f"| {s.nom} | {m_s} | {d_s} |")
        if a.ecrire:
            chemin = DATA / f"{s.slug}.json"
            if chemin.exists():
                _fusionne(chemin, r)
    if recap:
        with open(recap, "a", encoding="utf-8") as f:
            f.write("\n".join(lignes_recap) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
