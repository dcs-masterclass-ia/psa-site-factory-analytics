"""Revue FR : diapositives de résultats (traffic & leads par groupe, projection NC, conversion des ventes NSC)."""

import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from pipeline.deck.construit import Ctx
from pipeline.deck.donnees import Donnees
from pipeline.deck.revue_commun import GROUPE_XP, Revue
from pipeline.deck.revue_resultats import conversion_ventes_nc, projection_nc, trafic_leads_groupe


def _textes(s):
    out = []
    for sh in s.shapes:
        if sh.has_text_frame:
            out.append(sh.text_frame.text)
        if sh.has_table:
            out += [c.text for r in sh.table.rows for c in r.cells]
    return "\n".join(out)


class Resultats(unittest.TestCase):
    def _ctx(self, tmp, leads=True, trafic=True, c1st=True, oct_leads=True):
        racine = Path(tmp)
        (racine / "history").mkdir()
        brief = {"client": "x", "langue": "en", "periode": {"type": "mois", "annee": 2026, "indice": 9}, "perimetre": {"pays": ["FR"], "marques": []},
                 "comparaisons": {"precedente": True, "n1": True}, "modules": [], "contact": {}, "pointsOuverts": [], "prochainesEtapes": []}
        d = Donnees(["FR"], None, hist=racine / "history")
        d.sites = [("PEUGEOT FR", "PEUGEOT", "FR"), ("CITROEN FR", "CITROEN", "FR")]
        d.marques = ["PEUGEOT", "CITROEN"]
        L = defaultdict(lambda: defaultdict(int))
        if leads:
            for a, base in ((2025, 50), (2026, 100)):
                for mo in range(1, 10):
                    for marque, k in (("PEUGEOT", 1), ("CITROEN", 2)):
                        L[(marque, f"{a}-{mo:02d}-15")]["VN"] += base * k
            L[("PEUGEOT", "2025-10-10")]["VN"] += 310
            if oct_leads:
                L[("PEUGEOT", "2026-10-10")]["VN"] += 100
                L[("CITROEN", "2026-10-10")]["VN"] += 200
        d._leads = L
        d.utilisateurs = lambda p, m: None
        S = {("PEUGEOT", 2026, 9): 2000, ("PEUGEOT", 2026, 8): 1000, ("PEUGEOT", 2025, 9): 1600}
        d.canaux = lambda p, m: ({"Direct": S.get((m, p.annee, p.indice), 0)} if trafic else {})
        if c1st:
            d._c1st_partiel = "2026-10"
            d._c1st_data = {"FR": {f"{a}-{mo:02d}": {"nsc": [{"marque": "AP", "commandes_nsc": 10 * (a - 2024)}, {"marque": "AC", "commandes_nsc": 5}]}
                                   for a in (2025, 2026) for mo in range(1, 10)}}
        else:
            d._c1st_data, d._c1st_partiel = {}, ""
        ctx = Ctx(brief, d)
        return ctx, Revue(ctx)

    def test_trafic_leads_groupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp)
            s = trafic_leads_groupe(ctx, rv, "xP", [m for m in GROUPE_XP if m in ctx.d.marques])
            t = _textes(s)
            self.assertIn("Traffic and leads by brand xP", t)
            self.assertIn("2 000", t)          # sessions Peugeot sept.
            self.assertIn("+100.0%", t)        # MoM 1000 -> 2000
            self.assertIn("+25.0%", t)         # YoY 1600 -> 2000
            self.assertIn("Source: autobiz + GA", t)
            self.assertIn("MoM (Sep 26 vs Aug 26)", t)

    def test_trafic_leads_sans_donnees(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, leads=False, trafic=False)
            self.assertIsNone(trafic_leads_groupe(ctx, rv, "xP", ["PEUGEOT", "CITROEN"]))
            self.assertIsNone(trafic_leads_groupe(ctx, rv, "xF", ["FIAT"]))

    def test_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp)
            s = projection_nc(ctx, rv)
            t = _textes(s)
            self.assertIn("NC Leads projection", t)
            self.assertIn("Source: autobiz data till October 10th", t)
            self.assertIn("Projection Oct", t)
            self.assertIn("310", t)            # Peugeot : 100 leads à 10 jours -> 100/10*31
            self.assertIn("620", t)            # Citroën 200/10*31
            self.assertIn("+200%", t)          # total 930 vs 310 en octobre 2025
            self.assertIn("930", t)            # total général projeté
            self.assertIn("Total", t)
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, oct_leads=False)
            self.assertIsNone(projection_nc(ctx, rv))       # aucun lead du mois en cours
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, leads=False)
            self.assertIsNone(projection_nc(ctx, rv))

    def test_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp)
            s = conversion_ventes_nc(ctx, rv)
            t = _textes(s)
            self.assertIn("Leads from Jan. to September 30th. 26 incl.", t)
            # Peugeot : leads 9 x 100 = 900 (2026) vs 450 (2025) ; commandes 9 x 20 = 180 vs 90
            for v in ("900", "450", "180", "90", "100%"):
                self.assertIn(v, t)
            self.assertIn("20.0%", t)           # 180 / 900
            self.assertIn("Sales are still processing", t)
            self.assertIn("Total FR", t)
            self.assertIn("From Jan to Sep 30th. 2026", t)

    def test_conversion_sans_c1st(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, c1st=False)
            t = _textes(conversion_ventes_nc(ctx, rv))
            self.assertIn("n/a", t)             # commandes absentes : jamais inventées
            self.assertIn("900", t)
        with tempfile.TemporaryDirectory() as tmp:
            ctx, rv = self._ctx(tmp, leads=False, c1st=False)
            self.assertIsNone(conversion_ventes_nc(ctx, rv))


if __name__ == "__main__":
    unittest.main()
