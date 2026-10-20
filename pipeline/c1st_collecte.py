"""Collecte mensuelle C1ST (Salesforce CRM Analytics) : totaux par marché, mois et marque -> data/c1st/kpi.json (repo de données).

Authentification SANS navigateur : OAuth 2.0 « JWT bearer » d'une Connected App (compte de service en lecture). Secrets attendus (GitHub Actions) :
  C1ST_CLIENT_ID    clé du consommateur de la Connected App
  C1ST_USERNAME     nom d'utilisateur du compte de service (celui qui a pré-autorisé l'app)
  C1ST_PRIVATE_KEY  clé privée RSA (PEM) dont le certificat est déposé dans la Connected App
  C1ST_LOGIN_URL    (facultatif) adresse du point d'authentification : https://login.salesforce.com (défaut) ou le domaine de l'organisation (https://psa-customerfirst.my.salesforce.com)
  C1ST_AUDIENCE     (facultatif) audience du jeton JWT, https://login.salesforce.com par défaut

Ce que collecte le module (mêmes définitions que celles validées contre les graphiques C1ST, voir CLAUDE.md « C1ST ») :
  - leads / suivi : leads envoyés, contactés, traités, premier appel, opportunités (jeu « lead »)
  - clients uniques, devis (jeu « dealer ») et commandes NSC (jeu « SUB ») rattachées au lead entre 1 et 90 jours après sa création
  - périmètre : type 1, activité VN, campagne Autobiz, nature 47 (xP) ou A68 (xF) ; Spoticar (SP) : activité VO, nature « 15.Buyback request »
Seuls des totaux sont écrits : aucune donnée personnelle.

Usage : python -m pipeline.c1st_collecte [--depuis AAAA-MM] [--derniers N] [--courant] [--pays FR,BE,...] [--sortie data/c1st/kpi.json]
Par défaut : les 4 derniers mois terminés (les commandes sont rattachées jusqu'à 90 jours après le lead : les mois récents bougent encore).
--courant (collecte quotidienne) : le mois en cours + les 3 précédents ; le mois de `collecte.date` est PARTIEL, les consommateurs ne l'utilisent jamais comme un mois complet.
Codes de sortie : 0 = ok, 1 = au moins une requête a échoué (ce qui a réussi est écrit), 3 = secrets non configurés.
"""

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "data" / "c1st" / "kpi.json"
API = "v68.0"

DATASETS = {"leads": "0Fb0O000000XrKuSAK", "dealer": "0Fba2000000JM6TCAW", "sub": "0Fba20000014ZhlCAE"}
PAYS = ["FR", "BE", "ES", "PT", "IT", "DE", "PL", "AT", "GB"]          # marchés où C1ST contient des leads Autobiz (BE comprend le Luxembourg) ; suivi des concessionnaires quasi nul en DE / AT
MARQUES_STD = ["AC", "AH", "AP", "AR", "DS", "FO", "FT", "JE", "LA", "OP"]
XP = ["AC", "AP", "DS", "OP"]
# Avant 2026, les leads Autobiz xP se reconnaissent à la « Level 1 (Source Detail) » (315 / 515 / 311 / 511), toutes natures, pas à la campagne (identifiants numériques) ; xF : nature A68 + campagne Autobiz.
SOURCES_XP_AVANT_2026 = ["315.Brand Trade-in/ Reprise", "515.Brand by back/ Reprise (Mobile)", "311.PSA RETAIL", "511.PSA RETAIL (Mobile)"]
PERIMETRES = {
    "std": {"marques": MARQUES_STD, "natures": ["A68.Trade-In Value", "47.VO - VN Trade-in Operation"], "activite": "VN"},
    "sp": {"marques": ["SP"], "natures": ["15.Buyback request"], "activite": "VO"},
}


def _liste(valeurs):
    return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in valeurs) + "]"


def _periode(y, m, m0=None):
    """Plage de dates : le mois m, ou (m0 donné) du mois m0 au mois m inclus de la même année."""
    import calendar
    return f"dateRange([{y},{m0 or m},1],[{y},{m},{calendar.monthrange(y, m)[1]}])"


