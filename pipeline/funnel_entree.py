"""Entonnoir par MODE DE SAISIE du véhicule : immatriculation / marque-modèle (vue « Tunnel de conversion », pastilles).

Signal : le paramètre `virtualpage_url` des évènements du formulaire. Parcours plaque : /form/plate/<étape> ; parcours marque / modèle : /form/brand/<étape>
(étapes version, mileage, contact, map ; l'évènement d'estimation tradein_request « price estimation » porte la même URL). Chaque étape est comptée en
utilisateurs actifs du mois, par parcours. Vérifié sur OPEL FR (sept. 2026) : estimations 3 448 (plaque) + 141 (marque / modèle) = 3 589, contre 3 581 au tunnel
général (step_name) ; part marque / modèle 4,3 % des estimations, 4,4 % des leads « Marque / modèle » du back-office.
L'accueil est commun aux deux parcours (avant le choix du mode) : les barres partent de « Version ».

Stockage : {"AAAA-MM": {"immat": [5 entiers], "marque_modele": [5 entiers]}}, étapes Version, Kilométrage, Coordonnées, Point de vente, Estimation.
2 requêtes GA4 par site pour toute la fenêtre (visiteurs uniques du mois, comme funnelSeg).
"""

import re

from pipeline import funnel, ga4

ETAPES = ["Version", "Kilométrage", "Coordonnées", "Point de vente", "Estimation"]
PAGES = {"version": 0, "mileage": 1, "contact": 2, "map": 3}
_RE_PAGE = re.compile(r"/form/(plate|brand)/(version|mileage|contact|map|offer)\b", re.I)
MODES = {"plate": "immat", "brand": "marque_modele"}
DIM = "customEvent:virtualpage_url"


def _ym(v):
    return f"{v[:4]}-{v[4:6]}"


def funnel_entree(cli, pid, hote, debut, fin):
    """{"AAAA-MM": {"immat": [5], "marque_modele": [5]}} ou {} si la propriété n'a pas le paramètre virtualpage_url / aucun parcours reconnu."""
    deb, fi = debut.isoformat(), fin.isoformat()
    mois = {}

    def ligne(ym, mode):
        return mois.setdefault(_ym(ym), {"immat": [0] * 5, "marque_modele": [0] * 5})[MODES[mode]]

    try:
        pages = ga4._rapport(cli, pid, deb, fi, ["yearMonth", DIM], ["activeUsers"], ga4._egal("hostName", hote))
        for ym, url, users in pages:
            m = _RE_PAGE.search(url or "")
            if m and m.group(2).lower() in PAGES:
                ligne(ym, m.group(1).lower())[PAGES[m.group(2).lower()]] += int(users)
        valeur_estimation = dict(funnel.ETAPES_PARAM)["Estimation"]
        for ym, url, users in ga4._rapport(
                cli, pid, deb, fi, ["yearMonth", DIM], ["activeUsers"],
                ga4._et(ga4._egal("hostName", hote), ga4._egal("eventName", funnel.EVENEMENT_ESTIMATION), ga4._egal("customEvent:step_name", valeur_estimation))):
            m = _RE_PAGE.search(url or "")
            if m:
                ligne(ym, m.group(1).lower())[4] += int(users)
    except Exception:
        return {}
    return {m: v for m, v in sorted(mois.items()) if v["immat"][0] + v["marque_modele"][0] > 0}
