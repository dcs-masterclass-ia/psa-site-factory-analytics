"""Diagnostic ponctuel : funnel etape par etape filtre sur un canal GA4
(sessionDefaultChannelGroup), demande a la volee (KamIA/chat) pour un site
et une plage de dates donnes -- le pipeline standard (funnel.py) ne calcule
le funnel qu'au global, jamais croise avec le canal.

Reutilise la methode B de funnel.py (dimension personnalisee step_name,
la meme que les explorations GA4 manuelles du projet) en ajoutant un
troisieme filtre en ET : sessionDefaultChannelGroup = <canal>.

Lecture seule, aucune ecriture dans data/. Sortie : JSON sur stdout.

Usage :
    python -m pipeline._diag_funnel_canal --site opel-pt --debut 2026-08-01 --fin 2026-08-31 --canal "Paid Search"
"""

import argparse
import json

from pipeline import ga4
from pipeline.funnel import (
    CANDIDATS_PAGE_CATEGORY, CANDIDATS_STEP_NAME, ETAPE_HOME, ETAPES_PARAM,
    EVENEMENT_ESTIMATION, MOTIFS_HOME,
)
from pipeline.sites import site as trouve_site


def _dimension_valide(cli, pid, hote, debut, fin, canal_filtre, nom_api):
    try:
        l = ga4._rapport(cli, pid, debut, fin, [nom_api], ["activeUsers"],
                         ga4._et(ga4._egal("hostName", hote), canal_filtre))
        return bool(l)
    except Exception:
        return False


def funnel_par_canal(cli, pid, hote, debut, fin, canal):
    canal_filtre = ga4._egal("sessionDefaultChannelGroup", canal)
    base = ga4._egal("hostName", hote)

    resultat = []

    # etape 1 : page d'accueil, via page_category (meme logique que funnel.py)
    dim_home = next((c for c in CANDIDATS_PAGE_CATEGORY
                     if _dimension_valide(cli, pid, hote, debut, fin, canal_filtre, c)), None)
    if dim_home:
        lignes = ga4._rapport(cli, pid, debut, fin, [dim_home], ["activeUsers"],
                              ga4._et(base, canal_filtre))
        total_home = sum(int(u) for v, u in lignes if any(
            __import__("re").search(m, v, __import__("re").I) for m in MOTIFS_HOME))
        resultat.append({"step": ETAPE_HOME, "users": total_home})
    else:
        resultat.append({"step": ETAPE_HOME, "users": None, "erreur": "dimension page_category introuvable"})

    # etapes 2 a 6 : step_name
    dim_step = next((c for c in CANDIDATS_STEP_NAME
                     if _dimension_valide(cli, pid, hote, debut, fin, canal_filtre, c)), None)
    if not dim_step:
        for nom, _ in ETAPES_PARAM:
            resultat.append({"step": nom, "users": None, "erreur": "dimension step_name introuvable"})
        return resultat

    lignes = ga4._rapport(cli, pid, debut, fin, [dim_step], ["activeUsers"],
                          ga4._et(base, canal_filtre))
    par_valeur = {v.strip().lower(): int(u) for v, u in lignes}

    for nom, valeur_attendue in ETAPES_PARAM:
        if nom == "Estimation":
            lignes_evt = ga4._rapport(
                cli, pid, debut, fin, [dim_step], ["activeUsers"],
                ga4._et(base, canal_filtre, ga4._egal("eventName", EVENEMENT_ESTIMATION)))
            par_valeur_evt = {v.strip().lower(): int(u) for v, u in lignes_evt}
            resultat.append({"step": nom, "users": par_valeur_evt.get(valeur_attendue.lower(), 0)})
        else:
            resultat.append({"step": nom, "users": par_valeur.get(valeur_attendue.lower(), 0)})

    return resultat


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--site", required=True)
    p.add_argument("--debut", required=True)
    p.add_argument("--fin", required=True)
    p.add_argument("--canal", required=True)
    args = p.parse_args()

    s = trouve_site(args.site)
    if not s:
        raise SystemExit(f"Site inconnu : {args.site}")

    cli = ga4.client()
    steps = funnel_par_canal(cli, s.propriete, s.hote_reprise, args.debut, args.fin, args.canal)

    # taux de passage et d'abandon, etape par etape
    for i, st in enumerate(steps):
        if st.get("users") is None:
            st["taux_passage"] = None
            st["taux_abandon"] = None
            continue
        if i == 0:
            st["taux_passage"] = None
            st["taux_abandon"] = None
        else:
            prev = steps[i - 1]["users"]
            if prev:
                st["taux_passage"] = round(st["users"] / prev * 100, 1)
                st["taux_abandon"] = round(100 - st["taux_passage"], 1)
            else:
                st["taux_passage"] = None
                st["taux_abandon"] = None

    sortie = {
        "site": s.nom, "hote": s.hote_reprise, "canal": args.canal,
        "debut": args.debut, "fin": args.fin, "steps": steps,
    }
    print(json.dumps(sortie, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
