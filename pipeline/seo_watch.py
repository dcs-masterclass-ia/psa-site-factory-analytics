"""Veille SEO quotidienne (workflow seo-watch.yml) : le trafic Google baisse-t-il, un souci technique l'explique-t-il ?

Contexte : après la bascule des sites en V2 (FR 29-30/09, ES 06-07/10), la visibilité dans Google chute sur plusieurs sites sans
qu'aucun contrôle ne le signale (le site répond, le funnel marche). Deux familles de signaux, postées sur le canal Teams SEO :

1. Baisse de trafic SEO (données Converge déjà assemblées dans data/<site>.json, aucun appel supplémentaire) :
   - clics Google (Search Console) : 7 derniers jours connus vs moyenne hebdomadaire des 28 jours précédents ;
   - impressions Google : idem (une chute précède souvent celle des clics : désindexation, perte de positions) ;
   - sessions « Organic Search » GA4 : 3 derniers jours vs 14 jours précédents.
   Pour un site qui déclenche, les pages qui ont le plus perdu de clics sont relevées en direct dans Search Console.
2. Souci technique, contrôlé en direct sur la page d'accueil et les pages les plus cliquées (data/indexation.json) :
   erreur HTTP, noindex (balise ou en-tête), canonique pointant ailleurs, redirection vers un autre domaine,
   robots.txt qui bloque tout le site, sitemap introuvable. Une page protégée par un WAF (403) est ignorée, pas déclarée en panne.

Sortie console volontairement sobre (dépôt public : aucun chiffre métier dans les journaux d'Actions).
Variables : SEO_TEAMS_WEBHOOK_URL, GOOGLE_APPLICATION_CREDENTIALS (Search Console), SEO_STATE (état, cache du workflow),
SEO_DRY=1 (calcule sans envoyer et affiche le détail en local).
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from pipeline import sites

DATA = Path(__file__).resolve().parent.parent / "data"
DRY = os.environ.get("SEO_DRY") == "1"
CHEMIN_ETAT = os.environ.get("SEO_STATE", "seo_state.json")
URL_DASHBOARD = "https://psa-site-factory-analytics.vercel.app/"

CLICS_PCT = float(os.environ.get("SEO_CLICS_PCT", "25"))             # chute des clics (7 j vs moy. hebdo des 28 j), en %
CLICS_MIN = float(os.environ.get("SEO_CLICS_MIN", "50"))             # clics hebdo de référence au moins
IMPR_PCT = float(os.environ.get("SEO_IMPR_PCT", "30"))
IMPR_MIN = float(os.environ.get("SEO_IMPR_MIN", "1000"))
ORGA_PCT = float(os.environ.get("SEO_ORGA_PCT", "35"))               # chute des sessions organiques (3 j vs 14 j), en %
ORGA_MIN = float(os.environ.get("SEO_ORGA_MIN", "20"))               # sessions organiques / jour de référence au moins
RENOTIF_PTS = float(os.environ.get("SEO_RENOTIF_PTS", "15"))         # nouvelle alerte si la chute s'aggrave de
PAGES_CONTROLEES = int(os.environ.get("SEO_PAGES", "6"))             # accueil + pages les plus cliquées
IGNORES = re.compile(r"/(error[_-]?\d*|_preview|config|qr-code|__)(/|$)", re.I)      # pages techniques : jamais des pages à référencer
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


# ------------------------------------------------------------------ 1. baisse de trafic SEO

def _somme(v):
    return sum(x or 0 for x in v)


def mesure_trafic(slug):
    """Mesures du site depuis data/<slug>.json, ou None s'il n'a pas assez d'historique Search Console."""
    try:
        d = json.load(open(DATA / f"{slug}.json", encoding="utf-8"))
    except Exception:
        return None
    dl = d.get("daily") or {}
    sc, si, ds = dl.get("sc"), dl.get("si"), dl.get("d")
    if not sc or len(sc) < 40:
        return None
    last = max((i for i, v in enumerate(sc) if v is not None), default=None)
    if last is None or last < 35:
        return None
    a, b = _somme(sc[last - 6:last + 1]), _somme(sc[last - 34:last - 6]) / 4
    ia, ib = _somme(si[last - 6:last + 1]), _somme(si[last - 34:last - 6]) / 4
    r = {"slug": slug, "dernier_jour": ds[last], "clics": a, "clics_ref": b, "impr": ia, "impr_ref": ib,
         "v2": d.get("v2_date"), "propriete": d.get("gscProperty")}
    jours = {}
    for mois in (d.get("canalQuotidien") or {}).values():
        for j, c in mois.items():
            jours[j] = c.get("Organic Search", 0)
    js = sorted(jours)
    if len(js) >= 20:
        r["orga"], r["orga_ref"], r["orga_jour"] = sum(jours[j] for j in js[-3:]) / 3, sum(jours[j] for j in js[-17:-3]) / 14, js[-1]
    # depuis la V2 : clics par jour avant (28 j) / après
    if r["v2"] and r["v2"] in ds:
        iv = ds.index(r["v2"])
        apres = [x for x in sc[iv:last + 1] if x is not None]
        avant = [x for x in sc[max(0, iv - 28):iv] if x is not None]
        if len(apres) >= 5 and len(avant) >= 14:
            r["v2_jours"], r["v2_avant"], r["v2_apres"] = len(apres), sum(avant) / len(avant), sum(apres) / len(apres)
    return r


