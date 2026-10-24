"""Verrouillage d'urgence : fonctions pures (aucun appel à Vercel ni à GitHub)."""

import importlib.util
import json
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("urgence", Path(__file__).resolve().parents[2] / "scripts" / "urgence.py")
urgence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(urgence)


class Urgence(unittest.TestCase):
    def test_lecture_des_adresses_de_la_regle(self):
        texte = "  Conditions:\n      IP address is not any of 203.0.113.5, 198.51.100.7, 2001:db8::1\n\n  Action: Deny"
        self.assertEqual(urgence.lis_adresses_regle(texte), ["203.0.113.5", "198.51.100.7", "2001:db8::1"])
        self.assertEqual(urgence.lis_adresses_regle("rien"), [])

    def test_condition_de_la_regle(self):
        c = json.loads(urgence.condition_regle(["203.0.113.5"]))
        self.assertEqual((c["type"], c["op"], c["value"]), ("ip_address", "ninc", ["203.0.113.5"]))

    def test_adresse_de_verrouillage_non_routable(self):
        self.assertTrue(urgence.ADRESSE_MORTE.startswith("192.0.2."))        # TEST-NET-1 : jamais routée

    def test_simulation_ne_lance_rien(self):
        self.assertEqual(urgence.sh(["commande-qui-n-existe-pas"], simulation=True), "")


if __name__ == "__main__":
    unittest.main()
