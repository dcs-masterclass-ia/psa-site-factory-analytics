"""Tests du générateur de présentations (sans réseau, sans données réelles) : python3 -m unittest tests.py.test_deck"""
import os, tempfile, unittest

from pipeline.deck.periodes import Periode, depuis_brief
from pipeline.deck.textes import T


class Periodes(unittest.TestCase):
    def test_trimestre(self):
        p = Periode("trimestre", 2026, 3)
        self.assertEqual((p.debut.isoformat(), p.fin.isoformat()), ("2026-07-01", "2026-09-30"))
        self.assertEqual(p.precedente().indice, 2)
        self.assertEqual(p.n1().annee, 2025)

    def test_precedente_enjambe_l_annee(self):
        p = Periode("trimestre", 2026, 1).precedente()
        self.assertEqual((p.annee, p.indice), (2025, 4))

    def test_ancien_format_brief(self):
        p = depuis_brief({"annee": 2026, "trimestre": 3})
        self.assertEqual((p.type, p.indice), ("trimestre", 3))

    def test_annee(self):
        p = Periode("annee", 2025, None)
        self.assertEqual((p.debut.isoformat(), p.fin.isoformat()), ("2025-01-01", "2025-12-31"))


class Textes(unittest.TestCase):
    def test_base_faible_ns(self):
        self.assertIsNone(T("fr").evol(50, 40)[2])      # base < 100 : pas de pourcentage
        self.assertIsNone(T("fr").evol(None, 500)[2])

    def test_evolution(self):
        txt, signe, v = T("fr").evol(1100, 1000)
        self.assertEqual(signe, 1)
        self.assertAlmostEqual(v, 10)


class Construction(unittest.TestCase):
    def test_fumee_sans_donnees(self):
        """Un brief minimal produit un fichier PPTX même sans historique (modules vides, avertissements)."""
        from pipeline.deck.construit import construit
        from pipeline.deck.donnees import Donnees
        brief = {"titre": "Test", "client": "Stellantis", "langue": "fr", "periode": {"type": "trimestre", "annee": 2026, "indice": 3},
                 "perimetre": {"pays": ["BE"], "marques": []}, "comparaisons": {"precedente": True, "n1": True},
                 "modules": ["global", "points_ouverts"], "contact": {}, "pointsOuverts": [], "prochainesEtapes": []}
        with tempfile.TemporaryDirectory() as tmp:
            d = Donnees(["BE"], None, hist=tmp)
            d.utilisateurs = lambda *a, **k: {"utilisateurs": 0, "in_journey": 0, "hot_leads": 0}   # pas d'appel GA4
            out = os.path.join(tmp, "t.pptx")
            construit(brief, d, out)
            self.assertGreater(os.path.getsize(out), 10000)


if __name__ == "__main__":
    unittest.main()
