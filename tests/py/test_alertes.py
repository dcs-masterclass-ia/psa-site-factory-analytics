"""Alertes proactives : règles à seuils (sans réseau). python3 -m unittest tests.py.test_alertes"""
import unittest

from pipeline.alertes import CONFIG_DEFAUT, evaluer_site


def site(jours_a=7, accueil_b=1000, est_b=300, accueil_a=1000, est_a=300, sess_b=800, sess_a=800):
    """Site fictif : 28 jours de référence puis 7 jours récents, 6 étapes par jour."""
    fd, d, rep = {}, [], []
    import datetime as dt
    fin = dt.date(2026, 10, 9)
    for k in range(35):
        j = (fin - dt.timedelta(days=34 - k)).isoformat()
        recent = k >= 28
        a, e = (accueil_a, est_a) if recent else (accueil_b, est_b)
        fd[j] = [a, int(a * 0.6), int(a * 0.58), int(a * 0.57), int(a * 0.5), e]
        d.append(j); rep.append(sess_a if recent else sess_b)
    return {"site": "TEST FR", "funnelDaily": fd, "daily": {"d": d, "rep": rep}}


class Alertes(unittest.TestCase):
    def test_site_stable_sans_alerte(self):
        self.assertEqual(evaluer_site("TEST FR", site(), CONFIG_DEFAUT, "2026-10-10"), [])

    def test_chute_de_sessions(self):
        a = evaluer_site("TEST FR", site(sess_a=300), CONFIG_DEFAUT, "2026-10-10")
        self.assertEqual([x["regle"] for x in a], ["sessions"])
        self.assertEqual(a[0]["severite"], "haute")                 # −62 % : au-delà de 2× le seuil

    def test_chute_de_conversion_et_etape(self):
        a = evaluer_site("TEST FR", site(est_a=150), CONFIG_DEFAUT, "2026-10-10")
        self.assertIn("conversion", [x["regle"] for x in a])
        self.assertIn("etape", [x["regle"] for x in a])

    def test_volume_insuffisant_pas_d_alerte(self):
        a = evaluer_site("TEST FR", site(accueil_a=10, est_a=1, accueil_b=10, est_b=3, sess_a=50, sess_b=200), CONFIG_DEFAUT, "2026-10-10")
        self.assertEqual(a, [])

    def test_fraicheur(self):
        a = evaluer_site("TEST FR", site(), CONFIG_DEFAUT, "2026-10-20")
        self.assertEqual(a[0]["regle"], "fraicheur")

    def test_seuil_reglable(self):
        cfg = dict(CONFIG_DEFAUT, sessionsPct=80)
        self.assertEqual(evaluer_site("TEST FR", site(sess_a=300), cfg, "2026-10-10"), [])


if __name__ == "__main__":
    unittest.main()
