"""Veille de la répartition du trafic par canal, toutes les 30 minutes (workflow canaux-watch.yml).

Pourquoi : un changement de paramètres UTM sur une campagne (ex. medium « CPM » renommé « DRE » le 13/10/2026)
fait basculer des milliers de sessions de « Paid Other » vers « Unassigned » dans GA4, sans qu'aucun volume ne
bouge : ni le suivi des leads, ni le contrôle de disponibilité ne le voient. Ce contrôle compare, pour chaque site,
la part de sessions « Unassigned » du jour à celle des 7 jours précédents et alerte sur Teams en cas de saut.

Sortie console volontairement sobre (ce dépôt est public : les journaux d'Actions ne doivent contenir aucun chiffre
métier) — seuls les nombres de sites contrôlés et d'alertes sont affichés.

Variables : GOOGLE_APPLICATION_CREDENTIALS (GA4), LEADS_TEAMS_WEBHOOK_URL (canal « Alerte Leads »),
CANAUX_STATE (fichier d'état, restauré par le cache du workflow), CANAUX_DRY=1 (calcule sans envoyer).
"""
import collections
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

from pipeline import ga4, sites

SEUIL_SAUT_PTS = float(os.environ.get("CANAUX_SEUIL_PTS", "15"))     # hausse de la part « Unassigned », en points
PART_MIN_PCT = float(os.environ.get("CANAUX_PART_MIN", "15"))        # et part du jour au moins égale à
SESSIONS_MIN = int(os.environ.get("CANAUX_SESSIONS_MIN", "50"))      # sessions du jour au moins
NON_ASSIGNEES_MIN = int(os.environ.get("CANAUX_NA_MIN", "30"))       # sessions « Unassigned » au moins
RENOTIF_PTS = float(os.environ.get("CANAUX_RENOTIF_PTS", "20"))      # nouvelle alerte si la part monte encore de
URL_DASHBOARD = "https://uas-monitor.vercel.app/leads"
DRY = os.environ.get("CANAUX_DRY") == "1"
CHEMIN_ETAT = os.environ.get("CANAUX_STATE", "canaux_state.json")


def fenetre(s):
    """Sessions par jour et par canal (8 derniers jours) sur la page de reprise du site."""
    lignes = ga4._rapport(ga4.client(), s.propriete, "8daysAgo", "today", ["date", "sessionDefaultChannelGroup"],
                          ["sessions"], filtre=ga4._egal("hostName", s.hote_reprise))
    jours = collections.defaultdict(lambda: [0, 0])
    for date, canal, n in lignes:
        jours[date][0] += int(n)
        if canal == "Unassigned":
            jours[date][1] += int(n)
    return jours


def sources_non_assignees(s, jour):
    jour = f"{jour[:4]}-{jour[4:6]}-{jour[6:]}"      # GA4 renvoie AAAAMMJJ, mais attend AAAA-MM-JJ en entrée
    lignes = ga4._rapport(ga4.client(), s.propriete, jour, jour, ["sessionSourceMedium", "sessionDefaultChannelGroup"],
                          ["sessions"], filtre=ga4._egal("hostName", s.hote_reprise))
    nas = [(sm, int(n)) for sm, canal, n in lignes if canal == "Unassigned"]
    return sorted(nas, key=lambda x: -x[1])[:3]


def analyse(s):
    try:
        j = fenetre(s)
    except Exception:
        return None
    if not j:
        return None
    dates = sorted(j)
    aujourdhui = dates[-1]
    base = [j[d] for d in dates[:-1]][-7:]
    if not base:
        return None
    tb = sum(b[0] for b in base)
    pb = 100 * sum(b[1] for b in base) / tb if tb else 0.0
    t, u = j[aujourdhui]
    p = 100 * u / t if t else 0.0
    return {"site": s.nom, "jour": aujourdhui, "base": pb, "part": p, "sessions": t, "na": u, "obj": s}


def declenche(r):
    return (r["sessions"] >= SESSIONS_MIN and r["na"] >= NON_ASSIGNEES_MIN
            and r["part"] - r["base"] >= SEUIL_SAUT_PTS and r["part"] >= PART_MIN_PCT)


