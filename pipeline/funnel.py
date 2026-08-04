"""Reconstruction du funnel GA4, sans intervention humaine.

Trois methodes, essayees dans l'ordre :

  A. runFunnelReport (API v1alpha) : reproduit l'entonnoir strict tel que
     defini dans les explorations GA4. Le plus fidele, mais l'acces alpha
     n'est pas garanti — sur les 7 proprietes testees le 04/08/2026, aucune
     ne l'exposait.

  B. dimension personnalisee `step_name` : la structure reelle des
     explorations GA4 du projet (relevee dans l'interface le 04/08/2026)
     n'est pas une suite d'evenements distincts mais un evenement unique,
     filtre par ce parametre — sauf l'etape 1, filtree sur `page_category`
     avec l'expression reguliere "home page". C'est la methode la plus
     fiable des deux replis, puisqu'elle interroge le meme champ que les
     explorations manuelles.

  C. mot-cle sur eventName : dernier recours, si les dimensions
     personnalisees n'existent pas sur une propriete donnee.

Le choix se fait tout seul et est trace dans le champ `methode` du resultat.
Si aucune des trois methodes n'identifie les etapes avec certitude, le mois
est marque sans funnel plutot que de publier une supposition.
"""

import re

from pipeline import ga4

# etapes telles que definies dans les explorations GA4 (releve du 04/08/2026).
# La valeur exacte du parametre step_name pour les etapes 2 a 6 ; l'etape 1
# n'a pas ce parametre, elle est filtree sur page_category.
ETAPE_HOME = "Page d'accueil"
MOTIFS_HOME = (r"home", r"accueil", r"pagina.?inicial", r"landing")

ETAPES_PARAM = [
    ("Version", "version"),
    ("Kilométrage", "mileage"),
    ("Coordonnées", "contact details"),
    ("Point de vente", "dealer choice"),
    ("Estimation", "price estimation"),
]

# mots-cles de repli si la dimension personnalisee n'existe pas (piste C)
MOTIFS_EVT = {
    ETAPE_HOME: MOTIFS_HOME,
    "Version": (r"version", r"vers[aã]o"),
    "Kilométrage": (r"kilom", r"mileage", r"quilom"),
    "Coordonnées": (r"contact", r"coordon", r"contacto"),
    "Point de vente": (r"pdv\b", r"dealer", r"point.?de.?vente",
                       r"concession", r"ponto.?de.?venda"),
    "Estimation": (r"estimat", r"valuation", r"avalia", r"price"),
}

# nom d'API candidat pour les dimensions personnalisees : on ne le suppose
# pas non plus au hasard, on essaie et on retient celui qui repond.
CANDIDATS_STEP_NAME = ["customEvent:step_name", "customUser:step_name"]
CANDIDATS_PAGE_CATEGORY = ["customEvent:page_category", "customUser:page_category"]


def _correspond(nom, motifs):
    return any(re.search(m, nom, re.I) for m in motifs)


def _via_alpha(pid, hote, debut, fin):
    """Piste A. Leve une exception si l'API alpha n'est pas accessible."""
    from google.analytics.data_v1alpha import AlphaAnalyticsDataClient
    from google.analytics.data_v1alpha.types import (
        DateRange, Filter, Funnel, FunnelStep,
        FunnelFieldFilter, FunnelFilterExpression, RunFunnelReportRequest,
    )

    cli = AlphaAnalyticsDataClient()
    etapes = [(ETAPE_HOME, None)] + ETAPES_PARAM

    def filtre_etape(valeur):
        if valeur is None:
            return FunnelFilterExpression(funnel_field_filter=FunnelFieldFilter(
                field_name="eventName",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                    value="home", case_sensitive=False)))
        return FunnelFilterExpression(funnel_field_filter=FunnelFieldFilter(
            field_name="eventName",
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.EXACT,
                value=valeur, case_sensitive=False)))

    steps = [FunnelStep(name=nom, filter_expression=filtre_etape(val))
             for nom, val in etapes]
    rep = cli.run_funnel_report(RunFunnelReportRequest(
        property=f"properties/{pid}",
        date_ranges=[DateRange(start_date=debut, end_date=fin)],
        funnel=Funnel(steps=steps),
    ))
    resultat = [{"step": r.dimension_values[0].value, "users": int(r.metric_values[0].value)}
               for r in rep.funnel_table.rows]
    if not resultat:
        raise ValueError("reponse vide")
    return resultat


