import unittest
from pipeline import tickets_auto as ta


def tk(type_, titre, desc="Une description suffisamment longue", statut="nouveau"):
    return {"id": "T-1", "type": type_, "titre": titre, "description": desc, "statut": statut, "auteur": "a@b.c", "commentaires": []}


class TestTri(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(ta.classer(tk("question", "Comment ?"))[0], "question")
        self.assertEqual(ta.classer(tk("bug", "Écart de leads"))[0], "bug")
        self.assertEqual(ta.classer(tk("optimisation", "Total par canal", "Ajouter une colonne total"))[0], "donnee_simple")
        self.assertEqual(ta.classer(tk("optimisation", "Nouvel onglet", "Créer un nouvel onglet Ventes"))[0], "gros_chantier")
        self.assertEqual(ta.classer(tk("optimisation", "Truc", "Améliorer l'expérience globale du site"))[0], "gros_chantier")

    def test_description_longue_monte_d_un_niveau(self):
        self.assertEqual(ta.classer(tk("optimisation", "Ajouter une colonne", "x" * 800))[0], "gros_chantier")

    def test_trier_une_seule_fois_et_commentaire_visible(self):
        liste = [tk("optimisation", "Total", "Ajouter un total par canal"), tk("bug", "Déjà vu", statut="resolu")]
        self.assertEqual(len(ta.trier(liste, 1000)), 1)
        self.assertEqual(liste[0]["triage"]["niveau"], 1)
        self.assertTrue(liste[0]["commentaires"][0]["systeme"])
        self.assertEqual(ta.trier(liste, 2000), [])  # idempotent
        self.assertNotIn("triage", liste[1])

    def test_carte_adaptative(self):
        t = tk("bug", "Écart"); ta.trier([t])
        c = ta.carte(t)
        self.assertEqual(c["attachments"][0]["contentType"], "application/vnd.microsoft.card.adaptive")


if __name__ == "__main__":
    unittest.main()
