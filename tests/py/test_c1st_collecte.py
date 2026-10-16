"""Collecteur C1ST : requêtes SAQL, mois à collecter, fusion, authentification JWT (sans réseau) : python -m unittest tests.py.test_c1st_collecte"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pipeline import c1st_collecte as c


class Saql(unittest.TestCase):
    def test_leads_standard(self):
        q = c.saql_leads("0Fb0O000000XrKuSAK/0Fc1", "BE", 2026, 2, c.PERIMETRES["std"])
        self.assertIn('load "0Fb0O000000XrKuSAK/0Fc1"', q)
        self.assertIn("'LeadCountry__c' in [\"BE\"]", q)
        self.assertIn("'Activity__c' in [\"VN\"]", q)
        self.assertNotIn("NatureLabelized", q)
        self.assertIn("dateRange([2026,2,1],[2026,2,28])", q)         # février 2026 : 28 jours
        self.assertIn("'LeadTypeLabelized' in [\"1-Leads (urgent)\"]", q)
        self.assertIn("'CampaignIDUSER__c' in [\"AUTOBIZ\", \"Autobiz\"]", q)

    def test_spoticar_vo_rachat(self):
        q = c.saql_leads("x/y", "FR", 2026, 9, c.PERIMETRES["sp"])
        self.assertIn('\'PSABrand__c\' in ["SP"]', q)
        self.assertIn("'Activity__c' in [\"VO\"]", q)
        self.assertIn('"15.Buyback request"', q)

    def test_commandes_et_nsc_jeux_dealer_et_sub(self):
        qc = c.saql_commandes("d/v", "FR", 2026, 1, c.PERIMETRES["std"])
        self.assertIn("'ACCLead.CustomerType__c'", qc)                 # les jeux dealer et SUB préfixent les champs du lead
        self.assertIn("unique(dea.'ACCLead.LeadUniqueCust') as 'clients_uniques'", qc)
        qn = c.saql_nsc("s/v", "FR", 2026, 1, c.PERIMETRES["std"])
        self.assertIn("'LeadConversionTimeMailPhone' >= 1 && 'LeadConversionTimeMailPhone' <= 90", qn)
        self.assertIn("unique('OrderIdwMailPhone') as 'commandes_nsc'", qn)


class Mois(unittest.TestCase):
    def test_quatre_derniers_mois_termines(self):
        self.assertEqual(c.mois_a_collecter(date(2026, 11, 6)), [(2026, 7), (2026, 8), (2026, 9), (2026, 10)])

    def test_enjambe_l_annee(self):
        self.assertEqual(c.mois_a_collecter(date(2027, 1, 6)), [(2026, 9), (2026, 10), (2026, 11), (2026, 12)])

    def test_mois_en_cours_inclus_collecte_quotidienne(self):
        self.assertEqual(c.mois_a_collecter(date(2026, 10, 16), courant=True), [(2026, 7), (2026, 8), (2026, 9), (2026, 10)])

    def test_mois_en_cours_en_janvier(self):
        self.assertEqual(c.mois_a_collecter(date(2027, 1, 3), courant=True), [(2026, 10), (2026, 11), (2026, 12), (2027, 1)])

    def test_depuis(self):
        m = c.mois_a_collecter(date(2026, 11, 6), depuis="2025-01")
        self.assertEqual((m[0], m[-1], len(m)), ((2025, 1), (2026, 10), 22))


class Fusion(unittest.TestCase):
    def test_remplace_et_conserve(self):
        ex = {"donnees": {"FR": {"2026-08": {"leads": [{"marque": "AP", "leads": 5}]}, "2026-07": {"leads": [{"marque": "AP", "leads": 4}]}}}}
        self.assertTrue(c.fusionne(ex, "FR", "2026-08", {"leads": [{"marque": "AP", "leads": 9}], "commandes": [], "nsc": []}))
        self.assertEqual(ex["donnees"]["FR"]["2026-08"]["leads"][0]["leads"], 9)
        self.assertEqual(ex["donnees"]["FR"]["2026-07"]["leads"][0]["leads"], 4)         # mois non collecté : intact

    def test_refuse_d_ecraser_par_du_vide(self):
        ex = {"donnees": {"FR": {"2026-08": {"leads": [{"marque": "AP", "leads": 5}]}}}}
        self.assertFalse(c.fusionne(ex, "FR", "2026-08", {"leads": [], "commandes": [], "nsc": []}))
        self.assertEqual(ex["donnees"]["FR"]["2026-08"]["leads"][0]["leads"], 5)


class Authentification(unittest.TestCase):
    def test_secrets_absents(self):
        with self.assertRaises(c.NonConfigure):
            c.jeton({})

    def test_assertion_jwt(self):
        try:
            import jwt
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            import httpx
        except ImportError:
            self.skipTest("PyJWT / cryptography / httpx absents")
        cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = cle.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        vu = {}

        def faux_post(url, data=None, timeout=None):
            vu["url"], vu["data"] = url, data
            return httpx.Response(200, json={"access_token": "tok", "instance_url": "https://x.my.salesforce.com/"})
        vrai = httpx.post
        httpx.post = faux_post
        try:
            tok, inst = c.jeton({"C1ST_CLIENT_ID": "cid", "C1ST_USERNAME": "svc@x.com", "C1ST_PRIVATE_KEY": pem, "C1ST_LOGIN_URL": "https://psa-customerfirst.my.salesforce.com"})
        finally:
            httpx.post = vrai
        self.assertEqual((tok, inst), ("tok", "https://x.my.salesforce.com"))
        self.assertEqual(vu["url"], "https://psa-customerfirst.my.salesforce.com/services/oauth2/token")      # point d'authentification = domaine de l'organisation
        claims = jwt.decode(vu["data"]["assertion"], cle.public_key(), algorithms=["RS256"], audience="https://login.salesforce.com")
        self.assertEqual((claims["iss"], claims["sub"]), ("cid", "svc@x.com"))


class Principal(unittest.TestCase):
    """main() de bout en bout avec un client simulé : fichier écrit, codes de sortie."""

    def _lance(self, echec=False, secrets=True):
        with tempfile.TemporaryDirectory() as tmp:
            sortie = Path(tmp) / "c1st" / "kpi.json"
            vrais = (c.jeton, c.Client, c.collecte_mois)
            appels = []

            def faux_jeton(env=None):
                if not secrets:
                    raise c.NonConfigure("absents")
                return "tok", "https://x.my.salesforce.com"

            def faux_collecte(client, pays, y, m):
                appels.append((pays, y, m))
                if echec and pays == "BE":
                    raise RuntimeError("panne")
                return {"leads": [{"marque": "AP", "leads": 1}], "commandes": [], "nsc": []}
            c.jeton, c.Client, c.collecte_mois = faux_jeton, lambda t, i: object(), faux_collecte
            try:
                code = c.main(["--depuis", "2026-08", "--pays", "FR,BE", "--sortie", str(sortie)])
            finally:
                c.jeton, c.Client, c.collecte_mois = vrais
            return code, (json.loads(sortie.read_text()) if sortie.exists() else None), appels

    def test_succes(self):
        code, d, appels = self._lance()
        self.assertEqual(code, 0)
        self.assertTrue(d["donnees"]["FR"] and d["donnees"]["BE"])
        self.assertIn("collecte", d)

    def test_un_marche_en_echec_n_efface_pas_le_reste(self):
        code, d, _ = self._lance(echec=True)
        self.assertEqual(code, 1)                       # le workflow passe au rouge
        self.assertTrue(d["donnees"]["FR"])             # mais ce qui a réussi est écrit
        self.assertFalse(d["donnees"].get("BE"))

    def test_non_configure(self):
        code, d, _ = self._lance(secrets=False)
        self.assertEqual((code, d), (3, None))


if __name__ == "__main__":
    unittest.main()


class PerimetreAvant2026(unittest.TestCase):
    def test_xp_par_source_avant_2026_campagne_apres(self):
        avant = c.filtres("q", "FR", 2025, 3, c.PERIMETRES["std"])
        apres = c.filtres("q", "FR", 2026, 3, c.PERIMETRES["std"])
        self.assertIn("315.Brand Trade-in/ Reprise", avant)
        self.assertNotIn("315.Brand Trade-in/ Reprise", apres)
        self.assertNotIn("NatureLabelized", avant)          # aucun filtre de nature pour les marques standard
        self.assertNotIn("NatureLabelized", apres)
        self.assertIn("CampaignIDUSER__c", apres)
