"""Veille de sécurité : lit le journal de connexion (data/securite/connexions.json, écrit par api/auth.js) et prévient sur Teams.

  --mode veille  (toutes les 30 min) : carte seulement s'il y a quelque chose d'anormal depuis le dernier passage :
        · 3 échecs ou plus depuis la même adresse ;
        · un compte non autorisé qui tente de se connecter ;
        · une connexion réussie d'un compte jamais vu, d'une adresse nouvelle pour ce compte, ou d'un pays nouveau ;
        · SONDE (même passage) : depuis Internet, hors liste blanche, le site doit répondre 403 (ou 429 / challenge Vercel) ; une réponse 200 / 401 sur la page ou les données = liste d'adresses
          inefficace (alerte) ; 5xx ou aucune réponse deux passages de suite = Converge injoignable (alerte) ; carte de retour à la normale ;
  --mode digest  (chaque matin) : résumé des dernières 24 h (connexions, refus, comptes, adresses, pays) + refus du pare-feu Vercel si VERCEL_TOKEN existe.

Dépôt public : la console n'affiche que des comptages, jamais d'adresse ni de compte (ils ne figurent que dans la carte Teams).
Variables : SECURITE_WEBHOOK_URL (à défaut ALERTES_WEBHOOK_URL), VERCEL_TOKEN / VERCEL_PROJECT_ID / VERCEL_TEAM_ID (facultatives, digest)."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

JOURNAL = Path("data/securite/connexions.json")
ETAT = Path("securite_state.json")
SEUIL_ECHECS = 3
MOTIFS_COMPTE_INCONNU = ("compte_non_autorise", "domaine_non_autorise")


def charge():
    try:
        return json.loads(JOURNAL.read_text(encoding="utf-8")).get("evts", [])
    except Exception:
        return []


def analyse(evts, depuis_ms):
    """Constats sur la fenêtre [depuis_ms, maintenant] : liste de (code, titre, détail). `evts` = tout le journal (l'avant sert de mémoire des comptes, adresses et pays connus)."""
    fenetre = [e for e in evts if e.get("t", 0) >= depuis_ms]
    avant = [e for e in evts if e.get("t", 0) < depuis_ms]
    constats = []
    echecs_ip = Counter(e.get("ip") or "?" for e in fenetre if not e.get("ok"))
    for ip, n in echecs_ip.items():
        if n >= SEUIL_ECHECS:
            pays = next((e.get("pays") for e in fenetre if e.get("ip") == ip and e.get("pays")), "")
            constats.append(("echecs_repetes", f"{n} échecs de connexion depuis la même adresse", f"{ip} {('(' + pays + ')') if pays else ''}".strip()))
    for e in fenetre:
        if e.get("motif") in MOTIFS_COMPTE_INCONNU:
            constats.append(("compte_inconnu", "Compte non autorisé qui tente de se connecter", f"{e.get('email', '?')} depuis {e.get('ip') or '?'} {('(' + e['pays'] + ')') if e.get('pays') else ''}".strip()))
    connus_email = {e.get("email") for e in avant if e.get("ok")}
    ips_email, pays_vus = defaultdict(set), {e.get("pays") for e in avant if e.get("ok") and e.get("pays")}
    for e in avant:
        if e.get("ok"):
            ips_email[e.get("email")].add(e.get("ip"))
    deja = set()
    for e in fenetre:
        if not e.get("ok"):
            continue
        em, ip, pays = e.get("email"), e.get("ip"), e.get("pays")
        cle = (em, ip)
        if cle in deja:
            continue
        deja.add(cle)
        if em not in connus_email and avant:
            constats.append(("premier_acces", "Première connexion d'un compte jamais vu", f"{em} depuis {ip}" + (f" ({pays})" if pays else "")))
        elif ips_email.get(em) and ip not in ips_email[em]:
            constats.append(("nouvelle_adresse", "Connexion depuis une adresse nouvelle pour ce compte", f"{em} depuis {ip}" + (f" ({pays})" if pays else "")))
        if pays and pays_vus and pays not in pays_vus:
            constats.append(("nouveau_pays", "Connexion depuis un pays jamais vu", f"{em} depuis {pays} ({ip})"))
    return constats


def resume(evts, depuis_ms):
    f = [e for e in evts if e.get("t", 0) >= depuis_ms]
    ok = [e for e in f if e.get("ok")]
    ko = [e for e in f if not e.get("ok")]
    return {
        "connexions": len(ok), "refus": len(ko),
        "comptes": sorted({e.get("email") for e in ok if e.get("email")}),
        "adresses": len({e.get("ip") for e in ok if e.get("ip")}),
        "pays": sorted({e.get("pays") for e in ok if e.get("pays")}),
        "motifs": dict(Counter(e.get("motif", "?") for e in ko)),
    }


def pare_feu_vercel(depuis_ms, maintenant_ms):
    """Résumé des requêtes traitées par le pare-feu Vercel (refus de la liste blanche, limites de débit) ; None sans jeton ou en cas d'erreur."""
    jeton, projet, equipe = os.environ.get("VERCEL_TOKEN"), os.environ.get("VERCEL_PROJECT_ID"), os.environ.get("VERCEL_TEAM_ID")
    if not (jeton and projet and equipe):
        return None
    url = f"https://api.vercel.com/v1/security/firewall/events/summary?projectId={projet}&teamId={equipe}&startTimestamp={depuis_ms}&endTimestamp={maintenant_ms}"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {jeton}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception:
        return None


URL_SONDE = os.environ.get("SONDE_URL", "https://converge-tradein.vercel.app")
CHEMINS_SONDE = ("/", "/data/peugeot-fr.json", "/api/data?f=peugeot-fr")
REFUS_ATTENDUS = (403, 429)       # 403 = liste blanche d'adresses, 429 = challenge anti-bots Vercel : dans les deux cas rien n'est servi


def sonde():
    """Interroge le site depuis un réseau NON autorisé : [(chemin, statut)] ; statut 0 = aucune réponse. Aucun contenu n'est lu ni conservé."""
    out = []
    for ch in CHEMINS_SONDE:
        try:
            req = urllib.request.Request(URL_SONDE + ch, headers={"User-Agent": "converge-sonde/1"})
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    out.append((ch, r.status))
            except urllib.error.HTTPError as e:
                out.append((ch, e.code))
        except Exception:
            out.append((ch, 0))
    return out


def etat_sonde(resultats, precedent):
    """Compare au passage précédent : retourne (nouvel état, constats). États : ok | ouvert (liste blanche inefficace) | injoignable. L'alerte n'est envoyée qu'au changement d'état (pas toutes les 30 min)."""
    ouvert = [ch for ch, st in resultats if st in (200, 401, 304) or (200 <= st < 300)]
    panne = [ch for ch, st in resultats if st == 0 or st >= 500]
    constats = []
    if ouvert:
        etat = "ouvert"
        if precedent.get("etat") != "ouvert":
            constats.append(("liste_blanche", "ALERTE : la liste d'adresses ne protège plus Converge", "réponse servie à une adresse non autorisée sur : " + ", ".join(ouvert)))
    elif panne:
        n = precedent.get("pannes", 0) + 1
        etat = "injoignable" if n >= 2 else precedent.get("etat", "ok")
        if n == 2:
            constats.append(("injoignable", "Converge ne répond pas (2 contrôles de suite)", "erreur ou délai sur : " + ", ".join(panne) + " (panne, attaque par volume ou déploiement raté ?)"))
        return etat, constats, n
    else:
        etat = "ok"
        if precedent.get("etat") in ("ouvert", "injoignable"):
            constats.append(("retour", "Converge de nouveau protégé et joignable", "retour à la normale (sonde externe)"))
    return etat, constats, 0


def carte(titre, faits, lignes=()):
    corps = [{"type": "TextBlock", "size": "Medium", "weight": "Bolder", "wrap": True, "text": titre}]
    corps += [{"type": "TextBlock", "wrap": True, "text": t} for t in lignes]
    if faits:
        corps.append({"type": "FactSet", "facts": [{"title": a, "value": str(b)} for a, b in faits]})
    return {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "body": corps}}]}


