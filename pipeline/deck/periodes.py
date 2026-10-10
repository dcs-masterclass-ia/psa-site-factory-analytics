"""Périodes civiles d'une présentation : courante, précédente de même durée, même période N-1."""

import calendar
from dataclasses import dataclass
from datetime import date

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MOIS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MOIS_COURTS = {"fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
               "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]}
PAS = {"mois": 1, "trimestre": 3, "semestre": 6, "annee": 12}


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
            return f"{(MOIS_EN if langue == 'en' else MOIS_FR)[self.indice - 1].capitalize()} {self.annee}"
        if self.type == "trimestre":
            return f"Q{self.indice}-{self.annee}" if langue == "en" else f"T{self.indice}-{self.annee}"
        if self.type == "semestre":
            return f"H{self.indice}-{self.annee}" if langue == "en" else f"S{self.indice}-{self.annee}"
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
