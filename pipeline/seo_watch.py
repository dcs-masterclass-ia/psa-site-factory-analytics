"""Veille SEO quotidienne (workflow seo-watch.yml) : une card Teams PAR SITE quand sa visibilité Google baisse ou qu'un souci technique
l'explique. Même esprit que la veille des leads : des seuils qui s'adaptent à chaque site, une cause probable calculée, pas de bruit.

Données (Converge, data/<site>.json + data/indexation.json) :
  - clics et impressions Google par jour (Search Console), sessions « Organic Search » GA4, date de bascule V2.
Déclenchement ADAPTATIF (par site, par indicateur) : la semaine écoulée (7 derniers jours connus) est comparée à la médiane des 8 semaines
précédentes ; l'écart est exprimé en écarts-types (le bruit normal du site : max(√volume, variabilité réelle des semaines passées)).
Alerte à z ≤ -3 ET baisse ≥ 20 % ET perte absolue minimale ; « forte baisse » à z ≤ -5 ou -50 %. Un petit site au trafic irrégulier ne
déclenche pas pour trois clics de moins ; un gros site qui perd 20 % déclenche.
Cause probable (par ordre de confiance) : (1) les pages qui perdent le plus de clics répondent mal en direct (redirection sans destination,
404, noindex, canonique) ; (2) rupture datée proche de la bascule V2 ; (3) perte de positions vs baisse du CTR (Search Console) ;
(4) baisse partagée par la majorité des sites du même pays (marché / algorithme) plutôt que propre au site.
Souci technique, contrôlé en direct sur l'accueil et les pages les plus cliquées : redirection sans destination (301 sans Location),
erreur HTTP, noindex, canonique ailleurs, redirection hors domaine, robots.txt bloquant, sitemap introuvable, erreurs d'indexation Search Console.
Une card par site (trafic + technique + cause + actions), re-notifiée seulement si ça s'aggrave ou si un NOUVEAU problème critique apparaît ;
une card « rétabli » quand tout redevient normal. Sortie console sobre (dépôt public : aucun chiffre métier).
Variables : SEO_TEAMS_WEBHOOK_URL, GOOGLE_APPLICATION_CREDENTIALS (Search Console), SEO_STATE (état, cache du workflow),
SEO_DRY=1 (calcule sans envoyer, affiche un résumé), SEO_Z / SEO_PCT_MIN (seuils).
"""
import json
import math
import os
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from pipeline import sites

DATA = Path(__file__).resolve().parent.parent / "data"
DRY = os.environ.get("SEO_DRY") == "1"
CHEMIN_ETAT = os.environ.get("SEO_STATE", "seo_state.json")
URL_DASHBOARD = "https://converge-tradein.vercel.app/"

Z_BAISSE = float(os.environ.get("SEO_Z", "3"))                  # écarts-types sous la normale du site
Z_FORTE = float(os.environ.get("SEO_Z_FORTE", "5"))
PCT_MIN = float(os.environ.get("SEO_PCT_MIN", "20"))            # baisse minimale en %
PCT_FORTE = 50.0
SEMAINES_REF = 8                                                  # semaines de référence
# (référence hebdo minimale, perte absolue minimale) par indicateur
MINIS = {"clics": (40, 20), "impr": (800, 300), "orga": (100, 40)}
RENOTIF_Z = 2.0                                                   # nouvelle card si le z s'aggrave de
RENOTIF_PCT = 15.0
PAGES_CONTROLEES = int(os.environ.get("SEO_PAGES", "6"))
MAX_CARTES = int(os.environ.get("SEO_MAX_CARTES", "40"))
IGNORES = re.compile(r"/(error[_-]?\d*|_preview|config|qr-code|__)(/|$)", re.I)      # pages techniques : jamais des pages à référencer
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
CRITIQUES = {"redirection_cassee", "indexation_redirection", "http", "injoignable", "robots", "sitemap", "canonique", "redirection"}


# ------------------------------------------------------------------ 1. trafic SEO : seuils adaptatifs

def _hebdos(valeurs, fin, n=SEMAINES_REF + 1):
    """Sommes de 7 jours consécutifs finissant à l'indice `fin`, puis 7 jours avant, etc. (la plus récente en premier)."""
    out = []
    for k in range(n):
        b = fin - 7 * k
        if b - 6 < 0:
            break
        out.append(sum(x or 0 for x in valeurs[b - 6:b + 1]))
    return out


