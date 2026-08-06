#!/usr/bin/env python3
"""Insights IA sur les donnees du pipeline, via l'API OpenAI — un jeu de
signaux distinct par rapport (Acquisition, Leads, Parcours, Recherche),
chacun avec son propre vocabulaire et ses propres garde-fous de volume.

Objectif explicite, le meme sur les quatre : jamais d'alerte creuse du
genre « votre page a augmente de 120 % » parce qu'une requete est passee
de 10 a 22 clics. Deux garde-fous partout, pas un seul :
  1. cote Python (seuils de volume) : une ligne ou un mois en dessous du
     seuil n'est meme pas presente au modele comme candidat.
  2. cote prompt : consigne explicite de ne jamais commenter un petit
     echantillon, et de preferer une tendance confirmee sur plusieurs
     mois a un sursaut isole.

Optionnel comme Search Console lui-meme : une cle absente, une erreur
d'API, une reponse mal formee ne bloquent jamais le reste du pipeline —
on retourne une liste vide et on journalise, jamais une exception qui
remonte.
"""

import json
import os

MODELE = "gpt-4o-mini"
MAX_MOIS = 3              # nombre de mois de contexte envoyes (tendance, pas instantane)
MAX_INSIGHTS = 4
TEMPERATURE = 0.1          # coherence d'un jour sur l'autre plus importante
                            # qu'un peu de diversite pour ce genre d'analyse

SEUIL_GSC = 20              # clics OU impressions minimum pour qu'une requete/page GSC compte
PLANCHER_GSC_IMPR = 50       # impressions minimum pour qu'un mois GSC compte
PLANCHER_JOURS = 20           # jours de releve GA4 minimum pour qu'un mois compte, tous
                               # rapports GA4 confondus (voir _mois_incomplets)
PLANCHER_LEADS = 10          # leads minimum pour qu'un mois de leads compte
SEUIL_DIM_LEADS = 15         # leads minimum pour qu'une marque/un projet soit cite
PLANCHER_ENTREES = 30        # entrees de parcours minimum pour qu'un mois compte


def _mois_incomplets(traffic_month):
    """Mois dont GA4 n'a pas encore assez de jours releves pour dire quoi
    que ce soit de fiable (mois en cours, a peine commence). Un volume
    total ne suffit pas comme garde-fou ici : un site important peut
    depasser n'importe quel seuil de volume en seulement 3-4 jours, tout
    en restant tres largement en dessous du rythme du mois complet d'a
    cote — exactement ce qui donnait l'illusion d'un effondrement du
    trafic sur les tout premiers jours d'aout. Le nombre de jours reels
    (tdays) est le seul signal qui ne se fait pas biaiser par la taille du
    site, et il vaut pour tous les rapports GA4 (acquisition, leads,
    parcours partagent le meme calendrier de releve)."""
    return {m for m, v in (traffic_month or {}).items()
            if m != "total" and v.get("tdays", 0) < PLANCHER_JOURS}


# ============================== coeur partage ==============================

def _valide(payload):
    """Verifie la forme exacte attendue, tronque a MAX_INSIGHTS, rejette
    silencieusement toute ligne mal formee plutot que de planter."""
    if not isinstance(payload, dict):
        return []
    items = payload.get("insights")
    if not isinstance(items, list):
        return []
    types_ok = {"opportunite", "attention", "info"}
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        titre, typ, detail = it.get("titre"), it.get("type"), it.get("detail")
        if not (isinstance(titre, str) and titre.strip()
                and isinstance(detail, str) and detail.strip()
                and typ in types_ok):
            continue
        out.append({"titre": titre.strip(), "type": typ, "detail": detail.strip()})
        if len(out) >= MAX_INSIGHTS:
            break
    return out


def _appel_modele(nom_site, systeme, mois_data, contexte_err):
    cle = os.environ.get("OPENAI_API_KEY")
    if not cle:
        return []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=cle)
        resp = client.chat.completions.create(
            model=MODELE, temperature=TEMPERATURE, max_tokens=900,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": systeme},
                {"role": "user", "content": json.dumps(
                    {"site": nom_site, "mois": mois_data}, ensure_ascii=False)},
            ],
        )
        return _valide(json.loads(resp.choices[0].message.content))
    except Exception as e:
        print(f"   {nom_site} — insights {contexte_err} en erreur ({type(e).__name__}: {e})")
        return []


