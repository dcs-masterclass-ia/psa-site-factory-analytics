"""Remplit d['evDaily'] (évènements d'estimation par jour) pour tous les sites, sans refaire tout le rafraîchissement.

Une seule requête GA4 par site sur toute la fenêtre déjà publiée. Sert au taux de conversion « en sessions »
(tradein_request ÷ sessions du site de reprise, identique à Looker). Le rafraîchissement nocturne (build.py) le tient ensuite à jour.
Usage : python -m pipeline.ev_daily [--ecrire] [--sites SLUG ...]
"""
import argparse
import json
import sys
from pathlib import Path

from pipeline import discover, funnel, ga4, sites

DATA = Path("data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ecrire", action="store_true")
    ap.add_argument("--sites", nargs="*")
    a = ap.parse_args()
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    cli = BetaAnalyticsDataClient()
    voulus = set(a.sites or [])
    par_slug = {s.slug: s for s in sites.SITES}
    modifies = []
    for f in sorted(DATA.glob("*.json")):
        slug = f.stem
        if slug not in par_slug or (voulus and slug not in voulus):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            jours = (d.get("daily") or {}).get("d") or []
            if not jours:
                continue
            s = par_slug[slug]
            liste = ga4.hotes(cli, s.propriete, jours[0], jours[-1])
            _, hote_reprise, _jrn = discover.deduire(liste, s.pays)
            hote_reprise = discover.hotes_reprise_complets(liste, hote_reprise, s.pays)
            ev = ga4.evenements_par_jour(cli, s.propriete, hote_reprise, jours[0], jours[-1], funnel.EVENEMENT_ESTIMATION)
        except Exception as e:
            print(f"{slug} : en erreur ({type(e).__name__}: {e})", file=sys.stderr)
            continue
        print(f"{slug} : {len(ev)} jour(s), {sum(ev.values())} évènements")
        if a.ecrire and ev:
            d["evDaily"] = ev
            f.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            modifies.append(str(f))
    if a.ecrire and modifies:
        from pipeline.build import _commit_et_pousse, _configure_git
        _configure_git()
        ok, detail = _commit_et_pousse(modifies, f"chore(ev): evenements d'estimation par jour ({len(modifies)} site(s))")
        print("publié" if ok else f"push en échec : {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