# Marchés dont le tableau C1ST de référence compte les xP 2025 par la campagne Autobiz seule (et non par la source 315/515/311/511, validée sur la France uniquement).
# Espagne vérifiée le 2026-10-20 : campagne seule = 9 902 leads xP 2025 contre 9 956 dans le tableau (la règle par source en donnait 12 277). Les autres marchés restent à valider contre leur tableau.
PAYS_XP_CAMPAGNE_AVANT_2026 = ("ES",)
PAYS_CLIENTS_UNIQUES = ("ES",)      # marchés dont le tableau de référence compte des clients uniques (et non des leads) : voir saql_clients_cumul


def _origine(p, y, perim, pays=None):
    """Origine Autobiz du lead : 2026 -> campagne (Provider) AUTOBIZ / Autobiz ; avant 2026 -> pour les marques xP la source 315/515/311/511 (France et marchés non validés), pour xF la campagne Autobiz ;
    marchés de `PAYS_XP_CAMPAGNE_AVANT_2026` : la campagne Autobiz aussi pour les xP."""
    camp = f"'{p}CampaignIDUSER__c' in [\"AUTOBIZ\", \"Autobiz\"]"
    if y >= 2026 or perim is not PERIMETRES["std"] or pays in PAYS_XP_CAMPAGNE_AVANT_2026:
        return camp
    return f"(('{p}PSABrand__c' in {_liste(XP)} && '{p}LeadSourceLabelized' in {_liste(SOURCES_XP_AVANT_2026)}) || ('{p}PSABrand__c' not in {_liste(XP)} && {camp}))"


# Belgique avant 2026, marques xP : la référence client (decks BELUX) écarte les demandes de devis et d'information (sources 311 surtout) ; vérifié à l'unité sur T3-2025
# (Peugeot 1 753, Citroën 1 084, DS 50, Opel 555). La France, validée sans filtre de nature contre son propre tableau, n'est pas concernée.
NATURES_EXCLUES_BE_XP_AVANT_2026 = ["2.Quote request", "4.Information request"]


def _nature(p, y, perim, pays=None):
    """Nature : aucun filtre pour les marques standard (la nature 47 / A68 écartait 5 à 15 % des leads Autobiz), sauf Belgique avant 2026 sur les marques xP (voir ci-dessus) ;
    Spoticar : 15.Buyback request."""
    nat = f"'{p}NatureLabelized' in {_liste(perim['natures'])}"
    if perim is not PERIMETRES["std"]:
        return nat
    if pays == "BE" and y < 2026:
        return f"('{p}PSABrand__c' not in {_liste(XP)} || '{p}NatureLabelized' not in {_liste(NATURES_EXCLUES_BE_XP_AVANT_2026)})"
    return None      # autres cas : aucun filtre de nature (origine Autobiz = campagne / source ; validé à l'unité sur le tableau « NC Sales Conversion » 2025 et 2026)


def filtres(v, pays, y, m, perim, prefixe="", m0=None):
    """Bloc de filtres commun (comme le dashboard « Leads Funnel »). prefixe = « ACCLead. » pour les jeux dealer et SUB."""
    p = prefixe
    type_client = "CustomerType__c" if p else "CustomerTypeLabelized"
    return "\n".join([
        f"{v} = filter {v} by '{p}PSABrand__c' in {_liste(perim['marques'])};",
        f"{v} = filter {v} by '{p}LeadCountry__c' in {_liste([pays])};",
        f"{v} = filter {v} by '{p}LeadTypeLabelized' in [\"1-Leads (urgent)\"];",
        f"{v} = filter {v} by '{p}{type_client}' in [\"B2B\", \"B2C\"];",
        f"{v} = filter {v} by '{p}CentralLocal_lead' in [\"BRAND\", \"Central\"];",
        f"{v} = filter {v} by '{p}Activity__c' in {_liste([perim['activite']])};",
        f"{v} = filter {v} by {_origine(p, y, perim, pays)};",
        *([f"{v} = filter {v} by {_nature(p, y, perim, pays)};"] if _nature(p, y, perim, pays) else []),
        f"{v} = filter {v} by ('{p}LeadQualificationResult__c' not in [\"Black list filtering\"] || '{p}LeadQualificationResult__c' is null);",
        f"{v} = filter {v} by '{p}Test_JustDealer2' in [\"No\"];",
        f"{v} = filter {v} by date('{p}CreatedDate_Year', '{p}CreatedDate_Month', '{p}CreatedDate_Day') in [{_periode(y, m, m0)}];",
    ])