# ============================== acquisition ==============================

SYSTEME_ACQUISITION = """Tu es un analyste qui examine le trafic Google \
Analytics 4 d'un site de reprise automobile. Deux flux bien distincts, \
jamais a comparer en absolu : les sessions du site parent (la marque), \
et les sessions sur l'outil de reprise lui-meme (bien plus petit) — \
seule la tendance et le ratio entre les deux comptent.

Regles absolues :
- Les mois fournis sont deja filtres au-dessus d'un seuil de volume : ne \
descends jamais en dessous de ce que tu recois, et ne commente jamais un \
ecart d'un seul mois sur l'autre sans tendance confirmee sur au moins \
trois mois.
- Si des sessions automatisees (robots) sont signalees pour un mois, \
elles ont deja ete retirees du calcul net des sessions reprise — ne \
jamais lire une baisse des sessions robots comme une vraie baisse de \
trafic reel, c'est l'inverse (moins de bruit, pas moins de visiteurs).
- Priorite aux signaux actionnables : divergence entre le trafic du site \
parent et celui de l'outil de reprise (l'un progresse, l'autre stagne ou \
recule), evolution de la part vers la reprise (le site convertit-il \
mieux ou moins bien vers l'outil), tendance de fond sur les sessions.
- Chaque insight doit s'appuyer sur les chiffres bruts fournis.
- Reponds en francais, ton direct et concret, une a deux phrases par \
insight.
- Si rien ne se degage vraiment, renvoie une liste vide.

Reponds UNIQUEMENT en JSON, sur ce schema exact :
{"insights": [{"titre": "...", "type": "opportunite|attention|info", "detail": "..."}]}
"""


def _resume_mois_acquisition(mois, traffic, reprise, anomalie):
    tdays = traffic.get("tdays") or 1
    rdays = reprise.get("rdays") or 1
    out = {
        "mois": mois,
        "sessions_site_par_jour": round(traffic.get("sessions", 0) / tdays, 1),
        "sessions_reprise_par_jour": round(reprise.get("sessions", 0) / rdays, 1),
        "part_vers_reprise_pct": round(reprise.get("sessions", 0) / traffic["sessions"] * 100, 2)
                                   if traffic.get("sessions") else None,
    }
    if anomalie:
        out["sessions_automatisees_detectees"] = anomalie.get("sessions")
        out["sessions_reprise_nettes_hors_robot"] = anomalie.get("reprise_nette")
    return out


def genere_insights_acquisition(nom_site, traffic_month, reprise_month, anomaly, incomplets):
    mois_dispo = sorted(m for m in traffic_month
                         if m != "total" and m in reprise_month and m not in incomplets)
    mois_retenus = mois_dispo[-MAX_MOIS:]
    if len(mois_retenus) < 2:
        return []
    donnees = [_resume_mois_acquisition(m, traffic_month[m], reprise_month[m], (anomaly or {}).get(m))
               for m in mois_retenus]
    return _appel_modele(nom_site, SYSTEME_ACQUISITION, donnees, "acquisition")


# ============================== leads ==============================

SYSTEME_LEADS = """Tu es un analyste qui examine les leads d'un outil de \
reprise automobile : un visiteur demande une estimation de son vehicule, \
ce qui genere un lead cote back-office.

Regles absolues :
- Les mois et les marques/projets fournis sont deja filtres au-dessus \
d'un seuil de volume : ne descends jamais en dessous, et ne commente \
jamais un ecart d'un seul mois sur l'autre sans tendance confirmee sur \
plusieurs mois.
- Chaque insight doit s'appuyer sur les chiffres bruts fournis.
- Priorite aux signaux actionnables : evolution du volume de leads et du \
taux de conversion (leads / sessions reprise), changement notable dans \
la repartition des marques reprises ou des types de projet (neuf / \
occasion), ecart entre le volume de leads et la tendance du trafic.
- Reponds en francais, ton direct et concret, une a deux phrases par \
insight.
- Si rien ne se degage vraiment, renvoie une liste vide.

Reponds UNIQUEMENT en JSON, sur ce schema exact :
{"insights": [{"titre": "...", "type": "opportunite|attention|info", "detail": "..."}]}
"""


