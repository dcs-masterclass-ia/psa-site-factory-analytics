import tempfile
import unittest
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
        lignes = []
        if avec:
            def L(jour, src, pj, n, support="", camp=""):
                return {"date": jour, "source_acq": src, "support": support, "campagne": camp, "projet_achat": pj, "statut": "valide", "n": str(n)}
            lignes = [L("2026-09-10", "Search", "VN", 60), L("2026-09-11", "Display", "VN", 40), L("2026-09-12", "Search", "No purchase project", 30),
                      L("2026-09-13", "SOL", "VN", 20), L("2026-08-10", "Search", "VN", 50), L("2026-08-11", "Display", "VN", 50),
                      L("2025-09-10", "Search", "VN", 80), L("2025-08-10", "Search", "VN", 70),
                      # leads du site principal (Main-Website), tous supports : popin 30 + home-page 10 en septembre ; popin 20 en août
                      L("2026-09-14", "Main-Website", "VN", 30, "popinredirectionreprise", "dynamicyield"), L("2026-09-15", "Main-Website", "VN", 10, "home-page"),
                      L("2026-09-16", "Main-Website", "No purchase project", 5, "popinredirectionreprise"), L("2026-08-14", "Main-Website", "VN", 20, "popinredirectionreprise")]

        def lignes_periode(dossier, marque, per, cle="date"):
            return [r for r in lignes if per.debut.isoformat() <= r["date"] <= per.fin.isoformat()]
        d._periode_lignes = lignes_periode
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
            self.assertIn("SOL", txt)          # SOL est une source à part, pas un sous-groupe de Display
            self.assertIn("Total", txt)
            # total sept. 2026 = 195 ; août 2026 = 120 -> +62 % MoM ; sept. 2025 = 80 -> +144 % YoY
            self.assertIn("increased by +62% Month-over-Month", txt)
            self.assertIn("+144% Year-over-Year", txt)
            self.assertTrue(any(sh.has_chart for sh in s.shapes))

    def test_site_principal(self):
        from pipeline.deck.revue_canaux import site_principal
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp)
            s = site_principal(ctx, rv, "PEUGEOT")
            txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            self.assertIn("Popin is the leading generator of NC leads (75%)", txt)      # 30 popin vs 10 home-page en septembre
            self.assertIn("Homepage", txt)
            self.assertIn("Support (groupe)", txt)

    def test_sans_donnees(self):
        from pipeline.deck.revue_canaux import canaux, site_principal
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, avec=False)
            self.assertIsNone(canaux(ctx, rv, "PEUGEOT"))
            self.assertIsNone(site_principal(ctx, rv, "PEUGEOT"))


if __name__ == "__main__":
    unittest.main()
