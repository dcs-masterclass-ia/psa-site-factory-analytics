"""Controles avant publication.

Ce module ne fait qu'une chose : dire si un fichier de donnees est publiable.
Un controle `bloquant` qui echoue interdit l'ecriture. Un `avertissement`
laisse passer mais remonte dans data/pipeline.json et s'affiche dans le
dashboard.

Chaque controle est ne d'une erreur reellement survenue sur ce projet. Les
commentaires disent laquelle.
"""

from dataclasses import dataclass, field

DIMS = ("brand", "fuel", "entry", "project", "source", "code")

# seuils
ECART_DEPOT_MAX = 30.0        # %
NON_ADDITIVITE_MAX = 3.5      # %
TRANSFO_MIN, TRANSFO_MAX = 2.0, 45.0   # %
SESSIONS_PAR_USER_MAX = 3.0
TRAFIC_ETRANGER_MAX = 40.0    # %


@dataclass
class Resultat:
    nom: str
    ok: bool
    bloquant: bool
    detail: str = ""


@dataclass
class Rapport:
    site: str
    resultats: list = field(default_factory=list)

    def ajoute(self, nom, ok, bloquant, detail=""):
        self.resultats.append(Resultat(nom, ok, bloquant, detail))

    @property
    def echecs_bloquants(self):
        return [r for r in self.resultats if not r.ok and r.bloquant]

    @property
    def avertissements(self):
        return [r for r in self.resultats if not r.ok and not r.bloquant]

    @property
    def publiable(self):
        return not self.echecs_bloquants

    @property
    def statut(self):
        if self.echecs_bloquants:
            return "echec"
        return "degrade" if self.avertissements else "ok"

    def resume(self):
        p = sum(1 for r in self.resultats if r.ok)
        return f"{p}/{len(self.resultats)} controles passes"


def _mois_consolides(d):
    return [m for m in d["months"] if not d["meta"].get(m, {}).get("provisional")]