def _filtre_dim_leads(paires):
    return [{"nom": n, "leads": v} for n, v in (paires or []) if v >= SEUIL_DIM_LEADS][:8]


def _resume_mois_leads(mois, leads, reprise):
    total = leads.get("total", 0)
    jours = len(leads.get("daily") or []) or None
    return {
        "mois": mois,
        "leads_total": total,
        "leads_par_jour": round(total / jours, 1) if jours else None,
        "conversion_pct": round(total / reprise["sessions"] * 100, 2)
                            if reprise.get("sessions") else None,
        "top_marques_reprises": _filtre_dim_leads(leads.get("brand")),
        "top_projets": _filtre_dim_leads(leads.get("project")),
    }


def genere_insights_leads(nom_site, leads_month, reprise_month, incomplets):
    mois_dispo = sorted(m for m in leads_month if m != "total" and m not in incomplets)
    mois_retenus = mois_dispo[-MAX_MOIS:]
    while mois_retenus and leads_month[mois_retenus[-1]].get("total", 0) < PLANCHER_LEADS:
        mois_retenus = mois_retenus[:-1]
    if len(mois_retenus) < 2:
        return []
    donnees = [_resume_mois_leads(m, leads_month[m], reprise_month.get(m, {}))
               for m in mois_retenus]
    return _appel_modele(nom_site, SYSTEME_LEADS, donnees, "leads")


# ============================== parcours ==============================

SYSTEME_PARCOURS = """Tu es un analyste qui examine le parcours de \
reprise automobile : les etapes que suit un visiteur de l'outil de \
reprise, de l'arrivee jusqu'a l'estimation finale, mesurees en \
utilisateurs actifs Google Analytics 4 (pas des sessions).

Regles absolues :
- Les mois fournis sont deja filtres au-dessus d'un seuil de volume : ne \
descends jamais en dessous, et ne commente jamais un ecart d'un seul \
mois sur l'autre sans tendance confirmee sur plusieurs mois.
- Chaque insight doit s'appuyer sur les chiffres bruts fournis.
- Priorite aux signaux actionnables : quelle etape perd le plus \
d'utilisateurs par rapport a la precedente et si cette perte s'aggrave \
ou s'ameliore au fil des mois, evolution du taux de completion global \
(entree jusqu'a l'estimation), evolution du volume d'entrees dans le \
parcours.
- Reponds en francais, ton direct et concret, une a deux phrases par \
insight.
- Si rien ne se degage vraiment, renvoie une liste vide.

Reponds UNIQUEMENT en JSON, sur ce schema exact :
{"insights": [{"titre": "...", "type": "opportunite|attention|info", "detail": "..."}]}
"""


def _resume_mois_parcours(mois, fm):
    steps = fm.get("steps") or []
    return {
        "mois": mois,
        "entrees_par_jour": fm.get("users_per_day"),
        "completion_pct": fm.get("conversion_pct"),
        "etapes": [{"nom": s.get("step"), "utilisateurs": s.get("users")} for s in steps],
    }


def genere_insights_parcours(nom_site, funnel_month, incomplets):
    mois_dispo = sorted(m for m in funnel_month if m != "total" and m not in incomplets)
    mois_retenus = mois_dispo[-MAX_MOIS:]
    def entrees(m):
        steps = funnel_month[m].get("steps") or []
        return steps[0]["users"] if steps else 0
    while mois_retenus and entrees(mois_retenus[-1]) < PLANCHER_ENTREES:
        mois_retenus = mois_retenus[:-1]
    if len(mois_retenus) < 2:
        return []
    donnees = [_resume_mois_parcours(m, funnel_month[m]) for m in mois_retenus]
    return _appel_modele(nom_site, SYSTEME_PARCOURS, donnees, "parcours")


# ============================== recherche (Search Console) ==============================

