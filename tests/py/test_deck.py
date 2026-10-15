"""Tests du générateur de présentations (sans réseau, sans données réelles) : python3 -m unittest tests.py.test_deck"""
import os, tempfile, unittest

from pipeline.deck.periodes import Periode, depuis_brief
from pipeline.deck.textes import T


class Periodes(unittest.TestCase):
    def test_trimestre(self):
        p = Periode("trimestre", 2026, 3)
        self.assertEqual((p.debut.isoformat(), p.fin.isoformat()), ("2026-07-01", "2026-09-30"))
        self.assertEqual(p.precedente().indice, 2)
        self.assertEqual(p.n1().annee, 2025)

    def test_precedente_enjambe_l_annee(self):
        p = Periode("trimestre", 2026, 1).precedente()
        self.assertEqual((p.annee, p.indice), (2025, 4))

    def test_ancien_format_brief(self):
        p = depuis_brief({"annee": 2026, "trimestre": 3})
        self.assertEqual((p.type, p.indice), ("trimestre", 3))

    def test_annee(self):
        p = Periode("annee", 2025, None)
        self.assertEqual((p.debut.isoformat(), p.fin.isoformat()), ("2025-01-01", "2025-12-31"))


class Textes(unittest.TestCase):
    def test_base_faible_ns(self):
        self.assertIsNone(T("fr").evol(50, 40)[2])      # base < 100 : pas de pourcentage
        self.assertIsNone(T("fr").evol(None, 500)[2])

    def test_evolution(self):
        txt, signe, v = T("fr").evol(1100, 1000)
        self.assertEqual(signe, 1)
        self.assertAlmostEqual(v, 10)


class Analyse(unittest.TestCase):
    def test_regles_sans_ia(self):
        """L'analyse est calculée (aucun appel réseau) et ne cite que des chiffres issus des données."""
        from pipeline.deck.construit import Ctx
        from pipeline.deck import analyse
        from pipeline.deck.donnees import Donnees
        with tempfile.TemporaryDirectory() as tmp:
            brief = {"client": "x", "langue": "fr", "periode": {"type": "trimestre", "annee": 2026, "indice": 3}, "perimetre": {"pays": ["BE"], "marques": []},
                     "comparaisons": {"precedente": True, "n1": True}, "modules": ["analyse"]}
            d = Donnees(["BE"], None, hist=tmp)
            ctx = Ctx(brief, d)
            self.assertTrue(analyse.globale(ctx)["constats"][0].startswith("0 leads sur T3-2026"))

    def test_variation_base_faible(self):
        from pipeline.deck.analyse import _var
        self.assertIsNone(_var(50, 40))
        self.assertAlmostEqual(_var(110, 100), 10)


class Evenements(unittest.TestCase):
    def test_filtre_periode_et_sites(self):
        import json
        from pipeline.deck.donnees import Donnees
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "events")); os.makedirs(os.path.join(tmp, "history"))
            json.dump({"events": [{"date": "2026-09-20", "titre": "Campagne", "sites": []}, {"date": "2026-09-25", "titre": "V2 Peugeot", "sites": ["PEUGEOT BE"]},
                                  {"date": "2026-06-01", "titre": "Avant", "sites": []}]}, open(os.path.join(tmp, "events", "events.json"), "w"))
            d = Donnees(["BE"], None, hist=os.path.join(tmp, "history"))
            p = Periode("trimestre", 2026, 3)
            self.assertEqual([e["titre"] for e in d.evenements(p)], ["Campagne", "V2 Peugeot"])
            self.assertEqual([e["titre"] for e in d.evenements(p, "CITROEN")], ["Campagne"])      # l'événement Peugeot ne concerne pas Citroën