def baisse(vu, ref, pct, mini):
    return ref >= mini and vu <= ref * (1 - pct / 100)


def signaux_trafic(m):
    """Liste des chutes constatées : [(libellé, valeur, référence, % de variation)]."""
    out = []
    if baisse(m["clics"], m["clics_ref"], CLICS_PCT, CLICS_MIN):
        out.append(("Clics Google (7 j)", m["clics"], m["clics_ref"], (m["clics"] - m["clics_ref"]) / m["clics_ref"] * 100))
    if baisse(m["impr"], m["impr_ref"], IMPR_PCT, IMPR_MIN):
        out.append(("Impressions Google (7 j)", m["impr"], m["impr_ref"], (m["impr"] - m["impr_ref"]) / m["impr_ref"] * 100))
    if "orga" in m and baisse(m["orga"], m["orga_ref"], ORGA_PCT, ORGA_MIN):
        out.append(("Sessions organiques GA4 (3 j, par jour)", m["orga"], m["orga_ref"], (m["orga"] - m["orga_ref"]) / m["orga_ref"] * 100))
    return out


def pages_perdues(m):
    """Pages qui ont le plus perdu de clics (7 derniers jours connus vs 28 jours précédents, par semaine), en direct dans Search Console."""
    if not m.get("propriete") or not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return []
    try:
        from pipeline import search_console as sc
        cli = sc.client()
        fin = date.fromisoformat(m["dernier_jour"])
        a = {r["page"]: r["clics"] for r in sc.top_pages(cli, m["propriete"], str(fin - timedelta(days=6)), str(fin), 200)}
        b = {r["page"]: r["clics"] / 4 for r in sc.top_pages(cli, m["propriete"], str(fin - timedelta(days=34)), str(fin - timedelta(days=7)), 200)}
    except Exception:
        return []
    pertes = sorted(((p, b[p], a.get(p, 0)) for p in b), key=lambda x: x[2] - x[1])
    return [(p, ref, vu) for p, ref, vu in pertes if ref - vu >= 5][:3]


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
                pb.append(("canonique", f"canonique pointant vers {urlparse(canon).path or '/'} ({urlparse(canon).hostname})"))
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


# ------------------------------------------------------------------ cartes Teams

def _tb(t, **k):
    return {"type": "TextBlock", "text": t, "wrap": True, **k}


def _fmt(n):
    return f"{round(n):,}".replace(",", " ")


def _carte(titre, intro, blocs, bouton=True):
    corps = [_tb(titre, weight="Bolder", size="Medium"), _tb(intro, isSubtle=True, size="Small"), *blocs]
    c = {"type": "message", "summary": titre, "text": titre, "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4",
        "fallbackText": titre, "body": corps}}]}
    if bouton:
        c["attachments"][0]["content"]["actions"] = [{"type": "Action.OpenUrl", "title": "Voir le dashboard", "url": URL_DASHBOARD}]
    return c


