import tempfile
import unittest
from collections import defaultdict
from pathlib import Path


class RevueCanaux(unittest.TestCase):
    def _ctx(self, tmp, avec=True):
        from pipeline.deck.construit import Ctx
        from pipeline.deck.donnees import Donnees
        from pipeline.deck.revue_commun import Revue
        racine = Path(tmp)
        (racine / "history").mkdir()
        brief = {"client": "x", "langue": "en", "format": "revue_fr", "periode": {"type": "mois", "annee": 2026, "indice": 9}, "perimetre": {"pays": ["FR"], "marques": []},
                 "comparaisons": {"precedente": True, "n1": True}, "modules": [], "contact": {}, "pointsOuverts": [], "prochainesEtapes": []}
        d = Donnees(["FR"], None, hist=racine / "history")
        d.sites = [("PEUGEOT FR", "PEUGEOT", "FR")]
        d.marques = ["PEUGEOT"]
        acq = defaultdict(lambda: defaultdict(int))
        if avec:
            from pipeline.deck.donnees import groupe_source
            for jour, src, pj, n in [("2026-09-10", "search", "VN", 60), ("2026-09-11", "display", "VN", 40), ("2026-09-12", "search", "SANS", 30),
                                     ("2026-08-10", "search", "VN", 50), ("2026-08-11", "display", "VN", 50), ("2025-09-10", "search", "VN", 80), ("2025-08-10", "search", "VN", 70)]:
                acq[("PEUGEOT", jour)][(groupe_source(src), pj)] += n
        d._acq = acq
        d.cta = lambda per, m: ({"Popin": {"VN": 30, "SANS": 5, "VO": 0}, "Footer": {"VN": 10, "SANS": 0, "VO": 0}} if (avec and per.indice == 9) else
                                {"Popin": {"VN": 20, "SANS": 5, "VO": 0}} if avec else {})
        ctx = Ctx(brief, d)
        return ctx, Revue(ctx)

    def test_canaux(self):
        from pipeline.deck.revue_canaux import canaux
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp)
            s = canaux(ctx, rv, "PEUGEOT")
            self.assertEqual(s.shapes.title.text, "Leads by marketing channel")
            txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            self.assertIn("September 2026", txt)
            self.assertIn("SOURCE_ACQ", txt)
            self.assertIn("SEA", txt)
            self.assertIn("Total général", txt)
            # total sept. 2026 = 130 ; août 2026 = 100 -> +30 % MoM ; sept. 2025 = 80 -> +62 % YoY
            self.assertIn("increased by +30% Month-over-Month", txt)
            self.assertIn("+62% Year-over-Year", txt)
            self.assertTrue(any(sh.has_chart for sh in s.shapes))

    def test_site_principal(self):
        from pipeline.deck.revue_canaux import site_principal
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp)
            s = site_principal(ctx, rv, "PEUGEOT")
            txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            self.assertIn("Popin is the leading generator of NC leads (75%)", txt)
            self.assertIn("Support (groupe)", txt)

    def test_sans_donnees(self):
        from pipeline.deck.revue_canaux import canaux, site_principal
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, avec=False)
            self.assertIsNone(canaux(ctx, rv, "PEUGEOT"))
            self.assertIsNone(site_principal(ctx, rv, "PEUGEOT"))


if __name__ == "__main__":
    unittest.main()
