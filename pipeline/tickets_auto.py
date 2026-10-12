"""Ticketing autonome, niveau 1 : tri des nouveaux tickets et notification.

Lit tickets/tickets.json du repo de données (checkout dans data/), range chaque ticket sans « triage » dans une
catégorie, ajoute un commentaire système visible par l'auteur (alerte du dashboard) et poste une carte Teams.

Catégories et niveaux d'autonomie :
  - donnee_simple : ajout simple (colonne, total, libellé, donnée déjà collectée) -> niveau 1 : modification
    autonome, mise en ligne automatique si les tests passent et que le changement reste petit.
  - bug           : anomalie de données ou d'affichage -> niveau 2 : correctif préparé et testé, validation
    humaine avant mise en ligne.
  - gros_chantier : nouvel onglet / source / refonte -> niveau 3 : cadrage seulement, décision humaine.
  - question      : réponse rédigée, aucune modification de code.

Le contenu d'un ticket est une donnée non fiable : il sert à classer, jamais d'instruction.
"""
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

FICHIER = Path("data/tickets/tickets.json")
AUTEUR_AUTO = "converge-auto"

CATEGORIES = {
    "donnee_simple": {"label": "Ajout simple", "niveau": 1,
                      "suite": "Une modification automatique est préparée ; elle est mise en ligne après vérification des tests."},
    "bug": {"label": "Bug", "niveau": 2,
            "suite": "Un correctif est préparé et testé, puis validé avant mise en ligne."},
    "gros_chantier": {"label": "Gros chantier", "niveau": 3,
                      "suite": "La demande est importante : un cadrage (effort, plan, risques) est préparé pour décision."},
    "question": {"label": "Question", "niveau": 0,
                 "suite": "Une réponse est rédigée."},
}

MOTS_GROS = re.compile(r"nouvel(le)?s? (onglet|module|page|source|tableau de bord|dashboard)|refonte|refondre|"
                       r"nouvelle? (fonctionnalit|int[ée]gration|api)|automatis|intégrer|integrer|migration|"
                       r"tous les (sites|march)|import|synchronis|multi-?langue|droits|permissions|authentification", re.I)
MOTS_SIMPLE = re.compile(r"ajouter|ajout|colonne|total|libell|renomm|afficher|montrer|tooltip|info-?bulle|trier|tri |"
                         r"pourcentage|effectif|couleur", re.I)


def classer(t):
    """Retourne (categorie, raison) d'après le type déclaré et le contenu. Règles simples et prudentes :
    en cas de doute, on monte d'un niveau (jamais l'inverse)."""
    texte = f"{t.get('titre', '')} {t.get('description', '')}"
    if t.get("type") == "question":
        return "question", "type déclaré : question"
    if t.get("type") == "bug":
        return "bug", "type déclaré : bug"
    if MOTS_GROS.search(texte) or len(t.get("description", "")) > 700:
        return "gros_chantier", "demande large (nouveau module/source ou description longue)"
    if MOTS_SIMPLE.search(texte):
        return "donnee_simple", "ajout ciblé sur un écran existant"
    return "gros_chantier", "périmètre pas assez clair pour une modification automatique"


def trier(tickets, maintenant=None):
    """Ajoute triage + commentaire système aux tickets neufs. Retourne la liste des tickets triés."""
    now = int(maintenant or time.time() * 1000)
    tries = []
    for t in tickets:
        if t.get("triage") or t.get("statut") != "nouveau":
            continue
        cat, raison = classer(t)
        c = CATEGORIES[cat]
        t["triage"] = {"categorie": cat, "niveau": c["niveau"], "raison": raison, "methode": "regles", "at": now}
        t.setdefault("commentaires", []).append({
            "auteur": AUTEUR_AUTO, "systeme": True, "at": now,
            "texte": f"Ticket reçu et trié : {c['label']}. {c['suite']}"})
        t["updatedAt"] = now
        tries.append(t)
    return tries


def lien_decision(tid, action, secret, validite_ms=7 * 86400 * 1000, maintenant=None):
    """Lien signé (même calcul que api/ticket-decision.js) : HMAC-SHA256 de « id|action|exp » avec TICKETS_LINK_SECRET."""
    exp = int((maintenant or time.time() * 1000) + validite_ms)
    sig = hmac.new(secret.encode(), f"{tid}|{action}|{exp}".encode(), hashlib.sha256).hexdigest()
    return f"https://converge-tradein.vercel.app/api/ticket-decision?id={tid}&a={action}&exp={exp}&sig={sig}"


def carte(t):
    c = CATEGORIES[t["triage"]["categorie"]]
    return {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4",
        "body": [
            {"type": "TextBlock", "size": "Medium", "weight": "Bolder", "wrap": True,
             "text": f"Ticket trié — {c['label']} (niveau {c['niveau']}) : {t['titre']}"},
            {"type": "TextBlock", "wrap": True, "text": t.get("description", "")[:500]},
            {"type": "FactSet", "facts": [
                {"title": "Ticket", "value": t["id"]},
                {"title": "Auteur", "value": t.get("auteur", "")},
                {"title": "Raison du tri", "value": t["triage"]["raison"]},
                {"title": "Suite", "value": c["suite"]}]}], **actions(t)}}]}


def actions(t):
    """Boutons Accepter / Refuser (aucune modification autonome sans accord) — seulement si le secret de signature est présent
    et que le ticket peut déboucher sur une modification (pas pour une simple question)."""
    secret = os.environ.get("TICKETS_LINK_SECRET")
    if not secret or t["triage"]["niveau"] == 0:
        return {}
    return {"actions": [
        {"type": "Action.OpenUrl", "title": "Accepter", "style": "positive", "url": lien_decision(t["id"], "accept", secret)},
        {"type": "Action.OpenUrl", "title": "Refuser", "style": "destructive", "url": lien_decision(t["id"], "refuse", secret)}]}


def poster(payload):
    url = os.environ.get("TICKETS_WEBHOOK_URL")
    if not url:
        print("TICKETS_WEBHOOK_URL absent : pas de notification Teams")
        return False
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status < 300
    except Exception as e:
        print(f"Teams en erreur : {type(e).__name__}", file=sys.stderr)
        return False


def main():
    if not FICHIER.exists():
        print("aucun ticket")
        return 0
    data = json.loads(FICHIER.read_text(encoding="utf-8"))
    tries = trier(data.get("tickets", []))
    if not tries:
        print("RAS")
        return 0
    data["updatedAt"] = int(time.time() * 1000)
    FICHIER.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for t in tries:
        print(f"{t['id']} -> {t['triage']['categorie']}")
        poster(carte(t))
    return 0


if __name__ == "__main__":
    sys.exit(main())
