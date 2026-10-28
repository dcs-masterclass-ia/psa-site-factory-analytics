import json
import os
import tempfile
import unittest
from pathlib import Path


class Rattrapage(unittest.TestCase):
    def setUp(self):
        from pipeline import leads_extract as L
        self.L = L
        self.tmp = tempfile.TemporaryDirectory()
        f = Path(self.tmp.name) / "leads_rattrapage.json"
        f.write_text(json.dumps({"SPOTICAR DE": {"motif": "test", "ids": ["101", 102]}}), encoding="utf-8")
        os.environ["LEADS_RATTRAPAGE"] = str(f)
        L._RATTRAPAGE = None

    def tearDown(self):
        os.environ.pop("LEADS_RATTRAPAGE", None)
        self.L._RATTRAPAGE = None
        self.tmp.cleanup()

    def _ligne(self, id_, mode="MODE_PREVIEW", doublon="YES"):
        return {"LEAD ID": id_, "MODE": mode, "DOUBLON": doublon, "TEST": "NO", "TEST_INTERNE": "YES"}

    def test_lead_liste_compte_meme_mal_flague(self):
        L = self.L
        self.assertFalse(L._valide(self._ligne("101")))
        self.assertTrue(L.valide_ou_rattrape("SPOTICAR DE", self._ligne("101")))
        self.assertTrue(L.valide_ou_rattrape("SPOTICAR DE", self._ligne("102")))            # identifiant numerique dans le fichier

    def test_lead_non_liste_ou_autre_site_reste_exclu(self):
        L = self.L
        self.assertFalse(L.valide_ou_rattrape("SPOTICAR DE", self._ligne("999")))
        self.assertFalse(L.valide_ou_rattrape("PEUGEOT FR", self._ligne("101")))             # le rattrapage est propre a un site

    def test_lead_corrige_par_le_bo_compte_une_seule_fois(self):
        L = self.L
        corrige = {"LEAD ID": "101", "MODE": "MODE_PRODUCTION", "DOUBLON": "NO", "TEST": "NO", "TEST_INTERNE": "NO"}
        lignes = [l for l in [corrige, self._ligne("102"), self._ligne("999")] if L.valide_ou_rattrape("SPOTICAR DE", l)]
        self.assertEqual([l["LEAD ID"] for l in lignes], ["101", "102"])                     # une ligne = un lead, jamais deux

    def test_sans_fichier_aucun_effet(self):
        L = self.L
        os.environ["LEADS_RATTRAPAGE"] = str(Path(self.tmp.name) / "absent.json")
        L._RATTRAPAGE = None
        self.assertFalse(L.valide_ou_rattrape("SPOTICAR DE", self._ligne("101")))


if __name__ == "__main__":
    unittest.main()
