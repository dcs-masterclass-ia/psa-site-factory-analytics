"""Veille de sécurité : détection des connexions anormales à partir du journal (api/_lib/journal.js)."""

import unittest

from pipeline import securite_veille as sv

H = 3600 * 1000


def ok(t, email, ip, pays="FR"):
    return {"t": t, "ok": True, "email": email, "ip": ip, "pays": pays}


def ko(t, ip, motif="jeton_invalide", **k):
    return dict({"t": t, "ok": False, "ip": ip, "motif": motif, "pays": "FR"}, **k)


class Analyse(unittest.TestCase):
    base = [ok(1 * H, "a@exemple.test", "1.1.1.1"), ok(2 * H, "b@exemple.test", "2.2.2.2")]

    def codes(self, evts, depuis=10 * H):
        return [c for c, _, _ in sv.analyse(evts, depuis)]

    def test_connexion_habituelle_ne_signale_rien(self):
        self.assertEqual(self.codes(self.base + [ok(11 * H, "a@exemple.test", "1.1.1.1")]), [])

    def test_trois_echecs_meme_adresse(self):
        self.assertEqual(self.codes(self.base + [ko(11 * H + i, "9.9.9.9") for i in range(3)]), ["echecs_repetes"])
        self.assertEqual(self.codes(self.base + [ko(11 * H + i, "9.9.9.9") for i in range(2)]), [])

    def test_compte_inconnu(self):
        self.assertEqual(self.codes(self.base + [ko(11 * H, "9.9.9.9", "compte_non_autorise", email="x@gmail.com")]), ["compte_inconnu"])

    def test_nouvelle_adresse_et_nouveau_pays(self):
        self.assertEqual(self.codes(self.base + [ok(11 * H, "a@exemple.test", "5.5.5.5")]), ["nouvelle_adresse"])
        self.assertEqual(sorted(self.codes(self.base + [ok(11 * H, "a@exemple.test", "5.5.5.5", "RU")])), ["nouveau_pays", "nouvelle_adresse"])

    def test_premier_acces_d_un_compte_jamais_vu(self):
        self.assertEqual(self.codes(self.base + [ok(11 * H, "c@exemple.test", "1.1.1.1")]), ["premier_acces"])

    def test_les_faits_anciens_ne_sont_pas_resignales(self):
        self.assertEqual(self.codes(self.base + [ko(1 * H + i, "9.9.9.9") for i in range(5)]), [])

    def test_resume(self):
        r = sv.resume(self.base + [ko(11 * H, "9.9.9.9")], 0)
        self.assertEqual((r["connexions"], r["refus"], r["adresses"]), (2, 1, 2))


class Sonde(unittest.TestCase):
    """Sonde externe : hors liste blanche, le site ne doit rien servir."""

    def test_refus_normaux(self):
        self.assertEqual(sv.etat_sonde([("/", 403), ("/data/x.json", 403), ("/api/data", 429)], {}), ("ok", [], 0))

    def test_liste_blanche_inefficace_alerte_une_fois(self):
        etat, c, _ = sv.etat_sonde([("/", 200), ("/data/x.json", 401), ("/api/data", 403)], {"etat": "ok"})
        self.assertEqual((etat, [x[0] for x in c]), ("ouvert", ["liste_blanche"]))
        self.assertEqual(sv.etat_sonde([("/", 200)], {"etat": "ouvert"})[1], [])          # pas de répétition toutes les 30 min

    def test_panne_confirmee_au_deuxieme_passage(self):
        self.assertEqual(sv.etat_sonde([("/", 0)], {"etat": "ok", "pannes": 0}), ("ok", [], 1))
        etat, c, n = sv.etat_sonde([("/", 503)], {"etat": "ok", "pannes": 1})
        self.assertEqual((etat, [x[0] for x in c], n), ("injoignable", ["injoignable"], 2))

    def test_retour_a_la_normale(self):
        self.assertEqual([x[0] for x in sv.etat_sonde([("/", 403)], {"etat": "injoignable"})[1]], ["retour"])


class Sentinelle(unittest.TestCase):
    def test_commit_direct_et_fusion(self):
        from pipeline import sentinelle as st
        commits = [{"sha": "c3", "parents": [1]}, {"sha": "c2", "parents": [1, 2]}, {"sha": "c1", "parents": [1]}]
        self.assertEqual(st.commits_directs(commits, "c1"), [("c3", True), ("c2", False)])
        self.assertEqual(st.commits_directs(commits, "c3"), [])

    def test_sonde_ouverte_confirmee_en_deux_passages(self):
        e1, _, _ = sv.etat_sonde([("/", 200)], {})
        self.assertEqual(e1, "ouvert")
        e2, c, _ = sv.etat_sonde([("/", 200)], {"etat": e1})
        self.assertEqual((e2, c), ("ouvert", []))        # la sentinelle ne coupe qu'au 2e passage consécutif (état précédent déjà « ouvert »)


if __name__ == "__main__":
    unittest.main()
