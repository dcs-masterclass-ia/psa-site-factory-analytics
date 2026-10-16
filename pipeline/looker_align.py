"""Rattrapage unique pour aligner Converge sur Looker, sans refaire tout le rafraîchissement :

  - canaux d'acquisition = « Stellantis Custom Channel Group » (canal quotidien du site parent, conversion par canal × appareil,
    entonnoir par canal) sur tout l'historique publié, à la place du groupe par défaut de GA4 ;
  - propSessions : sessions de toute la propriété (tous domaines) par jour et par mois (« Visites site marque » de Looker).

Le rafraîchissement nocturne (build.py) tient ensuite ces données à jour avec les mêmes définitions.
Usage : python -m pipeline.looker_align [--ecrire] [--sites slug ...]
"""
import argparse
import calendar
import json
import sys
from datetime import date
from pathlib import Path

from pipeline import discover, funnel, funnel_daily, ga4, sites

DATA = Path("data")


def _fin_mois(m, dernier_jour):
    a, mo = int(m[:4]), int(m[5:7])
    fin = f"{m}-{calendar.monthrange(a, mo)[1]:02d}"
    return min(fin, dernier_jour)


def traite(cli, s, d):
    jours = (d.get("daily") or {}).get("d") or []
    if not jours:
        return None
    debut, dernier = jours[0], jours[-1]
    liste = ga4.hotes(cli, s.propriete, debut, dernier)
    hote_parent, hote_reprise, _ = discover.deduire(liste, s.pays)
    hote_reprise = discover.hotes_reprise_complets(liste, hote_reprise, s.pays)
    dim = ga4.dim_canal(s.propriete)
    mois = [m for m in d.get("months", []) if m != "total"]
    canal_q = d.setdefault("canalQuotidien", {})
    conv_cd = d.setdefault("convCanalDevice", {})
    for m in mois:
        deb, fin = f"{m}-01", _fin_mois(m, dernier)
        if deb > dernier:
            continue
        try:
            lignes = ga4._rapport(cli, s.propriete, deb, fin, ["date", dim], ["sessions"], ga4._egal("hostName", hote_parent))
            par_jour = {}
            for jour, canal, n in lignes:
                if len(jour) == 8 and jour.isdigit():
                    par_jour.setdefault(f"{jour[:4]}-{jour[4:6]}-{jour[6:]}", {})[canal.strip() or "(non défini)"] = int(n)
            if par_jour:
                canal_q[m] = par_jour
        except Exception as e:
            print(f"  {s.slug} {m} canal quotidien : {type(e).__name__}", file=sys.stderr)
        try:
            lignes = ga4._rapport(cli, s.propriete, deb, fin, ["date", dim], ["sessions"], ga4._egal("hostName", hote_reprise))
            par_jour = {}
            for jour, canal, n in lignes:
                if len(jour) == 8 and jour.isdigit():
                    par_jour.setdefault(f"{jour[:4]}-{jour[4:6]}-{jour[6:]}", {})[canal.strip() or "(non défini)"] = int(n)
            if par_jour:
                d.setdefault("canalReprise", {})[m] = par_jour           # sessions de la reprise par canal (courbe « Sessions par canal »)
        except Exception as e:
            print(f"  {s.slug} {m} canal reprise : {type(e).__name__}", file=sys.stderr)
        try:
            conv_cd[m] = funnel.conversion_par_canal_device(cli, s.propriete, hote_reprise, deb, fin)
        except Exception as e:
            print(f"  {s.slug} {m} canal x appareil : {type(e).__name__}", file=sys.stderr)
    try:
        seg = funnel_daily.funnel_segments(cli, s.propriete, hote_reprise, date.fromisoformat(mois[0] + "-01"), date.fromisoformat(dernier))
        if seg:
            d["funnelSeg"] = seg
    except Exception as e:
        print(f"  {s.slug} entonnoir par canal : {type(e).__name__}", file=sys.stderr)
    try:
        d["propSessions"] = {"daily": ga4.sessions_propriete_par_jour(cli, s.propriete, debut, dernier),
                             "month": ga4.sessions_propriete_par_mois(cli, s.propriete, debut, dernier)}
    except Exception as e:
        print(f"  {s.slug} sessions de la propriete : {type(e).__name__}", file=sys.stderr)
    return dim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ecrire", action="store_true")
    ap.add_argument("--sites", nargs="*")
    a = ap.parse_args()
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    cli = BetaAnalyticsDataClient()
    par_slug = {s.slug: s for s in sites.SITES}
    voulus = set(a.sites or [])
    modifies = []
    for f in sorted(DATA.glob("*.json")):
        slug = f.stem
        if slug not in par_slug or (voulus and slug not in voulus):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            dim = traite(cli, par_slug[slug], d)
        except Exception as e:
            print(f"{slug} : en erreur ({type(e).__name__}: {e})", file=sys.stderr)
            continue
        if dim is None:
            continue
        print(f"{slug} : canaux via {dim}")
        if a.ecrire:
            f.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            modifies.append(str(f))
    if a.ecrire and modifies:
        from pipeline.build import _commit_et_pousse, _configure_git
        _configure_git()
        ok, detail = _commit_et_pousse(modifies, f"chore(looker): canaux Stellantis + sessions propriete ({len(modifies)} site(s))")
        print("publié" if ok else f"push en échec : {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
