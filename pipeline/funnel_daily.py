"""Conversion quotidienne (accueil -> estimation), pour la courbe du dashboard.

Meme definition que le funnel (funnel.py, piste step_name) : etape d'entree =
utilisateurs actifs de la page "home page", etape finale = utilisateurs
actifs de l'evenement tradein_request avec step_name "price estimation".
Seules ces deux etapes sont lues, jour par jour : 4 requetes GA4 par site
pour toute la fenetre (pas une par jour), donc cout negligeable.

Donnee 100 % GA4 (aucun lead back-office) : visible aussi des profils limites.
"""

import re
from datetime import date

from pipeline import funnel, ga4

FENETRE_JOURS = 120


def _iso(yyyymmdd):
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def conversion_quotidienne(cli, pid, hote, debut, fin):
    """{ "YYYY-MM-DD": [accueil, estimation], ... } ou {} si la propriete n'a
    pas les dimensions personnalisees du funnel."""
    deb, fi = debut.isoformat(), fin.isoformat()
    dim_step = next((c for c in funnel.CANDIDATS_STEP_NAME
                     if funnel._dimension_valide(cli, pid, hote, deb, fi, c)), None)
    dim_page = next((c for c in funnel.CANDIDATS_PAGE_CATEGORY
                     if funnel._dimension_valide(cli, pid, hote, deb, fi, c)), None)
    if not dim_step or not dim_page:
        return {}

    accueil = {}
    for j, valeur, users in ga4._rapport(cli, pid, deb, fi, ["date", dim_page], ["activeUsers"],
                                          ga4._egal("hostName", hote)):
        if re.search(r"home\s*page", valeur, re.I):
            accueil[_iso(j)] = accueil.get(_iso(j), 0) + int(users)

    valeur_estimation = dict(funnel.ETAPES_PARAM)["Estimation"]
    estimation = {}
    for j, users in ga4._rapport(
            cli, pid, deb, fi, ["date"], ["activeUsers"],
            ga4._et(ga4._egal("hostName", hote),
                    ga4._egal("eventName", funnel.EVENEMENT_ESTIMATION),
                    ga4._egal(dim_step, valeur_estimation))):
        estimation[_iso(j)] = int(users)

    return {j: [accueil[j], estimation.get(j, 0)] for j in sorted(accueil) if accueil[j] > 0}
