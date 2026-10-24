"""Collecte GA4 de l'espace OEM (constructeurs hors Stellantis, ex. Ford) -> data/oem/<slug>.json + data/oem/index.json.

Pourquoi un collecteur séparé : les sites OEM ont leur propre compte de service GA4, leur propre plan de marquage (autres événements de tunnel, pas de step_name) et
aucun lead back-office. Ils ne passent donc pas par pipeline/build.py (contrôles de structure, leads BO, tunnel Stellantis). Les fichiers produits reprennent
les clés des fichiers de site Stellantis qu'ils peuvent alimenter (`daily`, `funnelDaily`, `canalQuotidien`, `repriseMonth`, `trafficMonth`) pour que le dashboard réutilise ses écrans GA4.

    python -m pipeline.oem [--sites ford-fr] [--jours 760] [--ecrire]

Identifiants : GA4_OEM_CREDENTIALS (contenu JSON de la clé du compte de service, secret GitHub GA4_OEM_SERVICE_ACCOUNT) ou GOOGLE_APPLICATION_CREDENTIALS_OEM (chemin du fichier).
Jamais de clé dans le dépôt ni dans les journaux."""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline import ga4

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data" / "oem"
PARIS = ZoneInfo("Europe/Paris")

# étapes du tunnel Ford (plan de marquage des « minisites » OEM) : événement GA4 -> libellé ; la 1re étape = tous les visiteurs du site de reprise.
ETAPES_FORD = [
    ("Visiteurs", None),
    ("Identification du véhicule", "tunnel_identificationVehicule"),
    ("État du véhicule", "tunnel_etatVehicule"),
    ("Projet d'achat", "tunnel_projetAchat"),
    ("Estimation", "page_estimation"),
    ("Offre", "tunnel_offer"),
]


@dataclass(frozen=True)
class SiteOem:
    nom: str
    slug: str
    constructeur: str
    pays: str
    propriete: str
    hotes: tuple                     # noms d'hôte de PRODUCTION uniquement (les hôtes ppr-, test-, stg- sont du bruit de recette)
    etapes: list = field(default_factory=lambda: list(ETAPES_FORD))


SITES_OEM = [
    SiteOem("FORD FR", "ford-fr", "Ford", "FR", "382291926", ("www.ford-reprise.fr",)),
]


