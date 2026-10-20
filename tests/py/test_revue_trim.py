import tempfile
import unittest
from collections import defaultdict
from pathlib import Path


def _donnees(tmp, c1st=True, leads=True):
    """Données injectées (sans réseau) : Peugeot et Citroën FR, leads VN / VO de janvier 2025 à septembre 2026, C1ST complet si demandé."""
    from pipeline.deck.donnees import Donnees
    racine = Path(tmp)
    (racine / "history").mkdir(exist_ok=True)
    d = Donnees(["FR"], None, hist=racine / "history")
    d.sites = [("PEUGEOT FR", "PEUGEOT", "FR"), ("CITROEN FR", "CITROEN", "FR")]
    d.marques = ["PEUGEOT", "CITROEN"]
    ld = defaultdict(lambda: defaultdict(int))
    if leads:
        for a, base in ((2025, 50), (2026, 100)):
            for mo in range(1, 10):
                for marque, k in (("PEUGEOT", 1), ("CITROEN", 2)):
                    ld[(marque, f"{a}-{mo:02d}-15")]["VN"] += base * k
                    ld[(marque, f"{a}-{mo:02d}-16")]["VO"] += 10
    d._leads = ld
    d._acq = {}
    if c1st:
        mois = {}
        for a in (2025, 2026):
            for mo in range(1, 10):
                f = 1 + (a - 2025)
                mois[f"{a}-{mo:02d}"] = {
                    "leads": [{"marque": c, "leads": 100 * f, "envoyes": 100 * f, "clients_envoyes": 100 * f, "contactes": 40 * f, "contactes_delai": 30 * f, "premier_appel_delai": 20 * f,
                               "traites": 50 * f, "traites_delai": 40 * f, "avec_opp": 10 * f} for c in ("AP", "AC")],
                    "commandes": [{"marque": c, "clients_uniques": 100 * f, "avec_devis": 20 * f} for c in ("AP", "AC")],
                    "nsc": [{"marque": c, "commandes_nsc": 5 * f} for c in ("AP", "AC")]}
        d._c1st_data = {"FR": mois}
        d._c1st_partiel = "2026-10"
    return d


def _brief(**kw):
    b = {"client": "Stellantis", "langue": "en", "format": "revue_trim", "periode": {"type": "trimestre", "annee": 2026, "indice": 3}, "perimetre": {"pays": ["FR"], "marques": []},
         "comparaisons": {"precedente": True, "n1": True}, "modules": ["global"], "contact": {"nom": "A B", "fonction": "DKAM", "email": "a@b.c"},
         "pointsOuverts": [{"titre": "Point", "texte": "Un\nDeux"}], "prochainesEtapes": [{"item": "Faire", "responsable": "MAF", "statut": "a_faire", "echeance": "01/11"}]}
    b.update(kw)
    return b


def _titres(prs):
    out = []
    for s in prs.slides:
        t = s.shapes.title.text if s.shapes.title is not None else ""
        out.append(t)
    return out


