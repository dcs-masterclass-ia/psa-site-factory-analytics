"""Textes calculés : jamais saisis à la main (docs/presentations-definitions.md, règles 5 et 6).

Les signes, les « pt » et les libellés de période sont produits ici, depuis les chiffres, en français ou en anglais.
Sous SEUIL_BASE leads/sessions dans la période de référence, aucun pourcentage n'est affiché : « n.s. ».
"""

SEUIL_BASE = 100
NBSP = " "
MOINS = "−"

LIBELLES = {
    "fr": {
        "confidentiel": "Strictement confidentiel", "source_bo": "Source : back-office autobiz", "source_ga4": "Source : GA4",
        "source_bo_ga4": "Sources : back-office autobiz (leads) et GA4 (trafic)", "perimetre": "Périmètre",
        "agenda": "Sommaire", "vue_globale": "Vue d'ensemble", "projets": "Projets d'achat", "detail_marques": "Détail par marque",
        "points_ouverts": "Points ouverts", "prochaines_etapes": "Prochaines étapes", "questions": "Questions / réponses",
        "contacts": "Contacts", "suivez": "Suivez-nous", "synthese": "Synthèse", "leads": "Leads", "leads_nc": "Leads New cars",
        "taux_nc": "Part de leads New cars", "sessions": "Sessions trade-in", "hot_leads": "Hot leads",
        "in_journey": "In Journey", "utilisateurs": "Utilisateurs trade-in", "cvr": "Taux de conversion (hot leads ÷ In Journey)",
        "taux_in_journey": "Taux In Journey", "total": "Total", "marque": "Marque", "canal": "Canal", "sessions_col": "Sessions",
        "source": "Source", "action": "Action", "responsable": "Responsable", "statut": "Statut", "echeance": "Échéance",
        "VN": "New cars & Demo", "SANS": "Trade-in only", "VO": "Used cars", "autre": "Autre",
        "n_s": "n.s.", "non_dispo": "n.d.", "vs_prec": "vs période précédente", "vs_n1": "vs N-1",
        "a_faire": "À faire", "en_cours": "En cours", "fait": "Fait", "bloque": "Bloqué",
        "trafic": "Trafic", "leads_titre": "Leads", "tendance": "Tendance", "par_mois": "par mois",
        "xp": "Marques XP", "xf": "Marques XF", "autres": "Autres marques",
        "ga4_indispo": "Mesures GA4 (utilisateurs, In Journey, hot leads) indisponibles pour cette édition.",
        "acq_indispo": "Sources d'acquisition indisponibles sur cette période (historique collecté depuis 2023).",
        "base_faible": "n.s. = non significatif (moins de 100 dans la période de référence).",
        "cvr_global": "Taux de conversion (hot leads ÷ utilisateurs)", "site_marque": "Trafic venant du site de la marque", "groupes": "Leads par groupe de marques",
        "hors_spoticar": "Hors Spoticar", "part_total": "Part du total", "annexes": "Annexes", "groupe": "Groupe",
    },
    "en": {
        "confidentiel": "Strictly confidential", "source_bo": "Source: autobiz back-office", "source_ga4": "Source: GA4",
        "source_bo_ga4": "Sources: autobiz back-office (leads) and GA4 (traffic)", "perimetre": "Scope",
        "agenda": "Agenda", "vue_globale": "Global overview", "projets": "Purchase projects", "detail_marques": "Brand deep dive",
        "points_ouverts": "Open points", "prochaines_etapes": "Next steps", "questions": "Q/A",
        "contacts": "Contacts", "suivez": "Follow us", "synthese": "Summary", "leads": "Leads", "leads_nc": "New cars leads",
        "taux_nc": "New cars leads share", "sessions": "Trade-in sessions", "hot_leads": "Hot leads",
        "in_journey": "In Journey", "utilisateurs": "Trade-in users", "cvr": "Conversion rate (hot leads ÷ In Journey)",
        "taux_in_journey": "In Journey rate", "total": "Total", "marque": "Brand", "canal": "Channel", "sessions_col": "Sessions",
        "source": "Source", "action": "Action", "responsable": "Owner", "statut": "Status", "echeance": "Deadline",
        "VN": "New cars & Demo", "SANS": "Trade-in only", "VO": "Used cars", "autre": "Other",
        "n_s": "n.s.", "non_dispo": "n/a", "vs_prec": "vs previous period", "vs_n1": "vs last year",
        "a_faire": "To do", "en_cours": "Ongoing", "fait": "Done", "bloque": "Blocked",
        "trafic": "Traffic", "leads_titre": "Leads", "tendance": "Trend", "par_mois": "by month",
        "xp": "XP brands", "xf": "XF brands", "autres": "Other brands",
        "ga4_indispo": "GA4 measures (users, In Journey, hot leads) are unavailable for this edition.",
        "acq_indispo": "Acquisition sources unavailable for this period (history collected since 2023).",
        "base_faible": "n.s. = not significant (fewer than 100 in the reference period).",
        "cvr_global": "Conversion rate (hot leads ÷ users)", "site_marque": "Traffic from the brand website", "groupes": "Leads by brand group",
        "hors_spoticar": "Excluding Spoticar", "part_total": "Share of total", "annexes": "Appendix", "groupe": "Group",
    },
}


class T:
    """Formatage et phrases selon la langue."""

    def __init__(self, langue="fr"):
        self.l = langue if langue in LIBELLES else "fr"
        self.L = LIBELLES[self.l]

    def __getitem__(self, cle):
        return self.L[cle]

    def nb(self, v):
        if v is None:
            return self.L["non_dispo"]
        s = f"{int(round(v)):,}"
        return s.replace(",", NBSP) if self.l == "fr" else s

    def dec(self, v, n=1):
        s = f"{v:.{n}f}"
        return s.replace(".", ",") if self.l == "fr" else s

    def pct(self, v, n=0, signe=False):
        s = self.dec(abs(v), n)
        sg = ""
        if signe:
            sg = ("+" if v > 0 else MOINS) if round(v, n) != 0 else ""
        return f"{sg}{s}{NBSP}%" if self.l == "fr" else f"{sg}{s}%"

    def pts(self, v):
        r = round(v)
        if r == 0:
            return "stable" if self.l == "fr" else "stable"
        sg = "+" if r > 0 else MOINS
        return f"{sg}{abs(r)}{NBSP}pt" if self.l == "fr" else f"{sg}{abs(r)} pt"

    def evol(self, cur, ref):
        """Évolution en % ; « n.s. » si la base de référence est inférieure à SEUIL_BASE. -> (texte, signe, valeur|None)"""
        if cur is None or ref is None or ref < SEUIL_BASE:
            return self.L["n_s"], 0, None
        v = (cur - ref) / ref * 100
        if round(v) == 0:
            return ("stable" if self.l == "fr" else "stable"), 0, v
        return self.pct(v, 0, signe=True), (1 if v > 0 else -1), v

    def taux(self, a, b):
        """a/b en % (None si b == 0)"""
        return None if not b else a / b * 100

    def periode_phrase(self, etiquette):
        return etiquette
