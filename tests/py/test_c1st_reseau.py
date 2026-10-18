"""Collecte C1ST « Leads Network Vision » : requêtes SAQL et fusion (sans réseau) : python -m unittest tests.py.test_c1st_reseau"""
import unittest

from pipeline import c1st_reseau as r


class Saql(unittest.TestCase):
    def test_filtres_du_tableau_de_bord_et_perimetre_reprise(self):
        q = r.saql("0Fb/ver", base=True)
        self.assertIn('load "0Fb/ver"', q)
        self.assertIn('"SOL ready for order"', q)
        self.assertIn("'ACCLead.CentralLocal_lead' in [\"BRAND\", \"Central\"]", q)
        self.assertIn('["1 month ago".."current day"]', q)
        self.assertIn("'Test_JustDealerT' in [\"No\"]", q)
        self.assertIn("'ACCLead.CampaignIDUSER__c' in [\"AUTOBIZ\", \"Autobiz\"]", q)       # périmètre reprise de Converge
        self.assertIn("'ACCLead.SendToNetwork' == \"Yes\"", q)
        self.assertIn("unique('ACCLead.Id') as 'leads', unique('ACCLead.LeadUniqueCust') as 'clients'", q)
        self.assertIn("'ACCLead.Partner_Contract', 'ACCLead.Marketing_Name'", q)

    def test_mesures_du_tableau(self):
        d = {k: (c, ch) for k, c, ch in r.MESURES}
        self.assertIn("FreespeeTreatmentTimeRespect__c' == \"On Time\"", d["fca"][0])
        self.assertIn("ContactedOnTime__c' == \"OnTime\" || 'ACCLead.ContactedOnTime__c' == \"OverTime\"", d["c"][0])
        self.assertIn("LeadConversionTimeMailPhone' >= 1", d["o"][0])
        self.assertEqual(d["o"][1], "OrderIdwMailPhone")                     # commandes : identifiant de commande, jamais une valeur en sortie (agrégat unique())
        q = r.saql("x/y", d["q"][0], d["q"][1])
        self.assertIn("'ACCLead.SendToNetwork' == \"Yes\" && 'HasQuotes' == \"YES\"", q)
        self.assertIn("unique('ACCLead.LeadUniqueCust') as 'v'", q)


class Collecte(unittest.TestCase):
    class Faux:
        def version(self, nom):
            return "ds/v"

        def requete(self, q):
            cle = ("pays", "marque", "code", "nom")
            ligne = {"pays": "BE", "marque": "AP", "code": "0000013", "nom": "MSCAR (PT0032S)"}
            if "as 'leads'" in q:
                return [dict(ligne, leads=120, clients=100), dict(ligne, code="0000022", nom="AUTRE", leads=0, clients=0)]
            return [dict(ligne, v=7)]

    def test_fusion_et_filtre_des_contrats_vides(self):
        out = r.collecte(self.Faux())
        self.assertEqual(len(out), 1)                                        # le contrat sans client est écarté
        c = out[0]
        self.assertEqual((c["leads"], c["clients"], c["fca"], c["o"], c["rel"]), (120, 100, 7, 7, 7))
        for cle, *_ in r.MESURES:
            self.assertIn(cle, c)


if __name__ == "__main__":
    unittest.main()