def carte(alertes):
    lignes = []
    triees = sorted(alertes, key=lambda x: x["na"], reverse=True)       # les plus gros volumes non attribués d'abord
    for r in triees[:8]:
        src = ", ".join(f"{sm} ({n})" for sm, n in r["sources"]) or "sources non déterminées"
        lignes.append({
            "type": "Container", "spacing": "Medium", "separator": True, "items": [
                {"type": "TextBlock", "text": f"{r['site']} — « Unassigned » {r['base']:.0f} % → {r['part']:.0f} %",
                 "weight": "Bolder", "wrap": True, "color": "Attention"},
                {"type": "TextBlock", "text": f"{r['na']} sessions sur {r['sessions']} aujourd'hui · sources : {src}",
                 "wrap": True, "isSubtle": True, "size": "Small", "spacing": "None"},
            ]})
    if len(triees) > 8:
        reste = triees[8:]
        lignes.append({"type": "TextBlock", "spacing": "Medium", "wrap": True, "isSubtle": True, "size": "Small",
                       "text": f"+ {len(reste)} autre(s) site(s) : " + ", ".join(r["site"] for r in reste[:12]) + ("…" if len(reste) > 12 else "")})
    titre = (f"Trafic non attribué en forte hausse — {alertes[0]['site']}" if len(alertes) == 1
             else f"Trafic non attribué en forte hausse sur {len(alertes)} sites")
    return {
        "type": "message", "summary": titre, "text": titre,
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4",
            "fallbackText": titre,
            "body": [
                {"type": "TextBlock", "text": titre, "weight": "Bolder", "size": "Medium", "wrap": True},
                {"type": "TextBlock", "wrap": True, "isSubtle": True, "size": "Small",
                 "text": "Une part de sessions passe en « Unassigned » dans GA4 : le plus souvent un paramètre UTM (medium) "
                         "modifié ou absent sur une campagne. Les leads du back-office ne sont pas touchés ; seule l'attribution "
                         "du trafic est faussée. À vérifier avec le marketing."},
                {"type": "Container", "spacing": "Medium", "items": lignes},
            ],
            "actions": [{"type": "Action.OpenUrl", "title": "Voir le dashboard", "url": URL_DASHBOARD}],
        }}],
    }


def main():
    webhook = os.environ.get("LEADS_TEAMS_WEBHOOK_URL", "")
    if not webhook and not DRY:
        print("LEADS_TEAMS_WEBHOOK_URL absent : aucune alerte ne peut partir.")
        sys.exit(1)
    cibles = [s for s in sites.SITES if s.acces_api and s.verifie]
    with ThreadPoolExecutor(5) as ex:
        resultats = [r for r in ex.map(analyse, cibles) if r]

    try:
        etat = json.load(open(CHEMIN_ETAT))
    except Exception:
        etat = {}
    jour_courant = max((r["jour"] for r in resultats), default="")
    if etat.get("jour") != jour_courant:          # nouvelle journée : on repart de zéro
        etat = {"jour": jour_courant, "alertes": {}}

    declenches = [r for r in resultats if declenche(r)]
    a_envoyer = []
    for r in declenches:
        deja = etat["alertes"].get(r["site"])
        if deja is None or r["part"] - deja >= RENOTIF_PTS:
            r["sources"] = sources_non_assignees(r["obj"], r["jour"])
            a_envoyer.append(r)

    envoye = False
    if a_envoyer and not DRY:
        resp = requests.post(webhook, json=carte(a_envoyer), timeout=20)
        envoye = resp.status_code in (200, 202)
        if envoye:
            for r in a_envoyer:
                etat["alertes"][r["site"]] = r["part"]
    json.dump(etat, open(CHEMIN_ETAT, "w"))

    print(f"{datetime.now(timezone.utc):%H:%M} UTC — {len(resultats)} site(s) contrôlé(s), "
          f"{len(declenches)} au-dessus du seuil, {len(a_envoyer)} alerte(s) {'envoyée(s)' if envoye else 'non envoyée(s)' if a_envoyer else 'à envoyer : aucune'}.")
    if DRY:
        for r in a_envoyer:      # affichage détaillé uniquement en essai local
            print(f"  [essai] {r['site']} : {r['base']:.0f} % -> {r['part']:.0f} % ({r['na']}/{r['sessions']}) {r['sources']}")


if __name__ == "__main__":
    main()