class Construction(unittest.TestCase):
    def test_fumee_sans_donnees(self):
        """Un brief minimal produit un fichier PPTX même sans historique, dans chacune des 5 langues."""
        from pipeline.deck.construit import construit
        from pipeline.deck.donnees import Donnees
        for langue in ("fr", "en", "it", "es", "de"):
            brief = {"titre": "Test", "client": "Stellantis", "langue": langue, "periode": {"type": "trimestre", "annee": 2026, "indice": 3},
                     "perimetre": {"pays": ["BE"], "marques": []}, "comparaisons": {"precedente": True, "n1": True},
                     "modules": ["global", "points_ouverts", "nps", "utm", "analyse"], "contact": {}, "pointsOuverts": [], "prochainesEtapes": []}
            with tempfile.TemporaryDirectory() as tmp:
                d = Donnees(["BE"], None, hist=tmp)
                d.utilisateurs = lambda *a, **k: {"utilisateurs": 0, "in_journey": 0, "hot_leads": 0}   # pas d'appel GA4
                out = os.path.join(tmp, "t.pptx")
                construit(brief, d, out)
                self.assertGreater(os.path.getsize(out), 10000, langue)


if __name__ == "__main__":
    unittest.main()


class ApercuMarques(unittest.TestCase):
    """Vue « une ligne par marque » : tendance, moteurs et actions calculés sur des données fictives."""

    def _ctx(self, **extra):
        from pipeline.deck.construit import Ctx
        brief = {"client": "x", "langue": "fr", "periode": {"type": "trimestre", "annee": 2026, "indice": 3}, "perimetre": {"pays": ["BE"], "marques": []},
                 "comparaisons": {"precedente": True, "n1": True}, "modules": ["global"], **extra}

        class D:
            marques = ["PEUGEOT", "FIAT"]
            sites = []
            def leads(self, p, m=None):
                actuel = p.indice == 3 and p.annee == 2026
                base = 1000 if m == "PEUGEOT" else 50
                n = base if actuel else int(base * 1.2)
                return {"VN": n // 2, "SANS": n // 4, "VO": n - n // 2 - n // 4}
            def leads_total(self, p, m=None):
                return sum(self.leads(p, m).values())
            def acquisition_disponible(self, p):
                return True
            def sources(self, p, m):
                actuel = p.indice == 3 and p.annee == 2026
                z = {g: {"VN": 0, "SANS": 0, "VO": 0} for g in ("Display", "Emailing", "LLM", "Main-Website", "Search", "Social", "Autre")}
                z["Display"]["VN"] = 100 if actuel else 300
                z["Search"]["VN"] = 400
                z["Autre"]["VN"] = 300 if actuel else 0
                return z
            def canaux(self, p, m):
                return {"Display": 1000 if p.indice == 3 and p.annee == 2026 else 1500}
            def utilisateurs(self, p, m):
                return None
        return Ctx(brief, D())

    def test_moteurs_et_actions(self):
        from pipeline.deck import analyse
        a = analyse.apercu_marque(self._ctx(), "PEUGEOT")
        self.assertTrue(any("Display" in x and "−200" in x for x in a["moteurs"]))
        self.assertTrue(any("Renforcer le display" in x for x in a["actions"]))
        self.assertTrue(any("balisage UTM" in x for x in a["actions"]))      # « Autre » = 30 % des leads
        self.assertTrue(a["evols"][0][1].startswith("−"))

    def test_petit_volume_sans_pourcentage(self):
        from pipeline.deck import analyse
        a = analyse.apercu_marque(self._ctx(), "FIAT")
        self.assertIn("faible", a["moteurs"][0])

    def test_diapositive_generee(self):
        from pipeline.deck.construit import apercu_marques
        ctx = self._ctx(actionsMarques={"PEUGEOT": ["Action saisie par le DKAM"]})
        apercu_marques(ctx)
        textes = " ".join(c.text for sl in ctx.prs.slides for sh in sl.shapes if sh.has_table for r in sh.table.rows for c in r.cells)
        self.assertIn("Action saisie par le DKAM", textes)


class CtaEtConquete(unittest.TestCase):
    """Lecture des historiques leads_acq / leads (CTA du site marque, marque reprise) sur des fichiers fictifs."""

    def _donnees(self, tmp):
        import csv, gzip
        from pathlib import Path
        from pipeline.deck.donnees import Donnees
        def ecrit(dossier, ent, lignes):
            p = Path(tmp) / dossier
            p.mkdir(parents=True, exist_ok=True)
            with gzip.open(p / "peugeot-be.csv.gz", "wt", encoding="utf-8", newline="") as f:
                w = csv.writer(f); w.writerow(ent); w.writerows(lignes)
        ecrit("leads_acq", ["date", "site_id", "source_acq", "support", "campagne", "projet_achat", "marque_achat", "statut", "n"], [
            ["2026-08-01", "1", "Main-Website", "footer", "CTA", "VN", "", "valide", "5"],
            ["2026-08-02", "1", "Main-Website", "footer", "CTA", "VO", "", "valide", "2"],
            ["2026-08-02", "1", "Main-Website", "footer", "CTA", "VN", "", "doublon", "9"],      # doublon : ignoré
            ["2026-08-03", "1", "Display", "", "123", "VN", "", "valide", "7"],                    # pas Main-Website : ignoré
            ["2026-05-03", "1", "Main-Website", "footer", "CTA", "VN", "", "valide", "4"]])        # hors période
        ecrit("leads", ["date", "site_id", "source", "appareil", "carburant", "projet_achat", "marque_reprise", "statut", "n"], [
            ["2026-08-01", "1", "", "", "", "VN", "PEUGEOT", "valide", "6"],
            ["2026-08-01", "1", "", "", "", "VN", "CITROËN", "valide", "3"],
            ["2026-08-02", "1", "", "", "", "VN", "RENAULT", "valide", "4"]])
        d = Donnees(["BE"], ["PEUGEOT"], hist=tmp)
        d.sites = [("PEUGEOT BE", "PEUGEOT", "BE")]
        return d

    def test_cta_et_reprises(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._donnees(tmp)
            p = Periode("trimestre", 2026, 3)
            self.assertEqual(d.cta(p, "PEUGEOT"), {"footer": {"VN": 5, "SANS": 0, "VO": 2}})
            self.assertEqual(d.reprises(p, "PEUGEOT"), {"PEUGEOT": 6, "CITROEN": 3, "RENAULT": 4})
            self.assertIsNone(d.modeles(p, "PEUGEOT"))        # historique des modèles pas encore collecté


class ProjectionMois(unittest.TestCase):
    """Projection de fin de mois : leads New cars du 1er au dernier jour connu, ramenés à la durée du mois."""

    def _ctx(self, dernier):
        from pipeline.deck.construit import Ctx
        brief = {"client": "x", "langue": "fr", "periode": {"type": "mois", "annee": 2026, "indice": 10}, "perimetre": {"pays": ["FR"], "marques": []},
                 "comparaisons": {"precedente": True, "n1": True}, "modules": ["global"]}

        class D:
            marques = ["PEUGEOT"]
            sites = []
            def leads(self, p, m=None):
                n = ((p.fin - p.debut).days + 1) * 10          # 10 leads New cars par jour
                return {"VN": n, "SANS": 0, "VO": 0}
            def leads_total(self, p, m=None):
                return sum(self.leads(p, m).values())
            def dernier_jour_leads(self):
                return dernier
        return Ctx(brief, D())

    def test_projection(self):
        from pipeline.deck.construit import projection_mois
        ctx = self._ctx("2026-10-10")
        s = projection_mois(ctx)
        self.assertIsNotNone(s)
        cellules = [c.text for sh in s.shapes if sh.has_table for r in sh.table.rows for c in r.cells]
        self.assertIn("100", cellules)      # 1er au 10 : 10 jours x 10
        self.assertIn("310", cellules)      # projection : 100 / 10 x 31
        self.assertIn("+3 %", [c.replace(" ", " ") for c in cellules])    # vs septembre (30 jours = 300)

    def test_mois_termine_pas_de_projection(self):
        from pipeline.deck.construit import projection_mois
        self.assertIsNone(projection_mois(self._ctx("2026-10-31")))


class ClassementMarches(unittest.TestCase):
    def test_pays_regroupes(self):
        from pipeline.deck.construit import NOMS_PAYS
        for l in ("fr", "en"):
            self.assertEqual(NOMS_PAYS[l]["BE"], NOMS_PAYS[l]["LU"])      # BELUX regroupé
            self.assertEqual(NOMS_PAYS[l]["GB"], NOMS_PAYS[l]["UK"])      # deux codes, un seul marché


class Commentaires(unittest.TestCase):
    """Commentaires du DKAM saisis dans le brief : affichés une seule fois par clé, sur la bonne diapositive."""

    def test_commentaire_une_fois(self):
        from pipeline.deck.construit import Ctx, nouvelle
        brief = {"client": "x", "langue": "fr", "periode": {"type": "trimestre", "annee": 2026, "indice": 3}, "perimetre": {"pays": ["BE"], "marques": []},
                 "comparaisons": {}, "modules": ["global"], "commentaires": {"marque:PEUGEOT": "Insister sur le display."}}

        class D:
            marques = []
        ctx = Ctx(brief, D())
        s1 = nouvelle(ctx, "A", cle="marque:PEUGEOT")
        s2 = nouvelle(ctx, "B", cle="marque:PEUGEOT")      # deuxième diapositive de la marque : pas de doublon
        s3 = nouvelle(ctx, "C", cle="marque:CITROEN")      # pas de commentaire saisi
        texte = lambda s: " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
        self.assertIn("Insister sur le display.", texte(s1))
        self.assertNotIn("Insister sur le display.", texte(s2))
        self.assertNotIn("Insister", texte(s3))


class EntreeEtV2(unittest.TestCase):
    """Mode de saisie du véhicule et avant / après V2, lus dans les fichiers de site (data/<site>.json)."""

    def test_lecture_fichiers_de_site(self):
        import json
        from pathlib import Path
        from pipeline.deck.donnees import Donnees
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            (racine / "history").mkdir()
            (racine / "peugeot-fr.json").write_text(json.dumps({
                "leads": {"2026-07": {"entry": {"Avec immatriculation": 90, "Marque / modele": 10}}, "2026-08": {"entry": {"Avec immatriculation": 80, "Marque / modele": 20}}},
                "v2": {"is_v2_split": True, "pre_label": "a", "post_label": "b"},
                "v2steps": [{"step": "Accueil", "a": 1000, "b": 2000}, {"step": "Estimation", "a": 100, "b": 400}]}), encoding="utf-8")
            d = Donnees(["FR"], ["PEUGEOT"], hist=racine / "history")
            d.sites = [("PEUGEOT FR", "PEUGEOT", "FR")]
            from pipeline.deck.periodes import Periode
            self.assertEqual(d.entree_leads(Periode("trimestre", 2026, 3), "PEUGEOT"), {"plaque": 170, "marque_modele": 30})
            self.assertIsNone(d.entree_leads(Periode("trimestre", 2025, 3), "PEUGEOT"))      # aucune donnée : jamais de zéro inventé
            v = d.v2("PEUGEOT")
            self.assertEqual(v["etapes"], [("Accueil", 1000, 2000), ("Estimation", 100, 400)])
            self.assertIsNone(d.v2("CITROEN"))


class C1st(unittest.TestCase):
    """Lecture du fichier c1st/kpi.json (leads VN envoyés vus par C1ST) et slides lead management / conversion."""

    def _donnees(self, tmp, mois_manquant=None):
        import json
        from pathlib import Path
        from pipeline.deck.donnees import Donnees
        racine = Path(tmp)
        (racine / "history").mkdir()
        (racine / "c1st").mkdir()
        mois = {}
        for m in ("2026-07", "2026-08", "2026-09", "2026-04", "2026-05", "2026-06"):
            if m == mois_manquant:
                continue
            mois[m] = {"leads": [{"marque": "AP", "leads": 1000, "envoyes": 990, "clients_envoyes": 980, "contactes": 490, "contactes_delai": 400, "premier_appel_delai": 500, "traites": 450, "traites_delai": 420, "avec_opp": 600}],
                       "commandes": [{"marque": "AP", "clients_uniques": 1000, "avec_devis": 300, "commandes": 60}]}
        (racine / "c1st" / "kpi.json").write_text(json.dumps({"donnees": {"FR": mois}}), encoding="utf-8")
        d = Donnees(["FR"], ["PEUGEOT"], hist=racine / "history")
        d.sites = [("PEUGEOT FR", "PEUGEOT", "FR")]
        d.marques = ["PEUGEOT"]
        return d

    def test_totaux_sur_la_periode(self):
        from pipeline.deck.periodes import Periode
        with tempfile.TemporaryDirectory() as tmp:
            c = self._donnees(tmp).c1st(Periode("trimestre", 2026, 3), "PEUGEOT")
            self.assertEqual((c["envoyes"], c["commandes"], c["clients_uniques"]), (2970, 180, 3000))

    def test_mois_manquant_pas_de_total_partiel(self):
        from pipeline.deck.periodes import Periode
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(self._donnees(tmp, "2026-08").c1st(Periode("trimestre", 2026, 3), "PEUGEOT"))

    def test_slides(self):
        from pipeline.deck.construit import Ctx, c1st_lead_management, c1st_conversion
        with tempfile.TemporaryDirectory() as tmp:
            brief = {"client": "x", "langue": "fr", "periode": {"type": "trimestre", "annee": 2026, "indice": 3}, "perimetre": {"pays": ["FR"], "marques": []},
                     "comparaisons": {"precedente": True, "n1": False}, "modules": ["global"]}
            ctx = Ctx(brief, self._donnees(tmp))
            s1, s2 = c1st_lead_management(ctx), c1st_conversion(ctx)
            texte = lambda s: " ".join(c.text for sh in s.shapes if sh.has_table for r in sh.table.rows for c in r.cells)
            self.assertIn("2\u00a0940", texte(s1))          # clients envoyés : 3 mois x 980
            self.assertIn("6,0", texte(s2).replace(" ", " "))   # 180 / 3000 = 6,0 %

    def test_pas_de_comparaison_sur_traitement_ni_sur_periode_immature(self):
        from datetime import date
        from pipeline.deck.construit import Ctx, c1st_lead_management, c1st_conversion
        with tempfile.TemporaryDirectory() as tmp:
            brief = {"client": "x", "langue": "fr", "periode": {"type": "trimestre", "annee": 2026, "indice": 3}, "perimetre": {"pays": ["FR"], "marques": []},
                     "comparaisons": {"precedente": True, "n1": False}, "modules": ["global"]}
            ctx = Ctx(brief, self._donnees(tmp))
            ctx.aujourdhui = date(2026, 10, 15)                       # T3 2026 fini depuis moins de 90 jours : provisoire
            tout = lambda s: " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            self.assertNotIn("vs période précédente", tout(c1st_lead_management(ctx)))      # jamais d'évolution sur le traitement
            self.assertIn("provisoires", tout(c1st_conversion(ctx)))
        with tempfile.TemporaryDirectory() as tmp2:
            ctx2 = Ctx(brief, self._donnees(tmp2))
            ctx2.aujourdhui = date(2027, 3, 1)                        # plus de 90 jours après la fin du T3 : plus de mention provisoire
            self.assertNotIn("provisoires", tout(c1st_conversion(ctx2)))
