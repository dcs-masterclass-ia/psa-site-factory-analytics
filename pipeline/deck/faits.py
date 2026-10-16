"""Table de faits d'une présentation : chaque chiffre significatif posé dans une diapositive est aussi enregistré ici (métrique, marque, période, valeur, diapositive, origine).

Le contrôle qualité (qa.py) lit cette table, jamais le PowerPoint : il compare ce que des diapositives différentes affirment d'un même chiffre, vérifie les sommes et la logique de
l'entonnoir, et signale ce qui n'est pas vraisemblable. Métriques : leads, leads_vn, leads_sans, leads_vo (leads du back-office), sessions, in_journey, ga_leads (GA4), c1st_leads, c1st_orders."""

import json


class Faits:
    def __init__(self):
        self.lignes = []
        self.slide = (None, "")          # (numéro, libellé) de la diapositive en cours de construction : posé par revue_fr._ajoute

    def debut(self, numero, libelle=""):
        self.slide = (numero, libelle)

    def ajoute(self, metrique, valeur, marque=None, periode="", source="", marques=None, **extra):
        """marque=None : total affiché ; `marques` = liste des marques que ce total est censé couvrir (permet de vérifier la somme)."""
        if valeur is None:
            return
        ligne = {"metrique": metrique, "marque": marque, "periode": str(periode), "valeur": valeur, "source": source, "slide": self.slide[1] or source, "numero": self.slide[0]}
        if marques is not None:
            ligne["marques"] = sorted(marques)
        ligne.update(extra)
        self.lignes.append(ligne)

    def ecrit(self, chemin):
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(self.lignes, f, ensure_ascii=False, separators=(",", ":"))
