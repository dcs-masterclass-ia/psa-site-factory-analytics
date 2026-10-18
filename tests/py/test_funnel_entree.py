"""Funnel par mode de saisie : sélection des mois à (re)calculer, jamais de valeur inventée."""
import unittest
from unittest import mock

from pipeline import funnel_entree as fe


class MettreAJour(unittest.TestCase):
    def _lance(self, existant, mois, resultats):
        appels = []

        def faux(cli, pid, hote, m, dernier):
            appels.append(m)
            return resultats.get(m)
        with mock.patch.object(fe, "AlphaAnalyticsDataClient", lambda: None), mock.patch.object(fe, "mois_entree", faux):
            out = fe.mettre_a_jour("1", "h", existant, mois, "2026-10-16")
        return out, appels

    def test_recalcule_les_deux_derniers_mois_et_rattrape_au_plus_trois_manquants(self):
        mois = [f"2026-{m:02d}" for m in range(1, 11)]
        res = {m: {"tous": [1] * 6, "marque_modele": [0] * 6} for m in mois}
        out, appels = self._lance({}, mois, res)
        self.assertEqual(sorted(appels), ["2026-07", "2026-08", "2026-09", "2026-10"][:0] + sorted(["2026-09", "2026-10", "2026-08", "2026-07", "2026-06"]))
        self.assertEqual(len(out), 5)

    def test_mois_deja_connu_non_recalcule_sauf_les_deux_derniers(self):
        mois = ["2026-07", "2026-08", "2026-09", "2026-10"]
        ancien = {"2026-07": {"tous": [9] * 6, "marque_modele": [1] * 6}}
        res = {m: {"tous": [2] * 6, "marque_modele": [1] * 6} for m in mois}
        out, appels = self._lance(ancien, mois, res)
        self.assertNotIn("2026-07", appels)
        self.assertEqual(out["2026-07"]["tous"], [9] * 6)          # conservé tel quel

    def test_mois_sans_visiteurs_non_enregistre(self):
        out, _ = self._lance({}, ["2026-09", "2026-10"], {})
        self.assertEqual(out, {})

    def test_marque_modele_jamais_superieur_au_total(self):
        class R:  # rapport simulé : le segment dépasse le total (arrondis de GA4)
            pass
        with mock.patch.object(fe, "_rapport", side_effect=[[10, 8, 7, 6, 4, 3], [12, 9, 7, 6, 4, 3]]):
            r = fe.mois_entree(None, "1", "h", "2026-09", "2026-10-16")
        self.assertEqual(r["marque_modele"], [10, 8, 7, 6, 4, 3])


if __name__ == "__main__":
    unittest.main()
