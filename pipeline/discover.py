"""Decouverte automatique des noms d'hote d'une propriete.

Remplace la configuration en dur. Le pipeline interroge GA4 a chaque execution
et deduit l'hote parent et l'hote de reprise du trafic reel.

Regle heritee du projet : ne jamais se fier a un libelle. Ici on ne se fie meme
plus a une liste ecrite a la main — c'est le volume mesure qui decide.

Si la deduction est ambigue, la fonction leve `Ambigu`. Le pipeline marque alors
le site `indisponible` plutot que de publier des chiffres batis sur une
supposition. Un trou signale vaut mieux qu'un chiffre faux.
"""

import re

# le mot pour "reprise" (ou son equivalent -- rachat/estimation du vehicule)
# change de sous-domaine selon le marche ; liste communiquee marche par
# marche (jamais devinee) : "retoma" (PT/ES sur certaines marques),
# "reprise"/"overname" (FR/BE), "tasacion" (ES), "valutazioneusato" /
# "valutiamoiltuousato" (IT), "odkup" (PL), "autoankauf" /
# "kauft-dein-auto" / "kauft-ihr-auto" / "wir-kaufen-ihr-auto" (DE/AT),
# "tradein" (UK).
MOTIFS_REPRISE = (
    r"\bretoma\b", r"\breprise\b", r"retoma-", r"reprise-",
    r"overname", r"tasacion", r"valutazioneusato", r"valutiamoiltuousato",
    r"odkup", r"autoankauf", r"kauft-dein-auto", r"kauft-ihr-auto",
    r"wir-kaufen-ihr-auto", r"\btradein\b", r"trade-in",
)

# hotes a ecarter d'office : recette, preproduction, boutique, outils tiers.
# "sklep" (PL) ajoute le 07/08/2026 : sur Citroen PL, la boutique en ligne
# (sklep.citroen.pl, 476k sessions) depassait le site vitrine et se faisait
# choisir comme hote parent a sa place -- meme famille que store/shop.
MOTIFS_EXCLUS = (
    r"recette", r"preprod", r"staging", r"\.dev\b", r"localhost",
    r"^store\.", r"\bshop\b", r"\bsklep\b", r"googleusercontent", r"translate\.goog",
)

PART_MINIMALE_PARENT = 0.30   # le parent doit peser au moins 30 % du trafic
SESSIONS_MINIMALES = 200      # sous ce volume, un hote n'est pas exploitable


class Ambigu(Exception):
    """La deduction n'est pas concluante : ne rien publier pour ce site."""


def _exclu(hote):
    return any(re.search(m, hote, re.I) for m in MOTIFS_EXCLUS)


def _est_reprise(hote):
    return any(re.search(m, hote, re.I) for m in MOTIFS_REPRISE)


def deduire(liste, pays=None):
    """liste : [(hote, sessions)] trie par volume decroissant.

    Retourne (hote_parent, hote_reprise, journal).
    """
    journal = []
    retenus = [(h, s) for h, s in liste if not _exclu(h) and s >= SESSIONS_MINIMALES]
    ecartes = [h for h, s in liste if _exclu(h)]
    if ecartes:
        journal.append(f"ecartes : {', '.join(ecartes)}")
    if not retenus:
        raise Ambigu("aucun hote au-dessus du seuil de volume")

    total = sum(s for _, s in retenus)

    reprises = [(h, s) for h, s in retenus if _est_reprise(h)]
    parents = [(h, s) for h, s in retenus if not _est_reprise(h)]

    if not reprises:
        raise Ambigu("aucun hote ne correspond a un motif de reprise "
                     f"({', '.join(h for h, _ in retenus)})")
    if len(reprises) > 1:
        # plusieurs candidats : on prend le plus gros mais on le signale
        journal.append("plusieurs hotes de reprise possibles : "
                       + ", ".join(f"{h} ({s})" for h, s in reprises))
    if not parents:
        raise Ambigu("aucun hote parent identifiable")

    hote_reprise, sess_reprise = reprises[0]
    hote_parent, sess_parent = parents[0]

    part = sess_parent / total
    if part < PART_MINIMALE_PARENT:
        raise Ambigu(f"le candidat parent {hote_parent} ne pese que "
                     f"{part * 100:.0f}% du trafic, sous le seuil de 30%")

    # l'outil de reprise doit etre plus petit que le site parent
    if sess_reprise > sess_parent:
        raise Ambigu(f"{hote_reprise} ({sess_reprise}) depasse {hote_parent} "
                     f"({sess_parent}) : hierarchie inattendue")

    # coherence de pays, quand on la connait
    if pays:
        suffixe = "." + pays.lower()
        if not hote_reprise.lower().endswith(suffixe):
            journal.append(f"note : {hote_reprise} ne finit pas par {suffixe}")

    journal.append(f"parent {hote_parent} ({sess_parent}, {part * 100:.0f}%)")
    journal.append(f"reprise {hote_reprise} ({sess_reprise})")
    return hote_parent, hote_reprise, journal
