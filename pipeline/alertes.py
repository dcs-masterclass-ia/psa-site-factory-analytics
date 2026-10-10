"""Alertes proactives GA4 (aucune IA, coût nul) : règles à seuils réglables sur les données déjà assemblées de chaque site.

Entrée : data/<site>.json (funnelDaily : 6 étapes par jour ; daily.rep : sessions du site de reprise) et data/alertes/config.json (seuils,
modifiables dans le dashboard, onglet GA4 > Pilotage > Alertes). Sortie : data/alertes.json, lu par le dashboard (jamais de lead back-office :
visible aussi des profils limités). Si ALERTES_WEBHOOK_URL (webhook Teams) est défini et que « notifier » est actif, les NOUVELLES alertes
sont postées sous forme de carte adaptative.

Fenêtres : A = 7 derniers jours de données, B = les 28 jours précédents (comparés en moyenne par semaine).
Règles : sessions (chute en %), conversion estimations ÷ accueil (chute en points), étape du tunnel (chute de passage en points), fraîcheur.

Usage : python -m pipeline.alertes [--ecrire]
"""

import argparse
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

CONFIG_DEFAUT = {
    "sessionsPct": 25,        # chute des sessions (7 j vs moyenne hebdo des 28 j précédents), en %
    "convPts": 1.5,           # chute du taux de conversion, en points
    "etapePts": 5,            # chute du passage d'une étape à la suivante, en points
    "fraicheurJours": 3,      # données plus anciennes que N jours
    "volumeMin": 500,         # sessions / visiteurs minimum sur 7 jours pour qu'une règle s'applique
    "notifier": False,        # poster les nouvelles alertes sur Teams (si ALERTES_WEBHOOK_URL est défini)
}
ETAPES = ["Page d'accueil", "Version", "Kilométrage", "Coordonnées", "Point de vente", "Estimation"]


def charger_config(data=DATA):
    cfg = dict(CONFIG_DEFAUT)
    chemin = Path(data) / "alertes" / "config.json"
    if chemin.exists():
        try:
            brut = json.loads(chemin.read_text(encoding="utf-8"))
            for k, v in (brut.get("config") or brut).items():
                if k in cfg and isinstance(v, (int, float, bool)):
                    cfg[k] = v
        except Exception:
            pass
    return cfg


def _f1(x, signe=False):
    """Nombre à une décimale, virgule française, signe typographique."""
    t = f"{x:+.1f}" if signe else f"{x:.1f}"
    return t.replace("-", "−").replace(".", ",")


def _somme(jours, a, b):
    return [sum(v[i] for j, v in jours.items() if a <= j <= b) for i in range(6)]


def _ajoute(jour, delta):
    return (date.fromisoformat(jour) + timedelta(days=delta)).isoformat()


def evaluer_site(nom, d, cfg, aujourdhui=None):
    """Liste d'alertes pour un site. Tolère l'absence de données (liste vide)."""
    aujourdhui = aujourdhui or datetime.now(timezone.utc).date().isoformat()
    out = []
    fd = d.get("funnelDaily") or {}
    if not fd:
        return out
    dernier = max(fd)
    retard = (date.fromisoformat(aujourdhui) - date.fromisoformat(dernier)).days
    if retard > cfg["fraicheurJours"]:
        out.append({"site": nom, "regle": "fraicheur", "severite": "haute" if retard > 2 * cfg["fraicheurJours"] else "moyenne",
                    "titre": "Données en retard", "detail": f"Dernier jour mesuré : {dernier} ({retard} jours).", "valeur": retard, "reference": cfg["fraicheurJours"], "jour": dernier})
    a0, a1 = _ajoute(dernier, -6), dernier
    b0, b1 = _ajoute(dernier, -34), _ajoute(dernier, -7)
    A, B = _somme(fd, a0, a1), _somme(fd, b0, b1)
    # sessions du site de reprise (daily.rep)
    dd = d.get("daily") or {}
    if dd.get("d") and dd.get("rep"):
        rep = dict(zip(dd["d"], dd["rep"]))
        sa = sum(v for j, v in rep.items() if a0 <= j <= a1)
        sb = sum(v for j, v in rep.items() if b0 <= j <= b1) / 4
        if sa >= cfg["volumeMin"] and sb >= cfg["volumeMin"]:
            chute = (sa - sb) / sb * 100
            if chute <= -cfg["sessionsPct"]:
                out.append({"site": nom, "regle": "sessions", "severite": "haute" if chute <= -2 * cfg["sessionsPct"] else "moyenne",
                            "titre": "Chute des sessions", "detail": f"{sa:,} sessions sur 7 jours ({chute:+.0f} % vs la moyenne des 4 semaines précédentes : {round(sb):,}).".replace(",", " "),
                            "valeur": round(chute, 1), "reference": -cfg["sessionsPct"], "jour": dernier})
    if A[0] >= cfg["volumeMin"] and B[0] >= cfg["volumeMin"]:
        ca, cb = A[5] / A[0] * 100, B[5] / B[0] * 100
        if ca - cb <= -cfg["convPts"]:
            out.append({"site": nom, "regle": "conversion", "severite": "haute" if ca - cb <= -2 * cfg["convPts"] else "moyenne",
                        "titre": "Baisse du taux de conversion", "detail": f"{_f1(ca)} % sur 7 jours contre {_f1(cb)} % sur les 28 jours précédents ({_f1(ca - cb, True)} pt).",
                        "valeur": round(ca - cb, 2), "reference": -cfg["convPts"], "jour": dernier})
        # étape qui fuit : la plus forte baisse de passage, si elle dépasse le seuil
        pire = None
        for k in range(1, 6):
            # une étape qui compte plus de visiteurs que la précédente (événements non séquentiels) n'a pas de taux de passage lisible
            if A[k - 1] >= cfg["volumeMin"] and B[k - 1] >= cfg["volumeMin"] and A[k] <= A[k - 1] and B[k] <= B[k - 1]:
                dk = A[k] / A[k - 1] * 100 - B[k] / B[k - 1] * 100
                if pire is None or dk < pire[0]:
                    pire = (dk, k, A[k] / A[k - 1] * 100, B[k] / B[k - 1] * 100)
        if pire and pire[0] <= -cfg["etapePts"]:
            out.append({"site": nom, "regle": "etape", "severite": "haute" if pire[0] <= -2 * cfg["etapePts"] else "moyenne",
                        "titre": f"Fuite à l'étape « {ETAPES[pire[1]]} »", "detail": f"Passage {ETAPES[pire[1] - 1]} → {ETAPES[pire[1]]} : {_f1(pire[2])} % contre {_f1(pire[3])} % ({_f1(pire[0], True)} pt).",
                        "valeur": round(pire[0], 2), "reference": -cfg["etapePts"], "jour": dernier})
    return out