SYSTEME_RECHERCHE = """Tu es un analyste SEO qui examine les donnees Google Search \
Console d'un site de reprise automobile (l'outil qui estime la valeur du \
vehicule d'un visiteur). Ton role : reperer 2 a 4 signaux vraiment utiles \
a quelqu'un d'occupe, jamais du bruit statistique.

Regles absolues :
- Ne jamais commenter une variation en pourcentage sur un volume faible. \
Les lignes fournies sont deja filtrees au-dessus d'un seuil minimum : ne \
descends jamais en dessous de ce que tu recois.
- Une tendance confirmee sur plusieurs mois vaut plus qu'un sursaut isole \
d'un mois sur l'autre.
- Chaque insight doit s'appuyer sur les chiffres bruts fournis, jamais une \
estimation ou une extrapolation.
- Priorite aux signaux actionnables : une requete qui monte en clics ET en \
position, une page qui perd des clics alors que ses impressions tiennent \
(probleme de position ou de meta), un fort volume d'impressions avec un \
CTR anormalement bas (opportunite de titre/meta), une position qui se \
degrade sur plusieurs mois pour une requete a fort volume.
- Reponds en francais, ton direct et concret, une a deux phrases par \
insight, jamais de generalite du type "continuez a optimiser votre SEO".
- Si les donnees ne degagent vraiment aucun signal fiable (trop peu de \
mois, tout est stable, rien au-dessus du bruit), renvoie une liste vide \
plutot que d'inventer un insight faible.

Reponds UNIQUEMENT en JSON, sur ce schema exact :
{"insights": [{"titre": "...", "type": "opportunite|attention|info", "detail": "..."}]}
"""


def _filtre_lignes_gsc(lignes, cle_nom):
    out = []
    for l in (lignes or []):
        if l.get("clics", 0) >= SEUIL_GSC or l.get("impressions", 0) >= SEUIL_GSC:
            out.append({
                "nom": l.get(cle_nom, ""),
                "clics": l.get("clics", 0),
                "impressions": l.get("impressions", 0),
                "ctr": l.get("ctr", 0),
                "position": l.get("position", 0),
            })
    return out[:10]


def _resume_mois_recherche(mois, sm):
    return {
        "mois": mois,
        "clics": sm.get("clics", 0),
        "impressions": sm.get("impressions", 0),
        "ctr": sm.get("ctr", 0),
        "position": sm.get("position", 0),
        "top_requetes": _filtre_lignes_gsc(sm.get("queries"), "requete"),
        "top_pages": _filtre_lignes_gsc(sm.get("pages"), "page"),
    }


def genere_insights_recherche(nom_site, search_month):
    mois_dispo = sorted(m for m in search_month if m != "total")
    mois_retenus = mois_dispo[-MAX_MOIS:]
    # un mois a peine commence (quelques impressions) donne l'illusion d'un
    # effondrement du trafic et biaise la lecture de tendance des mois
    # precedents — on l'exclut plutot que de laisser le modele s'y fier.
    while mois_retenus and search_month[mois_retenus[-1]].get("impressions", 0) < PLANCHER_GSC_IMPR:
        mois_retenus = mois_retenus[:-1]
    if len(mois_retenus) < 2:
        return []
    donnees = [_resume_mois_recherche(m, search_month[m]) for m in mois_retenus]
    if not any(d["top_requetes"] or d["top_pages"] for d in donnees):
        return []
    return _appel_modele(nom_site, SYSTEME_RECHERCHE, donnees, "recherche")


# ============================== orchestrateur ==============================

def genere_tous(nom_site, d, gsc_site):
    """Un jeu d'insights par rapport, jamais un seul bloc generique.
    Chaque generateur degrade independamment : l'echec de l'un (cle
    absente, erreur d'API, donnees insuffisantes) n'affecte jamais les
    autres, chacun retourne simplement une liste vide."""
    incomplets = _mois_incomplets(d.get("trafficMonth", {}))
    return {
        "acquisition": genere_insights_acquisition(
            nom_site, d.get("trafficMonth", {}), d.get("repriseMonth", {}), d.get("anomaly", {}), incomplets),
        "leads": genere_insights_leads(
            nom_site, d.get("leads", {}), d.get("repriseMonth", {}), incomplets),
        "parcours": genere_insights_parcours(
            nom_site, d.get("funnelMonth", {}), incomplets),
        "recherche": genere_insights_recherche(nom_site, d.get("searchMonth", {})) if gsc_site else [],
    }
