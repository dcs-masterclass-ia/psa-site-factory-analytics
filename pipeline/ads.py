"""Collecte Google Ads via GA4 -> data/ads/ga4.json.

Pourquoi GA4 et pas l'API Google Ads : l'accès direct au compte publicitaire n'est pas disponible pour le compte de service (l'accès a été donné à un compte utilisateur). Les propriétés GA4 des sites sont liées
aux comptes Google Ads, et l'API de données GA4 expose alors le compte, la campagne, les clics, les impressions et, quand la liaison le transmet, le coût (advertiserAdCost).
Limites à connaître (écrites dans le fichier, affichées par l'onglet) : seuls les comptes Ads liés à une propriété GA4 apparaissent, le coût n'est pas transmis pour tous les comptes (il vaut alors 0 alors que
les clics existent : `clics_sans_cout`), et les données suivent le décalage habituel de GA4 (1 à 2 jours).

    python -m pipeline.ads [--sites "PEUGEOT FR,OPEL FR"] [--ecrire]

Identifiants : GOOGLE_APPLICATION_CREDENTIALS (compte de service GA4 habituel, secret GA4_SERVICE_ACCOUNT). Lecture seule ; aucun nom de compte ni de campagne n'est écrit dans ce dépôt."""

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline import ga4, sites

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "data" / "ads" / "ga4.json"
PARIS = ZoneInfo("Europe/Paris")
MOIS_HISTORIQUE = 13          # mois civils collectés (dont le mois en cours)
JOURS_CAMPAGNES = 30          # fenêtre des campagnes et du total « 30 derniers jours »
TOP_CAMPAGNES = 12            # campagnes gardées par compte (par clics, sur la période courante ou la précédente)
SANS_COMPTE = ("", "(not set)")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def debut_historique(aujourdhui):
    """Premier jour du mois qui ouvre la fenêtre de MOIS_HISTORIQUE mois civils."""
    a, m = aujourdhui.year, aujourdhui.month - (MOIS_HISTORIQUE - 1)
    while m <= 0:
        a, m = a - 1, m + 12
    return date(a, m, 1)


def agrege(lignes_mois, lignes_camp, lignes_camp_prec=()):
    """Fusionne les requêtes GA4 d'une propriété en liste de comptes.

    lignes_mois : [(mois 'AAAAMM', compte, coût, clics, impressions)] ; lignes_camp : [(compte, campagne, coût, clics, impressions)] sur les JOURS_CAMPAGNES derniers jours ;
    lignes_camp_prec : même format sur les JOURS_CAMPAGNES jours d'avant (comparaison). Un compte garde ses séries mensuelles, ses totaux de la période et de la précédente
    (`cout_prec`, `clics_prec`, `impressions_prec`), son nombre de campagnes, ses TOP_CAMPAGNES premières campagnes [nom, coût, clics, impressions, clics période précédente] et
    `clics_sans_cout` : les clics des campagnes dont le coût est nul (coût non transmis par la liaison GA4 vers Ads, ou campagne réellement gratuite : on ne peut pas les distinguer d'ici)."""
    def neuf(compte):
        return {"nom": compte, "mensuel": {}, "cout": 0.0, "clics": 0, "impressions": 0, "cout_prec": 0.0, "clics_prec": 0, "impressions_prec": 0, "campagnes": 0, "clics_sans_cout": 0, "top": []}
    comptes = {}
    for mois, compte, cout, clics, impr in lignes_mois:
        if compte in SANS_COMPTE:
            continue
        c = comptes.setdefault(compte, neuf(compte))
        cle = f"{mois[:4]}-{mois[4:6]}"
        m = c["mensuel"].setdefault(cle, [0.0, 0, 0])
        m[0] += cout
        m[1] += clics
        m[2] += impr
    nom_camp = lambda camp: camp if camp not in ("", "(not set)") else "(sans campagne)"
    camps, prec = defaultdict(dict), defaultdict(dict)
    for compte, camp, cout, clics, impr in lignes_camp:
        if compte in SANS_COMPTE:
            continue
        c = comptes.setdefault(compte, neuf(compte))
        c["cout"] += cout
        c["clics"] += int(clics)
        c["impressions"] += int(impr)
        if cout == 0 and clics > 0:
            c["clics_sans_cout"] += int(clics)
        camps[compte][nom_camp(camp)] = [round(cout, 2), int(clics), int(impr)]
    for compte, camp, cout, clics, impr in lignes_camp_prec:
        if compte in SANS_COMPTE:
            continue
        c = comptes.setdefault(compte, neuf(compte))
        c["cout_prec"] += cout
        c["clics_prec"] += int(clics)
        c["impressions_prec"] += int(impr)
        prec[compte][nom_camp(camp)] = int(clics)
    out = []
    for compte, c in comptes.items():
        noms = set(camps.get(compte, {})) | set(prec.get(compte, {}))
        lignes = [[n, *camps.get(compte, {}).get(n, [0.0, 0, 0]), prec.get(compte, {}).get(n, 0)] for n in noms]
        lignes.sort(key=lambda x: (-max(x[2], x[4]), -x[1], x[0]))
        c["campagnes"] = len(camps.get(compte, {}))
        c["top"] = lignes[:TOP_CAMPAGNES]
        c["cout"] = round(c["cout"], 2)
        c["cout_prec"] = round(c["cout_prec"], 2)
        c["mensuel"] = {k: [round(v[0], 2), int(v[1]), int(v[2])] for k, v in sorted(c["mensuel"].items())}
        if c["clics"] or c["cout"] or c["clics_prec"] or any(v[1] or v[0] for v in c["mensuel"].values()):
            out.append(c)
    return sorted(out, key=lambda c: (-c["clics"], -c["cout"], c["nom"]))


