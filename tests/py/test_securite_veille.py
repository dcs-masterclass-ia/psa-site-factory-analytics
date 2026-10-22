"""Veille de sécurité : détection des connexions anormales à partir du journal (api/_lib/journal.js)."""

import unittest

from pipeline import securite_veille as sv

H = 3600 * 1000


def ok(t, email, ip, pays="FR"):
    return {"t": t, "ok": True, "email": email, "ip": ip, "pays": pays}


def ko(t, ip, motif="jeton_invalide", **k):
    return dict({"t": t, "ok": False, "ip": ip, "motif": motif, "pays": "FR"}, **k)


class Analyse(unittest.TestCase):
    base = [ok(1 * H, "a@autobiz.com", "1.1.1.1"), ok(2 * H, "b@autobiz.com", "2.2.2.2")]

    def codes(self, evts, depuis=10 * H):
        return [c for c, _, _ in sv.analyse(evts, depuis)]

    def test_connexion_habituelle_ne_signale_rien(self):
        self.assertEqual(self.codes(self.base + [ok(11 * H, "a@autobiz.com", "1.1.1.1")]), [])

    def test_trois_echecs_meme_adresse(self):
        self.assertEqual(self.codes(self.base + [ko(11 * H + i, "9.9.9.9") for i in range(3)]), ["echecs_repetes"])
        self.assertEqual(self.codes(self.base + [ko(11 * H + i, "9.9.9.9") for i in range(2)]), [])

    def test_compte_inconnu(self):
        self.assertEqual(self.codes(self.base + [ko(11 * H, "9.9.9.9", "compte_non_autorise", email="x@gmail.com")]), ["compte_inconnu"])

    def test_nouvelle_adresse_et_nouveau_pays(self):
        self.assertEqual(self.codes(self.base + [ok(11 * H, "a@autobiz.com", "5.5.5.5")]), ["nouvelle_adresse"])
        self.assertEqual(sorted(self.codes(self.base + [ok(11 * H, "a@autobiz.com", "5.5.5.5", "RU")])), ["nouveau_pays", "nouvelle_adresse"])

    def test_premier_acces_d_un_compte_jamais_vu(self):
        self.assertEqual(self.codes(self.base + [ok(11 * H, "c@autobiz.com", "1.1.1.1")]), ["premier_acces"])

    def test_les_faits_anciens_ne_sont_pas_resignales(self):
        self.assertEqual(self.codes(self.base + [ko(1 * H + i, "9.9.9.9") for i in range(5)]), [])

    def test_resume(self):
        r = sv.resume(self.base + [ko(11 * H, "9.9.9.9")], 0)
        self.assertEqual((r["connexions"], r["refus"], r["adresses"]), (2, 1, 2))


if __name__ == "__main__":
    unittest.main()