def evalue(hebdos, cle):
    """{vu, ref, z, pct} si la semaine écoulée est anormalement basse pour ce site, sinon None (ou mesure sans alerte si return_all)."""
    if len(hebdos) < 6:
        return None
    vu, prev = hebdos[0], hebdos[1:]
    ref = statistics.median(prev)
    ref_min, perte_min = MINIS[cle]
    if ref < ref_min:
        return None
    sd = max(math.sqrt(ref), statistics.pstdev(prev))
    z = (vu - ref) / sd
    pct = (vu - ref) / ref * 100
    return {"vu": vu, "ref": ref, "z": z, "pct": pct, "alerte": z <= -Z_BAISSE and pct <= -PCT_MIN and ref - vu >= perte_min,
            "forte": z <= -Z_FORTE or pct <= -PCT_FORTE}


def mesure_site(slug):
    try:
        d = json.load(open(DATA / f"{slug}.json", encoding="utf-8"))
    except Exception:
        return None
    dl = d.get("daily") or {}
    sc, si, ds = dl.get("sc"), dl.get("si"), dl.get("d")
    if not sc or len(sc) < 60:
        return None
    last = max((i for i, v in enumerate(sc) if v is not None), default=None)
    if last is None or last < 60:
        return None
    m = {"slug": slug, "ds": ds, "sc": sc, "si": si, "last": last, "dernier_jour": ds[last], "v2": d.get("v2_date"),
         "propriete": d.get("gscProperty"), "ind": {}}
    m["ind"]["clics"] = evalue(_hebdos(sc, last), "clics")
    m["ind"]["impr"] = evalue(_hebdos(si, last), "impr")
    jours = {}
    for mois in (d.get("canalQuotidien") or {}).values():
        for j, c in mois.items():
            jours[j] = c.get("Organic Search", 0)
    if len(jours) >= 60:
        fin = max(jours)
        d0 = date.fromisoformat(fin)
        serie = [jours.get((d0 - timedelta(days=55 - i)).isoformat(), 0) for i in range(56)]
        m["ind"]["orga"] = evalue(_hebdos(serie, 55), "orga")
        m["orga_jour"] = fin
    return m


def rupture(m):
    """Premier jour (sur 3 semaines) où la moyenne sur 3 jours s'effondre durablement par rapport à la semaine d'avant."""
    sc, ds, last = m["sc"], m["ds"], m["last"]
    for d in range(max(8, last - 20), last - 1):
        avant = [x or 0 for x in sc[d - 7:d]]
        apres = [x or 0 for x in sc[d:d + 3]]
        reste = [x or 0 for x in sc[d:last + 1]]
        mb = sum(avant) / 7
        if mb >= 4 and sum(apres) / 3 <= 0.6 * mb and sum(reste) / len(reste) <= 0.7 * mb:
            return ds[d]
    return None


def evolution_v2(m):
    if not m.get("v2") or m["v2"] not in m["ds"]:
        return None
    iv = m["ds"].index(m["v2"])
    apres = [x for x in m["sc"][iv:m["last"] + 1] if x is not None]
    avant = [x for x in m["sc"][max(0, iv - 28):iv] if x is not None]
    if len(apres) < 5 or len(avant) < 14 or not sum(avant):
        return None
    mv = sum(apres) / len(apres)
    ma = sum(avant) / len(avant)
    return {"jours": len(apres), "pct": (mv - ma) / ma * 100}


