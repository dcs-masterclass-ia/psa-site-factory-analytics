"""Entonnoir par MODE DE SAISIE du véhicule : immatriculation / marque-modèle (vue « Tunnel de conversion », pastilles).

GA4 n'a pas de champ « mode de saisie » (vehicle_registration est vide). Le parcours manuel passe par des étapes que la plaque saute :
« registration date », « fuel type », « engine power » (step_name). Un visiteur qui en a vu une au moins sur la période = parcours marque / modèle ;
tous les autres = immatriculation. Vérifié sur OPEL FR (sept. 2026) : 5,9 % des visiteurs de l'étape Version et 4,3 % des estimations, contre
4,4 % des leads « Marque / modèle » du back-office.

Méthode : rapport d'entonnoir de l'API Data (v1alpha), mêmes 6 étapes que funnel_daily (utilisateurs actifs, hôte de la reprise), une fois sans
segment (« tous ») et une fois pour le segment des visiteurs du parcours manuel ; immatriculation = tous − marque/modèle (les deux segments sont disjoints).
Mensuel (visiteurs uniques du mois, comme funnelSeg) : {"AAAA-MM": {"tous": [6 entiers], "marque_modele": [6 entiers]}}.
"""

import calendar
from datetime import date

from google.analytics.data_v1alpha import AlphaAnalyticsDataClient
from google.analytics.data_v1alpha.types import (
    DateRange, Funnel, FunnelEventFilter, FunnelFieldFilter, FunnelFilterExpression, FunnelFilterExpressionList, FunnelParameterFilter,
    FunnelParameterFilterExpression, FunnelStep, RunFunnelReportRequest, Segment, SegmentEventFilter, SegmentFilterExpression,
    SegmentFilterExpressionList, SegmentParameterFilter, SegmentParameterFilterExpression, StringFilter, UserCriteriaScoping, UserSegment,
    UserSegmentConditionGroup, UserSegmentCriteria,
)

SF = StringFilter
EVENEMENTS = ("page_view", "form_step_view", "uaevent", "form_start", "tradein_request")     # l'API exige un nom d'évènement par étape
ETAPES = [("Version", "version"), ("Kilométrage", "mileage"), ("Coordonnées", "contact details"), ("Point de vente", "dealer choice"), ("Estimation", "price estimation")]
ETAPES_MANUELLES = ("registration date", "fuel type", "engine power")
MAX_MOIS_PAR_PASSAGE = 3


def _exact(v):
    return SF(match_type=SF.MatchType.EXACT, value=v)


def _ou(*e):
    return e[0] if len(e) == 1 else FunnelFilterExpression(or_group=FunnelFilterExpressionList(expressions=list(e)))


def _et(*e):
    return FunnelFilterExpression(and_group=FunnelFilterExpressionList(expressions=list(e)))


def _param(champ, valeur, evenement, contient=False):
    sf = SF(match_type=SF.MatchType.CONTAINS, value=valeur, case_sensitive=False) if contient else _exact(valeur)
    return FunnelFilterExpression(funnel_event_filter=FunnelEventFilter(
        event_name=evenement, funnel_parameter_filter_expression=FunnelParameterFilterExpression(
            funnel_parameter_filter=FunnelParameterFilter(event_parameter_name=champ, string_filter=sf))))


def _hote(hote):
    return _ou(*[FunnelFilterExpression(funnel_field_filter=FunnelFieldFilter(field_name="hostName", string_filter=_exact(h))) for h in hote.split("|") if h])


def _etapes(hote):
    h = _hote(hote)
    tout = [("Page d'accueil", _param("page_category", "home page", "page_view", contient=True))]
    tout += [(nom, _ou(*[_param("step_name", v, e) for e in EVENEMENTS])) for nom, v in ETAPES]
    return [FunnelStep(name=nom, filter_expression=_et(h, expr)) for nom, expr in tout]


def _segment_manuel():
    ou = SegmentFilterExpressionList(expressions=[SegmentFilterExpression(segment_event_filter=SegmentEventFilter(
        event_name="page_view", segment_parameter_filter_expression=SegmentParameterFilterExpression(
            segment_parameter_filter=SegmentParameterFilter(event_parameter_name="step_name", string_filter=_exact(v))))) for v in ETAPES_MANUELLES])
    groupe = UserSegmentConditionGroup(condition_scoping=UserCriteriaScoping.USER_CRITERIA_ACROSS_ALL_SESSIONS,
                                       segment_filter_expression=SegmentFilterExpression(or_group=ou))
    return Segment(name="manuel", user_segment=UserSegment(user_inclusion_criteria=UserSegmentCriteria(and_condition_groups=[groupe])))


def _rapport(cli, pid, hote, debut, fin, segments=None):
    """-> [6 entiers] (utilisateurs actifs par étape)."""
    req = RunFunnelReportRequest(property=f"properties/{pid}", date_ranges=[DateRange(start_date=debut, end_date=fin)],
                                 funnel=Funnel(is_open_funnel=True, steps=_etapes(hote)), segments=segments or [])
    t = cli.run_funnel_report(request=req).funnel_table
    out = [0] * 6
    for r in t.rows:
        etape = int(r.dimension_values[0].value.split(".")[0]) - 1
        out[etape] = int(r.metric_values[0].value)
    return out


def mois_entree(cli, pid, hote, mois, dernier_jour):
    debut = f"{mois}-01"
    fin_mois = date(int(mois[:4]), int(mois[5:]), calendar.monthrange(int(mois[:4]), int(mois[5:]))[1])
    fin = min(fin_mois, date.fromisoformat(dernier_jour)).isoformat()
    tous = _rapport(cli, pid, hote, debut, fin)
    if tous[0] <= 0:
        return None
    manuel = _rapport(cli, pid, hote, debut, fin, [_segment_manuel()])
    return {"tous": tous, "marque_modele": [min(m, t) for m, t in zip(manuel, tous)]}


def mettre_a_jour(pid, hote, existant, mois_liste, dernier_jour):
    """Recalcule le mois en cours et le précédent à chaque passage, rattrape au plus MAX_MOIS_PAR_PASSAGE mois manquants. -> dict mis à jour."""
    cli = AlphaAnalyticsDataClient()
    out = dict(existant or {})
    recents = set(mois_liste[-2:])
    a_faire = [m for m in mois_liste if m in recents]
    a_faire += [m for m in reversed(mois_liste) if m not in out and m not in recents][:MAX_MOIS_PAR_PASSAGE]
    for m in a_faire:
        r = mois_entree(cli, pid, hote, m, dernier_jour)
        if r:
            out[m] = r
    return {m: out[m] for m in sorted(out)}
