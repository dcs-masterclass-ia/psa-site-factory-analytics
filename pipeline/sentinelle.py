"""Sentinelle de sécurité (toutes les 10 min) : sonde externe + changements sensibles + verrouillage automatique.

  1. SONDE : depuis un réseau non autorisé, Converge ne doit rien servir (pipeline/securite_veille.py : sonde / etat_sonde).
  2. CHANGEMENTS (dépôt public, lecture seule) : un commit « direct » sur main (un seul parent, pas une fusion de PR) = la protection de la branche a été contournée ou retirée ;
     un fichier sensible (workflows, middleware, vercel.json, scripts d'urgence) modifié par une fusion = signalé.
  3. CHANGEMENTS VERCEL (si VERCEL_TOKEN) : nouveau déploiement hors GitHub (ligne de commande), variable d'environnement modifiée (noms seulement, jamais les valeurs),
     version du pare-feu changée, membre ajouté à l'équipe.
  4. VERROUILLAGE AUTOMATIQUE (si VERCEL_TOKEN) : mise en PAUSE du projet Vercel (toute la production s'arrête, réversible : scripts/urgence.py deverrouiller --pause-seule) quand
     la liste d'adresses est confirmée inefficace deux contrôles de suite, ou qu'un commit direct apparaît sur main. Sans jeton : alerte seulement, sans coupure.
Alertes Teams au changement d'état ; la console n'affiche que des comptages (dépôt public). Variables : SECURITE_WEBHOOK_URL, VERCEL_TOKEN, GITHUB_TOKEN, SENTINELLE_ETAT."""

import json
import os
import sys
import urllib.request
from pathlib import Path

from pipeline import securite_veille as sv

DEPOT = "dcs-masterclass-ia/psa-site-factory-analytics"
PROJET = "prj_MEkEdI4FwBsAs2NkHBwGRG17OFef"
EQUIPE = "team_7aFIBOaUUuLV2uE72RRptkGD"
ETAT = Path(os.environ.get("SENTINELLE_ETAT", "sentinelle_state.json"))
SENSIBLES = (".github/workflows/", "middleware.js", "vercel.json", "scripts/urgence.py", "scripts/fetch-data.sh", "api/auth.js", "api/_lib/auth.js")


def api(url, jeton=None, methode="GET"):
    h = {"User-Agent": "converge-sentinelle/1", "Accept": "application/json"}
    if jeton:
        h["Authorization"] = f"Bearer {jeton}"
    req = urllib.request.Request(url, method=methode, headers=h, data=b"{}" if methode == "POST" else None)
    with urllib.request.urlopen(req, timeout=30) as r:
        corps = r.read().decode()
        return json.loads(corps) if corps.strip()[:1] in "{[" else {}


def commits_directs(commits, dernier_sha):
    """Commits de main postérieurs à `dernier_sha` (liste du plus récent au plus ancien) : [(sha, direct?)]. Fusion de PR = 2 parents."""
    nouveaux = []
    for c in commits:
        if c["sha"] == dernier_sha:
            break
        nouveaux.append((c["sha"], len(c.get("parents", [])) < 2))
    return nouveaux


def analyse_github(etat, jeton=None):
    constats, critique = [], False
    try:
        commits = api(f"https://api.github.com/repos/{DEPOT}/commits?sha=main&per_page=30", jeton)
    except Exception:
        return constats, critique, etat
    if not commits:
        return constats, critique, etat
    dernier = etat.get("main_sha")
    if dernier:
        for sha, direct in commits_directs(commits, dernier):
            if direct:
                constats.append(("CRITIQUE : commit direct sur main (protection contournée ou retirée)", sha[:7]))
                critique = True
            else:
                try:
                    fichiers = [f["filename"] for f in api(f"https://api.github.com/repos/{DEPOT}/commits/{sha}", jeton).get("files", [])]
                except Exception:
                    fichiers = []
                touches = sorted({f for f in fichiers if f.startswith(SENSIBLES) or f in SENSIBLES})
                if touches:
                    constats.append(("Fichier sensible modifié par une fusion", f"{sha[:7]} : " + ", ".join(touches[:5])))
    return constats, critique, {**etat, "main_sha": commits[0]["sha"]}