def carte_trafic(items):
    blocs = []
    for nom, m, sig, pertes in sorted(items, key=lambda x: min(s[3] for s in x[2]))[:8]:
        l = [_tb(f"{nom}", weight="Bolder", color="Attention", spacing="None")]
        for lib, vu, ref, pct in sig:
            l.append(_tb(f"{lib} : {pct:+.0f} % ({_fmt(vu)} vs {_fmt(ref)} en moyenne)", size="Small", spacing="None"))
        if m.get("v2_jours"):
            dv = (m["v2_apres"] - m["v2_avant"]) / m["v2_avant"] * 100 if m["v2_avant"] else 0
            l.append(_tb(f"Depuis la bascule V2 ({datetime.fromisoformat(m['v2']).strftime('%d/%m')}, {m['v2_jours']} jours) : "
                         f"clics par jour {dv:+.0f} % vs les 28 jours avant", size="Small", isSubtle=True, spacing="None"))
        if pertes:
            l.append(_tb("Pages qui perdent le plus de clics : " + " · ".join(
                f"{urlparse(p).path or '/'} ({_fmt(ref)} → {_fmt(vu)}/sem)" for p, ref, vu in pertes), size="Small", isSubtle=True, spacing="None"))
        l.append(_tb(f"Données Search Console jusqu'au {datetime.fromisoformat(m['dernier_jour']).strftime('%d/%m')} (2 à 3 jours de décalage)",
                     size="Small", isSubtle=True, spacing="None"))
        blocs.append({"type": "Container", "spacing": "Medium", "separator": True, "items": l})
    if len(items) > 8:
        blocs.append(_tb(f"+ {len(items) - 8} autre(s) site(s) : " + ", ".join(i[0] for i in items[8:14]), isSubtle=True, size="Small"))
    titre = (f"📉 Trafic SEO en baisse — {items[0][0]}" if len(items) == 1 else f"📉 Trafic SEO en baisse sur {len(items)} sites")
    return _carte(titre, "La visibilité du site dans Google recule nettement par rapport aux semaines précédentes. "
                         "Une chute des impressions précède en général celle des clics (pages désindexées, positions perdues).", blocs)


LIBELLES = {
    "redirection_cassee": ("Redirection sans destination", "La page répond « redirigée » (301) sans dire vers où : le navigateur affiche la page, mais Googlebot "
                           "y voit une erreur et la retire de ses résultats."),
    "indexation_redirection": ("Erreur de redirection signalée par Google", "Search Console indique « Erreur liée à des redirections » : la page n'est pas indexée."),
    "http": ("Page en erreur (404 / 500…)", "Une page qui recevait des clics depuis Google ne répond plus correctement."),
    "injoignable": ("Page injoignable", "La page ne répond pas."),
    "noindex": ("Page en noindex", "Google n'indexe pas ces pages (balise ou en-tête noindex). Normal pour une étape de formulaire, anormal pour une page d'entrée."),
    "canonique": ("Canonique vers une autre page", "L'adresse canonique pointe ailleurs : Google risque de ne garder que l'autre page."),
    "redirection": ("Redirection vers un autre domaine", "La page est redirigée hors du site."),
    "robots": ("Exploration interdite (robots.txt)", "Le robots.txt interdit à Google d'explorer le site."),
    "sitemap": ("Sitemap introuvable", "Le sitemap déclaré dans le robots.txt ne répond pas."),
    "indexation": ("Pages non indexées", "Search Console indique que ces pages ne sont pas indexées."),
}
ORDRE = ["redirection_cassee", "indexation_redirection", "http", "robots", "sitemap", "canonique", "redirection", "injoignable", "noindex", "indexation"]


