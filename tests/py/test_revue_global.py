import tempfile
import unittest
from collections import defaultdict
from pathlib import Path


class RevueGlobal(unittest.TestCase):
    """Diapositives 4 à 6 de la revue FR (résumé exécutif, vue globale, tendance) : données injectées, sans réseau."""

    def _ctx(self, tmp, vide=False, c1st=False):
        from pipeline.deck.construit import Ctx
        from pipeline.deck.donnees import Donnees
        from pipeline.deck.revue_commun import Revue
        racine = Path(tmp)
        (racine / "history").mkdir()
        brief = {"client": "x", "langue": "en", "format": "revue_fr", "periode": {"type": "mois", "annee": 2026, "indice": 9}, "perimetre": {"pays": ["FR"], "marques": []},
                 "comparaisons": {"precedente": True, "n1": True}, "modules": ["global"], "contact": {}, "pointsOuverts": [], "prochainesEtapes": []}
        d = Donnees(["FR"], None, hist=racine / "history")
        d.sites = [("PEUGEOT FR", "PEUGEOT", "FR"), ("CITROEN FR", "CITROEN", "FR")]
        d.marques = ["PEUGEOT", "CITROEN"]
        leads = defaultdict(lambda: defaultdict(int))
        if not vide:
            for a, base in ((2025, 50), (2026, 100)):
                for mo in range(1, 10):
                    for marque, k in (("PEUGEOT", 1), ("CITROEN", 2)):
                        leads[(marque, f"{a}-{mo:02d}-15")]["VN"] += base * k
                        leads[(marque, f"{a}-{mo:02d}-16")]["VO"] += 10
        d._leads = leads
        d._acq = {}
        if c1st:
            d._c1st_data = {"FR": {f"{a}-{m:02d}": {"nsc": [{"marque": "AP", "commandes_nsc": 10 * (a - 2024)}, {"marque": "AC", "commandes_nsc": 5}]}
                                    for a in (2025, 2026) for m in range(1, 10)}}
        ctx = Ctx(brief, d)
        return ctx, Revue(ctx)

    def test_tendance(self):
        from pipeline.deck.revue_global import tendance_leads
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp)
            s = tendance_leads(ctx, rv)
            self.assertEqual(s.shapes.title.text, "Executive Summary")
            self.assertEqual(sum(1 for sh in s.shapes if getattr(sh, "has_chart", False) and sh.has_chart), 2)
            ch = [sh.chart for sh in s.shapes if getattr(sh, "has_chart", False) and sh.has_chart][0]
            self.assertEqual(ch.plots[0].series[1].values[8], 100 * 3 + 20)          # septembre 2026 : (100 + 200) VN + 2 x 10 VO
            self.assertEqual(ch.plots[0].series[0].values[8], 50 * 3 + 20)
            txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            self.assertIn("+88% YoY in September", txt)                  # 320 vs 170

    def test_vue_globale(self):
        from pipeline.deck.revue_global import vue_globale
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp)
            s = vue_globale(ctx, rv)
            txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            self.assertIn("EXEC SUMMARY - TRADE IN SITUATION SEPTEMBER 2026", txt)
            self.assertIn("REPORTING YTD", txt)
            self.assertIn("320", txt)                                    # leads de septembre
            self.assertIn("2 880", txt)                                  # cumul : 9 x 320
            self.assertIn("+88%", txt)                                   # cumul vs 2025 : 2 880 / 1 530
            self.assertIn("Global view", " ".join(p.text for p in s.placeholders if p.placeholder_format.idx == 12))
            charts = [sh.chart for sh in s.shapes if getattr(sh, "has_chart", False) and sh.has_chart]
            self.assertEqual(len(charts), 2)
            self.assertEqual(len(list(charts[1].plots[0].series)), 3)

    def test_resume(self):
        from pipeline.deck.revue_global import resume_executif
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, c1st=True)
            s = resume_executif(ctx, rv)
            tb = [sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.startswith("Strong YTD")][0]
            paras = tb.text_frame.paragraphs
            self.assertGreaterEqual(len(paras), 4)
            self.assertTrue(paras[0].runs[0].font.bold)
            self.assertEqual(paras[0].runs[0].font.size.pt, 16)
            txt = tb.text_frame.text
            self.assertIn("2.9k leads generated, +88% vs 2025", txt)
            self.assertIn("225 NC sales", txt)                 # commandes NSC cumulées : (20 + 5) x 9
            self.assertIn("90 more than last year", txt)
            self.assertIn("Peugeot", txt)

    def test_sans_donnees(self):
        from pipeline.deck.revue_global import resume_executif, tendance_leads, vue_globale
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, vide=True)
            for f in (resume_executif, vue_globale, tendance_leads):
                self.assertIsNone(f(ctx, rv))


if __name__ == "__main__":
    unittest.main()
