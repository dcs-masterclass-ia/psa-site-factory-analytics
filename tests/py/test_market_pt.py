"""Portugal (ACAP) : lecture déterministe des fichiers xlsx / pdf (pipeline/market_pt.py), sans réseau. python3 -m unittest tests.py.test_market_pt"""
import unittest
from pipeline import market_pt as mp

PAGE = """
                                  Ligeiros Passageiros   Ligeiros Mercadorias  Pesados Mercadorias   Pesados Passageiros   Ligeiros Passageiros   Ligeiros Mercadorias      Pesados Mercadorias   Pesados Passageiros
            Elétrico (BEV)               9 338                    782                    3                    1                   54 726                  5 898                     62                   642
          % Elétrico (BEV)               47,7%                   27,6%                 0,4%                 2,6%                  29,0%                   23,5%                    1,1%                 55,0%
               Gasolina                  2 004                     11                                                             37 253                    90
             % Gasolina                  10,2%                    0,4%                                                            19,7%                    0,4%
                % PHEV/Gasolina          14,2%                    0,8%                                                            13,6%                    0,6%
                % PHEV/Gasóleo            1,2%                    0,0%                                                             1,4%
  Híbridos      % HEV/Gasolina           17,1%                    0,0%                                                            25,0%                    0,0%
  Elétricos     % HEV/Gasóleo             0,5%                    0,7%                                                             1,0%
"""


class Energie(unittest.TestCase):
    def test_mix_voitures_particulieres(self):
        m = mp.lit_energie(PAGE)
        self.assertEqual(m["electric_pct"], 47.7)          # colonne « Ligeiros Passageiros » du mois, pas « Mercadorias » (27,6)
        self.assertEqual(m["ytd_electric_pct"], 29.0)      # colonne du cumul
        self.assertEqual(m["petrol_pct"], 10.2)
        self.assertEqual(m["phev_pct"], 15.4)              # PHEV essence + diesel
        self.assertEqual(m["hybrid_pct"], 17.6)            # le mot de groupe « Híbridos » ne perturbe pas la ligne
        self.assertEqual(m["ytd_hybrid_pct"], 26.0)

    def test_en_tete_absent(self):
        with self.assertRaises(ValueError):
            mp.lit_energie("rien")


class Liens(unittest.TestCase):
    def test_liens_documents(self):
        html = '<a href="/site/x/a.xlsx" target="_blank">Matrículas de Veículos Automóveis por Marca</a><a href="https://acap.pt/b.pdf">Autre</a>'
        l = mp.trouve_liens(html)
        self.assertEqual(l[0], ("Matrículas de Veículos Automóveis por Marca", "https://www.acap.pt/site/x/a.xlsx"))
        self.assertEqual(l[1][1], "https://acap.pt/b.pdf")


if __name__ == "__main__":
    unittest.main()
