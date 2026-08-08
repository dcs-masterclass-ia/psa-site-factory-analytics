#!/usr/bin/env python3
"""Performance des sites de reprise via l'API PageSpeed Insights (Lighthouse).

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

# les 4 categories Lighthouse : demandees en une seule requete (categories
# repetees dans l'URL), un seul chargement de page pour les quatre plutot
# que 4 appels separes.
CATEGORIES = ("performance", "accessibility", "best-practices", "seo")

# id d'audit Lighthouse -> (cle de sortie, decimales). Ce sont les memes
# metriques que l'onglet "Performance" de l'outil PageSpeed Insights web.
# cumulative-layout-shift est un ratio sans unite (ex. 0.94) : arrondir a
# l'entier comme les autres (en millisecondes) l'ecrasait a 0 ou 1, perdant
# toute la valeur -- bug reel trouve le 08/08/2026 en testant sur OPEL FR.
AUDITS = {
    "largest-contentful-paint": ("lcp", 0),
    "cumulative-layout-shift": ("cls", 3),
    "total-blocking-time": ("tbt", 0),
    "first-contentful-paint": ("fcp", 0),
    "speed-index": ("si", 0),
}

# jusqu'a combien d'"opportunities" (recommandations chiffrees, gain
# estime en ms) on garde par mesure -- trie par gain decroissant, le reste
# est du bruit pour une lecture rapide.
MAX_OPPORTUNITES = 5

# CrUX (donnees terrain, vrais utilisateurs Chrome) : cle de la reponse ->
# cle de sortie. CUMULATIVE_LAYOUT_SHIFT_SCORE est renvoye par Google en
# centiemes (12 = 0.12), diviser par 100 pour rester comparable au CLS
# labo. Les autres sont deja en millisecondes.
METRIQUES_CRUX = {
    "LARGEST_CONTENTFUL_PAINT_MS": ("lcp", 1),
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": ("cls", 100),
    "INTERACTION_TO_NEXT_PAINT": ("inp", 1),
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
        "category": CATEGORIES, "key": cle_api(),
        # titres/descriptions d'audit Lighthouse traduits par Google
        # lui-meme (ex. audits.opportunites[].title) -- plus fiable qu'un
        # dictionnaire de traduction maison a maintenir a chaque nouvel
        # audit Lighthouse. N'affecte pas les chiffres, seulement le texte.
        "locale": "fr",
    }
    url = BASE + "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _opportunites(audits):
    """Recommandations chiffrees, triees par gain de temps estime decroissant.
    Seuls les audits Lighthouse de type "opportunity" avec un gain reel
    (overallSavingsMs > 0) sont retenus -- le reste (diagnostics sans gain
    chiffrable) est du bruit pour une lecture rapide."""
    trouvees = []
    for a in audits.values():
        details = a.get("details") or {}
        gain = details.get("overallSavingsMs")
        if details.get("type") == "opportunity" and gain:
            trouvees.append({"titre": a.get("title", "?"), "gainMs": round(gain)})
    trouvees.sort(key=lambda o: -o["gainMs"])
    return trouvees[:MAX_OPPORTUNITES]


def _terrain(rep):
    """Donnees CrUX (vrais utilisateurs Chrome), quand Google en a assez
    pour les publier -- loadingExperience (l'URL precise) en priorite,
    originLoadingExperience (tout le domaine) en repli. None si aucune des
    deux n'existe : jamais de donnee terrain inventee a partir du labo."""
    exp, origine = rep.get("loadingExperience"), False
    if not exp or not exp.get("metrics"):
        exp, origine = rep.get("originLoadingExperience"), True
    if not exp or not exp.get("metrics"):
        return None
    m = exp["metrics"]
    sortie = {"origine": origine, "categorie": exp.get("overall_category")}
    for cle_api_crux, (cle, diviseur) in METRIQUES_CRUX.items():
        v = m.get(cle_api_crux, {}).get("percentile")
        sortie[cle] = round(v / diviseur, 2) if v is not None else None
    return sortie


def mesure(hote, strategie):
    """Une mesure Lighthouse pour un hote et une strategie donnes.

    Retourne un dict (score performance + accessibilite/bonnes pratiques/
    SEO, LCP/CLS/TBT/FCP/SI labo, opportunites chiffrees, donnees terrain
    CrUX si disponibles) ou None si l'audit echoue entierement (URL
    injoignable, quota depasse, reponse mal formee) — jamais une exception
    qui remonte : un site en echec ne doit pas bloquer les autres."""
    url_cible = f"https://{hote}/"
    try:
        rep = _requete(url_cible, strategie)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    lh = rep.get("lighthouseResult")
    if not lh:
        return None
    cats = lh.get("categories", {})
    perf = cats.get("performance", {}).get("score")
    if perf is None:
        return None

    def score_cat(nom):
        v = cats.get(nom, {}).get("score")
        return round(v * 100) if v is not None else None

    audits = lh.get("audits", {})
    sortie = {
        "score": round(perf * 100),
        "accessibilite": score_cat("accessibility"),
        "bonnesPratiques": score_cat("best-practices"),
        "seo": score_cat("seo"),
        "opportunites": _opportunites(audits),
        "terrain": _terrain(rep),
    }
    for audit_id, (cle, decimales) in AUDITS.items():
        val = audits.get(audit_id, {}).get("numericValue")
        sortie[cle] = None if val is None else (round(val, decimales) if decimales else round(val))
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
