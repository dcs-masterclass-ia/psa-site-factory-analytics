#!/usr/bin/env python3
"""Insights IA sur les donnees Search Console, via l'API OpenAI.

Objectif explicite : jamais d'alerte creuse du genre « votre page a
augmente de 120 % » parce qu'une requete est passee de 10 a 22 clics. Deux
garde-fous, pas un seul :
  1. cote Python (SEUIL_MIN) : une requete ou une page en dessous du seuil
     de volume n'est meme pas presentee au modele comme candidate.
  2. cote prompt : consigne explicite de ne jamais commenter une variation
     sur un petit echantillon, et de preferer une tendance confirmee sur
     plusieurs mois a un sursaut isole.

Optionnel comme Search Console lui-meme : une cle absente, une erreur
d'API, une reponse mal formee ne bloquent jamais le reste du pipeline —
on retourne une liste vide et on journalise, jamais une exception qui
remonte.
"""

import json
import os

SEUIL_MIN = 20          # clics OU impressions minimum pour qu'une requete/page
                         # entre dans le lot presente au modele
PLANCHER_IMPRESSIONS = 50  # sous ce total mensuel, le mois est trop frais
                            # (juste commence) pour dire quoi que ce soit
MAX_MOIS = 3             # nombre de mois de contexte envoyes (tendance, pas instantane)
MAX_LIGNES = 10           # top N requetes/pages par mois, deja trie par clics
MODELE = "gpt-4o-mini"
MAX_INSIGHTS = 4

SYSTEME = """Tu es un analyste SEO qui examine les donnees Google Search \
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


def _filtre_lignes(lignes, cle_nom):
    """Ne garde que les lignes au-dessus du seuil de volume, avec un nom
    de champ uniforme ('nom') quel que soit 'requete' ou 'page' en entree."""
    out = []
    for l in lignes:
        if l.get("clics", 0) >= SEUIL_MIN or l.get("impressions", 0) >= SEUIL_MIN:
            out.append({
                "nom": l.get(cle_nom, ""),
                "clics": l.get("clics", 0),
                "impressions": l.get("impressions", 0),
                "ctr": l.get("ctr", 0),
                "position": l.get("position", 0),
            })
    return out[:MAX_LIGNES]


def _resume_mois(mois, sm):
    return {
        "mois": mois,
        "clics": sm.get("clics", 0),
        "impressions": sm.get("impressions", 0),
        "ctr": sm.get("ctr", 0),
        "position": sm.get("position", 0),
        "top_requetes": _filtre_lignes(sm.get("queries", []), "requete"),
        "top_pages": _filtre_lignes(sm.get("pages", []), "page"),
    }


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


def genere_insights(nom_site, search_month):
    """search_month : le dict d['searchMonth'] tel qu'assemble par build.py
    (cles = mois 'AAAA-MM', plus une eventuelle cle 'total' a ignorer ici —
    on ne veut que des mois calendaires pour une vraie serie temporelle)."""
    cle = os.environ.get("OPENAI_API_KEY")
    if not cle:
        return []

    mois_dispo = sorted(m for m in search_month if m != "total")
    mois_retenus = mois_dispo[-MAX_MOIS:]
    # un mois a peine commence (quelques impressions) donne l'illusion d'un
    # effondrement du trafic et biaise la lecture de tendance des mois
    # precedents — on l'exclut plutot que de laisser le modele s'y fier.
    while mois_retenus and search_month[mois_retenus[-1]].get("impressions", 0) < PLANCHER_IMPRESSIONS:
        mois_retenus = mois_retenus[:-1]
    if len(mois_retenus) < 2:
        return []  # une tendance ne se lit pas sur un seul point

    donnees = [_resume_mois(m, search_month[m]) for m in mois_retenus]
    # rien d'exploitable si aucun mois n'a de requete/page au-dessus du seuil
    if not any(d["top_requetes"] or d["top_pages"] for d in donnees):
        return []

    try:
        from openai import OpenAI
        client = OpenAI(api_key=cle)
        resp = client.chat.completions.create(
            model=MODELE,
            temperature=0.1,  # coherence d'un jour sur l'autre plus importante
                               # qu'un peu de diversite pour ce genre d'analyse
            max_tokens=900,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEME},
                {"role": "user", "content": json.dumps(
                    {"site": nom_site, "mois": donnees}, ensure_ascii=False)},
            ],
        )
        contenu = resp.choices[0].message.content
        return _valide(json.loads(contenu))
    except Exception as e:
        print(f"   {nom_site} — insights IA en erreur ({type(e).__name__}: {e})")
        return []