class RevueTrim(unittest.TestCase):
    def _construit(self, tmp, brief=None, **kw):
        from pipeline.deck.construit import construit
        sortie = Path(tmp) / "out.pptx"
        ctx = construit(brief or _brief(), _donnees(tmp, **kw), sortie)
        from pptx import Presentation
        return ctx, Presentation(str(sortie))

    def test_deck_complet(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, prs = self._construit(tmp)
            t = _titres(prs)
            for attendu in ("Global Overview", "Global Leads by brand / Q3 Vs YoY", "Global Leads by brand / Q3 Vs QoQ", "Global leads by Month", "Global NC leads by Month",
                            "Global NC leads by Month xP brand", "Leads by Purchase Project: Q3-2026 for xP", "Traffic & leads Overview Q3-2026", "Leads Overview Q3-2026",
                            "SALES PERFORMANCE", "SALES PERFORMANCE: leads VN xP autobiz", "SALES PERFORMANCE: additional business", "Ongoing Actions", "NEXT STEPS", "Q/A"):
                self.assertIn(attendu, t, attendu)
            self.assertEqual(t.count("Agenda"), 5)
            self.assertEqual(t.index("Ongoing Actions"), 1)           # 2e diapositive, juste après la couverture
            self.assertEqual(len(prs.slides), ctx.n)
            # pas d'annexe CTA ni de contenu statique propre à un pays
            self.assertFalse([x for x in t if "CTA" in x or "POP" in x.upper().split() or "RUN" in x.upper().split()])
            # deep dive par marque : trafic, canaux, conquête (conquête sans modèles : avertissement, jamais de diapo vide)
            self.assertEqual(t.count("Traffic DEEP DIVE"), 2)
            self.assertEqual(t.count("LEAD DEEP DIVE"), 0)               # pas d'historique d'acquisition / de modèles dans ces données : slides non créées, avertissements
            self.assertTrue([w for w in ctx.avertissements if "lead deep dive" in w])

    def test_leads_par_marque_valeurs_et_commentaires(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, prs = self._construit(tmp)
            s = next(x for x in prs.slides if x.shapes.title is not None and x.shapes.title.text == "Global Leads by brand / Q3 Vs YoY")
            ch = [sh.chart for sh in s.shapes if getattr(sh, "has_chart", False) and sh.has_chart][0]
            self.assertEqual(list(ch.plots[0].series[1].values), [3 * 100 + 30, 3 * 200 + 30])      # T3 2026 : (100 VN + 10 VO) x 3 mois
            self.assertEqual(list(ch.plots[0].series[0].values), [3 * 50 + 30, 3 * 100 + 30])
            txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
            self.assertIn("All brands increasing YoY", txt)
            self.assertIn("Citroën +91%", txt)                            # 630 vs 330
            self.assertIn("Peugeot +83%", txt)                            # 330 vs 180

    def test_c1st_absent_section_non_creee(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, prs = self._construit(tmp, c1st=False)
            t = _titres(prs)
            self.assertNotIn("SALES PERFORMANCE", t)
            self.assertEqual(t.count("Agenda"), 4)                        # pas de section « Sales performance » dans l'agenda
            self.assertTrue([w for w in ctx.avertissements if "C1ST" in w])

    def test_ventes_additionnelles_c1st_reel(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, prs = self._construit(tmp)
            s = next(x for x in prs.slides if x.shapes.title is not None and x.shapes.title.text == "SALES PERFORMANCE: additional business")
            tb = [sh.table for sh in s.shapes if getattr(sh, "has_table", False) and sh.has_table][0]
            lignes = [[c.text for c in r.cells] for r in tb.rows]
            # 3 mois x 100 leads (2025) puis x 200 (2026) ; commandes NSC 3 x 5 = 15 puis 3 x 10 = 30 : +15 par marque
            self.assertEqual(lignes[1][1], "300"); self.assertEqual(lignes[1][2], "600")
            self.assertEqual(lignes[1][5], "15"); self.assertEqual(lignes[1][7], "30"); self.assertEqual(lignes[1][8], "+15")
            self.assertEqual(lignes[-1][0], "Total"); self.assertEqual(lignes[-1][8], "+30")

    def test_commentaires_en_anglais_meme_si_brief_en_francais(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, prs = self._construit(tmp, _brief(langue="fr"))
            textes = " ".join(sh.text_frame.text for sl in prs.slides for sh in sl.shapes if sh.has_text_frame)
            for mot in ("période précédente", "Baisse", "Hausse", "Part de leads", "Relancer", "Compléter le balisage"):
                self.assertNotIn(mot, textes)

    def test_periode_trimestrielle_obligatoire(self):
        from pipeline.deck.construit import construit
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                construit(_brief(periode={"type": "mois", "annee": 2026, "indice": 9}), _donnees(tmp), Path(tmp) / "x.pptx")

    def test_aucun_lead_pas_de_marque(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx, prs = self._construit(tmp, c1st=False, leads=False)
            t = _titres(prs)
            self.assertNotIn("Traffic DEEP DIVE", t)
            self.assertNotIn("Global Leads by brand / Q3 Vs YoY", t)


class RevueTrimSocle(unittest.TestCase):
    def test_libelles_trimestre(self):
        from pipeline.deck.periodes import Periode
        from pipeline.deck.revue_commun import court, mois_label
        q = Periode("trimestre", 2026, 3)
        self.assertEqual(mois_label(q), "Q3-2026")
        self.assertEqual(court(q), "Q3")
        self.assertEqual(court(Periode("mois", 2026, 9)), "Sep")

    def test_revue_fr_reste_mensuelle(self):
        from pipeline.deck.construit import Ctx
        from pipeline.deck.revue_commun import Revue
        with tempfile.TemporaryDirectory() as tmp:
            ctx = Ctx(_brief(format="revue_fr", periode={"type": "mois", "annee": 2026, "indice": 9}), _donnees(tmp))
            rv = Revue(ctx)
            self.assertFalse(rv.trim)
            self.assertEqual(rv.vs_prec, "MoM")
            ctx = Ctx(_brief(periode={"type": "annee", "annee": 2026, "indice": None}), _donnees(tmp))
            with self.assertRaises(ValueError):
                Revue(ctx)


if __name__ == "__main__":
    unittest.main()