def _carte(nouvelles, total):
    corps = [{"type": "TextBlock", "size": "Medium", "weight": "Bolder", "wrap": True, "text": f"Converge — {len(nouvelles)} nouvelle(s) alerte(s) GA4"}]
    for a in nouvelles[:10]:
        corps.append({"type": "TextBlock", "wrap": True, "text": f"{'🔴' if a['severite'] == 'haute' else '🟠'} **{a['site']}** — {a['titre']} : {a['detail']}"})
    if len(nouvelles) > 10:
        corps.append({"type": "TextBlock", "wrap": True, "isSubtle": True, "text": f"… et {len(nouvelles) - 10} autre(s). {total} alerte(s) actives au total."})
    return {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive",
            "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "body": corps}}]}


def notifier(nouvelles, total):
    url = os.environ.get("ALERTES_WEBHOOK_URL")
    if not url or not nouvelles:
        return False
    req = urllib.request.Request(url, data=json.dumps(_carte(nouvelles, total)).encode(), method="POST", headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return 200 <= r.status < 300
    except Exception as e:
        print(f"notification Teams en échec : {type(e).__name__}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    cfg = charger_config()
    anciennes = {}
    try:
        for x in json.loads((DATA / "alertes.json").read_text(encoding="utf-8")).get("alertes", []):
            anciennes[(x["site"], x["regle"])] = x
    except Exception:
        pass
    aujourdhui = datetime.now(timezone.utc).date().isoformat()
    toutes = []
    for f in sorted(DATA.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict) or "funnelDaily" not in d or not d.get("site"):
            continue
        toutes.extend(evaluer_site(d["site"], d, cfg, aujourdhui))
    nouvelles = []
    for x in toutes:
        prec = anciennes.get((x["site"], x["regle"]))
        x["depuis"] = prec["depuis"] if prec else aujourdhui
        if not prec:
            nouvelles.append(x)
    toutes.sort(key=lambda x: (x["severite"] != "haute", x["site"]))
    sortie = {"genere": aujourdhui, "seuils": cfg, "alertes": toutes}
    print(f"{len(toutes)} alerte(s) ({len(nouvelles)} nouvelle(s))")
    for x in toutes[:15]:
        print(f"  [{x['severite']}] {x['site']} — {x['titre']} : {x['detail']}")
    if a.ecrire:
        from pipeline.build import _commit_et_pousse, _configure_git      # import tardif : evaluer_site() reste sans dependance reseau
        (DATA / "alertes.json").write_text(json.dumps(sortie, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        _configure_git()
        ok, detail = _commit_et_pousse(["data/alertes.json"], f"chore(alertes): {len(toutes)} alerte(s) au {aujourdhui}")
        print("alertes.json publié" if ok else f"push en échec : {detail}")
        if cfg.get("notifier"):
            print("notification Teams envoyée" if notifier(nouvelles, len(toutes)) else "notification Teams non envoyée")


if __name__ == "__main__":
    main()