def analyse_vercel(etat, jeton):
    constats, vus = [], {}
    p = api(f"https://api.vercel.com/v9/projects/{PROJET}?teamId={EQUIPE}", jeton)
    ver = (p.get("security") or {}).get("firewallConfigVersion")
    if etat.get("pare_feu") is not None and ver != etat["pare_feu"]:
        constats.append(("Pare-feu Vercel modifié", f"version {etat['pare_feu']} -> {ver}"))
    vus["pare_feu"] = ver
    env = api(f"https://api.vercel.com/v9/projects/{PROJET}/env?teamId={EQUIPE}", jeton).get("envs", [])
    maj = {e["key"] + "|" + ",".join(e.get("target") or []): e.get("updatedAt", 0) for e in env}
    if etat.get("env"):
        chg = sorted({k.split("|")[0] for k, v in maj.items() if etat["env"].get(k) != v})
        if chg:
            constats.append(("Variable(s) d'environnement modifiée(s)", ", ".join(chg[:8])))
    vus["env"] = maj
    deps = api(f"https://api.vercel.com/v6/deployments?projectId={PROJET}&teamId={EQUIPE}&limit=10", jeton).get("deployments", [])
    ids = [d["uid"] for d in deps]
    if etat.get("deploiements"):
        for d in deps:
            if d["uid"] not in etat["deploiements"] and d.get("target") == "production" and not (d.get("meta") or {}).get("githubCommitSha"):
                constats.append(("Déploiement de production hors GitHub", "lancé en ligne de commande ou par l'API"))
    vus["deploiements"] = ids
    m = api(f"https://api.vercel.com/v2/teams/{EQUIPE}/members?limit=50", jeton).get("members", [])
    uids = sorted(x["uid"] for x in m)
    if etat.get("membres") and uids != etat["membres"]:
        constats.append(("Membres de l'équipe Vercel modifiés", f"{len(etat['membres'])} -> {len(uids)}"))
    vus["membres"] = uids
    return constats, vus


def mettre_en_pause(jeton):
    api(f"https://api.vercel.com/v1/projects/{PROJET}/pause?teamId={EQUIPE}", jeton, "POST")


def main():
    try:
        etat = json.loads(ETAT.read_text(encoding="utf-8"))
    except Exception:
        etat = {}
    jeton_v, jeton_g = os.environ.get("VERCEL_TOKEN"), os.environ.get("GITHUB_TOKEN")
    constats, declencheur = [], []
    # 1. sonde, confirmée sur deux contrôles de suite avant toute coupure
    nouvel, c_sonde, pannes = sv.etat_sonde(sv.sonde(), etat.get("sonde", {}))
    constats += c_sonde
    expose_confirme = nouvel == "ouvert" and etat.get("sonde", {}).get("etat") == "ouvert"
    if expose_confirme:
        declencheur.append("liste d'adresses inefficace, confirmée deux contrôles de suite")
    # 2. changements GitHub
    c_gh, critique, etat = analyse_github(etat, jeton_g)
    constats += c_gh
    if critique:
        declencheur.append("commit direct sur main")
    # 3. changements Vercel
    vus = {}
    if jeton_v:
        try:
            c_v, vus = analyse_vercel(etat, jeton_v)
            constats += c_v
        except Exception as e:
            print(f"lecture Vercel impossible : {type(e).__name__}", file=sys.stderr)
    # 4. verrouillage automatique
    if declencheur and not etat.get("pause_auto"):
        if jeton_v:
            try:
                mettre_en_pause(jeton_v)
                etat["pause_auto"] = True
                constats.insert(0, ("CONVERGE MIS EN PAUSE AUTOMATIQUEMENT", " ; ".join(declencheur) + " — rouvrir : python3 scripts/urgence.py deverrouiller --executer --pause-seule"))
            except Exception as e:
                constats.insert(0, ("Verrouillage automatique ÉCHOUÉ", f"{type(e).__name__} — lance le bouton rouge à la main : python3 scripts/urgence.py verrouiller --executer"))
        else:
            constats.insert(0, ("Verrouillage automatique indisponible (pas de jeton Vercel)", " ; ".join(declencheur) + " — lance le bouton rouge à la main"))
    if not declencheur:
        etat["pause_auto"] = False if etat.get("pause_auto") and nouvel == "ok" else etat.get("pause_auto", False)
    etat = {**etat, "sonde": {"etat": nouvel, "pannes": pannes}, **vus}
    ETAT.write_text(json.dumps(etat), encoding="utf-8")
    print(f"sentinelle : sonde {nouvel}, {len(constats)} constat(s), vercel {'oui' if jeton_v else 'non (pas de jeton)'}")
    if constats:
        sv.poster(sv.carte("Sécurité Converge — sentinelle", [(t, d) for t, d in constats[:12]]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