def details_gsc(m):
    """Search Console en direct (sites en alerte seulement) : position moyenne, pages et requêtes qui perdent le plus."""
    if not m.get("propriete") or not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return {}
    try:
        from pipeline import search_console as sc
        cli = sc.client()
        fin = date.fromisoformat(m["dernier_jour"])
        fa, da = str(fin), str(fin - timedelta(days=6))
        fb, db = str(fin - timedelta(days=7)), str(fin - timedelta(days=34))
        ta, tb = sc.total_periode(cli, m["propriete"], da, fa), sc.total_periode(cli, m["propriete"], db, fb)
        pa = {r["page"]: r["clics"] for r in sc.top_pages(cli, m["propriete"], da, fa, 300)}
        pb = {r["page"]: r["clics"] / 4 for r in sc.top_pages(cli, m["propriete"], db, fb, 300)}
        qa = {r["requete"]: r["clics"] for r in sc.top_requetes(cli, m["propriete"], da, fa, 300)}
        qb = {r["requete"]: r["clics"] / 4 for r in sc.top_requetes(cli, m["propriete"], db, fb, 300)}
    except Exception:
        return {}
    pertes = sorted(((u, pb[u], pa.get(u, 0)) for u in pb), key=lambda x: x[2] - x[1])
    req = sorted(((q, qb[q], qa.get(q, 0)) for q in qb), key=lambda x: x[2] - x[1])
    return {"pos_a": ta["position"], "pos_b": tb["position"], "ctr_a": ta["ctr"], "ctr_b": tb["ctr"],
            "pages": [(u, r, v) for u, r, v in pertes if r - v >= 5][:3], "requetes": [(q, r, v) for q, r, v in req if r - v >= 4][:3]}


def diagnostic(site, m, det, contexte_pays):
    """Cause probable calculée : [(titre, détail)] du plus au moins probable, et actions conseillées."""
    causes, actions = [], []
    # 1. pages perdues -> état en direct
    for u, ref, vu in det.get("pages", []):
        pb = [x for x in inspecte_page(u) if x[0] in CRITIQUES or x[0] == "noindex"]
        det.setdefault("pages_etat", {})[u] = pb
        if pb and not any(c[0] == "tech" for c in causes):
            causes.append(("tech", f"La page {urlparse(u).path or '/'} (la plus touchée : {ref:.0f} → {vu:.0f} clics/sem) répond aujourd'hui : {pb[0][1]}."))
            if pb[0][0] == "redirection_cassee":
                actions.append("Faire corriger la réponse serveur de ces pages : un 200 (ou une vraie redirection avec destination), puis purger le cache CDN (réponse gardée 1 an).")
            elif pb[0][0] == "http":
                actions.append("Rétablir la page, ou rediriger l'ancienne adresse vers la nouvelle (301 avec destination).")
            elif pb[0][0] == "noindex":
                actions.append("Retirer le noindex de ces pages si elles doivent être référencées.")
            elif pb[0][0] == "canonique":
                actions.append("Corriger l'adresse canonique de ces pages.")
    # 2. rupture datée
    r = rupture(m)
    if r:
        txt = f"Chute datée du {datetime.fromisoformat(r).strftime('%d/%m')}"
        if m.get("v2"):
            ecart = (datetime.fromisoformat(r) - datetime.fromisoformat(m["v2"])).days
            if -3 <= ecart <= 5:
                txt += f", {abs(ecart)} jour(s) {'après' if ecart >= 0 else 'avant'} la bascule V2 ({datetime.fromisoformat(m['v2']).strftime('%d/%m')})"
                causes.append(("v2", txt + " : très probablement liée à la mise en production."))
                actions.append("Comparer l'ancienne et la nouvelle version : adresses des pages, balises title/H1, canoniques, robots.txt, sitemap, redirections 301.")
            else:
                causes.append(("rupture", txt + "."))
        else:
            causes.append(("rupture", txt + "."))
    # 3. positions vs CTR
    if det.get("pos_b"):
        dpos = det["pos_a"] - det["pos_b"]
        ind = m["ind"].get("impr")
        if dpos >= 3 and ind and ind["pct"] <= -20:
            causes.append(("positions", f"Perte de positions : position moyenne {det['pos_b']:.1f} → {det['pos_a']:.1f}, et impressions {ind['pct']:+.0f} %."))
            actions.append("Vérifier que le contenu, les titres et les pages indexées n'ont pas été dégradés ; regarder les pages et requêtes perdues ci-dessous.")
        elif det.get("ctr_b") and det["ctr_a"] <= det["ctr_b"] * 0.75 and (not ind or ind["pct"] > -20):
            causes.append(("ctr", f"Les impressions tiennent mais le taux de clic baisse ({det['ctr_b']:.1f} % → {det['ctr_a']:.1f} %) : titres ou descriptions moins attractifs."))
            actions.append("Revoir les balises title et description des pages d'entrée.")
    # 4. contexte pays
    n, tot = contexte_pays.get(site.pays, (0, 0))
    if tot >= 4 and n / tot >= 0.6:
        causes.append(("marche", f"{n} sites sur {tot} du marché {site.pays} baissent en même temps : effet de marché ou de Google plutôt que propre à ce site."))
    elif tot >= 4 and n <= 1:
        causes.append(("site", f"Propre à ce site : les autres sites du marché {site.pays} ne baissent pas."))
    if not causes:
        causes.append(("inconnue", "Cause non déterminée automatiquement : voir les pages et requêtes qui perdent le plus."))
    return causes, list(dict.fromkeys(actions))


