"""Textes calculés : jamais saisis à la main (docs/presentations-definitions.md, règles 5 et 6).

Les signes, les « pt » et les libellés de période sont produits ici, depuis les chiffres, en français ou en anglais.
Sous SEUIL_BASE leads/sessions dans la période de référence, aucun pourcentage n'est affiché : « n.s. ».
"""

SEUIL_BASE = 100
NBSP = " "
MOINS = "−"

STABLE = {"fr": "stable", "en": "stable", "it": "stabile", "es": "estable", "de": "stabil"}

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
        "ga4_indispo": "Mesures GA4 (sessions, In Journey, hot leads) indisponibles pour cette édition.",
        "acq_indispo": "Sources d'acquisition indisponibles sur cette période (historique collecté depuis 2023).",
        "base_faible": "n.s. = non significatif (moins de 100 dans la période de référence).",
        "cvr_global": "Taux de conversion (hot leads ÷ sessions)", "site_marque": "Trafic venant du site de la marque", "groupes": "Leads par groupe de marques",
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
        "ga4_indispo": "GA4 measures (sessions, In Journey, hot leads) are unavailable for this edition.",
        "acq_indispo": "Acquisition sources unavailable for this period (history collected since 2023).",
        "base_faible": "n.s. = not significant (fewer than 100 in the reference period).",
        "cvr_global": "Conversion rate (hot leads ÷ sessions)", "site_marque": "Traffic from the brand website", "groupes": "Leads by brand group",
        "hors_spoticar": "Excluding Spoticar", "part_total": "Share of total", "annexes": "Appendix", "groupe": "Group",
    },
    "it": {
        "confidentiel": "Strettamente confidenziale",
        "source_bo": "Fonte: back-office autobiz",
        "source_ga4": "Fonte: GA4",
        "source_bo_ga4": "Fonti: back-office autobiz (lead) e GA4 (traffico)",
        "perimetre": "Perimetro",
        "agenda": "Indice",
        "vue_globale": "Panoramica",
        "projets": "Progetti d'acquisto",
        "detail_marques": "Dettaglio per marchio",
        "points_ouverts": "Punti aperti",
        "prochaines_etapes": "Prossimi passi",
        "questions": "Domande / risposte",
        "contacts": "Contatti",
        "suivez": "Seguici",
        "synthese": "Sintesi",
        "leads": "Lead",
        "leads_nc": "Lead auto nuove",
        "taux_nc": "Quota di lead auto nuove",
        "sessions": "Sessioni trade-in",
        "hot_leads": "Hot lead",
        "in_journey": "In Journey",
        "utilisateurs": "Utenti trade-in",
        "cvr": "Tasso di conversione (hot lead ÷ In Journey)",
        "taux_in_journey": "Tasso In Journey",
        "total": "Totale",
        "marque": "Marchio",
        "canal": "Canale",
        "sessions_col": "Sessioni",
        "source": "Fonte",
        "action": "Azione",
        "responsable": "Responsabile",
        "statut": "Stato",
        "echeance": "Scadenza",
        "VN": "Auto nuove e Demo",
        "SANS": "Solo trade-in",
        "VO": "Auto usate",
        "autre": "Altro",
        "n_s": "n.s.",
        "non_dispo": "n.d.",
        "vs_prec": "vs periodo precedente",
        "vs_n1": "vs anno precedente",
        "a_faire": "Da fare",
        "en_cours": "In corso",
        "fait": "Fatto",
        "bloque": "Bloccato",
        "trafic": "Traffico",
        "leads_titre": "Lead",
        "tendance": "Tendenza",
        "par_mois": "per mese",
        "xp": "Marchi XP",
        "xf": "Marchi XF",
        "autres": "Altri marchi",
        "ga4_indispo": "Misure GA4 (sessioni, In Journey, hot lead) non disponibili per questa edizione.",
        "acq_indispo": "Fonti di acquisizione non disponibili per questo periodo (storico raccolto dal 2023).",
        "base_faible": "n.s. = non significativo (meno di 100 nel periodo di riferimento).",
        "cvr_global": "Tasso di conversione (hot lead ÷ sessioni)",
        "site_marque": "Traffico dal sito del marchio",
        "groupes": "Lead per gruppo di marchi",
        "hors_spoticar": "Escluso Spoticar",
        "part_total": "Quota sul totale",
        "annexes": "Allegati",
        "groupe": "Gruppo",
    },
    "es": {
        "confidentiel": "Estrictamente confidencial",
        "source_bo": "Fuente: back-office autobiz",
        "source_ga4": "Fuente: GA4",
        "source_bo_ga4": "Fuentes: back-office autobiz (leads) y GA4 (tráfico)",
        "perimetre": "Perímetro",
        "agenda": "Índice",
        "vue_globale": "Visión general",
        "projets": "Proyectos de compra",
        "detail_marques": "Detalle por marca",
        "points_ouverts": "Puntos abiertos",
        "prochaines_etapes": "Próximos pasos",
        "questions": "Preguntas / respuestas",
        "contacts": "Contactos",
        "suivez": "Síguenos",
        "synthese": "Resumen",
        "leads": "Leads",
        "leads_nc": "Leads coches nuevos",
        "taux_nc": "Cuota de leads coches nuevos",
        "sessions": "Sesiones trade-in",
        "hot_leads": "Hot leads",
        "in_journey": "In Journey",
        "utilisateurs": "Usuarios trade-in",
        "cvr": "Tasa de conversión (hot leads ÷ In Journey)",
        "taux_in_journey": "Tasa In Journey",
        "total": "Total",
        "marque": "Marca",
        "canal": "Canal",
        "sessions_col": "Sesiones",
        "source": "Fuente",
        "action": "Acción",
        "responsable": "Responsable",
        "statut": "Estado",
        "echeance": "Fecha límite",
        "VN": "Coches nuevos y Demo",
        "SANS": "Solo trade-in",
        "VO": "Coches usados",
        "autre": "Otro",
        "n_s": "n.s.",
        "non_dispo": "n.d.",
        "vs_prec": "vs período anterior",
        "vs_n1": "vs año anterior",
        "a_faire": "Por hacer",
        "en_cours": "En curso",
        "fait": "Hecho",
        "bloque": "Bloqueado",
        "trafic": "Tráfico",
        "leads_titre": "Leads",
        "tendance": "Tendencia",
        "par_mois": "por mes",
        "xp": "Marcas XP",
        "xf": "Marcas XF",
        "autres": "Otras marcas",
        "ga4_indispo": "Mediciones GA4 (sesiones, In Journey, hot leads) no disponibles para esta edición.",
        "acq_indispo": "Fuentes de adquisición no disponibles para este período (histórico recopilado desde 2023).",
        "base_faible": "n.s. = no significativo (menos de 100 en el período de referencia).",
        "cvr_global": "Tasa de conversión (hot leads ÷ sesiones)",
        "site_marque": "Tráfico desde el sitio de la marca",
        "groupes": "Leads por grupo de marcas",
        "hors_spoticar": "Sin Spoticar",
        "part_total": "Cuota del total",
        "annexes": "Anexos",
        "groupe": "Grupo",
    },
    "de": {
        "confidentiel": "Streng vertraulich",
        "source_bo": "Quelle: autobiz Back-Office",
        "source_ga4": "Quelle: GA4",
        "source_bo_ga4": "Quellen: autobiz Back-Office (Leads) und GA4 (Traffic)",
        "perimetre": "Umfang",
        "agenda": "Agenda",
        "vue_globale": "Gesamtübersicht",
        "projets": "Kaufprojekte",
        "detail_marques": "Details je Marke",
        "points_ouverts": "Offene Punkte",
        "prochaines_etapes": "Nächste Schritte",
        "questions": "Fragen / Antworten",
        "contacts": "Kontakte",
        "suivez": "Folgen Sie uns",
        "synthese": "Zusammenfassung",
        "leads": "Leads",
        "leads_nc": "Neuwagen-Leads",
        "taux_nc": "Anteil Neuwagen-Leads",
        "sessions": "Trade-in-Sitzungen",
        "hot_leads": "Hot Leads",
        "in_journey": "In Journey",
        "utilisateurs": "Trade-in-Nutzer",
        "cvr": "Conversion-Rate (Hot Leads ÷ In Journey)",
        "taux_in_journey": "In-Journey-Rate",
        "total": "Gesamt",
        "marque": "Marke",
        "canal": "Kanal",
        "sessions_col": "Sitzungen",
        "source": "Quelle",
        "action": "Maßnahme",
        "responsable": "Verantwortlich",
        "statut": "Status",
        "echeance": "Frist",
        "VN": "Neuwagen & Demo",
        "SANS": "Nur Trade-in",
        "VO": "Gebrauchtwagen",
        "autre": "Sonstige",
        "n_s": "n. s.",
        "non_dispo": "k. A.",
        "vs_prec": "ggü. Vorperiode",
        "vs_n1": "ggü. Vorjahr",
        "a_faire": "Offen",
        "en_cours": "In Arbeit",
        "fait": "Erledigt",
        "bloque": "Blockiert",
        "trafic": "Traffic",
        "leads_titre": "Leads",
        "tendance": "Trend",
        "par_mois": "pro Monat",
        "xp": "XP-Marken",
        "xf": "XF-Marken",
        "autres": "Weitere Marken",
        "ga4_indispo": "GA4-Messwerte (Sitzungen, In Journey, Hot Leads) für diese Ausgabe nicht verfügbar.",
        "acq_indispo": "Akquisitionsquellen für diesen Zeitraum nicht verfügbar (Historie seit 2023).",
        "base_faible": "n. s. = nicht signifikant (weniger als 100 im Referenzzeitraum).",
        "cvr_global": "Conversion-Rate (Hot Leads ÷ Sitzungen)",
        "site_marque": "Traffic von der Markenwebsite",
        "groupes": "Leads nach Markengruppe",
        "hors_spoticar": "Ohne Spoticar",
        "part_total": "Anteil am Gesamt",
        "annexes": "Anhang",
        "groupe": "Gruppe",
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
        if self.l == "fr":
            return s.replace(",", NBSP)
        return s.replace(",", ".") if self.l in ("it", "es", "de") else s

    def dec(self, v, n=1):
        s = f"{v:.{n}f}"
        return s.replace(".", ",") if self.l in ("fr", "it", "es", "de") else s

    def pct(self, v, n=0, signe=False):
        s = self.dec(abs(v), n)
        sg = ""
        if signe:
            sg = ("+" if v > 0 else MOINS) if round(v, n) != 0 else ""
        return f"{sg}{s}{NBSP}%" if self.l in ("fr", "es", "de") else f"{sg}{s}%"

    def pts(self, v):
        r = round(v)
        if r == 0:
            return STABLE[self.l]
        sg = "+" if r > 0 else MOINS
        return f"{sg}{abs(r)}{NBSP}pt" if self.l == "fr" else f"{sg}{abs(r)} pt"

    def evol(self, cur, ref):
        """Évolution en % ; « n.s. » si la base de référence est inférieure à SEUIL_BASE. -> (texte, signe, valeur|None)"""
        if cur is None or ref is None or ref < SEUIL_BASE:
            return self.L["n_s"], 0, None
        v = (cur - ref) / ref * 100
        if round(v) == 0:
            return STABLE[self.l], 0, v
        return self.pct(v, 0, signe=True), (1 if v > 0 else -1), v

    def taux(self, a, b):
        """a/b en % (None si b == 0)"""
        return None if not b else a / b * 100

    def periode_phrase(self, etiquette):
        return etiquette
