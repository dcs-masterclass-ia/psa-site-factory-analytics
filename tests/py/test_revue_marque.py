"""Tests des diapositives par marque de la revue mensuelle France (revue_marque) : sans réseau."""
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path


class RevueMarque(unittest.TestCase):
    def _ctx(self, tmp, ga4=True, leads=True, trafic=True):
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
        lead = defaultdict(lambda: defaultdict(int))
        if leads:
            for a, base in ((2025, 50), (2026, 100)):
                for mo in range(1, 10):
                    lead[("PEUGEOT", f"{a}-{mo:02d}-15")]["VN"] += base
                    lead[("PEUGEOT", f"{a}-{mo:02d}-16")]["VO"] += 10
        d._leads = lead
        d._trafic = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        d._site_marque = defaultdict(lambda: [0, 0])
        d._ga4 = {}
        if trafic:
            if ga4:
                for per, s, ij, hl, can in (("2026-09-01|2026-09-30", 1000, 400, 100, {"Display": 600, "Paid Search": 300, "Direct": 100}),
                                            ("2026-08-01|2026-08-31", 800, 300, 50, {"Display": 500, "Paid Search": 300}),
                                            ("2025-09-01|2025-09-30", 1250, 350, 40, {"Display": 800, "Paid Search": 450})):
                    a, b = per.split("|")
                    d._ga4[f"v3|PEUGEOT FR|{a}|{b}"] = {"sessions": s, "in_journey": ij, "hot_leads": hl, "utilisateurs": s, "canaux": can}
            else:
                d._ga4 = None
                d.utilisateurs = lambda p, m: None
                d._trafic[("PEUGEOT", "2026-09-10")]["Display"] = [500, 0]
            d._site_marque[("PEUGEOT", "2026-09-10")] = [200, 1000]
            d._site_marque[("PEUGEOT", "2025-09-10")] = [250, 1250]
        d._site_json = lambda nom: {"propSessions": {"month": {"2026-09": 20000, "2026-08": 25000, "2025-09": 30000}},
                                    "repriseMonth": {"2026-09": {"sessions": 1000}}}
        ctx = Ctx(brief, d)
        return ctx, Revue(ctx)

    def test_trafic(self):
        from pipeline.deck.revue_marque import trafic
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp)
            s = trafic(ctx, rv, "PEUGEOT")
            self.assertEqual(s.shapes.title.text, "Traffic")
            txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            self.assertIn("September 2026", txt)
            self.assertIn("1 000", txt)
            self.assertIn("Ratio trade-in sessions / main website sessions: 5.0%", txt)
            self.assertIn("overall conversion rate 10.0%", txt)
            self.assertIn("Main channel: Display, 60.0%", txt)
            self.assertIn("-20.0% YoY", txt)
            self.assertIn("outperformed Peugeot main website traffic", txt.replace("  ", " "))
            self.assertIn("20 000", txt)
            self.assertTrue(any(sh.has_chart for sh in s.shapes) and any(sh.has_table for sh in s.shapes))

    def test_trafic_sans_ga4(self):
        from pipeline.deck.revue_marque import trafic
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, ga4=False)
            s = trafic(ctx, rv, "PEUGEOT")
            txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            self.assertIn("n/a", txt)

    def test_trafic_aucune_session(self):
        from pipeline.deck.revue_marque import trafic
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, trafic=False)
            ctx.d.utilisateurs = lambda p, m: None
            self.assertIsNone(trafic(ctx, rv, "PEUGEOT"))

    def test_ytd(self):
        from pipeline.deck.revue_marque import ytd
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp)
            s = ytd(ctx, rv, "PEUGEOT")
            self.assertEqual(s.shapes.title.text, "YTD Leads Trends")
            self.assertEqual(sum(1 for sh in s.shapes if sh.has_chart), 2)
            txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            self.assertIn("990 leads year to date in 2026, +83% vs 2025 (540)", txt)
            self.assertIn("NC leads represent 91% of 2026", txt)

    def test_ytd_sans_donnees(self):
        from pipeline.deck.revue_marque import ytd
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, leads=False)
            self.assertIsNone(ytd(ctx, rv, "PEUGEOT"))


if __name__ == "__main__":
    unittest.main()
