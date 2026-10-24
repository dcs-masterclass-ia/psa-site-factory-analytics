#!/usr/bin/env python3
"""Verrouillage d'urgence de Converge : réaction radicale à une attaque, ou retour à la normale.

    python3 scripts/urgence.py etat                        # ce qui est ouvert / fermé en ce moment (lecture seule)
    python3 scripts/urgence.py verrouiller                 # SIMULATION : affiche ce qui serait fait, ne touche à rien
    python3 scripts/urgence.py verrouiller --executer      # coupe vraiment (demande de taper VERROUILLER)
    python3 scripts/urgence.py deverrouiller --executer    # rouvre (demande de taper ROUVRIR)

VERROUILLER (dans l'ordre, chaque étape est indépendante : un échec n'arrête pas les suivantes, le bilan final dit ce qui est fait) :
  1. pare-feu Vercel : la liste blanche d'adresses est remplacée par une adresse non routable (plus personne ne passe, toi compris) ;
  2. dépôt de code GitHub passé en PRIVÉ ;
  3. variables Vercel : ALLOWED_IPS = adresse non routable, AUTH_COOKIE_SECRET renouvelé (toutes les sessions ouvertes sont invalidées), puis redéploiement ;
  4. projet Vercel MIS EN PAUSE (la production ne répond plus du tout) ;
  5. GitHub Actions désactivé sur le dépôt de code (plus aucun traitement automatique ne tourne).
Le dépôt de DONNÉES est déjà privé. Rien n'est supprimé : tout se rouvre avec `deverrouiller`.

DEVERROUILLER : relance le projet, rétablit la liste d'adresses (sauvegardée localement dans ~/.claude/secrets/converge-verrouillage.json, chmod 600, jamais dans le dépôt),
réactive Actions, redéploie. Le dépôt reste PRIVÉ (--republier pour le repasser en public). Les sessions ne reviennent pas (nouveau secret).
NE PAS OUBLIER après un vrai incident : renouveler les jetons (docs/urgence-securite.md, section 4) et chercher ce qui s'est passé.

Prérequis : `vercel` et `gh` connectés (c'est le cas sur le poste de M.). Aucune adresse ni aucun jeton dans ce fichier (dépôt public)."""

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

DEPOT = "dcs-masterclass-ia/psa-site-factory-analytics"
REGLE = "liste-blanche-ip"
ADRESSE_MORTE = "192.0.2.1"          # TEST-NET-1 (RFC 5737) : réservée à la documentation, jamais routée sur Internet
ETAT = Path.home() / ".claude" / "secrets" / "converge-verrouillage.json"
RACINE = Path(__file__).resolve().parent.parent


def sh(cmd, entree=None, simulation=False, tolere=False):
    """Exécute une commande (liste) ; en simulation l'affiche seulement. Retourne la sortie texte."""
    if simulation:
        print("   [simulation] " + " ".join(cmd))
        return ""
    r = subprocess.run(cmd, input=entree, capture_output=True, text=True, cwd=RACINE, timeout=300)
    if r.returncode != 0 and not tolere:
        raise RuntimeError(f"{' '.join(cmd[:3])} : {(r.stderr or r.stdout).strip()[:200]}")
    return r.stdout + r.stderr          # la CLI Vercel écrit une partie de ses réponses sur la sortie d'erreur


def lis_adresses_regle(texte):
    """Extrait les adresses de la sortie de `vercel firewall rules inspect` ('IP address is not any of a, b, c')."""
    m = re.search(r"is not any of ([0-9a-fA-F:., /]+)", texte)
    return [a.strip() for a in m.group(1).split(",") if a.strip()] if m else []


def condition_regle(adresses):
    return json.dumps({"type": "ip_address", "op": "ninc", "value": list(adresses)})


def mode_attaque(action, sim):
    """Vercel exige que le mode Attack Challenge soit activé par un humain dans un terminal (refusé aux agents) : la commande garde le terminal
    (pas de capture) pour que la confirmation de Vercel s'affiche. Facultatif : le confinement tient sans lui (pare-feu + pause)."""
    if sim:
        print(f"   [simulation] vercel firewall attack-mode {action}")
        return
    r = subprocess.run(["vercel", "firewall", "attack-mode", action], cwd=RACINE, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"Vercel a refusé (à lancer toi-même dans un terminal : vercel firewall attack-mode {action}) — le reste du confinement n'en dépend pas")


