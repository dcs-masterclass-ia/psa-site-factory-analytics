"""Contrôle de parité des chiffres entre deux présentations (pipeline/deck/parite.py)."""

import unittest

from pipeline.deck import parite


class Nombres(unittest.TestCase):
    def vals(self, t):
        return [v for v, _ in parite.nombres(t)]

    def test_formats(self):
        self.assertEqual(self.vals("10 390 leads"), [10390.0])
        self.assertEqual(self.vals("1,234 and 12.5"), [1234.0, 12.5])
        self.assertEqual(self.vals("10.4k, +102%"), [10400.0, 102.0])
        self.assertEqual(self.vals("1 896 NC sales"), [1896.0])

    def test_pourcentage(self):
        self.assertEqual(parite.nombres("+15%"), [(15.0, True)])

    def test_tolerance(self):
        self.assertTrue(parite.present(10390, False, [(10400.0, False)]))
        self.assertFalse(parite.present(10390, False, [(10600.0, False)]))


if __name__ == "__main__":
    unittest.main()