# ------------------------------------------------------------------ 2. souci technique (contrôle en direct)

def _norm(u):
    p = urlparse(u)
    return (p.hostname or "").lower().removeprefix("www."), (p.path or "/").rstrip("/").lower() or "/"


def inspecte_page(url):
    """Liste de problèmes [(code, détail)] pour une page ; [] si tout va bien ou si la page est protégée (WAF)."""
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8"}, timeout=20, allow_redirects=True)
    except Exception:
        return [("injoignable", "la page ne répond pas")]
    if r.status_code == 403:
        return []                                                  # WAF : non vérifiable, pas une panne
    pb = []
    if 300 <= r.status_code < 400:
        # statut « redirigée » sans destination exploitable : un navigateur affiche le corps, Googlebot y voit une erreur de redirection
        return [("redirection_cassee", f"HTTP {r.status_code} sans adresse de destination (en-tête Location absent)")]
    if r.status_code >= 400:
        return [("http", f"erreur HTTP {r.status_code}")]
    if "html" not in (r.headers.get("content-type") or "").lower():
        return []
    if _norm(r.url)[0] != _norm(url)[0]:
        pb.append(("redirection", f"redirigée vers un autre domaine ({urlparse(r.url).hostname})"))
    html = r.text[:400000]
    xr = (r.headers.get("x-robots-tag") or "").lower()
    meta = re.findall(r"<meta\b[^>]*name=[\"'](?:robots|googlebot)[\"'][^>]*>", html, re.I)
    if "noindex" in xr or any("noindex" in t.lower() for t in meta):
        pb.append(("noindex", "page en noindex : Google ne l'indexe pas"))
    m = re.search(r"<link\b[^>]*rel=[\"']canonical[\"'][^>]*>", html, re.I)
    if m:
        h = re.search(r"href=[\"']([^\"']+)[\"']", m.group(0), re.I)
        if h:
            canon = urljoin(r.url, h.group(1))
            if _norm(canon) != _norm(r.url):
                meme_chemin = _norm(canon)[1] == _norm(r.url)[1]
                pb.append(("canonique_domaine" if meme_chemin else "canonique",
                           f"canonique pointant vers {urlparse(canon).path or '/'} ({urlparse(canon).hostname})"))
    return pb


def inspecte_site(nom, hote, pages):
    """Problèmes du site : robots.txt, sitemap, puis accueil + pages les plus cliquées."""
    base = f"https://{hote}"
    out = []
    try:
        rb = requests.get(f"{base}/robots.txt", headers={"User-Agent": UA}, timeout=15)
        if rb.status_code == 200 and "html" not in (rb.headers.get("content-type") or "").lower():
            txt, ua_etoile, bloque = rb.text, False, False
            for lig in txt.splitlines():
                l = lig.split("#")[0].strip().lower()
                if l.startswith("user-agent:"):
                    ua_etoile = l.split(":", 1)[1].strip() == "*"
                elif ua_etoile and re.fullmatch(r"disallow:\s*/", l):
                    bloque = True
            if bloque:
                out.append((f"{base}/robots.txt", "robots", "le robots.txt interdit l'exploration de tout le site (Disallow: /)"))
            for sm in re.findall(r"(?im)^sitemap:\s*(\S+)", txt)[:2]:
                try:
                    s = requests.get(sm, headers={"User-Agent": UA}, timeout=15)
                    if s.status_code in (404, 410) or s.status_code >= 500:
                        out.append((sm, "sitemap", f"sitemap introuvable (HTTP {s.status_code})"))
                except Exception:
                    pass
    except Exception:
        pass
    vus = []
    for u in [f"{base}/"] + [x for x in pages if not IGNORES.search(urlparse(x).path)]:
        if u in vus or len(vus) >= PAGES_CONTROLEES:
            continue
        vus.append(u)
        for code, det in inspecte_page(u):
            out.append((u, code, det))
    return [{"url": u, "code": c, "detail": d} for u, c, d in out]