def etape(bilan, nom, fonction):
    print(f"-> {nom}")
    try:
        fonction()
        bilan.append((nom, "ok"))
    except Exception as e:      # une étape qui échoue ne doit pas empêcher les suivantes : le bilan final la signale
        bilan.append((nom, f"ÉCHEC : {e}"))
        print(f"   ÉCHEC : {e}")


def etat():
    print("Pare-feu :")
    for ligne in sh(["vercel", "firewall", "rules", "inspect", REGLE], tolere=True).splitlines():
        if "IP address" in ligne:
            print("  liste blanche : " + str(len(lis_adresses_regle(ligne))) + " adresse(s)" + ("  (VERROUILLÉE : adresse non routable seule)" if ADRESSE_MORTE in ligne else ""))
    print("Attack mode  : consulter `vercel firewall overview`")
    print("Dépôt GitHub :", sh(["gh", "repo", "view", DEPOT, "--json", "visibility", "-q", ".visibility"], tolere=True).strip())
    print("Actions      :", sh(["gh", "api", f"repos/{DEPOT}/actions/permissions", "-q", ".enabled"], tolere=True).strip())
    print("Sauvegarde du verrouillage :", "présente" if ETAT.exists() else "aucune")


def verrouiller(sim):
    if ETAT.exists() and not sim:
        sys.exit(f"Un verrouillage est déjà enregistré ({ETAT}). Déverrouille d'abord, ou supprime ce fichier si tu es sûr.")
    bilan = []
    # sauvegarde des adresses actuelles AVANT de les remplacer (lisibles dans la règle ; ALLOWED_IPS est une variable « sensitive », illisible)
    actuelles = lis_adresses_regle(sh(["vercel", "firewall", "rules", "inspect", REGLE], simulation=False, tolere=True)) if not sim else ["<adresses actuelles>"]
    if not actuelles and not sim:
        sys.exit("Impossible de lire la liste d'adresses actuelle : je n'ai rien changé (sans elle, le déverrouillage serait impossible).")
    if not sim:
        ETAT.parent.mkdir(parents=True, exist_ok=True)
        ETAT.write_text(json.dumps({"adresses": actuelles, "date": time.strftime("%Y-%m-%d %H:%M:%S")}), encoding="utf-8")
        os.chmod(ETAT, 0o600)

    def pare_feu():
        sh(["vercel", "firewall", "rules", "edit", REGLE, "--condition", condition_regle([ADRESSE_MORTE]), "--yes"], simulation=sim)
        sh(["vercel", "firewall", "publish", "--yes"], simulation=sim)

    def prive():
        sh(["gh", "api", "-X", "PATCH", f"repos/{DEPOT}", "-F", "private=true"], simulation=sim)

    def variables():
        for nom, valeur in (("ALLOWED_IPS", ADRESSE_MORTE), ("AUTH_COOKIE_SECRET", secrets.token_hex(32) if not sim else "<nouveau secret>")):
            sh(["vercel", "env", "rm", nom, "production", "--yes"], simulation=sim, tolere=True)
            sh(["vercel", "env", "add", nom, "production", "--sensitive"], entree=valeur, simulation=sim)
        redeployer(sim)

    def pause():
        sh(["vercel", "api", f"/v1/projects/{projet_id()}/pause", "-X", "POST"], simulation=sim)

    def actions():
        sh(["gh", "api", "-X", "PUT", f"repos/{DEPOT}/actions/permissions", "-F", "enabled=false"], simulation=sim)

    print("VERROUILLAGE" + (" (SIMULATION, rien n'est modifié)" if sim else ""))
    etape(bilan, "1. pare-feu : liste blanche vidée (plus personne ne passe)", pare_feu)
    etape(bilan, "2. dépôt de code en privé", prive)
    etape(bilan, "3. variables Vercel (adresses, secret de session) + redéploiement", variables)
    etape(bilan, "4. projet Vercel en pause", pause)
    etape(bilan, "5. GitHub Actions désactivé", actions)
    rapport(bilan)