def _rapport(cli, propriete, dimensions, debut, fin):
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
    req = RunReportRequest(property=f"properties/{propriete}", date_ranges=[DateRange(start_date=debut, end_date=fin)],
                           dimensions=[Dimension(name=d) for d in dimensions],
                           metrics=[Metric(name=m) for m in ("advertiserAdCost", "advertiserAdClicks", "advertiserAdImpressions")], limit=100000)
    r = cli.run_report(req)
    lignes = [([d.value for d in x.dimension_values], [_f(m.value) for m in x.metric_values]) for x in r.rows]
    return lignes, r.metadata.currency_code


def mois_a_collecter(aujourdhui):
    """[(AAAAMM, premier jour, dernier jour à interroger)] : MOIS_HISTORIQUE mois civils, le dernier s'arrêtant à la veille."""
    veille = aujourdhui - timedelta(days=1)
    out, d = [], debut_historique(aujourdhui)
    while d <= veille:
        suivant = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        out.append((f"{d.year}{d.month:02d}", d.isoformat(), min(suivant - timedelta(days=1), veille).isoformat()))
        d = suivant
    return out


def collecte_site(cli, site, aujourdhui):
    fin = (aujourdhui - timedelta(days=1)).isoformat()
    # UNE requête par mois, sans la dimension yearMonth : combinée au compte Ads, yearMonth multiplie les métriques Ads par le nombre de jours du mois (constaté : 38 M de clics au lieu de 1,27 M)
    mois, devise = [], None
    for cle, d1, d2 in mois_a_collecter(aujourdhui):
        lignes, devise = _rapport(cli, site.propriete, ["sessionGoogleAdsAccountName"], d1, d2)
        mois += [(cle, d[0], m[0], m[1], m[2]) for d, m in lignes]
    dims = ["sessionGoogleAdsAccountName", "sessionGoogleAdsCampaignName"]
    debut_p = aujourdhui - timedelta(days=JOURS_CAMPAGNES)
    camps, _ = _rapport(cli, site.propriete, dims, debut_p.isoformat(), fin)
    prec, _ = _rapport(cli, site.propriete, dims, (debut_p - timedelta(days=JOURS_CAMPAGNES)).isoformat(), (debut_p - timedelta(days=1)).isoformat())
    f = lambda rows: [(d[0], d[1], m[0], m[1], m[2]) for d, m in rows]
    comptes = agrege(mois, f(camps), f(prec))
    return {"nom": site.nom, "noms": [site.nom], "pays": site.pays, "propriete": site.propriete, "devise": devise, "comptes": comptes}


def collecte(noms=None, aujourdhui=None):
    aujourdhui = aujourdhui or datetime.now(PARIS).date()
    cli = ga4.client()
    par_propriete = {}
    for s in sites.SITES:
        if s.acces_api and (not noms or s.nom in noms):
            par_propriete.setdefault(s.propriete, []).append(s)   # une propriété partagée par plusieurs sites n'est lue (et comptée) qu'une fois
    res, erreurs = [], []
    for groupe in par_propriete.values():
        s = groupe[0]
        try:
            r = collecte_site(cli, s, aujourdhui)
            r["noms"] = [x.nom for x in groupe]
            res.append(r)
        except Exception as e:                                  # une propriété en échec n'arrête pas les autres
            erreurs.append(f"{s.nom} : {type(e).__name__}")
    return {"generee": datetime.now(PARIS).isoformat(timespec="seconds"), "jusqua": (aujourdhui - timedelta(days=1)).isoformat(), "jours": JOURS_CAMPAGNES,
            "source": "GA4 (liaison Google Ads) : clics et impressions fiables, coût non transmis par toutes les liaisons", "sites": res, "erreurs": erreurs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", default="")
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    noms = {x.strip() for x in a.sites.split(",") if x.strip()} or None
    doc = collecte(noms)
    nb = sum(len(s["comptes"]) for s in doc["sites"])
    print(f"{len(doc['sites'])} propriétés, {nb} comptes Ads, {len(doc['erreurs'])} erreur(s)")
    for e in doc["erreurs"][:10]:
        print("  échec :", e)
    if not doc["sites"]:
        sys.exit("aucune propriété lue : rien écrit")
    if a.ecrire:
        FICHIER.parent.mkdir(parents=True, exist_ok=True)
        FICHIER.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print("écrit :", FICHIER)


if __name__ == "__main__":
    main()
