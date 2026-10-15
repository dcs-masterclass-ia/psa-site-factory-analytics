"""Accès aux données d'une présentation : leads (back-office), trafic (GA4).

Sources et règles : docs/presentations-definitions.md.
  - leads : data/history/leads et leads_acq (back-office, leads valides) ;
  - trafic : data/history/ga4_sources (sessions des sites de reprise) ;
  - chaîne GA4 alignée sur Looker (requête directe sur la période, jamais une somme de valeurs quotidiennes, mise en cache) :
    sessions (total GA4 de la période) -> In Journey (sessions dont la catégorie de page est « form page » ou « lead page », comme Looker et Converge) -> Hot leads (évènements tradein_request) ;
    canaux = « Stellantis Custom Channel Group » ; les utilisateurs distincts restent disponibles (clé « utilisateurs »).
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


MARQUES_STELLANTIS = {"PEUGEOT", "CITROEN", "DS", "OPEL", "VAUXHALL", "FIAT", "ALFA ROMEO", "JEEP", "LANCIA", "ABARTH", "LEAPMOTOR", "CHRYSLER", "DODGE", "RAM", "MASERATI", "SPOTICAR"}


def norme_marque(brut):
    """Marque normalisée : majuscules, sans accent (CITROËN -> CITROEN), FIAT PROFESSIONAL -> FIAT."""
    import unicodedata
    n = "".join(c for c in unicodedata.normalize("NFD", (brut or "").strip().upper()) if unicodedata.category(c) != "Mn")
    return "FIAT" if n.startswith("FIAT") else n


def Periode_fin_mois(mois):
    """Dernier jour (AAAA-MM-JJ) du mois AAAA-MM."""
    import calendar
    a, m = int(mois[:4]), int(mois[5:7])
    return f"{mois}-{calendar.monthrange(a, m)[1]:02d}"


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

    # ------------------------------------------------------- CTA du site marque, conquête / fidélité, modèles
    def _periode_lignes(self, dossier, marque, periode, cle_date="date"):
        """Lignes d'un historique (leads_acq, leads, leads_modeles) des sites de la marque sur la période ; date AAAA-MM-JJ ou mois AAAA-MM."""
        deb, fin = periode.debut.isoformat(), periode.fin.isoformat()
        for nom, m, _ in self.sites:
            if m != marque:
                continue
            for r in _lignes(self.hist / dossier / f"{slug(nom)}.csv.gz"):
                j = r.get(cle_date) or ""
                if len(j) == 7:                       # mois : retenu si le mois est entièrement dans la période
                    if deb[:7] <= j <= fin[:7] and deb <= j + "-01" and Periode_fin_mois(j) <= fin:
                        yield r
                elif deb <= j <= fin:
                    yield r

    def cta(self, periode, marque):
        """{support: {projet: n}} : leads valides du site de la marque (source Main-Website, campagne « CTA »), par emplacement du bouton."""
        out = {}
        for r in self._periode_lignes("leads_acq", marque, periode):
            if r["statut"] == "valide" and groupe_source(r["source_acq"]) == "Main-Website" and (r["campagne"] or "").strip().lower() == "cta":
                sup = (r["support"] or "").strip() or "(non renseigné)"
                out.setdefault(sup, {p: 0 for p in PROJETS})[PROJET_BO.get(r["projet_achat"], "SANS")] += int(r["n"])
        return out

    def reprises(self, periode, marque):
        """{marque reprise (normalisée): n} : leads valides par marque du véhicule repris."""
        out = defaultdict(int)
        for r in self._periode_lignes("leads", marque, periode):
            if r["statut"] == "valide" and r["marque_reprise"].strip():
                out[norme_marque(r["marque_reprise"])] += int(r["n"])
        return dict(out)

    def modeles(self, periode, marque):
        """[(marque_reprise, modele_reprise, marque_achat, modele_achat, n)] sur la période, ou None si l'historique des modèles n'est pas encore collecté."""
        if not any((self.hist / "leads_modeles" / f"{slug(nom)}.csv.gz").exists() for nom, m, _ in self.sites if m == marque):
            return None
        agg = defaultdict(int)
        for r in self._periode_lignes("leads_modeles", marque, periode, "mois"):
            agg[(norme_marque(r["marque_reprise"]), r["modele_reprise"].strip(), norme_marque(r["marque_achat"]), r["modele_achat"].strip())] += int(r["valides"])
        return [(*k, n) for k, n in agg.items()]

    # ------------------------------------------------------- fichiers de site (data/<site>.json) : mode de saisie, avant / après V2
    def _site_json(self, nom):
        try:
            return json.loads((self.hist.parent / f"{slug(nom)}.json").read_text(encoding="utf-8"))
        except Exception:
            return None

    def entree_leads(self, periode, marque):
        """{plaque, marque_modele} : leads par mode de saisie du véhicule (avec immatriculation / marque et modèle) sur les mois de la période, ou None si non disponible."""
        plaque = mm = 0
        vu = False
        for nom, m, _ in self.sites:
            if m != marque:
                continue
            d = self._site_json(nom)
            for a, mo in periode.mois():
                e = ((d or {}).get("leads", {}).get(f"{a}-{mo:02d}") or {}).get("entry")
                if e:
                    vu = True
                    plaque += e.get("Avec immatriculation", 0)
                    mm += e.get("Marque / modele", 0)
        return {"plaque": plaque, "marque_modele": mm} if vu else None

    def v2(self, marque):
        """Avant / après la bascule en V2 pour les sites de la marque du périmètre : utilisateurs par étape du tunnel (avant, après) et fenêtres, ou None si aucun site V2."""
        etapes, fenetres, n = {}, [], 0
        ordre = []
        for nom, m, pays in self.sites:
            if m != marque:
                continue
            d = self._site_json(nom) or {}
            v, st = d.get("v2") or {}, d.get("v2steps") or []
            if not v.get("is_v2_split") or not st:
                continue
            n += 1
            fenetres.append((nom, v.get("pre_label"), v.get("post_label")))
            for x in st:
                if x["step"] not in etapes:
                    etapes[x["step"]] = [0, 0]
                    ordre.append(x["step"])
                etapes[x["step"]][0] += x.get("a") or 0
                etapes[x["step"]][1] += x.get("b") or 0
        if not n:
            return None
        return {"etapes": [(k, *etapes[k]) for k in ordre], "sites": n, "fenetres": fenetres}

    # ------------------------------------------------------- C1ST : suivi des leads envoyés (fichier c1st/kpi.json du repo de données)
    CODES_C1ST = {"AP": "PEUGEOT", "AC": "CITROEN", "DS": "DS", "OP": "OPEL", "FT": "FIAT", "FO": "FIAT PRO", "JE": "JEEP", "AR": "ALFA ROMEO", "LA": "LANCIA", "AH": "ABARTH", "SP": "SPOTICAR"}
    PAYS_C1ST = {"BE": "BE", "LU": "BE"}        # le Luxembourg est compté dans la Belgique côté C1ST ; DE et LU seul : aucun lead

    def _c1st(self):
        if getattr(self, "_c1st_data", None) is None:
            try:
                self._c1st_data = json.loads((self.hist.parent / "c1st" / "kpi.json").read_text(encoding="utf-8")).get("donnees", {})
            except Exception:
                self._c1st_data = {}
        return self._c1st_data

    def c1st(self, periode, marque):
        """Totaux C1ST (leads VN envoyés vus par C1ST) de la marque sur les mois de la période, pour les marchés du périmètre ; None si un mois manque (jamais de total partiel)."""
        champs = ("leads", "envoyes", "clients_envoyes", "contactes", "contactes_delai", "premier_appel_delai", "traites", "traites_delai", "avec_opp")
        champs_c = ("clients_uniques", "avec_devis", "commandes")
        code = next((c for c, m in self.CODES_C1ST.items() if m == marque), None)
        cles = sorted({self.PAYS_C1ST.get(p, p) for p in self.pays})
        data = self._c1st()
        if not code or not data:
            return None
        tot = {k: 0 for k in champs + champs_c}
        for pays in cles:
            for a, mo in periode.mois():
                m = (data.get(pays) or {}).get(f"{a}-{mo:02d}")
                if not m or m.get("leads") is None or m.get("commandes") is None or m.get("nsc") is None:
                    return None
                for r in m["leads"]:
                    if r.get("marque") == code:
                        for k in champs:
                            tot[k] += r.get(k) or 0
                for r in m["commandes"]:
                    if r.get("marque") == code:
                        for k in ("clients_uniques", "avec_devis"):
                            tot[k] += r.get(k) or 0
                for r in m["nsc"]:                       # commandes = commandes NSC (jeu « SUB » de C1ST), comme le graphique « NSC Orders »
                    if r.get("marque") == code:
                        tot["commandes"] += r.get("commandes_nsc") or 0
        return tot

    def c1st_nsc(self, periode, marque):
        """Commandes NSC (jeu « SUB » de C1ST, 1 à 90 jours après le lead) de la marque sur les mois de la période, pour les marchés du périmètre ; None si un mois manque."""
        code = next((c for c, m in self.CODES_C1ST.items() if m == marque), None)
        cles = sorted({self.PAYS_C1ST.get(p, p) for p in self.pays})
        data = self._c1st()
        if not code or not data:
            return None
        total = 0
        for pays in cles:
            for a, mo in periode.mois():
                m = (data.get(pays) or {}).get(f"{a}-{mo:02d}")
                if not m or m.get("nsc") is None:
                    return None
                total += sum(r.get("commandes_nsc") or 0 for r in m["nsc"] if r.get("marque") == code)
        return total

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

    # ------------------------------------------------------------------ calendrier d'événements (data/events/events.json, saisi dans le dashboard)
    def evenements(self, periode, marque=None):
        """Événements dont la date tombe dans la période et qui concernent les sites du périmètre (et la marque donnée) : [{date, titre, type}]."""
        if getattr(self, "_events", None) is None:
            self._events = []
            f = self.hist.parent / "events" / "events.json"
            if f.exists():
                try:
                    import json
                    self._events = json.load(open(f, encoding="utf-8")).get("events", [])
                except Exception:
                    self._events = []
        noms = {nom for nom, m, _ in self.sites if marque is None or m == marque}
        deb, fin = periode.debut.isoformat(), periode.fin.isoformat()
        out = [e for e in self._events if deb <= (e.get("date") or "") <= fin and (not e.get("sites") or noms & set(e["sites"]))]
        return sorted(out, key=lambda e: e["date"])

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
        """{canal: sessions} sur la période : GA4 direct (groupe de canaux de Looker) ; repli sur l'historique si GA4 est indisponible."""
        u = self.utilisateurs(periode, marque)
        if u and u.get("canaux"):
            return dict(u["canaux"])
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
        """{sessions, in_journey, hot_leads, utilisateurs, canaux} sur la période (définitions de Looker), ou None si GA4 indisponible."""
        total = {"sessions": 0, "in_journey": 0, "hot_leads": 0, "utilisateurs": 0, "canaux": {}}
        for nom, m, _ in self.sites:
            if m != marque:
                continue
            cle = f"v3|{nom}|{periode.debut}|{periode.fin}"
            v = self._cache_ga4().get(cle)
            if v is None:
                v = self._requete_ga4(nom, periode)
                if v is None:
                    return None
                self._cache_ga4()[cle] = v
                self._sauve_cache()
            for k in ("sessions", "in_journey", "hot_leads", "utilisateurs"):
                total[k] += v[k]
            for c, n in v.get("canaux", {}).items():
                total["canaux"][c] = total["canaux"].get(c, 0) + n
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
        """Chaîne de Looker sur les sites de reprise : sessions (total de la période), In Journey (sessions sur « form page » / « lead page », comme Looker et Converge),
        Hot leads (évènements tradein_request), canaux (Stellantis Custom Channel Group) ; utilisateurs distincts en complément."""
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
            tot = ga4._rapport(cli, s.propriete, d0, d1, [], ["sessions", "totalUsers"], filtre)
            ev = ga4._rapport(cli, s.propriete, d0, d1, ["eventName"], ["sessions", "eventCount"], filtre)
            par_evt = {e: (int(float(se)), int(float(c))) for e, se, c in ev}
            ij = ga4._rapport(cli, s.propriete, d0, d1, [], ["sessions"], ga4._filtre_in_journey(hote))
            can = ga4._rapport(cli, s.propriete, d0, d1, [ga4.dim_canal(s.propriete)], ["sessions"], filtre)
            return {"sessions": int(float(tot[0][0])) if tot else 0, "utilisateurs": int(float(tot[0][1])) if tot else 0,
                    "in_journey": int(float(ij[0][0])) if ij else 0,
                    "hot_leads": par_evt.get("tradein_request", (0, 0))[1],
                    "canaux": {(c.strip() or "(non défini)"): int(float(n)) for c, n in can}}
        except (Exception, SystemExit) as e:  # GA4 indisponible (accès absent compris) : la présentation l'indique, elle ne s'arrête pas
            print(f"  GA4 indisponible pour {nom} {periode.etiquette()} : {type(e).__name__}")
            return None