def client_oem():
    """Client GA4 du compte de service OEM (distinct du compte Stellantis)."""
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.oauth2 import service_account
    brut = os.environ.get("GA4_OEM_CREDENTIALS")
    if brut:
        creds = service_account.Credentials.from_service_account_info(json.loads(brut), scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    else:
        chemin = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_OEM")
        if not chemin:
            sys.exit("GA4_OEM_CREDENTIALS ou GOOGLE_APPLICATION_CREDENTIALS_OEM non défini.")
        creds = service_account.Credentials.from_service_account_file(chemin, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    return BetaAnalyticsDataClient(credentials=creds)


def _iso(d):
    s = str(d)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else s


def _filtre_hote(s):
    return ga4._egal("hostName", "|".join(s.hotes))


def collecte(cli, s, debut, fin):
    """Toutes les séries d'un site OEM sur [debut, fin] (ISO)."""
    f = _filtre_hote(s)
    # 1. trafic quotidien du site de reprise
    jours = {}
    for d, sessions, users, engagees, vues in ga4._rapport(cli, s.propriete, debut, fin, ["date"], ["sessions", "activeUsers", "engagedSessions", "screenPageViews"], f):
        jours[_iso(d)] = (int(sessions), int(users), int(engagees), int(vues))
    ordre = sorted(jours)
    daily = {"d": ordre, "u": [jours[j][1] for j in ordre], "rep": [jours[j][0] for j in ordre], "eng": [jours[j][2] for j in ordre], "pv": [jours[j][3] for j in ordre]}
    # 2. sessions par jour et par canal par défaut -> canalQuotidien[mois][jour][canal]
    canal = {}
    for d, c, n in ga4._rapport(cli, s.propriete, debut, fin, ["date", "sessionDefaultChannelGroup"], ["sessions"], f):
        j = _iso(d)
        canal.setdefault(j[:7], {}).setdefault(j, {})[c or "(not set)"] = int(n)
    # 3. appareils par jour
    appareil = {}
    for d, a, n in ga4._rapport(cli, s.propriete, debut, fin, ["date", "deviceCategory"], ["sessions"], f):
        appareil.setdefault(_iso(d), {})[a] = int(n)
    # 4. tunnel quotidien : utilisateurs actifs par étape (la 1re = tous les visiteurs du site)
    evts = [e for _, e in s.etapes if e]
    funnel = {j: [0] * len(s.etapes) for j in ordre}
    for j in ordre:
        funnel[j][0] = jours[j][1]
    fe = ga4._et(f, ga4._egal("eventName", "|".join(evts)))
    for d, e, n in ga4._rapport(cli, s.propriete, debut, fin, ["date", "eventName"], ["activeUsers"], fe):
        j = _iso(d)
        for i, (_, ev) in enumerate(s.etapes):
            if ev == e and j in funnel:
                funnel[j][i] = int(n)
    # 5. pages d'entrée par mois (top 25)
    landing = {}
    for d, p, n in ga4._rapport(cli, s.propriete, debut, fin, ["yearMonth", "landingPage"], ["sessions"], f):
        landing.setdefault(f"{d[:4]}-{d[4:6]}", {})[p] = landing.get(f"{d[:4]}-{d[4:6]}", {}).get(p, 0) + int(n)
    landing = {m: dict(sorted(v.items(), key=lambda kv: -kv[1])[:25]) for m, v in landing.items()}
    # 6. totaux mensuels (compatibles repriseMonth / trafficMonth)
    mois = {}
    for j in ordre:
        m = mois.setdefault(j[:7], {"sessions": 0})
        m["sessions"] += jours[j][0]
    return {"daily": daily, "canalQuotidien": canal, "appareilQuotidien": appareil, "funnelDaily": funnel, "landingMonth": landing, "repriseMonth": mois, "trafficMonth": {m: v["sessions"] for m, v in mois.items()}}


def leads_bo(s):
    """Leads back-office du site (data/oem/<slug>-leads.json, écrit par pipeline.oem_leads) ; absents = pas de clé `leads` : jamais de valeur inventée."""
    f = DATA / f"{s.slug}-leads.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("leads")
    except (OSError, ValueError):
        return None


def fichier(s, series, debut, fin):
    leads = leads_bo(s)
    return {
        "site": s.nom, "espace": "oem", "constructeur": s.constructeur, "pays": s.pays, "propriete": s.propriete, "hotes": list(s.hotes),
        "generee": datetime.now(PARIS).isoformat(timespec="seconds"), "periode": [debut, fin],
        "funnelEtapes": [e for e, _ in s.etapes], "funnelEvenements": [v for _, v in s.etapes],
        "sources": "GA4 (compte de service OEM) — aucun lead back-office ni C1ST pour cet espace",
        **({"leads": leads} if leads else {}),
        **series,
    }


def controle(dossier):
    """Garde-fou minimal avant écriture : de vraies données, des jours récents, un tunnel qui ne remonte pas."""
    d = dossier["daily"]
    if len(d["d"]) < 14 or sum(d["rep"]) <= 0:
        return "moins de 14 jours de données ou aucune session"
    recent = date.today() - timedelta(days=5)
    if date.fromisoformat(d["d"][-1]) < recent:
        return f"dernier jour publié trop ancien ({d['d'][-1]})"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", nargs="*")
    ap.add_argument("--jours", type=int, default=760)
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    cibles = [s for s in SITES_OEM if not a.sites or s.slug in a.sites]
    cli = client_oem()
    fin = (date.today() - timedelta(days=1)).isoformat()
    debut = (date.today() - timedelta(days=a.jours)).isoformat()
    index = {"genere": datetime.now(PARIS).isoformat(timespec="seconds"), "sites": {}}
    code = 0
    for s in cibles:
        try:
            doc = fichier(s, collecte(cli, s, debut, fin), debut, fin)
        except Exception as e:
            print(f"{s.nom} : ERREUR {type(e).__name__}")
            index["sites"][s.nom] = {"slug": s.slug, "statut": "indisponible", "motif": type(e).__name__}
            code = 1
            continue
        probleme = controle(doc)
        if probleme:
            print(f"{s.nom} : refusé ({probleme})")
            index["sites"][s.nom] = {"slug": s.slug, "statut": "indisponible", "motif": probleme}
            code = 1
            continue
        n = len(doc["daily"]["d"])
        print(f"{s.nom} : {n} jours, {sum(doc['daily']['rep'])} sessions, tunnel {doc['funnelDaily'][doc['daily']['d'][-1]]} (dernier jour)")
        index["sites"][s.nom] = {"slug": s.slug, "constructeur": s.constructeur, "pays": s.pays, "statut": "ok", "dernier_jour": doc["daily"]["d"][-1]}
        if a.ecrire:
            DATA.mkdir(parents=True, exist_ok=True)
            (DATA / f"{s.slug}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if a.ecrire:
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