def carte_technique(items, premier=False):
    """items : [(site, pays, [problèmes])] -> un bloc par type de problème, avec répartition par pays et exemples."""
    groupes = {}
    for nom, pays, pbs in items:
        for pb in pbs:
            groupes.setdefault(pb["code"], []).append((nom, pays, pb))
    blocs = []
    for code in sorted(groupes, key=lambda c: ORDRE.index(c) if c in ORDRE else 99):
        g = groupes[code]
        lib, expl = LIBELLES.get(code, (code, ""))
        par_pays = {}
        for nom, pays, pb in g:
            par_pays[pays] = par_pays.get(pays, 0) + 1
        sites_n = len({n for n, _, _ in g})
        rep = " · ".join(f"{k} {v}" for k, v in sorted(par_pays.items(), key=lambda x: -x[1]))
        ex = []
        for nom, pays, pb in g[:3]:
            ex.append(f"{nom} : {urlparse(pb['url']).path or '/'}")
        blocs.append({"type": "Container", "spacing": "Medium", "separator": True, "items": [
            _tb(f"{lib} — {len(g)} page(s) sur {sites_n} site(s)", weight="Bolder", color="Attention", spacing="None"),
            _tb(expl, size="Small", isSubtle=True, spacing="None"),
            _tb(f"Pays : {rep}", size="Small", spacing="None"),
            _tb("Exemples : " + " · ".join(ex) + (" …" if len(g) > 3 else ""), size="Small", isSubtle=True, spacing="None")]})
    nb = sum(len(i[2]) for i in items)
    titre = ("🛠️ SEO — état des lieux technique des sites" if premier else
             (f"🛠️ Nouveau souci technique SEO — {items[0][0]}" if len(items) == 1 and nb == 1 else f"🛠️ Nouveaux soucis techniques SEO ({nb} sur {len(items)} sites)"))
    intro = ("Premier passage : état actuel des pages qui reçoivent du trafic depuis Google. Les prochaines cartes ne signaleront que les nouveaux problèmes."
             if premier else "Détectés lors du contrôle en direct de l'accueil et des pages les plus visitées depuis Google.")
    return _carte(titre, intro, blocs)


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
    etat.setdefault("trafic", {})
    etat.setdefault("tech", {})
    aujourd = date.today().isoformat()

    # --- 1. trafic
    mesures = [m for m in (mesure_trafic(s.slug) for s in sites.SITES) if m]
    noms = {s.slug: s.nom for s in sites.SITES}
    a_envoyer = []
    for m in mesures:
        sig = signaux_trafic(m)
        k = m["slug"]
        if not sig:
            etat["trafic"].pop(k, None)               # rétabli : on pourra ré-alerter
            continue
        pire = min(s[3] for s in sig)
        deja = etat["trafic"].get(k)
        if deja is None or pire <= deja["pire"] - RENOTIF_PTS:
            m["pertes"] = pages_perdues(m)
            a_envoyer.append((noms[k], m, sig, m["pertes"]))
            etat["trafic"][k] = {"pire": pire, "jour": aujourd}

    # --- 2. technique
    cibles = []
    for s in sites.SITES:
        if not s.hote_reprise:
            continue
        pages, non_idx = pages_indexation(s.nom)
        cibles.append((s, pages, non_idx))

    def controle(c):
        s, pages, non_idx = c
        try:
            pb = inspecte_site(s.nom, s.hote_reprise, pages)
        except Exception:
            pb = []
        for u, etat_idx in non_idx[:4]:
            code = "indexation_redirection" if "redirection" in (etat_idx or "").lower() else "indexation"
            pb.append({"url": u, "code": code, "detail": f"page non indexée par Google ({etat_idx})"})
        # une page déjà signalée par la vérification en direct n'est pas répétée par Search Console
        pb.sort(key=lambda x: x["code"].startswith("indexation"))
        vus_u = set()
        pb = [x for x in pb if not (x["code"].startswith("indexation") and x["url"] in vus_u) and (vus_u.add(x["url"]) or True)]
        return s.nom, s.pays, pb

    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(controle, cibles))
    tech = []
    premier = not etat["tech"]
    for nom, pays, pb in res:
        cles = {f"{p['code']}|{p['url']}" for p in pb}
        connus = set(etat["tech"].get(nom, []))
        nouveaux = [p for p in pb if f"{p['code']}|{p['url']}" not in connus]
        etat["tech"][nom] = sorted(cles)               # les problèmes disparus sortent de l'état : une récidive sera ré-annoncée
        if nouveaux:
            tech.append((nom, pays, nouveaux))

    envoyes = {"trafic": 0, "tech": 0}
    if a_envoyer and envoie(carte_trafic(a_envoyer), webhook):
        envoyes["trafic"] = len(a_envoyer)
    elif a_envoyer:                                    # échec d'envoi : on ne mémorise pas, nouvel essai au prochain passage
        for _, m, _, _ in a_envoyer:
            etat["trafic"].pop(m["slug"], None)
    if tech and envoie(carte_technique(tech, premier), webhook):
        envoyes["tech"] = len(tech)
    elif tech:
        for nom, _, _ in tech:
            etat["tech"].pop(nom, None)
    json.dump(etat, open(CHEMIN_ETAT, "w"))
    print(f"{len(mesures)} sites suivis en trafic, {len(res)} contrôlés techniquement — alertes : "
          f"{envoyes['trafic']} trafic, {envoyes['tech']} technique")


if __name__ == "__main__":
    main()