def saql_leads(ds, pays, y, m, perim):
    return f"""q = load "{ds}";
{filtres("q", pays, y, m, perim)}
stn = filter q by 'SendToNetwork' == "Yes";
con = filter stn by ('ContactedOnTime__c' == "OnTime" || 'ContactedOnTime__c' == "OverTime");
conT = filter stn by 'ContactedOnTime__c' == "OnTime";
fca = filter stn by 'FreespeeTreatmentTimeRespect__c' == "On Time";
trt = filter stn by ('TreatedOnTime__c' == "OnTime" || 'TreatedOnTime__c' == "OverTime");
trtT = filter stn by 'TreatedOnTime__c' == "OnTime";
opp = filter q by 'LeadWithOpp' == "YES";
r = group q by 'PSABrand__c' full, stn by 'PSABrand__c' full, con by 'PSABrand__c' full, conT by 'PSABrand__c' full, fca by 'PSABrand__c' full, trt by 'PSABrand__c' full, trtT by 'PSABrand__c' full, opp by 'PSABrand__c';
r = foreach r generate coalesce(q.'PSABrand__c', stn.'PSABrand__c', opp.'PSABrand__c') as 'marque', unique(q.'Lead_Id') as 'leads', unique(stn.'Lead_Id') as 'envoyes', unique(stn.'LeadUniqueCust') as 'clients_envoyes', unique(con.'LeadUniqueCust') as 'contactes', unique(conT.'LeadUniqueCust') as 'contactes_delai', unique(fca.'LeadUniqueCust') as 'premier_appel_delai', unique(trt.'LeadUniqueCust') as 'traites', unique(trtT.'LeadUniqueCust') as 'traites_delai', unique(opp.'LeadUniqueCust') as 'avec_opp';
r = limit r 100;"""


def saql_statuts(ds, pays, y, m, perim):
    """Leads par statut (« Leads Generated by Status » du rapport Leads Funnel) : champ Status_ProcessLogic (« 5.Qualified », « 4.Nurturing »…)."""
    return f"""q = load "{ds}";
{filtres("q", pays, y, m, perim)}
r = group q by ('PSABrand__c', 'Status_ProcessLogic');
r = foreach r generate 'PSABrand__c' as 'marque', 'Status_ProcessLogic' as 'statut', unique('Lead_Id') as 'leads';
r = limit r 500;"""


def saql_commandes(ds, pays, y, m, perim):
    return f"""dea = load "{ds}";
{filtres("dea", pays, y, m, perim, "ACCLead.")}
quo = filter dea by 'HasQuotes' == "YES";
ord = filter dea by 'LeadConversionTimeMailPhone' >= 1 && 'LeadConversionTimeMailPhone' <= 90;
r = group dea by 'ACCLead.PSABrand__c' full, quo by 'ACCLead.PSABrand__c' full, ord by 'ACCLead.PSABrand__c';
r = foreach r generate coalesce(dea.'ACCLead.PSABrand__c', quo.'ACCLead.PSABrand__c', ord.'ACCLead.PSABrand__c') as 'marque', unique(dea.'ACCLead.LeadUniqueCust') as 'clients_uniques', unique(quo.'ACCLead.LeadUniqueCust') as 'avec_devis', unique(ord.'OrderIdwMailPhone') as 'commandes';
r = limit r 100;"""


def saql_clients_cumul(ds, pays, y, m, perim):
    """Clients uniques (LeadUniqueCust) par marque de janvier au mois m : le « # Leads Generated » du tableau C1ST « NC Sales Conversion » de l'Espagne (vérifié le 2026-10-20 sur Jan.-Sep. 2026 :
    Peugeot 15 608 contre 15 598, Citroën 13 014 contre 12 995, Abarth 54 et Fiat Pro 244 à l'unité). Un client qui revient dans deux mois n'est compté qu'une fois : pas la somme des mois."""
    return f"""q = load "{ds}";
{filtres("q", pays, y, m, perim, "", 1)}
r = group q by 'PSABrand__c';
r = foreach r generate 'PSABrand__c' as 'marque', unique('LeadUniqueCust') as 'clients';
r = limit r 100;"""


