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
from collections import Counter, defaultdict
from datetime import date

BASE = "https://api-psa-site-factory.autobiz.com/v1/public/extract/extraction_report.csv"

# [(siteId, settings), ...] tel que releve dans l'interface d'extraction du
# back-office — aucune formule deductible entre les deux (deux sites
# differents peuvent partager le meme settings). La Belgique publie un
# site distinct par langue (.fr et .nl) sous un seul nom de domaine cote
# GA4 : les deux siteId sont donc additionnes pour retrouver le meme
# perimetre que le site "<MARQUE> BE" du pipeline GA4. Chaque valeur a ete
# identifiee le 07-08/08/2026 en interrogeant l'API d'extraction elle-meme
# (colonnes COUNTRY / SITE NAME du CSV), jamais devinee depuis le
# regroupement par marque fourni.
SITE_EXTRACT = {
    "OPEL FR":       [(15, 2016)],
    "OPEL PT":       [(52, 2011)],
    "CITROEN PT":    [(94, 2013)],
    "PEUGEOT PT":    [(95, 2013)],
    "DS PT":         [(96, 2013)],
    "FIAT PT":       [(160, 2026)],
    "JEEP PT":       [(161, 2026)],
    "ALFA ROMEO PT": [(163, 2026)],

    "ABARTH BE":     [(134, 2026), (136, 2026)],
    "ABARTH ES":     [(154, 2026)],
    "ABARTH IT":     [(170, 2026)],
    "ABARTH LU":     [(135, 2026)],
    "ABARTH PT":     [(162, 2026)],

    "ALFA ROMEO BE": [(130, 2026), (132, 2026)],
    "ALFA ROMEO DE": [(220, 2026)],  # corrige le 10/08/2026 : 211 renvoyait 0 ligne meme sur 500j (mauvais id) ; 220 = ALFA_ROMEO.GERMANY.de.3 (verifie via _diag_siteid.py)
    "ALFA ROMEO ES": [(157, 2026)],
    "ALFA ROMEO FR": [(143, 2026)],
    "ALFA ROMEO IT": [(168, 2026)],
    "ALFA ROMEO LU": [(131, 2026)],
    "ALFA ROMEO PL": [(150, 2026)],

    "CITROEN AT":    [(44, 2015)],
    "CITROEN BE":    [(73, 2016), (75, 2016)],
    "CITROEN DE":    [(87, 2016)],
    "CITROEN ES":    [(33, 2014)],
    "CITROEN FR":    [(2, 2016)],
    "CITROEN IT":    [(72, 2014)],
    "CITROEN LU":    [(76, 2016)],
    "CITROEN PL":    [(148, 2016)],

    "DS BE":         [(82, 2011), (83, 2011)],
    "DS DE":         [(49, 2016)],
    "DS ES":         [(35, 2011)],
    "DS FR":         [(5, 2016)],
    "DS GB":         [(173, 2016)],
    "DS IT":         [(77, 2014)],
    "DS LU":         [(84, 2011)],

    # pas d'entree "fr" fournie pour la Belgique cote FIAT (seule .nl a ete
    # communiquee) : perimetre incomplet en l'etat, a corriger si l'ID
    # manquant est retrouve.
    "FIAT BE":       [(121, 2026)],
    "FIAT ES":       [(155, 2026)],
    "FIAT FR":       [(137, 2026)],
    "FIAT IT":       [(166, 2026)],
    "FIAT LU":       [(124, 2026)],
    # FIAT PL (siteId 149) volontairement ecarte : aucun Site() GA4 en face.

    "JEEP BE":       [(127, 2026), (129, 2026)],
    "JEEP ES":       [(156, 2026)],
    "JEEP FR":       [(138, 2026)],
    "JEEP IT":       [(167, 2026)],
    "JEEP LU":       [(128, 2026)],
    "JEEP PL":       [(152, 2026)],

    # LANCIA BE : deux siteId (fr + nl), meme convention que les autres
    # marques belges multilingues ci-dessus.
    "LANCIA BE":     [(243, 2026), (244, 2026)],
    "LANCIA FR":     [(217, 2026)],
    "LANCIA IT":     [(165, 2026)],
    # siteId 245 (LANCIA.BELGIUM.fr.LUXEMBOURG, verifie via _diag_siteid.py
    # le 10/08/2026) volontairement ecarte : aucun Site() GA4 "LANCIA LU"
    # en face dans pipeline/sites.py -- meme situation que Leapmotor LU
    # plus haut dans l'historique, pas ajoutable sans onboarding GA4 prealable.

    "OPEL AT":       [(43, 2015)],
    "OPEL BE":       [(63, 2016), (64, 2016)],
    "OPEL DE":       [(88, 2016)],
    "OPEL ES":       [(46, 2014)],
    "OPEL IT":       [(50, 2014)],
    "OPEL LU":       [(89, 2016)],
    "OPEL PL":       [(153, 2016)],

    "PEUGEOT AT":    [(45, 2015)],
    "PEUGEOT BE":    [(91, 2011), (92, 2011)],
    "PEUGEOT DE":    [(85, 2016)],
    "PEUGEOT ES":    [(21, 2014)],
    "PEUGEOT FR":    [(4, 2016)],
    "PEUGEOT IT":    [(51, 2014)],
    "PEUGEOT LU":    [(93, 2011)],
    "PEUGEOT PL":    [(147, 2026)],

    # Spoticar + Stellantis&You, identifies le 10/08/2026 avec
    # pipeline/_diag_siteid.py (colonnes COUNTRY / SITE NAME du CSV,
    # meme methode que le reste de ce dictionnaire). Stellantis&You a un
    # siteId supplementaire fourni (114, cense etre la Belgique
    # neerlandophone ou le Luxembourg) qui n'a produit aucune ligne meme
    # sur 580 jours -- ecarte plutot que suppose, aucun marche STELLANTIS
    # &YOU LU dans notre perimetre (voir pipeline/sites.py).
    "SPOTICAR AT":         [(106, 2026)],
    "SPOTICAR BE":         [(66, 2026), (68, 2026)],
    "SPOTICAR DE":         [(81, 2026)],
    "SPOTICAR ES":         [(22, 2026)],
    "SPOTICAR FR":         [(1, 2026)],
    "SPOTICAR IT":         [(71, 2014)],
    "SPOTICAR LU":         [(69, 2026)],
    "SPOTICAR PL":         [(146, 2026)],
    "SPOTICAR PT":         [(70, 2026)],
    "SPOTICAR UK":         [(104, 2026)],

    "STELLANTIS &YOU AT":  [(145, 2026)],
    "STELLANTIS &YOU BE":  [(112, 2026), (113, 2026)],
    "STELLANTIS &YOU DE":  [(111, 2026)],
    "STELLANTIS &YOU ES":  [(110, 2026)],
    "STELLANTIS &YOU FR":  [(109, 2026)],
    "STELLANTIS &YOU IT":  [(115, 2014)],
    "STELLANTIS &YOU PL":  [(139, 2026)],
    "STELLANTIS &YOU PT":  [(116, 2026)],
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
# appareil (mobile / desktop / tablette). "BP" est la lettre de colonne
# Excel vue dans l'export, pas le nom du champ — verifie le 07/08/2026 sur un
# export reel OPEL FR : l'en-tete CSV est "DEVICE", valeurs "mobile"/"desktop"
# en minuscules. Le pipeline transporte le libelle brut tel quel malgre tout ;
# le regroupement (mobile/desktop/autres) se fait cote dashboard, generique,
# sans supposer la casse exacte.
COL_DEVICE = "DEVICE"


def token():
    t = os.environ.get("LEADS_EXTRACT_TOKEN")
    if not t:
        raise RuntimeError("LEADS_EXTRACT_TOKEN non defini")
    return t


def _telecharge_un(site_id, settings, debut, fin):
    params = {
        "extract": "1", "iframeLeads": "0",
        "dateBegin": debut, "dateEnd": fin,
        "siteId": str(site_id), "settings": str(settings),
        "token": token(),
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    texte = data.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def _telecharge(site_nom, debut, fin):
    """Concatene les lignes de tous les siteId du site (plusieurs pour la
    Belgique : .fr et .nl partagent un seul site GA4 mais deux sites
    back-office distincts)."""
    lignes = []
    for site_id, settings in SITE_EXTRACT[site_nom]:
        lignes.extend(_telecharge_un(site_id, settings, debut, fin))
    return lignes


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
    cours) : le tableau daily n'a que ces jours-la, jamais complete a la
    longueur du mois — meme convention que l'ancien processus manuel
    (« leads.daily a 30 valeurs pour un mois de 31 jours »)."""
    bornes = jours_reels if jours_reels is not None else jours_du_mois
    debut = f"{mois}-01"
    fin = f"{mois}-{max(1, bornes):02d}"
    lignes = [l for l in _telecharge(site_nom, debut, fin) if _valide(l)] if bornes > 0 else []

    daily = [0] * bornes
    brand, fuel, project, source, code, device = (Counter() for _ in range(6))
    entree = {"Avec immatriculation": 0, "Marque / modele": 0}
    # comptage jour par jour et par appareil, meme principe que `daily` mais
    # une serie par valeur trouvee dans DEVICE — sert au rapport hebdomadaire V2
    # (pipeline/v2_report.py) a isoler la part mobile/desktop sur une plage
    # de dates arbitraire, pas seulement sur le mois entier.
    daily_device = defaultdict(lambda: [0] * bornes)

    for l in lignes:
        d = (l.get(COL_DATE) or "")[:10]
        jour = None
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
        if l.get(COL_DEVICE):
            device[l[COL_DEVICE]] += 1
            if jour is not None and 1 <= jour <= bornes:
                daily_device[l[COL_DEVICE]][jour - 1] += 1
        if l.get(COL_PLATE) == "YES":
            entree["Avec immatriculation"] += 1
        elif l.get(COL_PLATE) == "NO":
            entree["Marque / modele"] += 1

    return {
        "total": len(lignes), "daily": daily,
        "brand": _top(brand), "fuel": _top(fuel),
        "entry": entree, "project": _top(project),
        "source": _top(source), "code": _top(code),
        "device": _top(device), "dailyDevice": dict(daily_device),
    }
