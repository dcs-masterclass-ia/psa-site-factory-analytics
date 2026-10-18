"""Funnel par mode de saisie : lecture de virtualpage_url (/form/plate/…, /form/brand/…), jamais de valeur inventée."""
import datetime
import unittest
from unittest import mock

from pipeline import funnel_entree as fe

D, F = datetime.date(2026, 9, 1), datetime.date(2026, 9, 30)


def faux_rapport(pages, estimations):
    """1er appel = pages vues par parcours, 2e = évènement d'estimation."""
    return mock.patch.object(fe.ga4, "_rapport", side_effect=[pages, estimations])


class FunnelEntree(unittest.TestCase):
    def test_parcours_plaque_et_marque_modele_separes(self):
        pages = [("202609", "/form/plate/version", "100"), ("202609", "/form/plate/mileage", "90"), ("202609", "/form/plate/contact", "85"), ("202609", "/form/plate/map", "50"),
                 ("202609", "/form/brand/version", "10"), ("202609", "/form/brand/mileage", "8"), ("202609", "/form/brand/contact", "7"), ("202609", "/form/brand/map", "4"),
                 ("202609", "/home", "999"), ("202609", "/form/plate/offer", "45")]                   # accueil et page d'offre ignorés (l'estimation vient de l'évènement)
        est = [("202609", "/form/plate/offer", "44"), ("202609", "/form/brand/offer", "3")]
        with faux_rapport(pages, est):
            r = fe.funnel_entree(None, "1", "h", D, F)
        self.assertEqual(r["2026-09"]["immat"], [100, 90, 85, 50, 44])
        self.assertEqual(r["2026-09"]["marque_modele"], [10, 8, 7, 4, 3])

    def test_sans_parcours_reconnu_rien_n_est_ecrit(self):
        with faux_rapport([("202609", "/home", "10"), ("202609", "(not set)", "5")], []):
            self.assertEqual(fe.funnel_entree(None, "1", "h", D, F), {})

    def test_url_avec_prefixe_de_langue_reconnue(self):
        with faux_rapport([("202609", "/nl/form/brand/version?x=1", "12")], []):
            r = fe.funnel_entree(None, "1", "h", D, F)
        self.assertEqual(r["2026-09"]["marque_modele"][0], 12)

    def test_erreur_ga4_donne_vide(self):
        with mock.patch.object(fe.ga4, "_rapport", side_effect=RuntimeError("quota")):
            self.assertEqual(fe.funnel_entree(None, "1", "h", D, F), {})


if __name__ == "__main__":
    unittest.main()
