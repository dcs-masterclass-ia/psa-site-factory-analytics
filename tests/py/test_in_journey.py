"""In Journey (alignement Looker) : définition et filtre (pipeline/ga4.py). python3 -m unittest tests.py.test_in_journey"""
import unittest
from pipeline import ga4


class InJourney(unittest.TestCase):
    def test_pages_du_parcours(self):
        # form page + lead page = In Journey de Looker (OPEL FR sept. 2026 : 6 945 + lead page -> 7 025)
        self.assertEqual(ga4.PAGES_IN_JOURNEY, ("form page", "lead page"))

    def test_filtre_hote_et_categorie(self):
        f = ga4._filtre_in_journey("www.reprise.opel.fr")
        champs = [e.filter.field_name for e in f.and_group.expressions]
        self.assertEqual(champs, ["hostName", "customEvent:page_category"])
        liste = f.and_group.expressions[1].filter.in_list_filter.values
        self.assertEqual(list(liste), ["form page", "lead page"])

    def test_plusieurs_hotes_de_reprise(self):
        f = ga4._filtre_in_journey("a.example|b.example")
        self.assertEqual(list(f.and_group.expressions[0].filter.in_list_filter.values), ["a.example", "b.example"])


if __name__ == "__main__":
    unittest.main()