def saql_nsc(ds, pays, y, m, perim, m0=None):
    """Commandes NSC uniques par marque ; m0 = 1 : sur toute la période de janvier au mois m (un même numéro de commande n'est compté qu'une fois, contrairement à la somme des mois)."""
    return f"""q = load "{ds}";
{filtres("q", pays, y, m, perim, "ACCLead.", m0)}
ord = filter q by 'LeadConversionTimeMailPhone' >= 1 && 'LeadConversionTimeMailPhone' <= 90;
r = group ord by 'ACCLead.PSABrand__c';
r = foreach r generate 'ACCLead.PSABrand__c' as 'marque', unique('OrderIdwMailPhone') as 'commandes_nsc';
r = limit r 100;"""


# ------------------------------------------------------------------ authentification et appels
class NonConfigure(Exception):
    pass


def jeton(env=None):
    """(access_token, instance_url) par OAuth JWT bearer. Lève NonConfigure si les secrets manquent."""
    env = os.environ if env is None else env
    manquants = [k for k in ("C1ST_CLIENT_ID", "C1ST_USERNAME", "C1ST_PRIVATE_KEY") if not env.get(k)]
    if manquants:
        raise NonConfigure("secrets C1ST absents : " + ", ".join(manquants))
    import httpx
    import jwt
    login = (env.get("C1ST_LOGIN_URL") or "https://login.salesforce.com").rstrip("/")
    audience = (env.get("C1ST_AUDIENCE") or "https://login.salesforce.com").rstrip("/")
    assertion = jwt.encode({"iss": env["C1ST_CLIENT_ID"], "sub": env["C1ST_USERNAME"], "aud": audience, "exp": int(time.time()) + 180},
                           env["C1ST_PRIVATE_KEY"].replace("\\n", "\n"), algorithm="RS256")
    r = httpx.post(login + "/services/oauth2/token", data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"authentification C1ST refusée ({r.status_code}) : {r.text[:200]}")
    j = r.json()
    return j["access_token"], j["instance_url"].rstrip("/")


class Client:
    def __init__(self, token, instance):
        import httpx
        self.http = httpx.Client(base_url=f"{instance}/services/data/{API}", headers={"Authorization": f"Bearer {token}"}, timeout=120)
        self._versions = {}

    def version(self, nom):
        """Identifiant « jeu/version » courant : change à chaque rafraîchissement nocturne du jeu."""
        if nom not in self._versions:
            r = self.http.get(f"/wave/datasets/{DATASETS[nom]}")
            r.raise_for_status()
            self._versions[nom] = f"{DATASETS[nom]}/{r.json()['currentVersionId']}"
        return self._versions[nom]

    def requete(self, saql, essais=3):
        for i in range(essais):
            r = self.http.post("/wave/query", json={"query": saql})
            if r.status_code == 200:
                return r.json().get("results", {}).get("records", [])
            if r.status_code in (401, 403):
                raise RuntimeError(f"accès C1ST refusé ({r.status_code}) : {r.text[:200]}")
            time.sleep(3 * (i + 1))
        raise RuntimeError(f"requête C1ST en échec ({r.status_code}) : {r.text[:200]}")


# ------------------------------------------------------------------ mois à collecter, fusion
def mois_a_collecter(aujourdhui, depuis=None, derniers=4, courant=False):
    """Liste de (année, mois) : de « depuis » au dernier mois TERMINÉ, ou les `derniers` mois terminés.
    courant=True : le mois en cours (partiel) est le dernier de la liste et compte parmi les `derniers`."""
    y, m = aujourdhui.year, aujourdhui.month - (0 if courant else 1)
    if m == 0:
        y, m = y - 1, 12
    fin = (y, m)
    if depuis:
        dy, dm = (int(x) for x in depuis.split("-"))
    else:
        dy, dm = y, m - derniers + 1
        while dm <= 0:
            dy, dm = dy - 1, dm + 12
    out = []
    while (dy, dm) <= fin:
        out.append((dy, dm))
        dm += 1
        if dm > 12:
            dy, dm = dy + 1, 1
    return out


