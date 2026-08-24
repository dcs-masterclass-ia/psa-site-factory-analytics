#!/usr/bin/env python3
"""Pre-tri statistique quotidien pour la veille automatique Hermes.

Repere les sites dont le trafic (sessions de reprise) ou les leads ont
significativement bouge sur les 7 derniers jours par rapport aux 7
precedents, avant de solliciter Claude (couteux, cf. scripts/hermes_watch.js)
pour une analyse narrative -- seuls les sites retenus ici declenchent un
appel Claude, jamais les sites sans mouvement notable.

N'ecrit rien dans data/ : imprime un JSON sur la sortie standard, lu par
scripts/hermes_watch.js via une redirection shell (voir
.github/workflows/hermes-watch.yml). Aucun etat partage avec build.py --
lit uniquement les data/<slug>.json deja produits par le pipeline.

Usage
-----
    python3 -m pipeline.watch > candidats.json
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from pipeline.sites import SITES
from pipeline.v2_report import _agrege_jours, _agrege_leads

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data"

SEUIL_ECART_PCT = 25.0     # en-dessous, pas assez significatif pour deranger
VOLUME_MIN = 20            # sous ce volume hebdo (sessions OU leads), un
                            # ecart en % n'est pas fiable (bruit statistique
                            # sur de petits chiffres) -- on ignore le site.

# signaux croises (PageSpeed, SEO) : independants du delta sessions/leads
# ci-dessus -- un site peut se degrader sur l'un sans que l'autre ait encore
# bouge (ex. une regression de perf avant que ca se voie sur le trafic).
PAGESPEED_SEUIL_PTS = 15   # points perdus (mobile OU desktop) entre les
                            # deux derniers releves pour declencher
SEARCH_SEUIL_POSITION = 3.0  # positions perdues sur GSC, mois vs mois precedent
SEARCH_PLANCHER_IMPR = 50  # meme plancher que PLANCHER_GSC_IMPR (pipeline/insights.py) --
                            # sous ce volume d'impressions, un ecart de position est du bruit


def _pagespeed_regression(pagespeed):
    """None si rien d'assez net -- deux releves dates minimum, chute d'au
    moins PAGESPEED_SEUIL_PTS sur mobile ou desktop entre les deux derniers."""
    historique = (pagespeed or {}).get("historique") or {}
    dates = sorted(historique.keys())
    if len(dates) < 2:
        return None
    precedent, recent = historique[dates[-2]], historique[dates[-1]]
    deltas = {}
    for plateforme in ("mobile", "desktop"):
        p, r = precedent.get(plateforme), recent.get(plateforme)
        if p is not None and r is not None and (p - r) >= PAGESPEED_SEUIL_PTS:
            deltas[plateforme] = r - p
    if not deltas:
        return None
    return {"deltas": deltas, "dateRecente": dates[-1], "datePrecedente": dates[-2]}


def _seo_degradation(search_month):
    """None si rien d'assez net -- deux mois avec assez d'impressions pour
    que la position ne soit pas du bruit, degradation d'au moins
    SEARCH_SEUIL_POSITION entre les deux derniers mois."""
    mois = sorted(m for m in (search_month or {}) if m != "total")
    if len(mois) < 2:
        return None
    precedent, recent = search_month[mois[-2]], search_month[mois[-1]]
    if (precedent.get("impressions", 0) < SEARCH_PLANCHER_IMPR
            or recent.get("impressions", 0) < SEARCH_PLANCHER_IMPR):
        return None
    # position GSC : un chiffre plus grand = plus loin dans les resultats,
    # donc pire -- delta positif ici veut dire une degradation.
    delta_position = recent.get("position", 0) - precedent.get("position", 0)
    if delta_position < SEARCH_SEUIL_POSITION:
        return None
    return {
        "deltaPosition": round(delta_position, 1),
        "moisRecent": mois[-1], "moisPrecedent": mois[-2],
        "positionRecente": recent.get("position"), "positionPrecedente": precedent.get("position"),
    }


def _charge(slug):
    chemin = DATA / f"{slug}.json"
    if not chemin.exists():
        return None
    try:
        return json.loads(chemin.read_text())
    except Exception:
        return None


def _ecart_pct(recent, precedent):
    """None si le calcul n'a pas de sens (base nulle) -- jamais 0 qui
    affirmerait a tort "aucun changement"."""
    if precedent <= 0:
        return None
    return round((recent - precedent) / precedent * 100, 1)


def evalue_site(d):
    """Retourne un dict de candidature (chiffres bruts, pas de texte) ou
    None si rien d'assez significatif pour justifier un appel Claude."""
    jours = (d.get("daily") or {}).get("d") or []
    if len(jours) < 14:
        return None  # pas assez d'historique pour comparer deux semaines
    if len(jours[-1]) != 10:
        return None  # site pas encore migre vers les dates completes
                      # "YYYY-MM-DD" (voir build.py, _decoupe_daily_existant) --
                      # se corrige tout seul au prochain passage de ce site.

    fin = datetime.fromisoformat(jours[-1]).date()
    debut_recent = fin - timedelta(days=6)
    debut_prec = debut_recent - timedelta(days=7)
    fin_prec = debut_recent - timedelta(days=1)

    rep = (d.get("daily") or {}).get("rep") or []
    sess_recent = _agrege_jours(jours, rep, debut_recent, fin)
    sess_prec = _agrege_jours(jours, rep, debut_prec, fin_prec)

    leads_recent = _agrege_leads(d.get("leads"), debut_recent, fin)
    leads_prec = _agrege_leads(d.get("leads"), debut_prec, fin_prec)

    anomalie = bool(d.get("anomaly") or {})
    ecart_sess = _ecart_pct(sess_recent, sess_prec)
    ecart_leads = _ecart_pct(leads_recent, leads_prec)

    volume_ok = (max(sess_prec, sess_recent) >= VOLUME_MIN
                 or max(leads_prec, leads_recent) >= VOLUME_MIN)
    significatif = volume_ok and (
        (ecart_sess is not None and abs(ecart_sess) >= SEUIL_ECART_PCT) or
        (ecart_leads is not None and abs(ecart_leads) >= SEUIL_ECART_PCT)
    )

    # signaux croises : declenchent independamment du trafic/leads --
    # capte une regression PageSpeed ou une degradation SEO avant qu'elle
    # ne se voie forcement deja sur les sessions/leads.
    pagespeed_regression = _pagespeed_regression(d.get("pagespeed"))
    seo_degradation = _seo_degradation(d.get("searchMonth"))

    if not (significatif or anomalie or pagespeed_regression or seo_degradation):
        return None

    return {
        "sessionsDelta": ecart_sess, "leadsDelta": ecart_leads,
        "trafficLeadsSignificatif": significatif,  # distingue "chiffre present" de
        # "assez marque pour compter comme signal" -- utilise par
        # scripts/hermes_watch.js (gravite()) pour ne pas confondre un delta
        # anodin avec un vrai signal croise.
        "anomalieDetectee": anomalie,
        "sessionsRecent": sess_recent, "sessionsPrecedent": sess_prec,
        "leadsRecent": leads_recent, "leadsPrecedent": leads_prec,
        "periodeRecente": f"{debut_recent.isoformat()}..{fin.isoformat()}",
        "pagespeedRegression": pagespeed_regression,
        "seoDegradation": seo_degradation,
    }


def main():
    candidats = []
    for s in SITES:
        d = _charge(s.slug)
        if not d:
            continue
        c = evalue_site(d)
        if c:
            c["site"] = s.nom
            candidats.append(c)
    print(json.dumps({"candidats": candidats}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