def pages_indexation(nom):
    try:
        i = json.load(open(DATA / "indexation.json", encoding="utf-8"))
    except Exception:
        return [], []
    e = (i.get("sites") or {}).get(nom) or {}
    pages = [p["url"] for p in e.get("pages", []) if p.get("url")]
    non_idx = [(p["url"], p.get("etat") or p.get("verdict")) for p in e.get("pages", [])
               if p.get("verdict") and p["verdict"] != "PASS" and not IGNORES.search(urlparse(p["url"]).path)]
    return pages, non_idx


# ------------------------------------------------------------------ cartes Teams (une par site)

def _tb(t, **k):
    return {"type": "TextBlock", "text": t, "wrap": True, **k}


def _fmt(n):
    return f"{round(n):,}".replace(",", " ")


def _d(j):
    return datetime.fromisoformat(j).strftime("%d/%m")


LIB_PB = {"redirection_cassee": "Redirection sans destination", "indexation_redirection": "Erreur de redirection (Google)", "http": "Page en erreur",
          "injoignable": "Page injoignable", "noindex": "noindex", "canonique": "Canonique ailleurs", "canonique_domaine": "Canonique sur un autre domaine", "redirection": "Redirection hors domaine",
          "robots": "robots.txt bloquant", "sitemap": "Sitemap introuvable", "indexation": "Non indexée"}
ORDRE_PB = ["redirection_cassee", "indexation_redirection", "http", "robots", "sitemap", "canonique", "redirection", "injoignable", "canonique_domaine", "noindex", "indexation"]
NOM_IND = {"clics": "Clics Google", "impr": "Impressions Google", "orga": "Sessions organiques GA4"}


def carte_site(site, m, ind_alertes, det, causes, actions, pbs, nouveaux_crit):
    trafic, tech = bool(ind_alertes), bool(pbs and (nouveaux_crit or not trafic))
    forte = any(i["forte"] for i in ind_alertes.values())
    emoji = "📉" if trafic else "🛠️"
    if trafic and tech:
        emoji = "📉🛠️"
    titre = (f"{emoji} SEO — {site.nom} : " + ("visibilité Google en forte baisse" if forte else "visibilité Google en baisse") if trafic
             else f"{emoji} SEO — {site.nom} : souci technique")
    corps = [_tb(titre, weight="Bolder", size="Medium", color="Attention")]
    if trafic:
        facts = []
        for cle in ("clics", "impr", "orga"):
            i = (m["ind"].get(cle) or {})
            if i:
                marque = " ⚠️" if cle in ind_alertes else ""
                facts.append({"title": NOM_IND[cle], "value": f"{_fmt(i['vu'])} sur 7 j vs {_fmt(i['ref'])} en médiane ({i['pct']:+.0f} %){marque}"})
        if det.get("pos_b"):
            facts.append({"title": "Position moyenne", "value": f"{det['pos_b']:.1f} → {det['pos_a']:.1f}"})
        ev = evolution_v2(m)
        if ev:
            facts.append({"title": f"Depuis la V2 ({_d(m['v2'])})", "value": f"clics par jour {ev['pct']:+.0f} % vs les 28 jours avant ({ev['jours']} jours)"})
        facts.append({"title": "Données", "value": f"Search Console jusqu'au {_d(m['dernier_jour'])} (2 à 3 jours de décalage)"})
        corps.append({"type": "FactSet", "facts": facts})
        corps.append(_tb("Cause probable", weight="Bolder", spacing="Medium"))
        for _, txt in causes[:3]:
            corps.append(_tb("• " + txt, spacing="None"))
        if det.get("pages"):
            corps.append(_tb("Pages qui perdent le plus de clics (par semaine)", weight="Bolder", spacing="Medium"))
            for u, ref, vu in det["pages"]:
                etat = det.get("pages_etat", {}).get(u) or []
                corps.append(_tb(f"• {urlparse(u).path or '/'} : {_fmt(ref)} → {_fmt(vu)}" + (f" — {etat[0][1]}" if etat else ""), size="Small", spacing="None"))
        if det.get("requetes"):
            corps.append(_tb("Requêtes qui perdent le plus : " + " · ".join(f"« {q} » ({_fmt(r)} → {_fmt(v)})" for q, r, v in det["requetes"]),
                             size="Small", isSubtle=True, spacing="Small"))
    if pbs:
        corps.append(_tb("Problèmes techniques détectés", weight="Bolder", spacing="Medium"))
        triees = sorted(pbs, key=lambda x: ORDRE_PB.index(x["code"]) if x["code"] in ORDRE_PB else 99)
        for pb in triees[:6]:
            corps.append(_tb(f"• {LIB_PB.get(pb['code'], pb['code'])} — {urlparse(pb['url']).path or '/'} : {pb['detail']}", size="Small", spacing="None"))
        if len(triees) > 6:
            corps.append(_tb(f"+ {len(triees) - 6} autre(s)", size="Small", isSubtle=True, spacing="None"))
        if not actions and any(x["code"] == "redirection_cassee" for x in pbs):
            actions = ["Faire corriger la réponse serveur de ces pages : un 200 (ou une vraie redirection avec destination), puis purger le cache CDN (réponse gardée 1 an)."]
    if actions:
        corps.append(_tb("À faire", weight="Bolder", spacing="Medium"))
        for a in actions[:3]:
            corps.append(_tb("• " + a, spacing="None"))
    return {"type": "message", "summary": titre, "text": titre, "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "fallbackText": titre,
        "body": corps, "actions": [{"type": "Action.OpenUrl", "title": "Voir le dashboard", "url": URL_DASHBOARD}]}}]}


