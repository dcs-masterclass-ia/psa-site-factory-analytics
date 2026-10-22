import tempfile
import unittest
from pathlib import Path


def _ctx(tmp, reprises, modeles):
    from pipeline.deck.construit import Ctx
    from pipeline.deck.donnees import Donnees
    from pipeline.deck.revue_commun import Revue
    racine = Path(tmp)
    (racine / "history").mkdir()
    brief = {"client": "x", "langue": "en", "periode": {"type": "mois", "annee": 2026, "indice": 9}, "perimetre": {"pays": ["FR"], "marques": []},
             "comparaisons": {"precedente": True, "n1": True}, "modules": [], "contact": {}, "pointsOuverts": [], "prochainesEtapes": []}
    d = Donnees(["FR"], None, hist=racine / "history")
    d.sites = [("PEUGEOT FR", "PEUGEOT", "FR")]
    d.marques = ["PEUGEOT"]
    d.reprises = lambda p, m: reprises
    d.modeles = lambda p, m, projet=None: modeles if projet is None else [x for x in modeles if x[4] != 999]
    ctx = Ctx(brief, d)
    return ctx, Revue(ctx)


MODS = [("PEUGEOT", "208", "PEUGEOT", "208", 60), ("RENAULT", "CLIO", "PEUGEOT", "208", 30), ("PEUGEOT", "308", "PEUGEOT", "3008", 10)]


class Conquete(unittest.TestCase):
    def test_slide_et_chiffres(self):
        from pipeline.deck.revue_conquete import conquete
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = _ctx(tmp, {"PEUGEOT": 50, "CITROEN": 14, "RENAULT": 36}, MODS)
            s = conquete(ctx, rv, "PEUGEOT")
            self.assertEqual(s.shapes.title.text, "LEAD DEEP DIVE")           # le mois figure dans le sous-titre « Conquest Vs Loyalty … »
            txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            self.assertIn("50% of trade-in website customers are loyalty", txt)
            self.assertIn("14% are Stellantis", txt)
            self.assertIn("36% are owners from competitors", txt)
            self.assertIn("Clio", txt)
            self.assertEqual(sum(1 for sh in s.shapes if sh.has_chart), 4)
            self.assertEqual(sum(1 for sh in s.shapes if sh.has_table), 1)

    def test_sans_modeles(self):
        from pipeline.deck.revue_conquete import conquete
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = _ctx(tmp, {"PEUGEOT": 5, "RENAULT": 5}, None)
            s = conquete(ctx, rv, "PEUGEOT")
            self.assertIsNotNone(s)
            self.assertEqual(sum(1 for sh in s.shapes if sh.has_table), 0)

    def test_sans_donnees(self):
        from pipeline.deck.revue_conquete import conquete
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = _ctx(tmp, {}, None)
            self.assertIsNone(conquete(ctx, rv, "PEUGEOT"))


if __name__ == "__main__":
    unittest.main()


class ModelesFiltre(unittest.TestCase):
    def test_filtre_projet(self):
        import gzip
        from pipeline.deck.donnees import Donnees
        from pipeline.deck.periodes import Periode
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp) / "history"
            (h / "leads_modeles").mkdir(parents=True)
            with gzip.open(h / "leads_modeles" / "peugeot-fr.csv.gz", "wt", encoding="utf-8") as f:
                f.write("mois,site_id,marque_reprise,modele_reprise,marque_achat,modele_achat,projet_achat,valides\n"
                        "2026-09,1,RENAULT,CLIO,PEUGEOT,208,VN,7\n2026-09,1,RENAULT,CLIO,PEUGEOT,208,VO,3\n")
            d = Donnees(["FR"], None, hist=h)
            d.sites = [("PEUGEOT FR", "PEUGEOT", "FR")]
            per = Periode("mois", 2026, 9)
            self.assertEqual(d.modeles(per, "PEUGEOT")[0][4], 10)
            self.assertEqual(d.modeles(per, "PEUGEOT", "VN")[0][4], 7)
