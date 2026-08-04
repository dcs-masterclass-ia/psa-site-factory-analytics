"""Reconstruction du funnel GA4, sans intervention humaine.

Deux methodes, essayees dans l'ordre :

  A. runFunnelReport (API v1alpha) : reproduit l'entonnoir strict tel que
     defini dans les explorations GA4. Le plus fidele, mais l'acces alpha
     n'est pas garanti sur toutes les proprietes/organisations — jamais
     teste depuis cet environnement.

  B. repli automatique : comptage d'utilisateurs actifs par evenement,
     l'evenement de chaque etape etant identifie par mot-cle (meme principe
     que la decouverte des hotes et du robot). Moins fidele a un entonnoir
     strict, mais ne depend d'aucune fonctionnalite alpha.

Le choix se fait tout seul et est trace dans le champ `methode` du resultat.
Si aucune des deux methodes n'identifie les etapes avec certitude, le mois
est marque sans funnel plutot que de publier une supposition.
"""

import re

from pipeline import ga4

# etapes standard du parcours de reprise, avec leurs mots-cles de reconnaissance.
# Les libelles francais/portugais varient (Homepage/Página inicial), on
# reconnait sur la racine plutot que sur la langue.
ETAPES = [
    ("Page d'accueil", (r"home", r"accueil", r"pagina.?inicial", r"landing")),
    ("Version", (r"version", r"vers[aã]o")),
    ("Kilométrage", (r"kilom", r"mileage", r"quilom")),
    ("Coordonnées", (r"contact", r"coordon", r"contacto")),
    ("Point de vente", (r"pdv\b", r"dealer", r"point.?de.?vente", r"concession",
                        r"ponto.?de.?venda")),
    ("Estimation", (r"estimat", r"valuation", r"avalia", r"price")),
]


def _correspond(nom, motifs):
    return any(re.search(m, nom, re.I) for m in motifs)


def _via_alpha(pid, hote, debut, fin):
    """Piste A. Leve une exception si l'API alpha n'est pas accessible."""
    from google.analytics.data_v1alpha import AlphaAnalyticsDataClient
    from google.analytics.data_v1alpha.types import (
        DateRange, Dimension, Filter, FilterExpression, Funnel, FunnelStep,
        FunnelFieldFilter, FunnelFilterExpression, RunFunnelReportRequest,
    )

    cli = AlphaAnalyticsDataClient()
    steps = [
        FunnelStep(
            name=nom,
            filter_expression=FunnelFilterExpression(
                funnel_field_filter=FunnelFieldFilter(
                    field_name="eventName",
                    string_filter=Filter.StringFilter(
                        match_type=Filter.StringFilter.MatchType.CONTAINS,
                        value=nom, case_sensitive=False),
                )),
        )
        for nom, _ in ETAPES
    ]
    rep = cli.run_funnel_report(RunFunnelReportRequest(
        property=f"properties/{pid}",
        date_ranges=[DateRange(start_date=debut, end_date=fin)],
        funnel=Funnel(steps=steps),
    ))
    resultat = []
    for row in rep.funnel_table.rows:
        resultat.append({"step": row.dimension_values[0].value,
                         "users": int(row.metric_values[0].value)})
    if not resultat:
        raise ValueError("reponse vide")
    return resultat


def _evenements_disponibles(cli, pid, hote, debut, fin):
    lignes = ga4._rapport(cli, pid, debut, fin, ["eventName"], ["activeUsers"],
                          ga4._egal("hostName", hote))
    return sorted(((n, int(u)) for n, u in lignes), key=lambda x: -x[1])


def _via_repli(cli, pid, hote, debut, fin):
    """Piste B. Identifie chaque etape par mot-cle parmi les evenements reels."""
    disponibles = _evenements_disponibles(cli, pid, hote, debut, fin)
    if not disponibles:
        raise ValueError("aucun evenement sur cet hote")

    trouves = []
    for nom_etape, motifs in ETAPES:
        cands = [(n, u) for n, u in disponibles if _correspond(n, motifs)]
        if not cands:
            continue                       # etape non identifiee : on l'omet
        evt, _ = max(cands, key=lambda x: x[1])
        l = ga4._rapport(cli, pid, debut, fin, [], ["activeUsers"],
                         ga4._egal("eventName", evt))
        u = int(l[0][0]) if l else 0
        trouves.append({"step": nom_etape, "users": u, "_evenement": evt})

    if len(trouves) < 3:
        raise ValueError(f"seulement {len(trouves)} etape(s) identifiee(s) sur "
                         f"{len(ETAPES)} : trop peu pour un funnel exploitable")

    trouves.sort(key=lambda x: -x["users"])   # ordre decroissant = ordre du parcours
    return trouves


def funnel_mensuel(cli, pid, hote, debut, fin):
    """Retourne (steps, methode) ou (None, motif_echec)."""
    try:
        steps = _via_alpha(pid, hote, debut, fin)
        return steps, "runFunnelReport (API alpha, entonnoir strict)"
    except Exception as e_alpha:
        try:
            steps = _via_repli(cli, pid, hote, debut, fin)
            for s in steps:
                s.pop("_evenement", None)
            return steps, ("repli par mot-cle sur les evenements "
                          "(approximation, pas un entonnoir strict)")
        except Exception as e_repli:
            return None, f"alpha: {e_alpha} | repli: {e_repli}"


def bloc_funnel(cli, pid, hote, debut, fin, jours):
    """Construit le bloc funnelMonth pour un mois, au format du dashboard."""
    steps, methode = funnel_mensuel(cli, pid, hote, debut, fin)
    if not steps or not steps[0]["users"]:
        return None, methode
    return {
        "steps": steps,
        "conversion_pct": round(steps[-1]["users"] / steps[0]["users"] * 100, 1),
        "users_per_day": round(steps[0]["users"] / jours, 1),
    }, methode
