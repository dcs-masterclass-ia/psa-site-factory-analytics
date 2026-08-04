"""Extraction GA4 par l'API Data.

Aucun etat, aucune ecriture : ce module ne fait que lire GA4 et rendre des
structures Python. L'assemblage et les controles sont ailleurs.
"""

import argparse
import calendar
import os
import sys
from collections import defaultdict

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Filter, FilterExpression, FilterExpressionList,
    Metric, RunReportRequest,
)

LIMITE = 100000


def client():
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        sys.exit("GOOGLE_APPLICATION_CREDENTIALS non defini.")
    return BetaAnalyticsDataClient()


def _egal(champ, valeur):
    return FilterExpression(filter=Filter(
        field_name=champ,
        string_filter=Filter.StringFilter(
            value=valeur, match_type=Filter.StringFilter.MatchType.EXACT),
    ))


def _et(*filtres):
    """Combine plusieurs filtres en ET. Utile pour croiser un evenement et
    un parametre personnalise sur la meme etape (ex : eventName = X ET
    step_name = Y, comme l'etape 6 des explorations GA4 du projet)."""
    return FilterExpression(and_group=FilterExpressionList(expressions=list(filtres)))


def _rapport(cli, pid, debut, fin, dimensions, metriques, filtre=None):
    """Requete paginee. Retourne une liste de listes de chaines."""
    lignes, offset = [], 0
    while True:
        rep = cli.run_report(RunReportRequest(
            property=f"properties/{pid}",
            date_ranges=[DateRange(start_date=debut, end_date=fin)],
            dimensions=[Dimension(name=d) for d in dimensions],
            metrics=[Metric(name=m) for m in metriques],
            dimension_filter=filtre,
            limit=LIMITE, offset=offset,
        ))
        for r in rep.rows:
            lignes.append([v.value for v in r.dimension_values]
                          + [v.value for v in r.metric_values])
        total = rep.row_count or 0
        offset += len(rep.rows)
        if offset >= total or not rep.rows:
            break
    return lignes


def hotes(cli, pid, debut, fin):
    """Noms d'hote de la propriete, par volume decroissant."""
    l = _rapport(cli, pid, debut, fin, ["hostName"], ["sessions"])
    return sorted(((h, int(s)) for h, s in l), key=lambda x: -x[1])


def sessions_par_jour(cli, pid, hote, debut, fin):
    l = _rapport(cli, pid, debut, fin, ["date"], ["sessions"], _egal("hostName", hote))
    return {d: int(s) for d, s in l}


def sessions_total(cli, pid, hote, debut, fin):
    """Total GA4 du mois. Ce n'est pas la somme des jours, et c'est normal."""
    l = _rapport(cli, pid, debut, fin, [], ["sessions"], _egal("hostName", hote))
    return int(l[0][0]) if l else 0


def sessions_et_utilisateurs(cli, pid, hote, debut, fin):
    l = _rapport(cli, pid, debut, fin, [], ["sessions", "totalUsers"], _egal("hostName", hote))
    return (int(l[0][0]), int(l[0][1])) if l else (0, 0)


def profils(cli, pid, hote, debut, fin):
    """Ventilation pays / navigateur / appareil, pour reperer un automate."""
    l = _rapport(cli, pid, debut, fin,
                 ["country", "browser", "deviceCategory"], ["sessions"],
                 _egal("hostName", hote))
    return sorted((((p, n, a), int(s)) for p, n, a, s in l), key=lambda x: -x[1])


def bornes(mois):
    """'2026-07' -> ('2026-07-01', '2026-07-31', 31)"""
    an, m = int(mois[:4]), int(mois[5:7])
    nb = calendar.monthrange(an, m)[1]
    return f"{mois}-01", f"{mois}-{nb:02d}", nb


def bloc_mensuel(cli, site, mois):
    """Extrait un mois pour un site. Retourne le detail necessaire a l'assemblage."""
    debut, fin, nb = bornes(mois)
    jp = sessions_par_jour(cli, site.propriete, site.hote_parent, debut, fin)
    jr = sessions_par_jour(cli, site.propriete, site.hote_reprise, debut, fin)
    tp = sessions_total(cli, site.propriete, site.hote_parent, debut, fin)
    tr = sessions_total(cli, site.propriete, site.hote_reprise, debut, fin)
    sess, users = sessions_et_utilisateurs(cli, site.propriete, site.hote_reprise, debut, fin)

    an, m = int(mois[:4]), int(mois[5:7])
    jours, u, rep = [], [], []
    for j in range(1, nb + 1):
        cle = f"{an}{m:02d}{j:02d}"
        jours.append(f"{m:02d}-{j:02d}")
        u.append(jp.get(cle, 0))
        rep.append(jr.get(cle, 0))

    return {
        "mois": mois, "jours_du_mois": nb,
        "d": jours, "u": u, "rep": rep,
        "traffic_total": tp, "reprise_total": tr,
        "reprise_sessions": sess, "reprise_utilisateurs": users,
    }


# ---------------------------------------------------------------- ligne de commande

def main():
    ap = argparse.ArgumentParser(description="Lecture GA4 par l'API Data")
    ap.add_argument("--propriete", required=True)
    ap.add_argument("--debut", default="2026-04-01")
    ap.add_argument("--fin", default="2026-07-31")
    ap.add_argument("--hotes", action="store_true")
    ap.add_argument("--hote")
    a = ap.parse_args()
    cli = client()

    if a.hotes:
        l = hotes(cli, a.propriete, a.debut, a.fin)
        tot = sum(s for _, s in l) or 1
        print(f"Propriete {a.propriete} — {a.debut} au {a.fin}\n")
        print(f"{'Nom d hote':<45}{'Sessions':>10}{'Part':>8}")
        print("-" * 63)
        for h, s in l:
            print(f"{h:<45}{s:>10}{s / tot * 100:>7.1f}%")
        print("-" * 63)
        print(f"{'Total':<45}{tot:>10}")
        print("\nInscrire les hotes retenus dans pipeline/sites.py avec verifie=True.")
    elif a.hote:
        j = sessions_par_jour(cli, a.propriete, a.hote, a.debut, a.fin)
        t = sessions_total(cli, a.propriete, a.hote, a.debut, a.fin)
        for d in sorted(j):
            print(f"  {d}  {j[d]:>7}")
        s = sum(j.values())
        print(f"\n  jours {len(j)} | somme {s} | total GA4 {t}"
              + (f" | ecart {(s - t) / t * 100:+.2f} %" if t else ""))
    else:
        sys.exit("Choisir --hotes ou --hote")


if __name__ == "__main__":
    main()
