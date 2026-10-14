"""Marché automobile (onglet « AAA Data ») : collecte mensuelle des immatriculations.

Sources (une par marché, domaines autorisés explicites) :
  FR  AAA Data  (aaa-data.fr)  communiqué mensuel, voitures particulières neuves
  EU  ACEA      (acea.auto)    cumul annuel Europe (UE + AELE + Royaume-Uni)
  DE  KBA       (kba.de)       Kraftfahrt-Bundesamt
  IT  UNRAE     (unrae.it)
  ES  ANFAC     (anfac.com)
  GB  SMMT      (smmt.co.uk)

Principe : un appel Claude (web_search + web_fetch limités au domaine de la source) lit le dernier communiqué et
rend UN JSON de relevés ; rien n'est écrit sans validation (période, plages, cohérence avec la série existante,
URL de la source sur le bon domaine, citation). Un relevé refusé est journalisé, la série existante est
conservée : on ne publie jamais un chiffre douteux.

Fichier produit : data/market.json (repo de données), lu par l'onglet AAA Data.
  france.monthly[]            {month,total,yoy_pct,electric_pct,source_url}   (AAA Data)
  europe.periods_2026[]       {label,yoy_pct,electric_pct,source_url}          (ACEA, cumul annuel)
  markets.<DE|IT|ES|GB>       {name, monthly:[{month,total,yoy_pct,electric_pct,source_url}]}

Usage :
  python -m pipeline.market                 # collecte, valide, écrit et publie
  python -m pipeline.market --dry-run       # collecte et affiche, n'écrit rien
  python -m pipeline.market --sources DE GB # seulement ces marchés
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "data" / "market.json"

MODELE = os.environ.get("MARKET_MODEL", "claude-sonnet-4-6")  # celui de la newsletter, déjà éprouvé avec web_search / web_fetch
API = "https://api.anthropic.com/v1/messages"

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"]

# id -> (nom, domaines autorisés, consigne propre au marché)
SOURCES = {
    "FR": ("France", ["aaa-data.fr"],
           "le communiqué de presse mensuel d'AAA Data sur les immatriculations de voitures particulières neuves en France"),
    "EU": ("Europe", ["acea.auto"],
           "le communiqué de presse mensuel de l'ACEA sur les immatriculations de voitures neuves dans l'Union européenne, "
           "l'AELE et le Royaume-Uni (chiffres cumulés depuis le début de l'année)"),
    "DE": ("Allemagne", ["kba.de"],
           "le communiqué de presse mensuel du Kraftfahrt-Bundesamt (KBA) sur les Neuzulassungen de voitures particulières (Pkw)"),
    "IT": ("Italie", ["unrae.it"],
           "le dernier communiqué mensuel de l'UNRAE sur les immatricolazioni d'autovetture en Italie"),
    "ES": ("Espagne", ["anfac.com"],
           "le dernier communiqué mensuel de l'ANFAC sur les matriculaciones de turismos en Espagne"),
    "GB": ("Royaume-Uni", ["smmt.co.uk"],
           "le dernier communiqué mensuel de la SMMT sur les new car registrations au Royaume-Uni"),
}

PROMPT = """Nous sommes le {date}. Trouve {consigne}.
Utilise web_search puis web_fetch, uniquement sur le domaine {domaines}. Récupère les {n} derniers mois publiés
(le plus récent d'abord) et rends UNIQUEMENT un objet JSON, sans texte autour :
{{"releves":[{{"periode":"AAAA-MM","total":<entier ou null>,"yoy_pct":<nombre ou null>,"electrique_pct":<nombre ou null>,
"source_url":"<URL exacte de la page lue>","citation":"<phrase exacte de la page qui contient le chiffre>"}}]}}
Règles : « periode » est le mois de l'immatriculation (pas la date de publication) ; « total » = immatriculations de
voitures particulières neuves du mois ; « yoy_pct » = évolution vs même mois de l'année précédente en % ;
« electrique_pct » = part des voitures 100 % électriques (batterie) en %. Mets null pour toute valeur absente de la page :
n'estime jamais, ne calcule jamais, ne complète pas de mémoire. Pas de relevé sans « source_url » et « citation »."""


class Refus(Exception):
    pass


# ---------------------------------------------------------------- validation (pure, testée)

def periode_valide(p):
    return isinstance(p, str) and re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", p) is not None


def valide_releve(r, domaines, serie, aujourdhui=None):
    """Lève Refus avec la raison, sinon renvoie un relevé normalisé.
    serie : relevés déjà publiés pour ce marché (liste de {month,total,...}), pour la cohérence."""
    if not isinstance(r, dict):
        raise Refus("relevé illisible")
    p = r.get("periode")
    if not periode_valide(p):
        raise Refus(f"période invalide ({p!r})")
    auj = aujourdhui or datetime.now(timezone.utc).date()
    if p > auj.strftime("%Y-%m"):
        raise Refus(f"période dans le futur ({p})")
    url = r.get("source_url") or ""
    hote = (urlparse(url).hostname or "").lower()
    if not any(hote == d or hote.endswith("." + d) for d in domaines):
        raise Refus(f"source hors domaine autorisé ({url or 'vide'})")
    if not (r.get("citation") or "").strip():
        raise Refus("aucune citation de la page")
    out = {"month": p, "source_url": url}
    total = r.get("total")
    if total is not None:
        if not isinstance(total, (int, float)) or isinstance(total, bool) or not (5_000 <= total <= 5_000_000):
            raise Refus(f"total hors plage ({total!r})")
        out["total"] = int(total)
    for cle, sortie, lo, hi in (("yoy_pct", "yoy_pct", -80, 150), ("electrique_pct", "electric_pct", 0, 100)):
        v = r.get(cle)
        if v is None:
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not (lo <= v <= hi):
            raise Refus(f"{cle} hors plage ({v!r})")
        out[sortie] = round(float(v), 1)
    if "total" not in out and "yoy_pct" not in out and "electric_pct" not in out:
        raise Refus("aucun chiffre exploitable")
    # cohérence avec la série : un total qui change d'un facteur > 3 d'un mois sur l'autre est suspect
    voisins = [s for s in serie if s.get("total") and s.get("month") != p]
    if "total" in out and voisins:
        proche = min(voisins, key=lambda s: abs(_mois_idx(s["month"]) - _mois_idx(p)))
        if abs(_mois_idx(proche["month"]) - _mois_idx(p)) <= 3:
            rap = out["total"] / proche["total"]
            if rap > 3 or rap < 1 / 3:
                raise Refus(f"total incohérent avec {proche['month']} ({out['total']} vs {proche['total']})")
    return out


def _mois_idx(m):
    return int(m[:4]) * 12 + int(m[5:7])


def fusionne_mensuel(serie, nouveaux):
    """Ajoute les mois absents, met à jour un mois existant si les chiffres diffèrent (révision), garde le tri.
    Renvoie (serie, journal)."""
    par_mois = {s["month"]: dict(s) for s in serie}
    journal = []
    for n in nouveaux:
        m = n["month"]
        if m not in par_mois:
            par_mois[m] = n
            journal.append(f"+ {m}")
        else:
            ancien = par_mois[m]
            fusion = {**ancien, **n}   # un champ null dans le nouveau relevé ne supprime jamais un chiffre connu
            if fusion != ancien:
                par_mois[m] = fusion
                journal.append(f"~ {m} (révisé)")
    return [par_mois[m] for m in sorted(par_mois)], journal


def fusionne_europe(periodes, nouveaux):
    """periods_2026 : une entrée par mois de cumul, libellé « Mois AAAA (cumul annuel) »."""
    par_label = {p["label"]: dict(p) for p in periodes}
    journal = []
    for n in nouveaux:
        y, m = n["month"].split("-")
        label = f"{MOIS_FR[int(m) - 1].capitalize()} {y} (cumul annuel)"
        entree = {"label": label, "source_url": n["source_url"]}
        for k in ("yoy_pct", "electric_pct"):
            if k in n:
                entree[k] = n[k]
        if "yoy_pct" not in entree:
            continue   # une entrée sans évolution n'a pas de sens pour ce bloc
        if label not in par_label:
            par_label[label] = entree
            journal.append(f"+ {label}")
        elif {**par_label[label], **entree} != par_label[label]:
            par_label[label] = {**par_label[label], **entree}
            journal.append(f"~ {label} (révisé)")
    ordre = sorted(par_label.values(), key=lambda p: _idx_label(p["label"]))
    return ordre, journal


def _idx_label(label):
    mot, annee = label.split(" ")[0].lower(), re.search(r"20\d{2}", label)
    mois = MOIS_FR.index(mot) + 1 if mot in MOIS_FR else 0
    return int(annee.group(0)) * 12 + mois if annee else 0


def applique(market, resultats):
    """resultats : {id: [relevés validés]} -> market mis à jour (copie) + journal {id: [...]}."""
    m = json.loads(json.dumps(market))
    journal = {}
    for sid, releves in resultats.items():
        if not releves:
            continue
        if sid == "FR":
            m["france"]["monthly"], j = fusionne_mensuel(m["france"].get("monthly", []), releves)
            if m["france"].get("monthly_source") is None and releves:
                m["france"]["monthly_source"] = "AAA DATA"
        elif sid == "EU":
            m["europe"]["periods_2026"], j = fusionne_europe(m["europe"].get("periods_2026", []), releves)
        else:
            bloc = m.setdefault("markets", {}).setdefault(sid, {"name": SOURCES[sid][0], "monthly": []})
            bloc["monthly"], j = fusionne_mensuel(bloc.get("monthly", []), releves)
        if j:
            journal[sid] = j
    if journal:
        m["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return m, journal


# ---------------------------------------------------------------- collecte

def _appel(prompt, domaines, cle):
    outils = [
        {"type": "web_search_20250305", "name": "web_search", "max_uses": 4, "allowed_domains": domaines},
        {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 4, "allowed_domains": domaines,
         "max_content_tokens": 30000},
    ]
    entetes = {"x-api-key": cle, "anthropic-version": "2023-06-01", "anthropic-beta": "web-fetch-2025-09-10",
               "content-type": "application/json"}
    messages = [{"role": "user", "content": prompt}]
    for _ in range(5):   # pause_turn : le serveur rend la main, on relance avec le tour déjà produit
        r = httpx.post(API, headers=entetes, timeout=300,
                       json={"model": MODELE, "max_tokens": 4096, "tools": outils, "messages": messages})
        if r.status_code >= 400:
            raise Refus(f"API {r.status_code} : {r.text[:300]}")
        d = r.json()
        if d.get("stop_reason") != "pause_turn":
            return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        messages = messages + [{"role": "assistant", "content": d["content"]}]
    raise Refus("trop de tours de pause")


def extrait_json(texte):
    m = re.search(r"\{.*\}", texte, re.S)
    if not m:
        raise Refus("aucun JSON dans la réponse")
    try:
        return json.loads(m.group(0))
    except ValueError as e:
        raise Refus(f"JSON illisible ({e})")


def collecte(sid, market, cle, n=6):
    nom, domaines, consigne = SOURCES[sid]
    prompt = PROMPT.format(date=datetime.now(timezone.utc).strftime("%d/%m/%Y"), consigne=consigne,
                           domaines=", ".join(domaines), n=n)
    brut = extrait_json(_appel(prompt, domaines, cle))
    if sid == "FR":
        serie = market.get("france", {}).get("monthly", [])
    elif sid == "EU":
        serie = []
    else:
        serie = market.get("markets", {}).get(sid, {}).get("monthly", [])
    valides, refus = [], []
    for r in brut.get("releves", []):
        try:
            valides.append(valide_releve(r, domaines, serie))
        except Refus as e:
            refus.append(f"{r.get('periode') if isinstance(r, dict) else '?'} : {e}")
    return valides, refus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sources", nargs="*", choices=sorted(SOURCES), help="par défaut : toutes")
    a = ap.parse_args()

    cle = os.environ.get("ANTHROPIC_API_KEY")
    if not cle:
        print("ANTHROPIC_API_KEY manquante", file=sys.stderr)
        return 2
    if not FICHIER.exists():
        print(f"{FICHIER} introuvable (repo de données non récupéré ?)", file=sys.stderr)
        return 2
    market = json.loads(FICHIER.read_text(encoding="utf-8"))

    resultats, echecs = {}, []
    for sid in (a.sources or list(SOURCES)):
        try:
            valides, refus = collecte(sid, market, cle)
        except Exception as e:
            echecs.append(sid)
            print(f"{sid} : ÉCHEC collecte ({type(e).__name__}: {e}) — série existante conservée")
            continue
        for r in refus:
            print(f"{sid} : relevé refusé — {r}")
        print(f"{sid} : {len(valides)} relevé(s) valide(s)" + (f" ({valides[0]['month']}…)" if valides else ""))
        if valides:
            resultats[sid] = valides

    nouveau, journal = applique(market, resultats)
    for sid, lignes in journal.items():
        print(f"{sid} : " + ", ".join(lignes))
    if not journal:
        print("Aucun changement.")
    if a.dry_run or not journal:
        return 1 if echecs and len(echecs) == len(a.sources or SOURCES) else 0

    FICHIER.write_text(json.dumps(nouveau, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from pipeline.build import _commit_et_pousse, _configure_git
    _configure_git()
    ok, detail = _commit_et_pousse(["data/market.json"], "Marché automobile : mise à jour mensuelle (" + ", ".join(sorted(journal)) + ")")
    if not ok:
        print(f"ECHEC commit/push ({detail})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