def _dimension_valide(cli, pid, hote, debut, fin, nom_api):
    """Teste si une dimension personnalisee existe et renvoie des valeurs sur cet hote."""
    try:
        l = ga4._rapport(cli, pid, debut, fin, [nom_api], ["activeUsers"],
                         ga4._egal("hostName", hote))
        return bool(l)
    except Exception:
        return False


def _via_step_name(cli, pid, hote, debut, fin):
    """Piste B. Utilise la dimension personnalisee step_name, comme les
    explorations GA4 manuelles du projet."""
    dim_step = next((c for c in CANDIDATS_STEP_NAME
                     if _dimension_valide(cli, pid, hote, debut, fin, c)), None)
    if not dim_step:
        raise ValueError("aucune dimension step_name trouvee sur cette propriete")

    lignes = ga4._rapport(cli, pid, debut, fin, [dim_step], ["activeUsers"],
                          ga4._egal("hostName", hote))
    par_valeur = {v.strip().lower(): int(u) for v, u in lignes}

    trouves = []
    for nom, valeur_attendue in ETAPES_PARAM:
        u = par_valeur.get(valeur_attendue.lower())
        if u is None:
            continue
        trouves.append({"step": nom, "users": u})
    if len(trouves) < 3:
        raise ValueError(f"seulement {len(trouves)} etape(s) trouvee(s) via {dim_step}")

    # etape 1 : page_category si disponible, sinon mot-cle sur eventName
    entree = _entree_page_category(cli, pid, hote, debut, fin)
    if entree is None:
        entree = _entree_par_mot_cle(cli, pid, hote, debut, fin, MOTIFS_HOME)
    if entree is None:
        raise ValueError("etape d'entree introuvable")

    return [{"step": ETAPE_HOME, "users": entree}] + trouves


def _entree_page_category(cli, pid, hote, debut, fin):
    dim = next((c for c in CANDIDATS_PAGE_CATEGORY
               if _dimension_valide(cli, pid, hote, debut, fin, c)), None)
    if not dim:
        return None
    lignes = ga4._rapport(cli, pid, debut, fin, [dim], ["activeUsers"],
                          ga4._egal("hostName", hote))
    for v, u in lignes:
        if re.search(r"home\s*page", v, re.I):
            return int(u)
    return None


def _evenements_disponibles(cli, pid, hote, debut, fin):
    lignes = ga4._rapport(cli, pid, debut, fin, ["eventName"], ["activeUsers"],
                          ga4._egal("hostName", hote))
    return sorted(((n, int(u)) for n, u in lignes), key=lambda x: -x[1])


def _entree_par_mot_cle(cli, pid, hote, debut, fin, motifs):
    disponibles = _evenements_disponibles(cli, pid, hote, debut, fin)
    cands = [(n, u) for n, u in disponibles if _correspond(n, motifs)]
    return max((u for _, u in cands), default=None)


def _via_mot_cle(cli, pid, hote, debut, fin):
    """Piste C. Dernier recours : chaque etape identifiee par mot-cle sur eventName."""
    disponibles = _evenements_disponibles(cli, pid, hote, debut, fin)
    if not disponibles:
        raise ValueError("aucun evenement sur cet hote")

    trouves = []
    for nom_etape, motifs in MOTIFS_EVT.items():
        cands = [(n, u) for n, u in disponibles if _correspond(n, motifs)]
        if not cands:
            continue
        evt, u = max(cands, key=lambda x: x[1])
        l = ga4._rapport(cli, pid, debut, fin, [], ["activeUsers"],
                         ga4._egal("eventName", evt))
        trouves.append({"step": nom_etape, "users": int(l[0][0]) if l else 0})

    if len(trouves) < 3:
        raise ValueError(f"seulement {len(trouves)} etape(s) identifiee(s) "
                         "sur mot-cle : trop peu pour un funnel exploitable")
    trouves.sort(key=lambda x: -x["users"])
    return trouves


def funnel_mensuel(cli, pid, hote, debut, fin):
    """Retourne (steps, methode) ou (None, motif_echec)."""
    try:
        return _via_alpha(pid, hote, debut, fin), \
               "runFunnelReport (API alpha, entonnoir strict)"
    except Exception as e_alpha:
        pass
    try:
        return _via_step_name(cli, pid, hote, debut, fin), \
               "dimension step_name (repli fidele a l'exploration GA4)"
    except Exception as e_step:
        pass
    try:
        return _via_mot_cle(cli, pid, hote, debut, fin), \
               "repli par mot-cle sur eventName (approximation)"
    except Exception as e_mot:
        return None, f"alpha: {e_alpha} | step_name: {e_step} | mot-cle: {e_mot}"


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
