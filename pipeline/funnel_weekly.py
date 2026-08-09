"""Funnel hebdomadaire "glissant", independant de la V2.

funnelMonth (voir build.py) ne connait le funnel qu'a la resolution du
mois calendaire complet : des qu'une periode choisie par l'utilisateur
chevauche un mois, le dashboard doit prendre le mois ENTIER, pas
seulement les jours selectionnes -- l'ecart avec les sessions (precises
au jour) pouvait atteindre ~30 jours et donnait des chiffres visiblement
incoherents entre eux (signale le 10/08/2026).

Ce module ajoute une resolution hebdomadaire glissante, sur le meme
principe que le rapport V2 (v2_report.py) : une requete GA4 par semaine,
mais seulement pour les semaines recentes (SEMAINES_CONSERVEES), jamais
tout l'historique -- pas de backfill couteux, la couverture s'etend
naturellement au fil des runs quotidiens. Au-dela de cette fenetre
glissante, funnelMonth reste la donnee de repli (mensuelle, moins
precise mais toujours reelle).
"""

from datetime import date, timedelta

from pipeline import funnel

SEMAINES_RATTRAPAGE = 2  # au-dela de la semaine en cours, tente de combler les N precedentes si absentes (run manque, echec transitoire GA4...)
SEMAINES_CONSERVEES = 20  # ~5 mois glissants ; au-dela, le dashboard retombe sur funnelMonth (mensuel)


def _lundi(d):
    return d - timedelta(days=d.weekday())


def semaines_a_calculer(existantes, jour_fiable):
    """(debut, fin) des semaines a (re)calculer aujourd'hui : la semaine en
    cours (toujours, elle continue d'accumuler des jours) + les
    SEMAINES_RATTRAPAGE precedentes si absentes de `existantes` (dict cle
    par lundi ISO)."""
    lundi_courant = _lundi(jour_fiable)
    semaines = [(lundi_courant, jour_fiable)]
    for i in range(1, SEMAINES_RATTRAPAGE + 1):
        lundi = lundi_courant - timedelta(days=7 * i)
        if lundi.isoformat() not in existantes:
            semaines.append((lundi, lundi + timedelta(days=6)))
    return semaines


def purge_anciennes(funnel_weekly, jour_fiable):
    """Retire les semaines plus vieilles que SEMAINES_CONSERVEES : au-dela,
    le dashboard retombe sciemment sur funnelMonth plutot que de faire
    grossir ce champ indefiniment pour 64 sites x plusieurs annees."""
    limite = _lundi(jour_fiable) - timedelta(weeks=SEMAINES_CONSERVEES)
    return {k: v for k, v in funnel_weekly.items() if date.fromisoformat(k) >= limite}


def bloc_semaine(cli, pid, hote, debut, fin, jours):
    """Meme forme que funnel.bloc_funnel, pour une semaine (ou portion de
    semaine en cours) au lieu d'un mois calendaire entier."""
    return funnel.bloc_funnel(cli, pid, hote, debut.isoformat(), fin.isoformat(), jours)
