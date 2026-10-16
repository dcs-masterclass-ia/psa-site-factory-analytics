"""Contrôle qualité des chiffres d'une présentation : python -m unittest tests.py.test_qa"""
import unittest

from pipeline.deck import qa
from pipeline.deck.faits import Faits


def _f(*lignes):
    ft = Faits()
    for l in lignes:
        metrique, valeur, marque, periode, source = l[:5]
        extra = l[5] if len(l) > 5 else {}
        ft.ajoute(metrique, valeur, marque, periode, source, **extra)
    return ft


class Controles(unittest.TestCase):
    def test_deck_coherent_sans_erreur(self):
        ft = _f(("leads", 100, "A", "Q3-2026", "s1"), ("leads", 100, "A", "Q3-2026", "s2"),
                ("leads", 50, "B", "Q3-2026", "s1"), ("leads", 150, None, "Q3-2026", "tot", {"marques": ["A", "B"]}))
        r = qa.controle(ft)
        self.assertEqual((len(r["erreurs"]), len(r["alertes"])), (0, 0))

    def test_meme_chiffre_different_selon_les_slides(self):
        r = qa.controle(_f(("leads", 100, "A", "Q3-2026", "s1"), ("leads", 101, "A", "Q3-2026", "s2")))
        self.assertEqual([e["code"] for e in r["erreurs"]], ["chiffre_different"])

    def test_perimetres_differents_info_pas_erreur(self):
        r = qa.controle(_f(("sessions", 100, "A", "Q3-2026", "s1", {"perimetre": "BE"}), ("sessions", 110, "A", "Q3-2026", "s2", {"perimetre": "BE+LU"})))
        self.assertEqual(len(r["erreurs"]), 0)
        self.assertEqual([i["code"] for i in r["infos"]], ["perimetres_differents"])

    def test_somme_des_marques_differente_du_total(self):
        r = qa.controle(_f(("leads", 100, "A", "Q3-2026", "s1"), ("leads", 50, "B", "Q3-2026", "s1"), ("leads", 160, None, "Q3-2026", "tot", {"marques": ["A", "B"]})))
        self.assertEqual([e["code"] for e in r["erreurs"]], ["somme_incorrecte"])

    def test_somme_ignoree_si_une_marque_n_est_pas_affichee(self):
        r = qa.controle(_f(("leads", 100, "A", "Q3-2026", "s1"), ("leads", 160, None, "Q3-2026", "tot", {"marques": ["A", "B"]})))
        self.assertEqual(r["erreurs"], [])

    def test_projets_ne_somment_pas_aux_leads(self):
        ft = _f(("leads_vn", 60, "A", "Q3-2026", "s1"), ("leads_sans", 30, "A", "Q3-2026", "s1"), ("leads_vo", 10, "A", "Q3-2026", "s1"), ("leads", 105, "A", "Q3-2026", "s2"))
        self.assertEqual([e["code"] for e in qa.controle(ft)["erreurs"]], ["projets_incoherents"])

    def test_trois_mois_ne_somment_pas_au_trimestre(self):
        ft = _f(("leads", 10, None, "2026-07", "m"), ("leads", 20, None, "2026-08", "m"), ("leads", 30, None, "2026-09", "m"), ("leads", 61, None, "Q3-2026", "tot"))
        self.assertEqual([e["code"] for e in qa.controle(ft)["erreurs"]], ["mensuel_vs_trimestre"])
        ok = _f(("leads", 10, None, "2026-07", "m"), ("leads", 20, None, "2026-08", "m"), ("leads", 30, None, "2026-09", "m"), ("leads", 60, None, "Q3-2026", "tot"))
        self.assertEqual(qa.controle(ok)["erreurs"], [])

    def test_entonnoir_impossible(self):
        ft = _f(("sessions", 100, "A", "Q3-2026", "s"), ("in_journey", 120, "A", "Q3-2026", "s"), ("ga_leads", 10, "A", "Q3-2026", "s"))
        self.assertEqual([e["code"] for e in qa.controle(ft)["erreurs"]], ["entonnoir"])
        ft = _f(("sessions", 100, "A", "Q3-2026", "s"), ("in_journey", 50, "A", "Q3-2026", "s"), ("ga_leads", 60, "A", "Q3-2026", "s"))
        self.assertEqual([e["code"] for e in qa.controle(ft)["erreurs"]], ["entonnoir"])

    def test_chute_a_zero_et_valeur_negative(self):
        ft = _f(("leads", 0, "A", "Q3-2026", "s"), ("leads", 200, "A", "Q2-2026", "s"), ("leads", -3, "B", "Q3-2026", "s"))
        r = qa.controle(ft, None, [("Q3-2026", "Q2-2026")])
        self.assertEqual(sorted(a["code"] for a in r["alertes"]), ["chute_a_zero", "valeur_negative"])

    def test_donnee_partielle(self):
        r = qa.controle(_f(), {"fin_periode": "2026-09-30", "dernier_jour_leads": "2026-09-20", "collecte_c1st": "2026-10-16"})
        self.assertEqual([a["code"] for a in r["alertes"]], ["donnee_partielle"])
        self.assertIn("leads", r["alertes"][0]["message"])


class DeckReel(unittest.TestCase):
    def test_un_deck_trimestriel_produit_ses_faits_et_son_rapport(self):
        import tempfile
        from tests.py.test_revue_trim import RevueTrim
        t = RevueTrim()
        with tempfile.TemporaryDirectory() as tmp:
            ctx, _ = t._construit(tmp)
            self.assertGreater(len(ctx.faits.lignes), 0)
            self.assertEqual(ctx.qa["nb_faits"], len(ctx.faits.lignes))
            self.assertEqual(ctx.qa["erreurs"], [], ctx.qa["erreurs"])


if __name__ == "__main__":
    unittest.main()
