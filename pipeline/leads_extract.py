"""Extraction automatisee des leads depuis le back-office PSA Site Factory.

Remplace l'extraction manuelle (export CSV depuis l'interface web, analyse
a la main) par un appel au meme point d'API que celui utilise par le bouton
"Exporter" de l'interface : GET avec un token de compte (verifie stable sur
8 sites et plusieurs jours le 06/08/2026), une plage de dates et
l'identifiant du site.

N'exploite que les dimensions deja documentees au README (marque reprise,
carburant, source, code marketing, mode d'entree, projet d'achat) — jamais
les colonnes PII du CSV (telephone, commentaires, nom du concessionnaire,
etc.), qui ne sont ni lues ni publiees dans data/*.json.
"""

import csv
import io
import os
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date

BASE = "https://api-psa-site-factory.autobiz.com/v1/public/extract/extraction_report.csv"

# (siteId, settings) tel que releve dans l'interface d'extraction du
# back-office — aucune formule deductible entre les deux (deux sites
# differents peuvent partager le meme settings), chaque valeur a ete
# verifiee individuellement le 06/08/2026.
SITE_EXTRACT = {
    "OPEL FR":       (15, 2016),
    "OPEL PT":       (52, 2011),
    "CITROEN PT":    (94, 2013),
    "PEUGEOT PT":    (95, 2013),
    "DS PT":         (96, 2013),
    "FIAT PT":       (160, 2026),
    "JEEP PT":       (161, 2026),
    "ALFA ROMEO PT": (163, 2026),
}

# colonnes du CSV effectivement exploitees -- jamais les colonnes PII
# (PHONE, COMMENT, DEALER NAME, etc.), ni lues ni conservees.
COL_BRAND = "TRADE-IN BRAND"
COL_FUEL = "FUEL"
COL_PROJECT = "PURCHASE PROJECT"
COL_SOURCE = "SOURCE"
COL_CODE = "MARKETING_CODE"
COL_PLATE = "REGISTRATION-PLATE"
COL_DATE = "CREATION DATE"
COL_DOUBLON = "DOUBLON"
COL_TEST = "TEST"
COL_TEST_INTERNE = "TEST_INTERNE"
COL_MODE = "MODE"


def token():
    t = os.environ.get("LEADS_EXTRACT_TOKEN")
    if not t:
        raise RuntimeError("LEADS_EXTRACT_TOKEN non defini")
    return t


def _telecharge(site_nom, debut, fin):
    site_id, settings = SITE_EXTRACT[site_nom]
    params = {
        "extract": "1", "iframeLeads": "0",
        "dateBegin": debut, "dateEnd": fin,
        "siteId": str(site_id), "settings": str(settings),
        "token": token(),
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    texte = data.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def _valide(ligne):
    """Memes regles que celles documentees au README : hors doublons, hors
    tests, uniquement les leads de production."""
    return (ligne.get(COL_DOUBLON) == "NO"
            and ligne.get(COL_TEST) == "NO"
            and ligne.get(COL_TEST_INTERNE) == "NO"
            and ligne.get(COL_MODE) == "MODE_PRODUCTION")


def _top(compteur, limite=20):
    return [[nom, n] for nom, n in compteur.most_common(limite) if nom]


def bloc_leads_mois(site_nom, mois, jours_du_mois, jours_reels=None):
    """Construit le bloc leads[mois] pour un site, au meme format que celui
    jusqu'ici maintenu a la main (total/daily/brand/fuel/entry/project/
    source/code). Leve une exception si l'extraction echoue — a
    l'appelant de degrader proprement plutot que de publier un mois
    tronque a la place du precedent sans le signaler.

    jours_reels borne la plage interrogee aux jours deja ecoules (mois en
    cours) : au-dela, ce ne sont pas des jours a zero lead mais des jours
    qui n'ont pas encore eu lieu — meme logique que le reste du pipeline,
    jamais 0 la ou c'est « pas encore connu »."""
    bornes = jours_reels if jours_reels is not None else jours_du_mois
    debut = f"{mois}-01"
    fin = f"{mois}-{max(1, bornes):02d}"
    lignes = [l for l in _telecharge(site_nom, debut, fin) if _valide(l)] if bornes > 0 else []

    daily = [0] * bornes + [None] * (jours_du_mois - bornes)
    brand, fuel, project, source, code = (Counter() for _ in range(5))
    entree = {"Avec immatriculation": 0, "Marque / modele": 0}

    for l in lignes:
        d = (l.get(COL_DATE) or "")[:10]
        try:
            jour = date.fromisoformat(d).day
            if 1 <= jour <= bornes:
                daily[jour - 1] += 1
        except ValueError:
            pass
        if l.get(COL_BRAND):
            brand[l[COL_BRAND]] += 1
        if l.get(COL_FUEL):
            fuel[l[COL_FUEL]] += 1
        if l.get(COL_PROJECT):
            project[l[COL_PROJECT]] += 1
        if l.get(COL_SOURCE):
            source[l[COL_SOURCE]] += 1
        if l.get(COL_CODE):
            code[l[COL_CODE]] += 1
        if l.get(COL_PLATE) == "YES":
            entree["Avec immatriculation"] += 1
        elif l.get(COL_PLATE) == "NO":
            entree["Marque / modele"] += 1

    return {
        "total": len(lignes), "daily": daily,
        "brand": _top(brand), "fuel": _top(fuel),
        "entry": entree, "project": _top(project),
        "source": _top(source), "code": _top(code),
    }
