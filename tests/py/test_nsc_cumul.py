"""Commandes NSC cumulées (janvier au mois) : valeur dédupliquée collectée à part, repli sur la somme des mois. python -m unittest tests.py.test_nsc_cumul"""
import unittest

from pipeline.deck.donnees import Donnees
from pipeline.deck.periodes import Periode


def donnees(data, partiel=""):
    d = object.__new__(Donnees)
    d._c1st_data, d._c1st_partiel, d.pays = data, partiel, ["FR"]
    return d


class _Cumul:
    """Même contrat que la période « janvier au mois » du tableau NC Sales Conversion."""
    def __init__(self, a, m):
        self.a, self.m = a, m

    def mois(self):
        return [(self.a, i) for i in range(1, self.m + 1)]


class NscCumul(unittest.TestCase):
    def test_cumul_prioritaire_sur_la_somme(self):
        data = {"FR": {"2026-01": {"nsc": [{"marque": "AC", "commandes_nsc": 100}], "nsc_cumul": [{"marque": "AC", "commandes_nsc": 100}]},
                       "2026-02": {"nsc": [{"marque": "AC", "commandes_nsc": 90}], "nsc_cumul": [{"marque": "AC", "commandes_nsc": 170}]}}}      # 190 en sommant, 170 dédupliqué
        self.assertEqual(donnees(data).c1st_nsc(_Cumul(2026, 2), "CITROEN"), 170)

    def test_repli_somme_sans_cumul(self):
        data = {"FR": {"2026-01": {"nsc": [{"marque": "AC", "commandes_nsc": 100}]}, "2026-02": {"nsc": [{"marque": "AC", "commandes_nsc": 90}]}}}
        self.assertEqual(donnees(data).c1st_nsc(_Cumul(2026, 2), "CITROEN"), 190)

    def test_mois_partiel_jamais_utilise(self):
        data = {"FR": {"2026-01": {"nsc": [], "nsc_cumul": [{"marque": "AC", "commandes_nsc": 5}]}}}
        self.assertIsNone(donnees(data, partiel="2026-01").c1st_nsc(_Cumul(2026, 1), "CITROEN"))

    def test_periode_hors_cumul_somme_des_mois(self):
        data = {"FR": {"2026-02": {"nsc": [{"marque": "AC", "commandes_nsc": 7}], "nsc_cumul": [{"marque": "AC", "commandes_nsc": 99}]}}}
        self.assertEqual(donnees(data).c1st_nsc(Periode("mois", 2026, 2), "CITROEN"), 7)


if __name__ == "__main__":
    unittest.main()