def collecte_mois(client, pays, y, m):
    """{leads, commandes, nsc} d'un marché et d'un mois (marques standard + Spoticar)."""
    std, sp = PERIMETRES["std"], PERIMETRES["sp"]
    leads = client.requete(saql_leads(client.version("leads"), pays, y, m, std)) + client.requete(saql_leads(client.version("leads"), pays, y, m, sp))
    commandes = client.requete(saql_commandes(client.version("dealer"), pays, y, m, std)) + client.requete(saql_commandes(client.version("dealer"), pays, y, m, sp))
    nsc = client.requete(saql_nsc(client.version("sub"), pays, y, m, std))
    statuts = client.requete(saql_statuts(client.version("leads"), pays, y, m, std))
    nsc_cumul = client.requete(saql_nsc(client.version("sub"), pays, y, m, std, m0=1))      # commandes uniques de janvier au mois m (tableau « NC Sales Conversion » cumulé)
    res = {"leads": leads, "commandes": commandes, "nsc": nsc, "statuts": statuts, "nsc_cumul": nsc_cumul}
    if pays in PAYS_CLIENTS_UNIQUES:
        res["clients_cumul"] = client.requete(saql_clients_cumul(client.version("leads"), pays, y, m, std))
    return res


def fusionne(existant, pays, cle_mois, nouveau):
    """Remplace le mois par la nouvelle collecte ; refuse d'écraser un mois non vide par un résultat vide (accident d'API)."""
    donnees = existant.setdefault("donnees", {}).setdefault(pays, {})
    ancien = donnees.get(cle_mois)
    if ancien and ancien.get("leads") and not nouveau["leads"]:
        return False
    donnees[cle_mois] = nouveau
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--depuis")
    ap.add_argument("--derniers", type=int, default=4)
    ap.add_argument("--courant", action="store_true", help="inclure le mois en cours (partiel) : collecte quotidienne")
    ap.add_argument("--pays", default=",".join(PAYS))
    ap.add_argument("--sortie", default=str(FICHIER))
    a = ap.parse_args(argv)
    try:
        token, instance = jeton()
    except NonConfigure as e:
        print(f"C1ST non configuré : {e}", file=sys.stderr)
        return 3
    client = Client(token, instance)
    sortie = Path(a.sortie)
    existant = json.loads(sortie.read_text(encoding="utf-8")) if sortie.exists() else {}
    mois = mois_a_collecter(date.today(), a.depuis, a.derniers, a.courant)
    ok = ko = ignores = 0
    for pays in a.pays.split(","):
        for y, m in mois:
            cle = f"{y}-{m:02d}"
            try:
                if fusionne(existant, pays, cle, collecte_mois(client, pays, y, m)):
                    ok += 1
                else:
                    ignores += 1
                    print(f"  {pays} {cle} : résultat vide, mois existant conservé", file=sys.stderr)
            except Exception as e:                                       # un mois en échec n'empêche pas les autres
                ko += 1
                print(f"  {pays} {cle} : {type(e).__name__}: {e}", file=sys.stderr)
            time.sleep(0.4)
        sortie.parent.mkdir(parents=True, exist_ok=True)       # sauvegarde après chaque marché : une collecte interrompue ne perd pas le travail fait
        sortie.write_text(json.dumps(existant, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    existant["collecte"] = {"date": date.today().isoformat(), "source": "C1ST (CRM Analytics), collecte automatique — totaux par marché, mois et marque, aucune donnée personnelle ; le mois de la date de collecte est partiel",
                            "mois": f"{mois[0][0]}-{mois[0][1]:02d} à {mois[-1][0]}-{mois[-1][1]:02d} (derniers mois collectés)", "pays": a.pays.split(",")}
    existant["perimetre"] = "type 1, activité VN, campagne Autobiz, nature 47 (xP) ou A68 (xF) ; SPOTICAR (SP) : activité VO, nature 15.Buyback request (leads de rachat)"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(existant, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"C1ST : {ok} mois collectés, {ignores} conservés, {ko} en échec")
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main())
