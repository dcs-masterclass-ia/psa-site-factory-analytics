"""Accès aux données d'une présentation : leads (back-office), trafic (GA4).

Sources et règles : docs/presentations-definitions.md.
  - leads : data/history/leads et leads_acq (back-office, leads valides) ;
  - trafic : data/history/ga4_sources (sessions des sites de reprise) ;
  - utilisateurs distincts (trafic, In Journey, Hot leads) : requête GA4 directe sur la période
    (jamais une somme de valeurs quotidiennes), mise en cache.
Un seul périmètre (pays) pour toutes les mesures d'une présentation.
"""

import csv
import gzip
import json
import os
import re
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
HIST = Path(os.environ.get("PSA_HISTORY_DIR") or RACINE / "data" / "history")
CACHE_GA4 = Path(os.environ.get("PSA_DECK_CACHE") or RACINE / "data" / ".cache_deck_ga4.json")

ORDRE_MARQUES = ["PEUGEOT", "CITROEN", "DS", "OPEL", "ALFA ROMEO", "ABARTH", "FIAT", "FIAT PRO", "JEEP", "LANCIA", "LEAPMOTOR",
                 "SPOTICAR", "STELLANTIS &YOU"]
NOMS_MARQUES = {"PEUGEOT": "Peugeot", "CITROEN": "Citroën", "DS": "DS", "OPEL": "Opel", "ALFA ROMEO": "Alfa Romeo", "ABARTH": "Abarth",
                "FIAT": "Fiat", "FIAT PRO": "Fiat Professional", "JEEP": "Jeep", "LANCIA": "Lancia", "LEAPMOTOR": "Leapmotor",
                "SPOTICAR": "Spoticar", "STELLANTIS &YOU": "Stellantis &You"}
GROUPES_MARQUES = {"XP": ["PEUGEOT", "CITROEN", "DS", "OPEL"],
                   "XF": ["ALFA ROMEO", "ABARTH", "FIAT", "FIAT PRO", "JEEP", "LANCIA", "LEAPMOTOR"]}

# Mots reconnus dans l'URL du site de la marque (source « referral ») ; la source UTM « Main-Website » marque les boutons du site de la marque.
DOMAINES_MARQUE = {"PEUGEOT": ["peugeot"], "CITROEN": ["citroen"], "DS": ["dsautomobiles", "ds-automobiles"], "OPEL": ["opel"], "ALFA ROMEO": ["alfaromeo", "alfa-romeo"],
                   "ABARTH": ["abarth"], "FIAT": ["fiat"], "FIAT PRO": ["fiatprofessional", "fiat-professional"], "JEEP": ["jeep"], "LANCIA": ["lancia"],
                   "LEAPMOTOR": ["leapmotor"], "SPOTICAR": ["spoticar"], "STELLANTIS &YOU": ["stellantisandyou", "stellantis"]}

# Projets d'achat (back-office) -> catégories de la présentation
PROJETS = ["VN", "SANS", "VO"]
PROJET_BO = {"VN": "VN", "No purchase project": "SANS", "VO": "VO"}

# Regroupement de SOURCE_ACQUISITION (valeur brute du back-office). Validé sur Peugeot BELUX T3-2026 :
# Display 241, Emailing 57, Main-Website 262, Search 421, Autre 598 contre 241/57/261/420/597 ici.
# Une valeur absente de ce tableau tombe dans « Autre » ; à compléter si une nouvelle source apparaît.
GROUPES_SOURCES = {
    "Search": ["search", "google ads", "google", "bing", "sem", "yahoo", "ecosia"],
    "Display": ["display", "taboola", "criteo", "rtbhouse", "outbrain", "amazon", "sol", "dv360", "programmatic"],
    "Social": ["meta", "metafacebook", "metafacebook instagram", "fb", "facebook", "instagram", "tiktok", "snapchat", "linkedin", "pinterest"],
    "Emailing": ["sfmc", "email", "newsletter"],
    "Main-Website": ["main-website", "website"],
    "LLM": ["chatgpt.com", "chatgpt", "perplexity", "perplexity.ai", "gemini", "claude.ai", "copilot"],
}
ORDRE_SOURCES = ["Display", "Emailing", "LLM", "Main-Website", "Search", "Social", "Autre"]
_SOURCE_VERS_GROUPE = {v: g for g, vs in GROUPES_SOURCES.items() for v in vs}


