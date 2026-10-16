"""Périodes civiles d'une présentation : courante, précédente de même durée, même période N-1."""

import calendar
from dataclasses import dataclass
from datetime import date

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MOIS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MOIS_NOMS = {
    "fr": MOIS_FR, "en": MOIS_EN,
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
}
PREFIXE_TRIM = {"fr": "T", "en": "Q", "it": "T", "es": "T", "de": "Q"}
PREFIXE_SEM = {"fr": "S", "en": "H", "it": "S", "es": "S", "de": "H"}
MOIS_COURTS = {"fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
               "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
               "it": ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"],
               "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
               "de": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]}
PAS = {"mois": 1, "trimestre": 3, "semestre": 6, "annee": 12}


@dataclass(frozen=True)
class PeriodeJours:
    """Plage de dates quelconque (pas une période civile) : sert à la comparaison « période précédente de même nombre de jours » de Looker."""
    debut: date
    fin: date
    type: str = "jours"

    @property
    def jours(self):
        return (self.fin - self.debut).days + 1

    def etiquette(self, langue="fr"):
        return f"{self.debut.strftime('%d/%m/%Y')}-{self.fin.strftime('%d/%m/%Y')}"


@dataclass(frozen=True)
class Periode:
    type: str          # mois | trimestre | semestre | annee
    annee: int
    indice: int | None  # 1-12 / 1-4 / 1-2 / None

    @property
    def mois_debut(self):
        return 1 if self.type == "annee" else (self.indice - 1) * PAS[self.type] + 1

    @property
    def debut(self):
        return date(self.annee, self.mois_debut, 1)

    @property
    def fin(self):
        m = self.mois_debut + PAS[self.type] - 1
        return date(self.annee, m, calendar.monthrange(self.annee, m)[1])

    @property
    def jours(self):
        return (self.fin - self.debut).days + 1

    def etiquette(self, langue="fr"):
        if self.type == "mois":
            return f"{MOIS_NOMS.get(langue, MOIS_FR)[self.indice - 1].capitalize()} {self.annee}"
        if self.type == "trimestre":
            return f"{PREFIXE_TRIM.get(langue, 'T')}{self.indice}-{self.annee}"
        if self.type == "semestre":
            return f"{PREFIXE_SEM.get(langue, 'S')}{self.indice}-{self.annee}"
        return str(self.annee)

    def precedente(self):
        """Période précédente de même durée (sans objet pour une année : renvoie N-1)."""
        if self.type == "annee":
            return Periode("annee", self.annee - 1, None)
        n = (self.annee * 12 + self.mois_debut - 1) - PAS[self.type]
        a, m0 = divmod(n, 12)
        return Periode(self.type, a, (m0 // PAS[self.type]) + 1)

    def n1(self):
        return Periode(self.type, self.annee - 1, self.indice)

    def precedente_jours(self):
        """Les N jours qui précèdent immédiatement la période (N = sa durée en jours) : la comparaison « période précédente » de Looker.
        Pour T3 (92 jours) : du 31/03 au 30/06, pas le T2 civil (91 jours)."""
        from datetime import timedelta
        return PeriodeJours(self.debut - timedelta(days=self.jours), self.debut - timedelta(days=1))

    def mois(self):
        """Les (année, mois) de la période."""
        return [(self.annee, self.mois_debut + k) for k in range(PAS[self.type])]


def depuis_brief(p):
    """periode du brief -> Periode (anciens briefs { annee, trimestre } acceptés)."""
    t = p.get("type") or ("trimestre" if p.get("trimestre") is not None else None)
    if t not in PAS:
        raise ValueError("période invalide dans le brief")
    indice = p.get("indice", p.get("trimestre"))
    return Periode(t, int(p["annee"]), None if t == "annee" else int(indice))
