import unittest
from datetime import date


class AgregeAds(unittest.TestCase):
    def test_comptes_mois_et_campagnes(self):
        from pipeline.ads import agrege
        mois = [("202609", "Compte A", 100.0, 1000, 20000), ("202610", "Compte A", 50.0, 400, 9000), ("202610", "(not set)", 0, 5, 5), ("202610", "Compte B", 0.0, 300, 7000)]
        camps = [("Compte A", "Camp 1", 120.0, 900, 18000), ("Compte A", "Camp 2", 0.0, 100, 2000), ("Compte B", "Camp 3", 0.0, 300, 7000), ("(not set)", "x", 1, 1, 1)]
        r = agrege(mois, camps)
        self.assertEqual([c["nom"] for c in r], ["Compte A", "Compte B"])           # triés par clics, « (not set) » ignoré
        a = r[0]
        self.assertEqual(a["mensuel"], {"2026-09": [100.0, 1000, 20000], "2026-10": [50.0, 400, 9000]})
        self.assertEqual((a["cout"], a["clics"], a["impressions"], a["campagnes"]), (120.0, 1000, 20000, 2))
        self.assertEqual(a["clics_sans_cout"], 100)                                  # Camp 2 : des clics mais aucun coût transmis
        self.assertEqual(a["top"][0], ["Camp 1", 120.0, 900, 18000, 0])
        self.assertEqual(r[1]["clics_sans_cout"], 300)                               # tout le compte B est sans coût

    def test_periode_precedente(self):
        from pipeline.ads import agrege
        camps = [("A", "Camp 1", 10.0, 500, 9000)]
        prec = [("A", "Camp 1", 8.0, 400, 8000), ("A", "Camp 2", 3.0, 300, 5000), ("B", "Camp 9", 0.0, 50, 500)]
        r = {c["nom"]: c for c in agrege([("202610", "A", 10, 500, 9000)], camps, prec)}
        a = r["A"]
        self.assertEqual((a["clics_prec"], a["impressions_prec"], a["cout_prec"]), (700, 13000, 11.0))
        tops = {t[0]: t for t in a["top"]}
        self.assertEqual(tops["Camp 1"][4], 400)                                    # clics de la période précédente
        self.assertEqual(tops["Camp 2"], ["Camp 2", 0.0, 0, 0, 300])                # campagne arrêtée : gardée pour les « perdantes »
        self.assertEqual(r["B"]["clics"], 0)                                        # compte actif seulement avant : conservé avec ses clics précédents
        self.assertEqual(r["B"]["clics_prec"], 50)

    def test_top_limite_et_compte_vide_ecarte(self):
        from pipeline.ads import TOP_CAMPAGNES, agrege
        camps = [("A", f"C{i}", 1.0, 100 - i, 10) for i in range(TOP_CAMPAGNES + 5)]
        r = agrege([("202610", "A", 1, 1, 1), ("202610", "Vide", 0, 0, 0)], camps)
        self.assertEqual(len(r), 1)                                                  # un compte sans clic ni coût disparaît
        self.assertEqual(len(r[0]["top"]), TOP_CAMPAGNES)
        self.assertEqual(r[0]["campagnes"], TOP_CAMPAGNES + 5)

    def test_debut_historique(self):
        from pipeline.ads import debut_historique
        self.assertEqual(debut_historique(date(2026, 10, 28)), date(2025, 10, 1))
        self.assertEqual(debut_historique(date(2026, 1, 5)), date(2025, 1, 1))

    def test_mois_a_collecter(self):
        from pipeline.ads import MOIS_HISTORIQUE, mois_a_collecter
        m = mois_a_collecter(date(2026, 10, 28))
        self.assertEqual(len(m), MOIS_HISTORIQUE)
        self.assertEqual(m[0], ("202510", "2025-10-01", "2025-10-31"))
        self.assertEqual(m[-1], ("202610", "2026-10-01", "2026-10-27"))              # le mois en cours s'arrête à la veille
        self.assertEqual(mois_a_collecter(date(2026, 3, 1))[-1], ("202602", "2026-02-01", "2026-02-28"))


if __name__ == "__main__":
    unittest.main()
