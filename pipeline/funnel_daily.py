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


def _ym(v):
    return f"{v[:4]}-{v[4:6]}"


def funnel_segments(cli, pid, hote, debut, fin):
    """Entonnoir MENSUEL par appareil et par canal d'acquisition : mêmes définitions que funnel_quotidien (6 étapes en utilisateurs actifs),
    mais ventilées. {"device": {"AAAA-MM": {"mobile": [6 entiers], ...}}, "canal": {...}} ou {} si le funnel n'est pas mesurable.
    6 requêtes GA4 par site pour toute la fenêtre (3 étapes de requête × 2 découpages)."""
    deb, fi = debut.isoformat(), fin.isoformat()
    dim_step = next((c for c in funnel.CANDIDATS_STEP_NAME if funnel._dimension_valide(cli, pid, hote, deb, fi, c)), None)
    dim_page = next((c for c in funnel.CANDIDATS_PAGE_CATEGORY if funnel._dimension_valide(cli, pid, hote, deb, fi, c)), None)
    if not dim_step or not dim_page:
        return {}
    attendu = {v.lower(): i + 1 for i, (_, v) in enumerate(funnel.ETAPES_PARAM[:-1])}
    valeur_estimation = dict(funnel.ETAPES_PARAM)["Estimation"]
    out = {}
    for nom, dim in (("device", "deviceCategory"), ("canal", "sessionDefaultChannelGroup")):
        mois = {}

        def ligne(ym, seg):
            return mois.setdefault(_ym(ym), {}).setdefault(seg or "(inconnu)", [0] * len(ETAPES))

        for ym, seg, valeur, users in ga4._rapport(cli, pid, deb, fi, ["yearMonth", dim, dim_page], ["activeUsers"], ga4._egal("hostName", hote)):
            if re.search(r"home\s*page", valeur, re.I):
                ligne(ym, seg)[0] += int(users)
        for ym, seg, valeur, users in ga4._rapport(cli, pid, deb, fi, ["yearMonth", dim, dim_step], ["activeUsers"], ga4._egal("hostName", hote)):
            i = attendu.get(valeur.strip().lower())
            if i is not None:
                ligne(ym, seg)[i] += int(users)
        for ym, seg, users in ga4._rapport(
                cli, pid, deb, fi, ["yearMonth", dim], ["activeUsers"],
                ga4._et(ga4._egal("hostName", hote), ga4._egal("eventName", funnel.EVENEMENT_ESTIMATION), ga4._egal(dim_step, valeur_estimation))):
            ligne(ym, seg)[len(ETAPES) - 1] += int(users)
        # on ne garde que les segments qui ont des visiteurs à l'accueil (le reste est du bruit)
        out[nom] = {m: {seg: v for seg, v in segs.items() if v[0] > 0} for m, segs in sorted(mois.items())}
        out[nom] = {m: segs for m, segs in out[nom].items() if segs}
    return out