def groupe_source(brut):
    return _SOURCE_VERS_GROUPE.get((brut or "").strip().lower(), "Autre")


def slug(nom):
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", nom.lower()))


def _lignes(chemin):
    if not chemin.exists():
        return
    with gzip.open(chemin, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def sites_du_perimetre(pays, marques=None):
    """[(nom_de_site, marque, pays)] des sites du back-office du périmètre, dans l'ordre des marques."""
    from pipeline.leads_extract import SITE_EXTRACT
    voulues = {m.strip().upper() for m in (marques or [])}
    out = []
    for nom in SITE_EXTRACT:
        m, p = nom.rsplit(" ", 1)
        if p in pays and (not voulues or m in voulues):
            out.append((nom, m, p))
    out.sort(key=lambda x: (ORDRE_MARQUES.index(x[1]) if x[1] in ORDRE_MARQUES else 99, x[2]))
    return out


class Donnees:
    def __init__(self, pays, marques=None, hist=HIST):
        self.pays = [p.upper() for p in pays]
        self.hist = Path(hist)
        self.sites = sites_du_perimetre(self.pays, marques)
        self.marques = [m for m in ORDRE_MARQUES if any(s[1] == m for s in self.sites)]
        self._leads = None
        self._acq = None
        self._trafic = None
        self._ga4 = None

    # ------------------------------------------------------------------ leads
    def _charge_leads(self):
        """(marque, 'AAAA-MM-JJ') -> {projet: n}, leads valides."""
        if self._leads is not None:
            return
        d = defaultdict(lambda: defaultdict(int))
        for nom, marque, _ in self.sites:
            for r in _lignes(self.hist / "leads" / f"{slug(nom)}.csv.gz"):
                if r["statut"] == "valide":
                    d[(marque, r["date"])][PROJET_BO.get(r["projet_achat"], "SANS")] += int(r["n"])
        self._leads = d

    def leads(self, periode, marque=None):
        """{projet: n} sur la période (toutes marques si marque=None)."""
        self._charge_leads()
        out = {p: 0 for p in PROJETS}
        deb, fin = periode.debut.isoformat(), periode.fin.isoformat()
        for (m, jour), v in self._leads.items():
            if deb <= jour <= fin and (marque is None or m == marque):
                for p, n in v.items():
                    out[p] += n
        return out

    def leads_total(self, periode, marque=None):
        return sum(self.leads(periode, marque).values())

    def leads_mensuels(self, annee, marque=None, projet=None):
        """12 valeurs (janvier..décembre) ; projet = 'VN' pour les leads New cars."""
        self._charge_leads()
        out = [0] * 12
        for (m, jour), v in self._leads.items():
            if jour.startswith(str(annee)) and (marque is None or m == marque):
                out[int(jour[5:7]) - 1] += (v.get(projet, 0) if projet else sum(v.values()))
        return out

    def dernier_jour_leads(self):
        self._charge_leads()
        return max((j for (_, j) in self._leads), default=None)

    # ------------------------------------------------------- acquisition (sources)
    def _charge_acq(self):
        """(marque, jour) -> {(groupe_source, projet): n}"""
        if self._acq is not None:
            return
        d = defaultdict(lambda: defaultdict(int))
        for nom, marque, _ in self.sites:
            for r in _lignes(self.hist / "leads_acq" / f"{slug(nom)}.csv.gz"):
                if r["statut"] == "valide":
                    d[(marque, r["date"])][(groupe_source(r["source_acq"]), PROJET_BO.get(r["projet_achat"], "SANS"))] += int(r["n"])
        self._acq = d

    def sources(self, periode, marque):
        """{groupe_source: {projet: n}} sur la période."""
        self._charge_acq()
        out = {g: {p: 0 for p in PROJETS} for g in ORDRE_SOURCES}
        deb, fin = periode.debut.isoformat(), periode.fin.isoformat()
        for (m, jour), v in self._acq.items():
            if m == marque and deb <= jour <= fin:
                for (g, p), n in v.items():
                    out[g][p] += n
        return out

    def acquisition_disponible(self, periode):
        self._charge_acq()
        jours = [j for (_, j) in self._acq]
        return bool(jours) and min(jours) <= periode.debut.isoformat()

    # ------------------------------------------------------------------ contexte historique
    def _charge_funnel(self):
        if getattr(self, "_funnel", None) is not None:
            return
        d = defaultdict(lambda: [0, 0])
        for nom, marque, _ in self.sites:
            for r in _lignes(self.hist / "ga4_funnel" / f"{slug(nom)}.csv.gz"):
                v = d[(marque, r["date"])]
                v[0] += int(r["accueil"] or 0); v[1] += int(r["estimation"] or 0)
        self._funnel = d

    def funnel(self, periode, marque=None):
        """(visiteurs de l'accueil, estimations) cumulés par jour sur la période (série quotidienne GA4, cohérente d'une année à l'autre)."""
        self._charge_funnel()
        deb, fin = periode.debut.isoformat(), periode.fin.isoformat()
        a = e = 0
        for (m, jour), (x, y) in self._funnel.items():
            if (marque is None or m == marque) and deb <= jour <= fin:
                a += x; e += y
        return a, e

    def premier_jour_trafic(self):
        self._charge_trafic()
        return min((j for (_, j) in self._trafic), default=None)

    def gsc(self, periode, marque=None):
        """(clics, impressions, position moyenne pondérée par les impressions) Search Console sur la période, ou None si non couvert."""
        if not hasattr(self, "_gsc"):
            self._gsc = defaultdict(lambda: [0, 0, 0.0])
            self._gsc_min = {}
            for nom, m, _ in self.sites:
                for r in _lignes(self.hist / "gsc_daily" / f"{slug(nom)}.csv.gz"):
                    v = self._gsc[(m, r["date"])]
                    imp = int(r["impressions"] or 0)
                    v[0] += int(r["clics"] or 0); v[1] += imp; v[2] += float(r["position"] or 0) * imp
                    self._gsc_min[m] = min(self._gsc_min.get(m, "9999"), r["date"])
        deb, fin = periode.debut.isoformat(), periode.fin.isoformat()
        c = i = 0; pos = 0.0
        for (m, jour), v in self._gsc.items():
            if (marque is None or m == marque) and deb <= jour <= fin:
                c += v[0]; i += v[1]; pos += v[2]
        premier = self._gsc_min.get(marque) if marque else min(self._gsc_min.values(), default=None)
        if not i or not premier or premier > deb:
            return None
        return c, i, pos / i

    def v2_dates(self, marque):
        """{pays: 'AAAA-MM-JJ'} des sites de la marque passés en V2 (data/<site>.json -> v2_date)."""
        import json
        out = {}
        for nom, m, pays in self.sites:
            if m != marque:
                continue
            f = self.hist.parent / f"{slug(nom)}.json"
            if f.exists():
                try:
                    v = json.load(open(f, encoding="utf-8")).get("v2_date")
                except Exception:
                    v = None
                if v:
                    out[pays] = v
        return out

    # ------------------------------------------------------------------ trafic
    def _charge_trafic(self):
        """(marque, jour) -> {canal: [sessions, engagées]}  (sites de reprise, groupe de canaux principal)"""
        if self._trafic is not None:
            return
        d = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        for nom, marque, _ in self.sites:
            for r in _lignes(self.hist / "ga4_sources" / f"{slug(nom)}.csv.gz"):
                c = d[(marque, r["date"])][r["canal_principal"] or "Unassigned"]
                c[0] += int(r["sessions"]); c[1] += int(r["sessions_engagees"])
        self._trafic = d

    def trafic_site_marque(self, periode, marque):
        """(sessions venant du site de la marque, sessions totales) sur la période : source UTM « Main-Website » ou referral depuis l'URL de la marque."""
        if getattr(self, "_site_marque", None) is None:
            self._site_marque = defaultdict(lambda: [0, 0])
            for nom, m, _ in self.sites:
                mots = DOMAINES_MARQUE.get(m, [m.lower().replace(" ", "")])
                for r in _lignes(self.hist / "ga4_sources" / f"{slug(nom)}.csv.gz"):
                    n = int(r["sessions"])
                    v = self._site_marque[(m, r["date"])]
                    v[1] += n
                    src = (r.get("source") or "").lower()
                    if src in ("main-website", "website") or ((r.get("canal_principal") or "") == "Referral" and any(k in src for k in mots)):
                        v[0] += n
        deb, fin = periode.debut.isoformat(), periode.fin.isoformat()
        a = b = 0
        for (m, jour), (x, y) in self._site_marque.items():
            if m == marque and deb <= jour <= fin:
                a += x; b += y
        return a, b

    def canaux(self, periode, marque):
        """{canal: sessions} sur la période."""
        self._charge_trafic()
        out = defaultdict(int)
        deb, fin = periode.debut.isoformat(), periode.fin.isoformat()
        for (m, jour), v in self._trafic.items():
            if m == marque and deb <= jour <= fin:
                for c, (s, _) in v.items():
                    out[c] += s
        return dict(out)

    # ------------------------------------------- utilisateurs distincts (GA4, direct)
    def utilisateurs(self, periode, marque):
        """{utilisateurs, in_journey, hot_leads} distincts sur la période, ou None si GA4 indisponible."""
        cles = []
        total = {"utilisateurs": 0, "in_journey": 0, "hot_leads": 0}
        for nom, m, _ in self.sites:
            if m != marque:
                continue
            cle = f"{nom}|{periode.debut}|{periode.fin}"
            v = self._cache_ga4().get(cle)
            if v is None:
                v = self._requete_ga4(nom, periode)
                if v is None:
                    return None
                self._cache_ga4()[cle] = v
                self._sauve_cache()
            for k in total:
                total[k] += v[k]
        return total

    def _cache_ga4(self):
        if self._ga4 is None:
            try:
                self._ga4 = json.loads(CACHE_GA4.read_text())
            except Exception:
                self._ga4 = {}
        return self._ga4

    def _sauve_cache(self):
        try:
            CACHE_GA4.parent.mkdir(parents=True, exist_ok=True)
            CACHE_GA4.write_text(json.dumps(self._ga4))
        except Exception:
            pass

    def _requete_ga4(self, nom, periode):
        """Utilisateurs distincts des sites de reprise : tous, avec form_step_view (In Journey), avec tradein_request (Hot leads)."""
        try:
            from pipeline import ga4, sites as sites_mod
            from pipeline.history import hote_reprise_ga4
            s = next((x for x in sites_mod.SITES if x.nom == nom), None)
            if s is None or not s.acces_api:
                return None
            cli = ga4.client()
            d0, d1 = periode.debut.isoformat(), periode.fin.isoformat()
            hote = hote_reprise_ga4(cli, s, d0, d1)
            filtre = ga4._egal("hostName", hote)
            tot = ga4._rapport(cli, s.propriete, d0, d1, [], ["totalUsers"], filtre)
            ev = ga4._rapport(cli, s.propriete, d0, d1, ["eventName"], ["totalUsers"], filtre)
            par_evt = {e: int(u) for e, u in ev}
            return {"utilisateurs": int(tot[0][0]) if tot else 0, "in_journey": par_evt.get("form_step_view", 0),
                    "hot_leads": par_evt.get("tradein_request", 0)}
        except Exception as e:  # GA4 indisponible : la présentation l'indique, elle ne s'arrête pas
            print(f"  GA4 indisponible pour {nom} {periode.etiquette()} : {type(e).__name__}")
            return None