def carte_retabli(site, trafic, tech):
    quoi = " et ".join(x for x in ("la visibilité Google est revenue à un niveau normal" if trafic else "", "les problèmes techniques signalés sont corrigés" if tech else "") if x)
    titre = f"✅ SEO — {site.nom} : rétabli"
    return {"type": "message", "summary": titre, "text": titre, "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "fallbackText": titre,
        "body": [_tb(titre, weight="Bolder", size="Medium", color="Good"), _tb(f"Sur {site.nom} : {quoi}.")]}}]}


def envoie(payload, webhook):
    if DRY:
        print(json.dumps(payload, ensure_ascii=False, indent=1)[:6000])
        return True
    for essai in range(3):
        try:
            r = requests.post(webhook, json=payload, timeout=20)
            if r.status_code in (200, 202):
                return True
        except Exception:
            pass
    return False


# ------------------------------------------------------------------ principal

def main():
    webhook = os.environ.get("SEO_TEAMS_WEBHOOK_URL", "")
    if not webhook and not DRY:
        print("SEO_TEAMS_WEBHOOK_URL absent : aucune alerte ne peut partir.")
        sys.exit(1)
    try:
        etat = json.load(open(CHEMIN_ETAT))
    except Exception:
        etat = {}
    if etat.get("version") != 2:                      # nouvelle logique (cards par site) : on repart d'un état propre
        etat = {"version": 2, "sites": {}}
    aujourd = date.today().isoformat()
    par_slug = {s.slug: s for s in sites.SITES}

    # --- 1. trafic (seuils adaptatifs) + contrôle technique en direct, tous les sites
    mesures = {s.slug: mesure_site(s.slug) for s in sites.SITES}
    en_alerte = {sl: m for sl, m in mesures.items() if m and any(i and i["alerte"] for i in m["ind"].values())}
    contexte = {}
    for pays in {s.pays for s in sites.SITES}:
        suivis = [sl for sl, m in mesures.items() if m and par_slug[sl].pays == pays and (m["ind"].get("clics") or m["ind"].get("impr"))]
        contexte[pays] = (len([sl for sl in suivis if sl in en_alerte]), len(suivis))

    def technique(s):
        if not s.hote_reprise:
            return s.slug, []
        pages, non_idx = pages_indexation(s.nom)
        try:
            pb = inspecte_site(s.nom, s.hote_reprise, pages)
        except Exception:
            pb = []
        for u, e in non_idx[:4]:
            pb.append({"url": u, "code": "indexation_redirection" if "redirection" in (e or "").lower() else "indexation",
                       "detail": f"page non indexée par Google ({e})"})
        pb.sort(key=lambda x: x["code"].startswith("indexation"))
        vus = set()
        return s.slug, [x for x in pb if not (x["code"].startswith("indexation") and x["url"] in vus) and (vus.add(x["url"]) or True)]

    with ThreadPoolExecutor(6) as ex:
        tech = dict(ex.map(technique, sites.SITES))

    # --- 2. décisions par site
    cartes = []                                        # (priorité, site, payload, slug, nouvel état)
    for s in sites.SITES:
        sl = s.slug
        m = mesures.get(sl)
        prev = etat["sites"].get(sl, {})
        pbs = tech.get(sl, [])
        cles_crit = sorted(f"{x['code']}|{x['url']}" for x in pbs if x["code"] in CRITIQUES)
        cles_toutes = sorted(f"{x['code']}|{x['url']}" for x in pbs)
        nouveaux_crit = [k for k in cles_crit if k not in prev.get("crit", [])]
        ind_alertes = {c: i for c, i in (m["ind"].items() if m else []) if i and i["alerte"]}
        pire = min((i["z"] for i in ind_alertes.values()), default=None)
        pct = min((i["pct"] for i in ind_alertes.values()), default=None)
        a_trafic = prev.get("trafic")
        # alerte trafic : nouvelle, ou aggravée
        envoyer_trafic = bool(ind_alertes) and (a_trafic is None or pire <= a_trafic["z"] - RENOTIF_Z or pct <= a_trafic["pct"] - RENOTIF_PCT)
        envoyer = envoyer_trafic or bool(nouveaux_crit)
        nouvel = {"crit": cles_crit, "tous": cles_toutes}
        if ind_alertes:
            nouvel["trafic"] = {"z": min(pire, a_trafic["z"]) if a_trafic and not envoyer_trafic else pire, "pct": pct, "jour": aujourd}
        if envoyer:
            det, causes, actions = {}, [], []
            if ind_alertes:
                det = details_gsc(m)
                causes, actions = diagnostic(s, m, det, contexte)
            payload = carte_site(s, m or {}, ind_alertes, det, causes, actions, pbs, nouveaux_crit)
            prio = (0 if any(i["forte"] for i in ind_alertes.values()) else 1 if ind_alertes else 2, pire or 0)
            cartes.append((prio, s, payload, sl, nouvel))
        else:
            retabli_trafic = bool(a_trafic) and not ind_alertes
            retabli_tech = bool(prev.get("crit")) and not cles_crit
            if retabli_trafic or retabli_tech:
                cartes.append(((3, 0), s, carte_retabli(s, retabli_trafic, retabli_tech), sl, nouvel))
            else:
                etat["sites"][sl] = {**nouvel, **({"trafic": a_trafic} if a_trafic and ind_alertes else {})}
    cartes.sort(key=lambda c: c[0])

    envoyees = {"alerte": 0, "retabli": 0}
    for prio, s, payload, sl, nouvel in cartes[:MAX_CARTES]:
        if DRY:
            t = payload["attachments"][0]["content"]["body"]
            print("\n=== " + t[0]["text"])
            for b in t[1:]:
                if b.get("text"):
                    print("   " + b["text"][:230])
                for f in b.get("facts", []):
                    print("   " + f["title"] + " : " + f["value"][:200])
            ok = True
        else:
            ok = envoie(payload, webhook)
            time.sleep(1.5)
        if ok:
            envoyees["retabli" if prio[0] == 3 else "alerte"] += 1
            etat["sites"][sl] = nouvel if prio[0] != 3 else {"crit": nouvel["crit"], "tous": nouvel["tous"]}
    json.dump(etat, open(CHEMIN_ETAT, "w"))
    print(f"{sum(1 for m in mesures.values() if m)} sites suivis, {len(tech)} contrôlés — cards : {envoyees['alerte']} alerte(s), {envoyees['retabli']} rétabli(s)")


if __name__ == "__main__":
    main()