def deverrouiller(sim, republier, pause_seule=False):
    if pause_seule:       # après un verrouillage AUTOMATIQUE de la sentinelle : seule la pause Vercel a été posée, rien d'autre à rétablir
        bilan = []
        print("DÉVERROUILLAGE (pause seule)" + (" (SIMULATION, rien n'est modifié)" if sim else ""))
        etape(bilan, "projet Vercel relancé", lambda: sh(["vercel", "api", f"/v1/projects/{projet_id()}/unpause", "-X", "POST"], simulation=sim))
        rapport(bilan)
        return
    try:
        adresses = json.loads(ETAT.read_text(encoding="utf-8"))["adresses"]
    except Exception:
        adresses = ["<adresses sauvegardées>"] if sim else None
    if not adresses:
        sys.exit(f"Pas de sauvegarde des adresses ({ETAT}) : donne-les-moi pour rétablir la liste, rien n'a été changé.")
    bilan = []

    def relance():
        sh(["vercel", "api", f"/v1/projects/{projet_id()}/unpause", "-X", "POST"], simulation=sim)

    def pare_feu():
        sh(["vercel", "firewall", "rules", "edit", REGLE, "--condition", condition_regle(adresses), "--yes"], simulation=sim)
        sh(["vercel", "firewall", "publish", "--yes"], simulation=sim)

    def variables():
        sh(["vercel", "env", "rm", "ALLOWED_IPS", "production", "--yes"], simulation=sim, tolere=True)
        sh(["vercel", "env", "add", "ALLOWED_IPS", "production", "--sensitive"], entree=",".join(adresses), simulation=sim)
        redeployer(sim)

    def actions():
        sh(["gh", "api", "-X", "PUT", f"repos/{DEPOT}/actions/permissions", "-F", "enabled=true", "-f", "allowed_actions=all"], simulation=sim)

    def public():
        if republier:
            sh(["gh", "api", "-X", "PATCH", f"repos/{DEPOT}", "-F", "private=false"], simulation=sim)

    print("DÉVERROUILLAGE" + (" (SIMULATION, rien n'est modifié)" if sim else ""))
    etape(bilan, "1. projet Vercel relancé", relance)
    etape(bilan, "2. pare-feu : liste d'adresses rétablie", pare_feu)
    etape(bilan, "3. variable ALLOWED_IPS + redéploiement", variables)
    etape(bilan, "4. GitHub Actions réactivé", actions)
    if republier:
        etape(bilan, "5. dépôt de code repassé en public", public)
    rapport(bilan)
    if not sim and all(s == "ok" for _, s in bilan):
        ETAT.unlink(missing_ok=True)
    print("Le dépôt de code reste PRIVÉ" if not republier else "")


def redeployer(sim):
    """Redéploie la dernière production EXISTANTE (jamais le dossier local : il peut contenir du code non validé) pour que les variables changées soient prises en compte."""
    if sim:
        sh(["vercel", "redeploy", "<dernière production>"], simulation=True)
        return
    sortie = sh(["vercel", "ls", "--prod", "--yes"])
    ligne = next((l for l in sortie.splitlines() if "Ready" in l and "Production" in l), "")
    m = re.search(r"https://\S+\.vercel\.app", ligne)
    if not m:
        raise RuntimeError("aucune production prête trouvée (vercel ls --prod)")
    sh(["vercel", "redeploy", m.group(0)])


def projet_id():
    return json.loads((RACINE / ".vercel" / "project.json").read_text())["projectId"]


def rapport(bilan):
    print("\nBILAN")
    for nom, s in bilan:
        print(f"  [{'OK' if s == 'ok' else '!!'}] {nom}" + ("" if s == "ok" else f" -> {s}"))
    if any(s != "ok" for _, s in bilan):
        print("Des étapes ont échoué : à reprendre à la main (docs/urgence-securite.md).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=("etat", "verrouiller", "deverrouiller"))
    ap.add_argument("--executer", action="store_true", help="agit vraiment (sinon simulation)")
    ap.add_argument("--pause-seule", action="store_true", help="déverrouiller : relance seulement le projet Vercel (verrouillage automatique de la sentinelle)")
    ap.add_argument("--republier", action="store_true", help="déverrouiller : repasse aussi le dépôt de code en public")
    a = ap.parse_args()
    if a.action == "etat":
        return etat()
    sim = not a.executer
    if not sim:
        mot = "VERROUILLER" if a.action == "verrouiller" else "ROUVRIR"
        if input(f"Action réelle sur la production. Tape {mot} pour confirmer : ").strip() != mot:
            sys.exit("Annulé.")
    verrouiller(sim) if a.action == "verrouiller" else deverrouiller(sim, a.republier, a.pause_seule)


if __name__ == "__main__":
    main()
