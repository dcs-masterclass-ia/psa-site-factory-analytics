"""Funnel quotidien : source unique de tous les taux de conversion du dashboard.

Une ligne par jour : [accueil, version, kilometrage, coordonnees, point de
vente, estimation], en utilisateurs actifs, avec exactement les definitions du
funnel (funnel.py, piste step_name) :
  - accueil    = page_category "home page"
  - 4 etapes   = parametre step_name (version, mileage, contact details,
                 dealer choice)
  - estimation = evenement tradein_request avec step_name "price estimation"

Le dashboard somme ces jours sur la periode choisie (jours exacts, meme base
que les sessions) : taux de conversion = estimation / accueil, partout.
5 requetes GA4 par site pour toute la fenetre (pas une par jour). Donnee 100 %
GA4 (aucun lead back-office) : visible aussi des profils limites.
"""

import re

from pipeline import funnel, ga4

FENETRE_JOURS = 180
ETAPES = ["Page d'accueil", "Version", "Kilométrage", "Coordonnées", "Point de vente", "Estimation"]


def _iso(yyyymmdd):
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def funnel_quotidien(cli, pid, hote, debut, fin):
    """{ "YYYY-MM-DD": [6 entiers], ... } ou {} si la propriete n'a pas les
    dimensions personnalisees du funnel."""
    deb, fi = debut.isoformat(), fin.isoformat()
    dim_step = next((c for c in funnel.CANDIDATS_STEP_NAME
                     if funnel._dimension_valide(cli, pid, hote, deb, fi, c)), None)
    dim_page = next((c for c in funnel.CANDIDATS_PAGE_CATEGORY
                     if funnel._dimension_valide(cli, pid, hote, deb, fi, c)), None)
    if not dim_step or not dim_page:
        return {}

    jours = {}

    def ligne(j):
        return jours.setdefault(_iso(j), [0] * len(ETAPES))

    for j, valeur, users in ga4._rapport(cli, pid, deb, fi, ["date", dim_page], ["activeUsers"],
                                          ga4._egal("hostName", hote)):
        if re.search(r"home\s*page", valeur, re.I):
            ligne(j)[0] += int(users)

    attendu = {v.lower(): i + 1 for i, (_, v) in enumerate(funnel.ETAPES_PARAM[:-1])}
    for j, valeur, users in ga4._rapport(cli, pid, deb, fi, ["date", dim_step], ["activeUsers"],
                                          ga4._egal("hostName", hote)):
        i = attendu.get(valeur.strip().lower())
        if i is not None:
            ligne(j)[i] += int(users)

    valeur_estimation = dict(funnel.ETAPES_PARAM)["Estimation"]
    for j, users in ga4._rapport(
            cli, pid, deb, fi, ["date"], ["activeUsers"],
            ga4._et(ga4._egal("hostName", hote),
                    ga4._egal("eventName", funnel.EVENEMENT_ESTIMATION),
                    ga4._egal(dim_step, valeur_estimation))):
        ligne(j)[len(ETAPES) - 1] += int(users)

    return {j: v for j, v in sorted(jours.items()) if v[0] > 0}
