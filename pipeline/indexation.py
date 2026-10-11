"""Indexation des pages principales de chaque site (API URL Inspection de Search Console) -> data/indexation.json.

Pour chaque site ayant une propriété Search Console, les 10 pages qui reçoivent le plus de clics (dernier mois connu) sont inspectées :
verdict d'indexation, état de couverture, autorisation du robots.txt, dernière exploration, canonique choisie par Google vs déclarée.
~10 appels par site et par passage (quota : 2 000 / jour / propriété). Aucune donnée personnelle.

Usage : python -m pipeline.indexation [--ecrire] [--sites "PEUGEOT FR" ...]
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline import search_console

DATA = Path(__file__).resolve().parent.parent / "data"
PAGES_PAR_SITE = 10


def pages_principales(d, n=PAGES_PAR_SITE):
    """Pages les plus cliquées du dernier mois de recherche connu."""
    sm = d.get("searchMonth") or {}
    for mois in sorted((m for m in sm if m != "total"), reverse=True):
        pages = (sm[mois] or {}).get("pages") or []
        if pages:
            return [p["page"] for p in sorted(pages, key=lambda x: -x["clics"])[:n]]
    return []


def inspecte(cli, propriete, url):
    r = cli.urlInspection().index().inspect(body={"inspectionUrl": url, "siteUrl": propriete, "languageCode": "fr"}).execute()
    st = (r.get("inspectionResult") or {}).get("indexStatusResult") or {}
    return {"url": url, "verdict": st.get("verdict", "VERDICT_UNSPECIFIED"), "etat": st.get("coverageState", ""),
            "robots": st.get("robotsTxtState", ""), "indexation": st.get("indexingState", ""), "exploration": (st.get("lastCrawlTime") or "")[:10],
            "canoniqueOk": (not st.get("googleCanonical") or not st.get("userCanonical") or st["googleCanonical"].rstrip("/") == st["userCanonical"].rstrip("/")),
            "canonique": st.get("googleCanonical", "") if st.get("googleCanonical") != url else ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ecrire", action="store_true")
    ap.add_argument("--sites", nargs="*")
    a = ap.parse_args()
    cli = search_console.client()
    sortie = {"genere": datetime.now(timezone.utc).date().isoformat(), "sites": {}}
    ancien = {}
    try:
        ancien = json.loads((DATA / "indexation.json").read_text(encoding="utf-8")).get("sites", {})
    except Exception:
        pass
    voulus = {s.strip().upper() for s in (a.sites or [])}
    for f in sorted(DATA.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict) or not d.get("gscProperty") or not d.get("site"):
            continue
        if voulus and d["site"].upper() not in voulus:
            sortie["sites"][d["site"]] = ancien.get(d["site"])      # conserve les autres sites tels quels
            continue
        pages = []
        for url in pages_principales(d):
            try:
                pages.append(inspecte(cli, d["gscProperty"], url))
            except Exception as e:
                pages.append({"url": url, "verdict": "ERREUR", "etat": type(e).__name__, "robots": "", "indexation": "", "exploration": "", "canoniqueOk": True, "canonique": ""})
            time.sleep(0.15)
        if pages:
            sortie["sites"][d["site"]] = {"propriete": d["gscProperty"], "pages": pages}
            nb_ko = sum(1 for p in pages if p["verdict"] not in ("PASS",))
            print(f"{d['site']} : {len(pages)} page(s), {nb_ko} non indexée(s) ou en erreur")
    sortie["sites"] = {k: v for k, v in sortie["sites"].items() if v}
    if a.ecrire:
        (DATA / "indexation.json").write_text(json.dumps(sortie, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        from pipeline.build import _commit_et_pousse, _configure_git
        _configure_git()
        ok, detail = _commit_et_pousse(["data/indexation.json"], f"chore(indexation): {len(sortie['sites'])} site(s) au {sortie['genere']}")
        print("indexation.json publié" if ok else f"push en échec : {detail}")


if __name__ == "__main__":
    main()