def poster(payload):
    url = os.environ.get("SECURITE_WEBHOOK_URL") or os.environ.get("ALERTES_WEBHOOK_URL")
    if not url:
        print("webhook Teams absent : pas de notification")
        return False
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status < 300
    except Exception as e:
        print(f"Teams en erreur : {type(e).__name__}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("veille", "digest"), default="veille")
    a = ap.parse_args()
    now = int(time.time() * 1000)
    evts = charge()
    if a.mode == "digest":
        depuis = now - 24 * 3600 * 1000
        r = resume(evts, depuis)
        pf = pare_feu_vercel(depuis, now)
        faits = [("Connexions réussies", r["connexions"]), ("Connexions refusées", r["refus"]), ("Comptes", ", ".join(r["comptes"]) or "aucun"),
                 ("Adresses distinctes", r["adresses"]), ("Pays", ", ".join(r["pays"]) or "–")]
        if r["motifs"]:
            faits.append(("Motifs de refus", ", ".join(f"{k} ×{v}" for k, v in r["motifs"].items())))
        if pf is not None:
            faits.append(("Requêtes traitées par le pare-feu Vercel", pf.get("total", 0)))
        else:
            faits.append(("Pare-feu Vercel", "voir l'onglet Firewall du projet (aucun jeton configuré)"))
        poster(carte("Sécurité Converge — bilan des dernières 24 h", faits))
        print(f"digest : {r['connexions']} connexions, {r['refus']} refus")
        return 0
    try:
        etat_prec = json.loads(ETAT.read_text(encoding="utf-8"))
    except Exception:
        etat_prec = {}
    dernier = etat_prec.get("dernier", 0)
    depuis = max(dernier, now - 2 * 3600 * 1000) if dernier else now - 35 * 60 * 1000
    constats = analyse(evts, depuis)
    res = sonde()
    nouvel, c_sonde, pannes = etat_sonde(res, etat_prec.get("sonde", {}))
    constats = c_sonde + constats
    print("sonde : " + ", ".join(f"{ch.split('?')[0]} {st}" for ch, st in res) + f" -> {nouvel}")
    ETAT.write_text(json.dumps({"dernier": now, "sonde": {"etat": nouvel, "pannes": pannes}}), encoding="utf-8")
    if not constats:
        print("RAS")
        return 0
    poster(carte("Sécurité Converge — à vérifier", [(t, d) for _, t, d in constats[:12]]))
    print(f"{len(constats)} constat(s) signalé(s) sur Teams")
    return 0


if __name__ == "__main__":
    sys.exit(main())
