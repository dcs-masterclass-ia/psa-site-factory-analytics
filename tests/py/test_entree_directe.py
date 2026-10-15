"""Règle « Site Marque vs Entrée directe » de Looker (pipeline/ga4.py: classe_entree). python3 -m unittest tests.py.test_entree_directe"""
import unittest
from pipeline.ga4 import classe_entree

T, B = "Trade In Entry", "Brand Websites"


class Classement(unittest.TestCase):
    def test_source_main_website(self):
        self.assertEqual(classe_entree("Main-Website", "https://www.google.com/"), B)
        self.assertEqual(classe_entree("Main-Website", ""), B)

    def test_source_main_website_est_une_correspondance_complete(self):
        # REGEXP_MATCH de Looker : le motif doit couvrir toute la valeur
        self.assertEqual(classe_entree("Main-Website-2", "https://www.google.com/"), T)

    def test_provenance_reprise(self):
        self.assertEqual(classe_entree("google", "https://www.reprise.opel.fr/estimation"), T)
        self.assertEqual(classe_entree("x", "https://www.opel.de/wir-kaufen-ihr-auto"), T)

    def test_provenance_site_marque(self):
        self.assertEqual(classe_entree("google", "https://www.opel.fr/"), B)
        self.assertEqual(classe_entree("google", "https://www.citroen.fr/offres"), B)
        self.assertEqual(classe_entree("google", "https://www.dsautomobiles.fr/"), B)

    def test_autres_provenances(self):
        for ref in ("https://www.google.com/", "https://facebook.com/", "", "(not set)"):
            self.assertEqual(classe_entree("google", ref), T)

    def test_reprise_prioritaire_sur_marque(self):
        # « reprise » est testé avant les noms de marque : reprise.opel.fr = Trade In Entry
        self.assertEqual(classe_entree("google", "https://reprise.peugeot.fr/"), T)


if __name__ == "__main__":
    unittest.main()