def controle(nouveau, ancien=None, modele=None):
    """Applique tous les controles a un fichier de donnees assemble.

    nouveau : dict du fichier candidat
    ancien  : dict du fichier actuellement en ligne, pour l'ecart au depot
    modele  : dict d'un fichier de reference, pour la structure
    """
    r = Rapport(site=nouveau.get("site", "?"))

    # --- coherence interne -------------------------------------------------
    # ne du trou du 31/07 : leads.daily a 30 valeurs pour un mois de 31 jours
    # les jours inconnus (None) sont ignores : un jour de leads pas encore
    # extrait du back-office ne doit pas faire echouer la coherence du mois.
    ok = all(sum(v for v in nouveau["leads"][m]["daily"] if v is not None)
             == nouveau["leads"][m]["total"]
             for m in nouveau["periods"])
    r.ajoute("somme_daily_egale_total", ok, True,
             "" if ok else "au moins un mois ou la somme des jours differe du total")

    mauvais = [m for m in nouveau["periods"]
               if len(nouveau["leads"][m]["daily"]) != nouveau["meta"][m]["days"]]
    r.ajoute("longueur_daily_egale_days", not mauvais, True,
             "" if not mauvais else f"mois en ecart : {mauvais}")

    longueurs = {k: len(nouveau["daily"][k]) for k in ("d", "u", "rep", "sc", "si")}
    ok = len(set(longueurs.values())) == 1
    r.ajoute("series_alignees", ok, True, "" if ok else str(longueurs))

    # ne du cumul perime d'OPEL FR : leads.total ignorait le rattrapage du 31/07
    cons = _mois_consolides(nouveau)
    attendu = sum(nouveau["leads"][m]["total"] for m in cons)
    ok = nouveau["leads"]["total"]["total"] == attendu
    r.ajoute("cumul_egale_somme_mois", ok, True,
             "" if ok else f"cumul {nouveau['leads']['total']['total']} vs somme {attendu}")

    # --- structure ---------------------------------------------------------
    if modele:
        # les cles prefixees par _ sont des diagnostics internes, retires avant
        # ecriture : elles ne font pas partie du schema publie.
        # cles de schema ajoutees volontairement par le pipeline, au-dela du
        # modele historique : `anomaly` (trafic automatise documente),
        # `canalQuotidien` (repartition par canal, jour par jour),
        # `searchMonth` (Search Console : clics/impressions/CTR/position,
        # top requetes et top pages) et `insights` (signaux IA sur ces
        # memes donnees Search Console). Toute AUTRE cle inattendue doit
        # continuer de bloquer la publication.
        SCHEMA_ETENDU = {"anomaly", "canalQuotidien", "searchMonth", "insights", "v2Weekly"}
        sup = {k for k in nouveau if not k.startswith("_")} - set(modele) - SCHEMA_ETENDU
        manq = set(modele) - set(nouveau)
        ok = not sup and not manq
        r.ajoute("structure_identique", ok, True,
                 "" if ok else f"en trop {sorted(sup)} / manquantes {sorted(manq)}")

    # --- ecart au depot ----------------------------------------------------
    if ancien:
        gros = []
        for m in nouveau["months"]:
            if m not in ancien.get("leads", {}):
                continue
            a = ancien["leads"][m]["total"]
            b = nouveau["leads"][m]["total"]
            if a and abs(b - a) / a * 100 > ECART_DEPOT_MAX:
                gros.append(f"{m} {a}->{b}")
        r.ajoute("ecart_depot_sous_30pct", not gros, True,
                 "" if not gros else "; ".join(gros))

    # --- non-additivite GA4 (avertissement : c'est normal, pas a corriger) --
    souples = []
    for m in nouveau["months"]:
        if m not in nouveau.get("trafficMonth", {}):
            continue
        mm = m[5:7]
        idx = [i for i, x in enumerate(nouveau["daily"]["d"]) if x[:2] == mm]
        for cle, serie in (("trafficMonth", "u"), ("repriseMonth", "rep")):
            tot = nouveau[cle][m]["sessions"]
            s = sum(v for i, v in enumerate(nouveau["daily"][serie]) if i in idx and v is not None)
            if tot and abs(s - tot) / tot * 100 > NON_ADDITIVITE_MAX:
                souples.append(f"{m} {cle} {(s - tot) / tot * 100:+.1f}%")
    r.ajoute("non_additivite_sous_3_5pct", not souples, False,
             "" if not souples else "; ".join(souples))

    # --- taux de transformation -------------------------------------------
    hors = []
    for m in nouveau["months"]:
        if m not in nouveau.get("repriseMonth", {}):
            continue
        an = (nouveau.get("anomaly") or {}).get(m)
        net = an["reprise_nette"] if an else nouveau["repriseMonth"][m]["sessions"]
        l = nouveau["leads"][m]["total"]
        if not net:
            continue
        t = l / net * 100
        if not (TRANSFO_MIN <= t <= TRANSFO_MAX):
            hors.append(f"{m} {t:.1f}%")
    r.ajoute("transformation_dans_2_45pct", not hors, False,
             "" if not hors else "; ".join(hors))

    # --- signature de trafic automatise -----------------------------------
    # ne du robot espagnol : 14 sessions par utilisateur sur ALFA ROMEO en juin
    mauvais = []
    for m, val in (nouveau.get("_ratios_sessions_users") or {}).items():
        if val and val > SESSIONS_PAR_USER_MAX:
            mauvais.append(f"{m} ratio {val:.1f}")
    r.ajoute("sessions_par_utilisateur_sous_3", not mauvais, False,
             "" if not mauvais else "; ".join(mauvais))

    # ne du meme robot : 85 % du trafic venait d'Espagne sur un site portugais
    mauvais = []
    for m, val in (nouveau.get("_part_etranger") or {}).items():
        if val and val > TRAFIC_ETRANGER_MAX:
            mauvais.append(f"{m} {val:.0f}% hors pays")
    r.ajoute("trafic_etranger_sous_40pct", not mauvais, False,
             "" if not mauvais else "; ".join(mauvais))

    # --- funnel ---------------------------------------------------------
    # un entonnoir doit decroitre etape par etape ; une hausse signale que la
    # methode de repli (mot-cle sur les evenements) a mal identifie une etape
    non_decroissant = []
    for m, fm in (nouveau.get("funnelMonth") or {}).items():
        vals = [s["users"] for s in fm.get("steps", [])]
        if any(vals[i] < vals[i + 1] for i in range(len(vals) - 1)):
            non_decroissant.append(m)
    r.ajoute("funnel_decroissant", not non_decroissant, False,
             "" if not non_decroissant else f"mois en ecart : {non_decroissant}")

    # la bascule sur une methode de repli degrade la fidelite : on le signale,
    # sans bloquer, en precisant LAQUELLE des deux methodes de repli a servi —
    # step_name est fidele a l'exploration GA4 manuelle, mot-cle est une
    # approximation plus grossiere.
    methodes = nouveau.get("_methodes_funnel") or {}
    via_step_name = [m for m, meth in methodes.items() if meth and "step_name" in meth]
    via_mot_cle = [m for m, meth in methodes.items() if meth and "mot-cle" in meth]
    if via_mot_cle:
        r.ajoute("funnel_methode_precise", False, False,
                 f"repli par mot-cle (approximation) sur : {via_mot_cle}")
    elif via_step_name:
        r.ajoute("funnel_methode_precise", False, False,
                 f"dimension step_name (fidele a l'exploration GA4) sur : {via_step_name}")
    else:
        r.ajoute("funnel_methode_precise", True, False)

    # ne de la correction du 04/08/2026 : l'etape Estimation etait surevaluee
    # (filtre sur step_name seul, sans le croisement avec l'evenement
    # tradein_request exige par l'exploration GA4). On mesure l'ampleur du
    # changement pour ce mois si l'ancien fichier avait deja un funnel.
    ecarts_estim = []
    for m, fm in (nouveau.get("funnelMonth") or {}).items():
        ancien_fm = (ancien.get("funnelMonth") or {}).get(m) if ancien else None
        if not ancien_fm or not fm.get("steps") or not ancien_fm.get("steps"):
            continue
        # comparaison par position : les libelles heritent parfois de
        # relevés manuels anterieurs ("6. price estimation") plutot que du
        # libelle produit par ce module ("Estimation")
        n_new = fm["steps"][-1]["users"]
        n_old = ancien_fm["steps"][-1]["users"]
        if n_old and n_new != n_old:
            ecarts_estim.append(f"{m} {n_old}->{n_new} ({(n_new-n_old)/n_old*100:+.0f}%)")
    if ecarts_estim:
        r.ajoute("funnel_estimation_recalculee", False, False, "; ".join(ecarts_estim))
    else:
        r.ajoute("funnel_estimation_recalculee", True, False)

    return r


def affiche(rapports):
    """Rend le rapport lisible dans un journal d'execution."""
    lignes = []
    for r in rapports:
        lignes.append(f"\n{r.site} — {r.resume()} — statut {r.statut}")
        for res in r.resultats:
            if res.ok:
                lignes.append(f"   ok       {res.nom}")
            else:
                marque = "BLOQUANT" if res.bloquant else "avert."
                lignes.append(f"   {marque:<9}{res.nom}  {res.detail}")
    return "\n".join(lignes)
