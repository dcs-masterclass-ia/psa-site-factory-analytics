"""Nouveau design des présentations (moderne.py / moderne_graphiques.py) : les graphiques se dessinent et les polices embarquées sont présentes."""

import unittest
from pathlib import Path

try:
    from pipeline.deck import moderne_graphiques as mg
except Exception:                                   # matplotlib absent de l'environnement de test
    mg = None


@unittest.skipIf(mg is None, "matplotlib non installé")
class Graphiques(unittest.TestCase):
    def test_polices_embarquees(self):
        for f in ("Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf", "Inter-Bold.ttf", "LICENSE-Inter-OFL.txt"):
            self.assertTrue((Path(mg.__file__).parent / "polices" / f).exists(), f)

    def test_les_graphiques_produisent_des_png(self):
        mois = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        old, cur = [100 + i * 10 for i in range(12)], [150 + i * 12 for i in range(12)]
        sorties = [
            mg.courbes(6, 3, mois, old, cur, 9),
            mg.barres_annuelles(8, 2, mois, old, cur, 9, valeurs=True),
            mg.barres_marques(6, 3, [("A", 100, 60, 50), ("B", 60, 40, 30)]),
            mg.anneau(3, 3, [5, 3, 2], ["#2F3DFF", "#FF4D6D", "#FFA23A"], "10", "x"),
            mg.courbes_projets(8, 2, mois[:6], [("VN", [5, 6, 7, 8, 9, 10], "2F3DFF")]),
            mg.colonnes_empilees(6, 3, ["a", "b"], [("VO", [1, 2], "FFA23A"), ("VN", [3, 4], "2F3DFF")]),
        ]
        for buf in sorties:
            self.assertEqual(buf.read(8), b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
