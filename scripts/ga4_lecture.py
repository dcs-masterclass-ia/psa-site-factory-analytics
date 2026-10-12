"""Lecture GA4 en LECTURE SEULE pour l'agent de réponse aux questions (tickets).

Interroge GA4 pour un site du parc sur des métriques et dimensions d'une liste blanche, et affiche le résultat en JSON.
Aucune écriture, aucun autre accès : l'agent n'a pas le droit d'exécuter autre chose que cette commande.

Usage : python scripts/ga4_lecture.py --site citroen-fr --debut 2026-09-01 --fin 2026-09-30 [--hote reprise|parent]
          [--metriques sessions,eventCount] [--dimensions yearMonth] [--evenement tradein_request]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

METRIQUES = {"sessions", "activeUsers", "totalUsers", "newUsers", "eventCount", "keyEvents", "sessionKeyEventRate", "engagedSessions",
             "screenPageViews", "userEngagementDuration", "bounceRate"}
DIMENSIONS = {"date", "yearMonth", "yearWeek", "eventName", "sessionDefaultChannelGroup", "deviceCategory", "hostName", "sessionSourceMedium",
              "sessionCampaignName", "landingPagePlusQueryString"}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--site", required=True)
    a.add_argument("--debut", required=True)
    a.add_argument("--fin", required=True)
    a.add_argument("--hote", choices=["reprise", "parent", "aucun"], default="reprise")
    a.add_argument("--metriques", default="sessions")
    a.add_argument("--dimensions", default="")
    a.add_argument("--evenement", default="")
    a = a.parse_args()
    mets = [m for m in a.metriques.split(",") if m]
    dims = [d for d in a.dimensions.split(",") if d]
    if not mets or any(m not in METRIQUES for m in mets) or any(d not in DIMENSIONS for d in dims):
        print(json.dumps({"erreur": "métrique ou dimension hors liste blanche", "metriques": sorted(METRIQUES), "dimensions": sorted(DIMENSIONS)}))
        return 2
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import DateRange, Dimension, Filter, FilterExpression, FilterExpressionList, Metric, RunReportRequest
    from pipeline import sites
    s = next((x for x in sites.SITES if x.slug == a.site), None)
    if s is None:
        print(json.dumps({"erreur": f"site inconnu : {a.site}"}))
        return 2
    egal = lambda champ, v: FilterExpression(filter=Filter(field_name=champ, string_filter=Filter.StringFilter(value=v, match_type=Filter.StringFilter.MatchType.EXACT)))
    filtres = []
    hote = {"reprise": s.hote_reprise, "parent": s.hote_parent}.get(a.hote)
    if hote:
        filtres.append(egal("hostName", hote))
    if a.evenement:
        filtres.append(egal("eventName", a.evenement))
    req = RunReportRequest(property=f"properties/{s.propriete}", date_ranges=[DateRange(start_date=a.debut, end_date=a.fin)],
                           dimensions=[Dimension(name=d) for d in dims], metrics=[Metric(name=m) for m in mets], limit=200,
                           dimension_filter=FilterExpression(and_group=FilterExpressionList(expressions=filtres)) if filtres else None)
    import os
    cle = os.environ.get("GA4_SERVICE_ACCOUNT_JSON")  # clé en variable d'environnement : aucun fichier que l'agent pourrait lire
    if cle:
        from google.oauth2 import service_account
        cli = BetaAnalyticsDataClient(credentials=service_account.Credentials.from_service_account_info(json.loads(cle)))
    else:
        cli = BetaAnalyticsDataClient()
    r = cli.run_report(req)
    lignes = [{**{d: v.value for d, v in zip(dims, row.dimension_values)}, **{m: float(v.value) for m, v in zip(mets, row.metric_values)}} for row in r.rows]
    print(json.dumps({"site": a.site, "hote": hote, "periode": [a.debut, a.fin], "lignes": lignes}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
