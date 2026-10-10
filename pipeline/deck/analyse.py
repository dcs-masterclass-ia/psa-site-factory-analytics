"""Analyse rédigée par Claude à partir des chiffres calculés de la présentation (jamais d'autres données).

Garde-fous : (1) le modèle ne reçoit que des faits déjà calculés (mêmes valeurs que les diapositives) ; (2) tout chiffre cité
dans le texte doit figurer dans ces faits, sinon la phrase est écartée ; (3) les causes ne sont jamais affirmées : seulement
des hypothèses marquées comme telles ; (4) sans clé API ou en cas d'erreur, la diapositive n'est pas générée (avertissement).
"""

import json
import os
import re
import urllib.request

MODELE = os.environ.get("DECK_ANALYSE_MODELE", "claude-opus-5")
URL = "https://api.anthropic.com/v1/messages"

CONSIGNES = {
    "fr": """Tu es analyste digital chez autobiz et tu rédiges l'analyse d'une présentation de performance destinée à des dirigeants Stellantis (sites de reprise / trade-in).
Tu reçois des FAITS déjà calculés (JSON). Règles strictes :
- N'utilise QUE les chiffres présents dans les faits, recopiés exactement (pas d'arrondi nouveau, pas de calcul nouveau, pas de chiffre externe).
- Ne déduis jamais une cause comme un fait : toute explication est une « hypothèse à confirmer », formulée comme telle.
- Quand une base de comparaison est faible (le fait vaut « n.s. » ou le volume est petit), dis que le volume est trop faible pour conclure.
- Ton sobre, factuel, orienté décision. Phrases courtes (25 mots maximum). Pas de jargon inutile, pas d'emoji.
Réponds uniquement par un objet JSON : {"constats":[3 à 4 phrases],"lectures":[2 à 3 phrases, chacune commençant par « Hypothèse : » ou « Point d'attention : »],"recommandations":[2 à 3 actions concrètes et réalistes pour l'équipe site / marque]}""",
    "en": """You are a digital analyst at autobiz writing the analysis section of a performance review for Stellantis executives (trade-in websites).
You receive pre-computed FACTS (JSON). Strict rules:
- Use ONLY numbers present in the facts, copied exactly (no new rounding, no new calculation, no external figure).
- Never state a cause as fact: every explanation is a "hypothesis to be confirmed", worded as such.
- When a comparison base is small (fact is "n.s." or low volume), say the volume is too low to conclude.
- Sober, factual, decision-oriented tone. Short sentences (max 25 words). No jargon, no emoji.
Answer with a single JSON object: {"constats":[3 to 4 sentences],"lectures":[2 to 3 sentences, each starting with "Hypothesis:" or "Watch point:"],"recommandations":[2 to 3 concrete, realistic actions for the site / brand team]}""",
}


def _chiffres(texte):
    """Suites de chiffres d'un texte, sans séparateurs ('13 343' -> '13343', '−12,5 %' -> '125')."""
    out = set()
    for m in re.finditer(r"\d[\d   .,]*\d|\d", texte):
        brut = m.group(0)
        out.add(re.sub(r"\D", "", brut))
        for morceau in re.split(r"[,.]", brut):          # 12,5 -> 12 et 5 aussi acceptés
            out.add(re.sub(r"\D", "", morceau))
    out.discard("")
    return out


def phrases_verifiees(sortie, faits):
    """Écarte toute phrase citant un chiffre absent des faits (numéros de période, années et petits nombres exemptés)."""
    permis = _chiffres(json.dumps(faits, ensure_ascii=False))
    def ok(ph):
        return all(len(c) <= 1 or c in permis for c in _chiffres(re.sub(r"\b(T[1-4]|Q[1-4]|S[12]|N-1)\b", "", ph)))
    res, ecartees = {}, 0
    for k in ("constats", "lectures", "recommandations"):
        garde = [p.strip() for p in (sortie.get(k) or []) if isinstance(p, str) and p.strip() and ok(p)]
        ecartees += len(sortie.get(k) or []) - len(garde)
        res[k] = garde
    return res, ecartees


def appelle(faits, langue, sujet):
    cle = os.environ.get("ANTHROPIC_API_KEY")
    if not cle:
        raise RuntimeError("ANTHROPIC_API_KEY absente")
    corps = {"model": MODELE, "max_tokens": 2500, "system": CONSIGNES.get(langue, CONSIGNES["fr"]),
             "messages": [{"role": "user", "content": f"Sujet : {sujet}\nFAITS :\n{json.dumps(faits, ensure_ascii=False, indent=1)}"}]}
    req = urllib.request.Request(URL, data=json.dumps(corps).encode(), method="POST",
                                 headers={"content-type": "application/json", "x-api-key": cle, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as r:
        rep = json.load(r)
    texte = "".join(b.get("text", "") for b in rep.get("content", []) if b.get("type") == "text")
    m = re.search(r"\{.*\}", texte, re.S)
    return json.loads(m.group(0))


def analyse(faits, langue, sujet):
    """-> {"constats","lectures","recommandations"} vérifiés, ou None (le motif est levé en exception)."""
    sortie = appelle(faits, langue, sujet)
    res, _ = phrases_verifiees(sortie, faits)
    if not res["constats"]:
        sortie = appelle(faits, langue, sujet)        # un seul nouvel essai
        res, _ = phrases_verifiees(sortie, faits)
    if not res["constats"]:
        raise RuntimeError("analyse non vérifiable (chiffres hors faits)")
    return res
