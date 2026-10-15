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


class Analyse(unittest.TestCase):
    def test_regles_sans_ia(self):
        """L'analyse est calculée (aucun appel réseau) et ne cite que des chiffres issus des données."""
        from pipeline.deck.construit import Ctx
        from pipeline.deck import analyse
        from pipeline.deck.donnees import Donnees
        with tempfile.TemporaryDirectory() as tmp:
            brief = {"client": "x", "langue": "fr", "periode": {"type": "trimestre", "annee": 2026, "indice": 3}, "perimetre": {"pays": ["BE"], "marques": []},
                     "comparaisons": {"precedente": True, "n1": True}, "modules": ["analyse"]}
            d = Donnees(["BE"], None, hist=tmp)
            ctx = Ctx(brief, d)
            self.assertTrue(analyse.globale(ctx)["constats"][0].startswith("0 leads sur T3-2026"))

    def test_variation_base_faible(self):
        from pipeline.deck.analyse import _var
        self.assertIsNone(_var(50, 40))
        self.assertAlmostEqual(_var(110, 100), 10)


class Evenements(unittest.TestCase):
    def test_filtre_periode_et_sites(self):
        import json
        from pipeline.deck.donnees import Donnees
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "events")); os.makedirs(os.path.join(tmp, "history"))
            json.dump({"events": [{"date": "2026-09-20", "titre": "Campagne", "sites": []}, {"date": "2026-09-25", "titre": "V2 Peugeot", "sites": ["PEUGEOT BE"]},
                                  {"date": "2026-06-01", "titre": "Avant", "sites": []}]}, open(os.path.join(tmp, "events", "events.json"), "w"))
            d = Donnees(["BE"], None, hist=os.path.join(tmp, "history"))
            p = Periode("trimestre", 2026, 3)
            self.assertEqual([e["titre"] for e in d.evenements(p)], ["Campagne", "V2 Peugeot"])
            self.assertEqual([e["titre"] for e in d.evenements(p, "CITROEN")], ["Campagne"])      # l'événement Peugeot ne concerne pas Citroën


class Construction(unittest.TestCase):
    def test_fumee_sans_donnees(self):
        """Un brief minimal produit un fichier PPTX même sans historique, dans chacune des 5 langues."""
        from pipeline.deck.construit import construit
        from pipeline.deck.donnees import Donnees
        for langue in ("fr", "en", "it", "es", "de"):
            brief = {"titre": "Test", "client": "Stellantis", "langue": langue, "periode": {"type": "trimestre", "annee": 2026, "indice": 3},
                     "perimetre": {"pays": ["BE"], "marques": []}, "comparaisons": {"precedente": True, "n1": True},
                     "modules": ["global", "points_ouverts", "nps", "utm", "analyse"], "contact": {}, "pointsOuverts": [], "prochainesEtapes": []}
            with tempfile.TemporaryDirectory() as tmp:
                d = Donnees(["BE"], None, hist=tmp)
                d.utilisateurs = lambda *a, **k: {"utilisateurs": 0, "in_journey": 0, "hot_leads": 0}   # pas d'appel GA4
                out = os.path.join(tmp, "t.pptx")
                construit(brief, d, out)
                self.assertGreater(os.path.getsize(out), 10000, langue)


if __name__ == "__main__":
    unittest.main()


class ApercuMarques(unittest.TestCase):
    """Vue « une ligne par marque » : tendance, moteurs et actions calculés sur des données fictives."""

    def _ctx(self, **extra):
        from pipeline.deck.construit import Ctx
        brief = {"client": "x", "langue": "fr", "periode": {"type": "trimestre", "annee": 2026, "indice": 3}, "perimetre": {"pays": ["BE"], "marques": []},
                 "comparaisons": {"precedente": True, "n1": True}, "modules": ["global"], **extra}

        class D:
            marques = ["PEUGEOT", "FIAT"]
            sites = []
            def leads(self, p, m=None):
                actuel = p.indice == 3 and p.annee == 2026
                base = 1000 if m == "PEUGEOT" else 50
                n = base if actuel else int(base * 1.2)
                return {"VN": n // 2, "SANS": n // 4, "VO": n - n // 2 - n // 4}
            def leads_total(self, p, m=None):
                return sum(self.leads(p, m).values())
            def acquisition_disponible(self, p):
                return True
            def sources(self, p, m):
                actuel = p.indice == 3 and p.annee == 2026
                z = {g: {"VN": 0, "SANS": 0, "VO": 0} for g in ("Display", "Emailing", "LLM", "Main-Website", "Search", "Social", "Autre")}
                z["Display"]["VN"] = 100 if actuel else 300
                z["Search"]["VN"] = 400
                z["Autre"]["VN"] = 300 if actuel else 0
                return z
            def canaux(self, p, m):
                return {"Display": 1000 if p.indice == 3 and p.annee == 2026 else 1500}
            def utilisateurs(self, p, m):
                return None
        return Ctx(brief, D())

    def test_moteurs_et_actions(self):
        from pipeline.deck import analyse
        a = analyse.apercu_marque(self._ctx(), "PEUGEOT")
        self.assertTrue(any("Display" in x and "−200" in x for x in a["moteurs"]))
        self.assertTrue(any("Renforcer le display" in x for x in a["actions"]))
        self.assertTrue(any("balisage UTM" in x for x in a["actions"]))      # « Autre » = 30 % des leads
        self.assertTrue(a["evols"][0][1].startswith("−"))

    def test_petit_volume_sans_pourcentage(self):
        from pipeline.deck import analyse
        a = analyse.apercu_marque(self._ctx(), "FIAT")
        self.assertIn("faible", a["moteurs"][0])

    def test_diapositive_generee(self):
        from pipeline.deck.construit import apercu_marques
        ctx = self._ctx(actionsMarques={"PEUGEOT": ["Action saisie par le DKAM"]})
        apercu_marques(ctx)
        textes = " ".join(c.text for sl in ctx.prs.slides for sh in sl.shapes if sh.has_table for r in sh.table.rows for c in r.cells)
        self.assertIn("Action saisie par le DKAM", textes)
