"""Construction de la présentation : diapositives, graphiques natifs, textes calculés.

Cœur du générateur : couverture, sommaire, vue d'ensemble, projets d'achat, détail par marque (trafic, leads, sources),
points ouverts, prochaines étapes, contacts. Module « cta » : non généré pour l'instant (signalé dans les avertissements).
"""

from datetime import date
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from . import analyse as an
from . import graphiques as g
from .donnees import GROUPES_MARQUES, NOMS_MARQUES, ORDRE_SOURCES, PROJETS, Donnees
from .periodes import MOIS_COURTS, Periode, depuis_brief
from .textes import MOINS, T

GABARIT = Path(__file__).with_name("gabarit_autobiz.pptx")
X0, X1 = 0.45, 12.9        # marges horizontales du contenu
Y0, Y1 = 1.45, 6.85        # zone de contenu


class Ctx:
    def __init__(self, brief, donnees, gabarit=GABARIT):
        self.brief, self.d = brief, donnees
        self.t = T(brief.get("langue", "fr"))
        self.langue = self.t.l
        self.prs = Presentation(str(gabarit))
        self.lay = {l.name: l for l in self.prs.slide_layouts}
        self.per = depuis_brief(brief["periode"])
        comp = brief.get("comparaisons") or {}
        self.refs = []                     # [(clé, Periode, libellé court)]
        if comp.get("precedente") and self.per.type != "annee":
            self.refs.append(("prec", self.per.precedente()))
        if comp.get("n1"):
            self.refs.append(("n1", self.per.n1()))
        self.n = 0                         # numéro de diapositive
        self.comm_utilises = set()         # clés de commentaires déjà affichées
        self.avertissements = []
        self.modules = set(brief.get("modules") or [])
        pays = [p.upper() for p in brief["perimetre"]["pays"]]
        self.perimetre = "BELUX" if sorted(pays) == ["BE", "LU"] else " + ".join(pays)
        self.client = brief.get("client") or ""

    def et(self, p):
        return p.etiquette(self.langue)

    @property
    def periodes(self):
        """Périodes à afficher dans l'ordre chronologique : références puis période courante."""
        return sorted([p for _, p in self.refs], key=lambda p: (p.annee, p.mois_debut)) + [self.per]

    def nom(self, marque):
        return NOMS_MARQUES.get(marque, marque.title())


# ------------------------------------------------------------------ squelette de diapositive
def nouvelle(ctx, titre, sous_titre=None, source=None, layout="Title and Subtitle", notes=None, cle=None):
    s = ctx.prs.slides.add_slide(ctx.lay[layout])
    ctx.n += 1
    s.shapes.title.text = titre
    for ph in s.placeholders:
        if ph.placeholder_format.idx == 12:
            ph.text = sous_titre or ""
    if sous_titre is None and layout == "Title and Subtitle":
        for ph in list(s.placeholders):
            if ph.placeholder_format.idx == 12:
                ph._element.getparent().remove(ph._element)
    g.texte(s, 0.3, 7.1, 6.5, 0.3, source or "", taille=9, couleur=g.GRIS)
    g.texte(s, 4.4, 7.1, 4.5, 0.3, ctx.t["confidentiel"], taille=9, couleur=g.GRIS, align=PP_ALIGN.CENTER)
    g.texte(s, 12.2, 7.1, 0.8, 0.3, str(ctx.n), taille=9, couleur=g.GRIS, align=PP_ALIGN.RIGHT)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    if cle:
        commentaire_diapo(ctx, s, cle)
    return s


def commentaire_diapo(ctx, s, cle):
    """Commentaire du DKAM saisi dans le questionnaire (brief["commentaires"][clé]), affiché sous le titre à droite ; une clé n'est affichée qu'une fois
    (la clé « marque:X » apparaît donc sur la première diapositive de la marque)."""
    txt = ((ctx.brief.get("commentaires") or {}).get(cle) or "").strip()
    if not txt or cle in ctx.comm_utilises:
        return
    ctx.comm_utilises.add(cle)
    g.encadre(s, 4.7, 0.78, 8.2, 0.42, None, [txt[:240]], taille=9.5, couleur=g.ORANGE)


def source_bo(ctx):
    return ctx.t["source_bo"]


def source_ga4(ctx):
    return ctx.t["source_ga4"]


def source_les_deux(ctx):
    return ctx.t["source_bo_ga4"]


def note_definitions(ctx, extra=""):
    return (f"{ctx.t['perimetre']} : {ctx.perimetre}. Leads : back-office autobiz, leads valides (production, hors doublons, tests et tests internes). "
            f"Trafic : sites de reprise (GA4). Définitions : docs/presentations-definitions.md. {extra}").strip()


# ------------------------------------------------------------------ commentaires calculés
def commentaire_evolutions(ctx, etiquettes, courant, ref, nom_ref, max_lignes=4):
    """Hausses / baisses par élément (marque…), pourcentage seulement si la base de référence >= 100."""
    t = ctx.t
    hausses, baisses, petites = [], [], []
    for e, c, r in zip(etiquettes, courant, ref):
        txt, signe, v = t.evol(c, r)
        if v is None:
            if (c or 0) + (r or 0) > 0 and c != r:
                petites.append(f"{e} : {t.nb(c)} (vs {t.nb(r)})")
            continue
        if signe > 0:
            hausses.append((v, f"{e} {txt}"))
        elif signe < 0:
            baisses.append((v, f"{e} {txt}"))
    hausses.sort(reverse=True); baisses.sort()
    lignes = []
    if hausses:
        lignes.append((("En hausse " if ctx.langue == "fr" else "Up ") + nom_ref + " :", True))
        lignes.append(", ".join(x[1] for x in hausses[:max_lignes]))
    if baisses:
        lignes.append((("En baisse " if ctx.langue == "fr" else "Down ") + nom_ref + " :", True))
        lignes.append(", ".join(x[1] for x in baisses[:max_lignes]))
    if petites:
        lignes.append((("Petits volumes (pas de %) :" if ctx.langue == "fr" else "Small volumes (no %):"), True))
        lignes.append(", ".join(petites[:max_lignes]))
    if not lignes:
        lignes.append("Pas d'évolution significative." if ctx.langue == "fr" else "No significant change.")
    return lignes


def libelle_ref(ctx, cle):
    return ctx.t["vs_prec"] if cle == "prec" else ctx.t["vs_n1"]


# ------------------------------------------------------------------ pièces
def couverture(ctx):
    s = ctx.prs.slides.add_slide(ctx.lay["Title Slide"])
    ctx.n += 1
    titre = ctx.brief.get("titre") or f"{ctx.client} — {ctx.perimetre} {ctx.et(ctx.per)}"
    g.texte(s, 1.0, 2.5, 8.5, 1.0, ctx.client.upper(), taille=34, gras=True, couleur="FFFFFF")
    g.texte(s, 1.0, 3.55, 11.0, 1.2, titre, taille=22, gras=True, couleur="FFFFFF")
    g.texte(s, 1.0, 5.2, 11.0, 0.5, f"{ctx.perimetre} · {ctx.et(ctx.per)} · {date.today().strftime('%d/%m/%Y')}", taille=16, couleur="FFFFFF")
    return s


def sommaire(ctx, sections, actif=None):
    s = nouvelle(ctx, ctx.t["agenda"])
    y = 1.9
    for i, (cle, libelle) in enumerate(sections):
        on = cle == actif
        box = s.shapes.add_shape(1, Inches(1.2), Inches(y), Inches(10.4), Inches(0.5))
        box.fill.solid(); box.fill.fore_color.rgb = g.rgb(g.BLEU if on else "F1F4F9")
        box.line.fill.background(); box.shadow.inherit = False
        g.texte(s, 1.35, y + 0.05, 10.0, 0.4, libelle.upper(), taille=15, gras=on, couleur="FFFFFF" if on else g.BLEU, ancre=MSO_ANCHOR.MIDDLE)
        y += 0.68
    return s


def synthese(ctx):
    t, d, per = ctx.t, ctx.d, ctx.per
    s = nouvelle(ctx, f"{t['synthese']} — {ctx.et(per)}", f"{ctx.perimetre}", source_les_deux(ctx), notes=note_definitions(ctx), cle="synthese")
    leads = d.leads(per); tot = sum(leads.values()); nc = leads["VN"]
    sess_cur = sum(sum(d.canaux(per, m).values()) for m in d.marques)
    # tuiles
    def detail_evol(v_cur, f_ref):
        parties = []
        for cle, p in ctx.refs:
            txt, signe, _ = t.evol(v_cur, f_ref(p))
            parties.append(f"{txt} {libelle_ref(ctx, cle)}")
        return "  ·  ".join(parties) if parties else None
    x, w, gap = X0, 3.0, 0.15
    g.tuile(s, x, 1.55, w, 1.35, t["leads"], t.nb(tot), detail_evol(tot, d.leads_total))
    taux_cur = t.taux(nc, tot)
    det = []
    for cle, p in ctx.refs:
        r = d.leads(p); tr = t.taux(r["VN"], sum(r.values()))
        det.append(f"{t.pts(taux_cur - tr) if (taux_cur is not None and tr is not None and sum(r.values()) >= 100) else t['n_s']} {libelle_ref(ctx, cle)}")
    g.tuile(s, x + (w + gap), 1.55, w, 1.35, t["taux_nc"], t.pct(taux_cur, 0) if taux_cur is not None else t["non_dispo"], "  ·  ".join(det) or None)
    g.tuile(s, x + 2 * (w + gap), 1.55, w, 1.35, t["sessions"], t.nb(sess_cur),
            detail_evol(sess_cur, lambda p: sum(sum(d.canaux(p, m).values()) for m in d.marques)))
    ga = {m: d.utilisateurs(per, m) for m in d.marques}
    mesurees = [m for m, v in ga.items() if v is not None]
    if mesurees:
        hot = sum(ga[m]["hot_leads"] for m in mesurees)
        det_h = []
        for cle, p in ctx.refs:
            rr = [d.utilisateurs(p, m) for m in mesurees]
            if all(v is not None for v in rr):       # comparaison sur les mêmes marques uniquement
                det_h.append(f"{t.evol(hot, sum(v['hot_leads'] for v in rr))[0]} {libelle_ref(ctx, cle)}")
        if len(mesurees) < len(d.marques):
            det_h.append((f"{len(mesurees)} marques sur {len(d.marques)} mesurées" if ctx.langue == "fr" else f"{len(mesurees)} of {len(d.marques)} brands measured"))
        g.tuile(s, x + 3 * (w + gap), 1.55, w, 1.35, t["hot_leads"], t.nb(hot), "  ·  ".join(det_h) or None)
    else:
        g.tuile(s, x + 3 * (w + gap), 1.55, w, 1.35, t["hot_leads"], t["non_dispo"], t["ga4_indispo"])
    # commentaires : marques
    lignes = []
    for cle, p in ctx.refs:
        etiq = [ctx.nom(m) for m in d.marques]
        lignes += commentaire_evolutions(ctx, etiq, [d.leads_total(per, m) for m in d.marques], [d.leads_total(p, m) for m in d.marques],
                                         f"{libelle_ref(ctx, cle)} ({ctx.et(p)})", max_lignes=5)
    g.encadre(s, X0, 3.2, 8.3, 3.5, ("Leads par marque" if ctx.langue == "fr" else "Leads by brand"), lignes, taille=11.5)
    g.texte(s, 9.0, 3.2, 3.9, 3.5, [(t["base_faible"], {"taille": 10, "couleur": g.GRIS, "italique": True})])
    return s


def groupes_de_marques(ctx):
    """{nom du groupe: [marques]} limité aux marques du périmètre : XP, XF, Spoticar, autres."""
    ms = ctx.d.marques
    g_ = {"XP": [m for m in GROUPES_MARQUES["XP"] if m in ms], "XF": [m for m in GROUPES_MARQUES["XF"] if m in ms], "Spoticar": [m for m in ms if m == "SPOTICAR"]}
    g_["Autres" if ctx.langue == "fr" else "Other"] = [m for m in ms if m not in sum(g_.values(), [])]
    return {k: v for k, v in g_.items() if v}


def vue_groupes(ctx):
    """Leads par groupe de marques (XP / XF / Spoticar / autres), avec la vue « hors Spoticar »."""
    t, d, per = ctx.t, ctx.d, ctx.per
    grp = groupes_de_marques(ctx)
    if len(grp) < 2:
        return None
    periodes = ctx.periodes
    L = lambda p, ms: sum(d.leads_total(p, m) for m in ms)
    s = nouvelle(ctx, f"{t['groupes']} — {ctx.et(per)}", ctx.perimetre, source_bo(ctx), notes=note_definitions(ctx), cle="groupes")
    couleurs = ["1F3F7A", "F58A1F", "7FB7B0", "9AA3B2"]
    series = [(k, [L(p, ms) for p in periodes], couleurs[i % 4]) for i, (k, ms) in enumerate(grp.items())]
    g.colonnes(s, X0, Y0, 5.6, 4.2, [ctx.et(p) for p in periodes], series, empile=True, taille=10, fmt=t.nb)
    ent = [t["groupe"], f"{t['leads']} {ctx.et(per)}", t["part_total"], f"{t['part_total']} ({t['hors_spoticar'].lower()})"] + [libelle_ref(ctx, c) for c, _ in ctx.refs]
    tot = L(per, d.marques)
    tot_hs = sum(L(per, ms) for k, ms in grp.items() if k != "Spoticar")
    lignes = [ent]
    for k, ms in grp.items():
        v = L(per, ms)
        row = [k, t.nb(v), t.pct(v / tot * 100, 0) if tot else "–", "–" if k == "Spoticar" or not tot_hs else t.pct(v / tot_hs * 100, 0)]
        row += [t.evol(v, L(p, ms))[0] for _, p in ctx.refs]
        lignes.append(row)
    lignes.append([t["total"], t.nb(tot), "100 %", "–"] + [t.evol(tot, L(p, d.marques))[0] for _, p in ctx.refs])
    if "Spoticar" in grp:
        lignes.append([t["hors_spoticar"], t.nb(tot_hs), t.pct(tot_hs / tot * 100, 0) if tot else "–", "100 %"] + [t.evol(tot_hs, sum(L(p, ms) for k, ms in grp.items() if k != "Spoticar"))[0] for _, p in ctx.refs])
    nc = len(ent)
    g.tableau(s, 6.3, Y0 + 0.3, 6.6, lignes, largeurs=[1.5] + [(6.6 - 1.5) / (nc - 1)] * (nc - 1), taille=10, hauteur_ligne=0.4, gras_derniere=True)
    bandeau(ctx, s, an.s_groupes(ctx, grp))
    return s


def blocs_fixes(ctx, nom):
    """Diapositives fixes réutilisables : NPS autobiz (2), modèle d'URL avec balisage UTM (1)."""
    fr = ctx.langue == "fr"
    if nom == "nps":
        s = nouvelle(ctx, "NPS autobiz — pourquoi ?" if fr else "NPS at autobiz — why?", None)
        g.texte(s, X0, 1.6, 12.4, 0.5, ("Quel que soit le point de départ, l'objectif est d'améliorer le taux de réponse et le score NPS." if fr else "Whatever the starting point, the target is to improve the answer rate and the NPS score."), taille=16, gras=True, couleur=g.BLEU)
        g.puces(s, X0, 2.4, 12.4, 3.8, [
            ("Partager à l'avance les évolutions produit et les nouvelles fonctionnalités" if fr else "Share product evolutions and new features in advance"),
            ("Suivi régulier et rencontres physiques" if fr else "Regular follow-up and physical meetings"),
            ("Mise en place d'enquêtes qualitatives" if fr else "Qualitative surveys setup"),
            ("Plus de communication en amont" if fr else "More communication in advance")], taille=16)
        s = nouvelle(ctx, "NPS autobiz — comment ?" if fr else "NPS at autobiz — how?", None)
        g.puces(s, X0, 1.8, 12.4, 4.0, [("Prochaine enquête NPS : dates à renseigner (envoi par e-mail)." if fr else "Next NPS survey: dates to be filled in (sent by email).")], taille=16)
        return s
    if nom == "utm":
        s = nouvelle(ctx, "Modèle d'URL avec balisage UTM" if fr else "Template to generate URL with UTM tracking", None)
        ent = ["URL du site trade-in", "utm_source", "utm_medium", "utm_campaign", "URL à poser sur le bouton"] if fr else ["Trade-in site URL", "utm_source", "utm_medium", "utm_campaign", "URL to add to the CTA"]
        ex = ["https://reprise.marque.xx/", "Main-Website", "Showroom", "e-C3", "…?utm_source=Main-Website&utm_medium=Showroom&utm_campaign=e-C3"]
        g.tableau(s, X0, 1.8, 12.4, [ent, ex], largeurs=[2.4, 1.6, 1.6, 1.6, 5.2], taille=11, hauteur_ligne=0.5, alignements=None)
        g.puces(s, X0, 3.3, 12.4, 3.0, [
            ("Source et medium : à laisser tels quels (ils identifient les boutons du site de la marque)." if fr else "Source and medium: leave as is (they identify the brand-website CTAs)."),
            ("Pour les pages showroom uniquement : renseigner la campagne avec le modèle de la page (ex. « e-C3 »)." if fr else "For showroom pages only: set the campaign to the page's model (e.g. “e-C3”)."),
            ("L'URL finale se construit automatiquement à partir de ces colonnes ; c'est elle qu'il faut poser sur le bouton pour le suivre." if fr else "The final URL is built from these columns; it is the one to place on the button to track it.")], taille=14)
        return s


def leads_par_marque(ctx, cle, ref):
    t, d, per = ctx.t, ctx.d, ctx.per
    marques = [m for m in d.marques if d.leads_total(per, m) + d.leads_total(ref, m) > 0]
    cur = [d.leads_total(per, m) for m in marques]
    rf = [d.leads_total(ref, m) for m in marques]
    s = nouvelle(ctx, f"{t['leads']} — {ctx.et(per)} {libelle_ref(ctx, cle)}", f"{ctx.perimetre} · {ctx.et(per)} / {ctx.et(ref)}", source_bo(ctx),
                 notes=note_definitions(ctx), cle="leads_marques")
    perso = [None] + [[f"{t.nb(c)}\n{t.evol(c, r)[0]}" if t.evol(c, r)[2] is not None else t.nb(c) for c, r in zip(cur, rf)]]
    g.colonnes(s, X0, Y0, 8.9, 4.2, [ctx.nom(m) for m in marques],
               [(ctx.et(ref), rf, g.COULEURS_PERIODES[1]), (ctx.et(per), cur, g.COULEURS_PERIODES[2])],
               libelles_perso={1: perso[1]}, taille=10, fmt=t.nb)
    g.encadre(s, 9.55, Y0 + 0.1, 3.4, 4.0, None, commentaire_evolutions(ctx, [ctx.nom(m) for m in marques], cur, rf, f"({ctx.et(ref)})"), taille=10.5)
    bandeau(ctx, s, an.s_leads_marques(ctx, cle, ref))
    return s


def leads_mensuels(ctx, projet=None):
    t, d, per = ctx.t, ctx.d, ctx.per
    dernier = d.dernier_jour_leads()
    def complets(a, vals):
        """Seuls les mois entièrement écoulés sont tracés : le mois en cours (partiel) et les mois futurs restent vides."""
        out = []
        for k, v in enumerate(vals):
            fin_mois = Periode("mois", a, k + 1).fin.isoformat()
            out.append(v if (v and dernier and fin_mois <= dernier) else None)
        return out
    annees = [a for a in (per.annee - 2, per.annee - 1, per.annee) if sum(d.leads_mensuels(a, projet=projet)) > 0]
    if not annees:
        return None
    titre = (t["leads_nc"] if projet else t["leads"]) + f" {t['par_mois']}"
    s = nouvelle(ctx, titre, ctx.perimetre, source_bo(ctx), notes=note_definitions(ctx), cle=("leads_nc_mensuels" if projet else "leads_mensuels"))
    g.texte(s, X1 - 5.5, 1.12, 5.5, 0.3, ("Mois complets uniquement" if ctx.langue == "fr" else "Complete months only"), taille=9.5, couleur=g.GRIS, align=PP_ALIGN.RIGHT, italique=True)
    series = []
    for i, a in enumerate(annees):
        couleur = g.COULEURS_PERIODES[3 - len(annees) + i]
        vals = d.leads_mensuels(a, projet=projet)
        series.append((str(a), complets(a, vals), couleur))
    cats = MOIS_COURTS[ctx.langue]
    g.colonnes(s, X0, Y0, 12.4, 4.2, cats, series, taille=10, largeur_barre=40, fmt=t.nb)
    bandeau(ctx, s, an.s_mensuel(ctx, projet))
    return s


def apercu_marques(ctx):
    """Vue « Leads overview » : une ligne par marque (tendance et part New cars, moteurs de hausse ou de baisse, actions recommandées),
    xP puis xF, 6 marques par diapositive. Les actions sont des suggestions calculées ; `actionsMarques` du brief les remplace."""
    t, d, fr = ctx.t, ctx.d, ctx.langue == "fr"
    grp = groupes_de_marques(ctx)
    lots = [("XP", [m for k in ("XP", "Spoticar") for m in grp.get(k, [])] + [m for k in grp if k not in ("XP", "XF", "Spoticar") for m in grp[k]]), ("XF", grp.get("XF", []))]
    perso = ctx.brief.get("actionsMarques") or {}
    for nom_lot, marques in lots:
        marques = [m for m in marques if d.leads_total(ctx.per, m) + sum(d.leads_total(p, m) for _, p in ctx.refs) > 0]
        nb_diapos = -(-len(marques) // 6)
        taille_lot = -(-len(marques) // nb_diapos) if nb_diapos else 6      # lots équilibrés : 7 marques -> 4 + 3, jamais 6 + 1
        for i in range(0, len(marques), taille_lot or 6):
            morceau = marques[i:i + taille_lot]
            suite = "" if nb_diapos <= 1 else f" ({i // taille_lot + 1}/{nb_diapos})"
            s = nouvelle(ctx, f"{t['leads']} overview — {ctx.et(ctx.per)}{suite}" if not fr else f"Vue d'ensemble des leads — {ctx.et(ctx.per)}{suite}",
                         f"{ctx.perimetre} · {nom_lot}", source_bo(ctx),
                         notes=note_definitions(ctx, "Moteurs : écarts de leads par canal d'acquisition (back-office), part New cars et trafic GA4, vs la première période de comparaison. "
                                                     "Actions : suggestions calculées, à relire ; le champ « actionsMarques » du brief les remplace."), cle="apercu")
            ent = [t["marque"], ("Tendance & part New cars" if fr else "Lead trend & NC share"), ("Moteurs de la variation" if fr else "Drivers of increase / decrease"),
                   ("Actions recommandées" if fr else "Recommended actions")]
            lignes = [ent]
            for m in morceau:
                a = an.apercu_marque(ctx, m)
                tend = " | ".join(f"{e} {libelle_ref(ctx, c)}" for c, e in a["evols"]) or "–"
                if a["nc"]:
                    tend += f"\n{a['nc'][0]}"
                acts = perso.get(m) or a["actions"]
                lignes.append([ctx.nom(m), tend, "\n".join("• " + x for x in a["moteurs"]), "\n".join("• " + x for x in acts)])
            g.tableau(s, X0, Y0 + 0.05, 12.4, lignes, largeurs=[1.5, 2.6, 4.1, 4.2], taille=9, hauteur_ligne=0.68,
                      alignements=[PP_ALIGN.LEFT] * 4, colonnes_gras=(0,))
            g.texte(s, X0, 6.75, 12.4, 0.3, t["base_faible"], taille=8.5, couleur=g.GRIS, italique=True)


def cta_marque(ctx, m):
    """Leads issus des boutons trade-in du site de la marque (source Main-Website, campagne « CTA »), par emplacement et par projet d'achat."""
    t, d, per = ctx.t, ctx.d, ctx.per
    fr = ctx.langue == "fr"
    cur = d.cta(per, m)
    if not cur or not d.acquisition_disponible(per):
        return None
    ref = d.cta(ctx.refs[0][1], m) if ctx.refs else {}
    tot = lambda v: sum(v.values())
    supports = sorted(cur, key=lambda k: -tot(cur[k]))
    s = nouvelle(ctx, f"{ctx.nom(m)} — {'CTA du site de la marque' if fr else 'CTA on the brand website'} {ctx.et(per)}", ctx.perimetre, source_bo(ctx),
                 notes=note_definitions(ctx, "CTA : leads valides de la source Main-Website, campagne « CTA », par SUPPORT (emplacement du bouton) ; la colonne de comparaison est la première période de comparaison."), cle=f"marque:{m}")
    ent = [("Emplacement" if fr else "Placement")] + [t[pj] for pj in PROJETS] + [t["total"]]
    if ctx.refs:
        ent += [f"{t['total']} {ctx.et(ctx.refs[0][1])}", libelle_ref(ctx, ctx.refs[0][0])]
    lignes = [ent]
    for sup in supports:
        row = [sup] + [t.nb(cur[sup][pj]) for pj in PROJETS] + [t.nb(tot(cur[sup]))]
        if ctx.refs:
            r = tot(ref.get(sup, {}))
            row += [t.nb(r), t.evol(tot(cur[sup]), r)[0]]
        lignes.append(row)
    total = [t["total"]] + [t.nb(sum(cur[k][pj] for k in cur)) for pj in PROJETS] + [t.nb(sum(tot(v) for v in cur.values()))]
    if ctx.refs:
        tr = sum(tot(v) for v in ref.values())
        total += [t.nb(tr), t.evol(sum(tot(v) for v in cur.values()), tr)[0]]
    lignes.append(total)
    nc = len(ent)
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[2.6] + [(12.4 - 2.6) / (nc - 1)] * (nc - 1), taille=10.5, hauteur_ligne=0.4, gras_derniere=True)
    gtot = sum(tot(v) for v in cur.values())
    top = supports[0]
    g.encadre(s, X0, Y0 + 0.4 * len(lignes) + 0.4, 12.4, 1.2, ("Lecture" if fr else "Reading"), [
        (f"« {top} » est l'emplacement qui génère le plus de leads : {t.nb(tot(cur[top]))} ({t.pct(tot(cur[top]) / gtot * 100, 0)} des leads CTA du site)."
         if fr else f"“{top}” is the placement generating the most leads: {t.nb(tot(cur[top]))} ({t.pct(tot(cur[top]) / gtot * 100, 0)} of the site's CTA leads)."),
        (f"{len(supports)} emplacements actifs sur la période." if fr else f"{len(supports)} active placements over the period.")], taille=11, couleur=g.BLEU)
    return s


def conquete_marque(ctx, m):
    """Conquête vs fidélité : origine des clients (marque du véhicule repris), top marques reprises, et top modèles repris / lien repris -> acheté si l'historique des modèles est collecté."""
    from .donnees import MARQUES_STELLANTIS, norme_marque
    t, d, per = ctx.t, ctx.d, ctx.per
    fr = ctx.langue == "fr"
    rep = d.reprises(per, m)
    total = sum(rep.values())
    if total < 100:
        return None
    nm = norme_marque(m)
    fideles = rep.get(nm, 0)
    autres = sum(n for k, n in rep.items() if k != nm and k in MARQUES_STELLANTIS)
    conq = total - fideles - autres
    s = nouvelle(ctx, f"{ctx.nom(m)} — {'Conquête vs fidélité' if fr else 'Conquest vs loyalty'} {ctx.et(per)}", ctx.perimetre, source_bo(ctx),
                 notes=note_definitions(ctx, "Marque du véhicule repris (TRADE-IN BRAND) comparée à la marque du site : fidèles = même marque ; autres Stellantis ; concurrents = toutes les autres marques."), cle=f"marque:{m}")
    lab = (f"Fidèles ({ctx.nom(m)})", "Autres Stellantis", "Concurrents") if fr else (f"Loyalty ({ctx.nom(m)})", "Other Stellantis", "Competitors")
    g.texte(s, X0, Y0 - 0.05, 5.5, 0.3, "Origine des clients" if fr else "Customer origin", taille=12, gras=True, couleur=g.BLEU)
    g.anneau(s, X0, Y0 + 0.25, 5.6, 2.6, list(lab), [fideles, autres, conq], couleurs=["4E79A7", "76B7B2", "F28E2B"], taille=10.5)
    top = sorted(((k, n) for k, n in rep.items()), key=lambda kv: -kv[1])[:8]
    g.texte(s, 6.4, Y0 - 0.05, 6.4, 0.3, ("Top marques reprises" if fr else "Top trade-in brands"), taille=12, gras=True, couleur=g.BLEU)
    g.colonnes(s, 6.4, Y0 + 0.25, 6.5, 2.6, [(k if len(k) <= 3 else k.title()) for k, _ in top], [("n", [n for _, n in top], "4E79A7")], legende=False, taille=9, fmt=t.nb, largeur_barre=40)
    lignes = [(f"{t.pct(fideles / total * 100, 0)} des clients du site reprennent un véhicule {ctx.nom(m)} (fidèles), {t.pct(autres / total * 100, 0)} une autre marque Stellantis "
               f"et {t.pct(conq / total * 100, 0)} une marque concurrente, sur {t.nb(total)} leads." if fr else
               f"{t.pct(fideles / total * 100, 0)} of the site's customers trade in a {ctx.nom(m)} (loyalty), {t.pct(autres / total * 100, 0)} another Stellantis brand and "
               f"{t.pct(conq / total * 100, 0)} a competitor brand, out of {t.nb(total)} leads.")]
    mods = d.modeles(per, m)
    if mods:
        stla = {}
        hors = {}
        for mr, mo, ma, mo_a, n in mods:
            if mo:
                (stla if mr in MARQUES_STELLANTIS else hors)[f"{mr.title()} {mo.title()}"] = (stla if mr in MARQUES_STELLANTIS else hors).get(f"{mr.title()} {mo.title()}", 0) + n
        paires = {}
        for mr, mo, ma, mo_a, n in mods:
            if mo and mo_a:
                paires[(f"{mr.title()} {mo.title()}", mo_a.title())] = paires.get((f"{mr.title()} {mo.title()}", mo_a.title()), 0) + n
        if stla and hors:
            ts, th = sorted(stla.items(), key=lambda kv: -kv[1])[:5], sorted(hors.items(), key=lambda kv: -kv[1])[:5]
            lignes.append((f"Modèles Stellantis les plus repris : {', '.join(k for k, _ in ts)}. Modèles concurrents les plus repris : {', '.join(k for k, _ in th)}." if fr else
                           f"Most traded-in Stellantis models: {', '.join(k for k, _ in ts)}. Most traded-in competitor models: {', '.join(k for k, _ in th)}."))
        if paires:
            tp = sorted(paires.items(), key=lambda kv: -kv[1])[:4]
            lignes.append(("Reprise → achat les plus fréquents : " if fr else "Most frequent trade-in → purchase: ") + " ; ".join(f"{a} → {b} ({t.nb(n)})" for (a, b), n in tp))
    g.encadre(s, X0, Y0 + 3.05, 12.4, 1.9, ("Lecture" if fr else "Reading"), lignes, taille=11, couleur=g.BLEU)
    return s


NOMS_PAYS = {
    "fr": {"FR": "France", "BE": "BELUX", "LU": "BELUX", "ES": "Espagne", "PT": "Portugal", "IT": "Italie", "DE": "Allemagne", "PL": "Pologne", "GB": "Royaume-Uni", "UK": "Royaume-Uni", "AT": "Autriche"},
    "en": {"FR": "France", "BE": "BELUX", "LU": "BELUX", "ES": "Spain", "PT": "Portugal", "IT": "Italy", "DE": "Germany", "PL": "Poland", "GB": "United Kingdom", "UK": "United Kingdom", "AT": "Austria"},
}


def classement_marches(ctx):
    """Leads New cars (VN) par marché autobiz sur la période : rang, part du total, évolution vs N-1 et cumul de l'année. Belgique et Luxembourg sont regroupés (BELUX)."""
    from datetime import date as _d
    from pipeline.leads_extract import SITE_EXTRACT
    t, per = ctx.t, ctx.per
    fr = ctx.langue == "fr"
    tous = sorted({nom.rsplit(" ", 1)[1] for nom in SITE_EXTRACT})
    if len(tous) < 3:
        return None
    noms = NOMS_PAYS.get(ctx.langue, NOMS_PAYS["en"])
    dall = Donnees(tous, None, hist=ctx.d.hist)
    dernier = dall.dernier_jour_leads()
    if not dernier:
        return None
    fin_ytd = min(per.fin, _d.fromisoformat(dernier))
    class _Ytd:
        debut, fin = _d(per.annee, 1, 1), fin_ytd
    n1 = per.n1()
    from .donnees import PROJET_BO, _lignes, slug
    par_pays = {}
    for nom, marque, pays in dall.sites:
        k = noms.get(pays, pays)
        a = par_pays.setdefault(k, {"cur": 0, "n1": 0, "ytd": 0})
        for r in _lignes(dall.hist / "leads" / f"{slug(nom)}.csv.gz"):
            if r["statut"] != "valide" or PROJET_BO.get(r["projet_achat"], "SANS") != "VN":
                continue
            j, n = r["date"], int(r["n"])
            if per.debut.isoformat() <= j <= per.fin.isoformat():
                a["cur"] += n
            if n1.debut.isoformat() <= j <= n1.fin.isoformat():
                a["n1"] += n
            if _Ytd.debut.isoformat() <= j <= _Ytd.fin.isoformat():
                a["ytd"] += n
    total = sum(a["cur"] for a in par_pays.values())
    total_ytd = sum(a["ytd"] for a in par_pays.values())
    if total < 100:
        return None
    classe = sorted(par_pays.items(), key=lambda kv: -kv[1]["cur"])
    mon = noms.get(ctx.brief["perimetre"]["pays"][0].upper(), ctx.perimetre)
    s = nouvelle(ctx, ("Classement des marchés — leads New cars" if fr else "Market ranking — New cars leads"), ctx.perimetre, source_bo(ctx),
                 notes=note_definitions(ctx, "Leads New cars (projet VN, leads valides) de tous les marchés autobiz ; Belgique et Luxembourg regroupés. Cumul = du 1er janvier à la fin de la période (ou au dernier jour connu)."), cle="marches")
    ent = [("Rang" if fr else "Rank"), ("Marché" if fr else "Market"), f"{t['leads_nc']} {ctx.et(per)}", t["part_total"], libelle_ref(ctx, "n1"),
           (f"Cumul {per.annee}" if fr else f"YTD {per.annee}"), (f"Part du cumul" if fr else "YTD share")]
    lignes = [ent]
    for i, (k, a) in enumerate(classe, 1):
        lignes.append([str(i), k, t.nb(a["cur"]), t.pct(a["cur"] / total * 100, 0), t.evol(a["cur"], a["n1"])[0], t.nb(a["ytd"]),
                       t.pct(a["ytd"] / total_ytd * 100, 0) if total_ytd else "–"])
    lignes.append(["", t["total"], t.nb(total), "100 %", t.evol(total, sum(a["n1"] for a in par_pays.values()))[0], t.nb(total_ytd), "100 %"])
    g.tableau(s, X0, Y0 + 0.1, 8.2, lignes, largeurs=[0.7, 1.9, 1.5, 1.1, 1.0, 1.2, 0.8], taille=10, hauteur_ligne=0.36, gras_derniere=True,
              alignements=[PP_ALIGN.CENTER, PP_ALIGN.LEFT] + [PP_ALIGN.RIGHT] * 5)
    rang = next((i for i, (k, _) in enumerate(classe, 1) if k == mon), None)
    if rang:
        a = par_pays[mon]
        txt = [(f"{mon} se classe n°{rang} sur {len(classe)} marchés, avec {t.pct(a['cur'] / total * 100, 0)} des leads New cars autobiz sur la période ({t.nb(a['cur'])} leads)."
                if fr else f"{mon} ranks #{rang} of {len(classe)} markets, with {t.pct(a['cur'] / total * 100, 0)} of autobiz New cars leads over the period ({t.nb(a['cur'])} leads)."),
               (f"Évolution : {t.evol(a['cur'], a['n1'])[0]} {libelle_ref(ctx, 'n1')}." if fr else f"Change: {t.evol(a['cur'], a['n1'])[0]} {libelle_ref(ctx, 'n1')}.")]
        g.encadre(s, 9.0, Y0 + 0.1, 3.9, 3.2, ("Lecture" if fr else "Reading"), txt, taille=11, couleur=g.BLEU)
    return s


def projection_mois(ctx):
    """Projection de fin de mois des leads New cars par marque, pour une édition mensuelle dont le mois n'est pas terminé :
    leads du 1er au dernier jour connu, ramenés à la durée du mois au rythme moyen constant (indicatif), comparés au même mois de l'an dernier et au mois précédent."""
    import calendar
    t, d, per = ctx.t, ctx.d, ctx.per
    fr = ctx.langue == "fr"
    dernier = d.dernier_jour_leads()
    if per.type != "mois" or not dernier or dernier >= per.fin.isoformat() or dernier < per.debut.isoformat():
        return None
    jours_ecoules = int(dernier[8:10])
    jours_mois = calendar.monthrange(per.annee, per.mois_debut)[1]
    from datetime import date as _d
    class _P:                                        # période « du 1er au dernier jour connu »
        debut, fin = per.debut, _d.fromisoformat(dernier)
    n1, prec = per.n1(), per.precedente()
    lignes = [[t["marque"], f"{t['leads_nc']} 1–{jours_ecoules}", ("Projection fin de mois" if fr else "End-of-month projection"),
               f"{t['leads_nc']} {ctx.et(n1)}", libelle_ref(ctx, "n1"), f"{t['leads_nc']} {ctx.et(prec)}", libelle_ref(ctx, "prec")]]
    tot = [0, 0.0, 0, 0]
    for m in d.marques:
        cur = d.leads(_P, m)["VN"]
        r1, rp = d.leads(n1, m)["VN"], d.leads(prec, m)["VN"]
        if cur + r1 + rp == 0:
            continue
        proj = cur / jours_ecoules * jours_mois
        lignes.append([ctx.nom(m), t.nb(cur), t.nb(proj), t.nb(r1), t.evol(proj, r1)[0], t.nb(rp), t.evol(proj, rp)[0]])
        tot[0] += cur; tot[1] += proj; tot[2] += r1; tot[3] += rp
    if len(lignes) < 2:
        return None
    lignes.append([t["total"], t.nb(tot[0]), t.nb(tot[1]), t.nb(tot[2]), t.evol(tot[1], tot[2])[0], t.nb(tot[3]), t.evol(tot[1], tot[3])[0]])
    s = nouvelle(ctx, (f"Projection {ctx.et(per)} — leads New cars" if fr else f"{ctx.et(per)} projection — New cars leads"), ctx.perimetre, source_bo(ctx),
                 notes=note_definitions(ctx, f"Projection = leads New cars du 1er au {jours_ecoules} ÷ {jours_ecoules} jours × {jours_mois} jours : rythme moyen constant, indicatif (ne tient pas compte de la saisonnalité intra-mois)."), cle="projection")
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[2.1, 1.7, 1.9, 1.7, 1.7, 1.7, 1.6], taille=10.5, hauteur_ligne=0.38, gras_derniere=True)
    g.texte(s, X0, 6.55, 12.4, 0.5,
            (f"Données du 1er au {jours_ecoules} {MOIS_COURTS[ctx.langue][per.mois_debut - 1]} : la projection prolonge le rythme moyen quotidien sur les {jours_mois} jours du mois (indicatif)."
             if fr else f"Data from {MOIS_COURTS[ctx.langue][per.mois_debut - 1]} 1 to {jours_ecoules}: the projection extends the average daily rate over the {jours_mois} days of the month (indicative)."),
            taille=9, couleur=g.GRIS, italique=True)
    return s


def vue_ensemble_table(ctx):
    t, d, per = ctx.t, ctx.d, ctx.per
    s = nouvelle(ctx, f"{t['trafic']} & {t['leads'].lower()} — {ctx.et(per)}", ctx.perimetre, source_les_deux(ctx), notes=note_definitions(ctx), cle="vue_trafic_leads")
    ent = [t["marque"], f"{t['sessions_col']} {ctx.et(per)}"] + [f"{libelle_ref(ctx, c)}" for c, _ in ctx.refs] + [f"{t['leads']} {ctx.et(per)}"] + [f"{libelle_ref(ctx, c)}" for c, _ in ctx.refs]
    lignes = [ent]
    tot_s, tot_l = 0, 0
    tot_sr = [0] * len(ctx.refs); tot_lr = [0] * len(ctx.refs)
    for m in d.marques:
        s_cur = sum(d.canaux(per, m).values()); l_cur = d.leads_total(per, m)
        if not (s_cur or l_cur):
            continue
        row = [ctx.nom(m), t.nb(s_cur)]
        for k, (_, p) in enumerate(ctx.refs):
            sr = sum(d.canaux(p, m).values()); tot_sr[k] += sr
            row.append(t.evol(s_cur, sr)[0])
        row.append(t.nb(l_cur))
        for k, (_, p) in enumerate(ctx.refs):
            lr = d.leads_total(p, m); tot_lr[k] += lr
            row.append(t.evol(l_cur, lr)[0])
        tot_s += s_cur; tot_l += l_cur
        lignes.append(row)
    lignes.append([t["total"], t.nb(tot_s)] + [t.evol(tot_s, v)[0] for v in tot_sr] + [t.nb(tot_l)] + [t.evol(tot_l, v)[0] for v in tot_lr])
    nc = len(ent)
    lw = [2.4] + [(12.4 - 2.4) / (nc - 1)] * (nc - 1)
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=lw, taille=10.5, hauteur_ligne=0.27, gras_derniere=True)
    g.texte(s, X0, 6.85, 12.4, 0.25, t["base_faible"], taille=9, couleur=g.GRIS, italique=True)
    bandeau(ctx, s, an.s_table(ctx))
    return s


def projets_groupe(ctx, nom_groupe, marques):
    t, d, per = ctx.t, ctx.d, ctx.per
    marques = [m for m in marques if m in d.marques and d.leads_total(per, m) > 0]
    if not marques:
        return None
    s = nouvelle(ctx, f"{t['projets']} — {t[nom_groupe]}", f"{ctx.perimetre} · {ctx.et(per)}", source_bo(ctx), notes=note_definitions(ctx), cle="projets")
    ref = ctx.refs[-1][1] if ctx.refs else None            # n1 en priorité (dernier ajouté)
    larg = 6.1 if ref else 8.9
    def graphique(x, p):
        series = [(t[pj], [d.leads(p, m)[pj] for m in marques], g.COULEURS_PROJETS[pj]) for pj in PROJETS]
        g.texte(s, x, Y0, larg, 0.3, ctx.et(p), taille=13, gras=True, couleur=g.BLEU, align=PP_ALIGN.CENTER)
        g.colonnes(s, x, Y0 + 0.3, larg, 3.0, [ctx.nom(m) for m in marques], series, empile=True, taille=10, fmt=t.nb)
    graphique(X0, ref if ref else per)
    if ref:
        graphique(X0 + larg + 0.2, per)
    lignes = []
    for m in marques:
        c = d.leads(per, m); tc = sum(c.values())
        if tc < 100:
            continue
        taux = t.taux(c["VN"], tc)
        ligne = f"{ctx.nom(m)} : {t.pct(taux, 0)} {t['VN']}"
        if ref:
            r = d.leads(ref, m); tr = sum(r.values())
            if tr >= 100:
                ligne += f" ({t.pts(taux - t.taux(r['VN'], tr))} {libelle_ref(ctx, 'n1' if ref == ctx.per.n1() else 'prec')})"
        lignes.append(ligne)
    g.encadre(s, X0, Y0 + 3.45, 12.4, 0.8, ("Part de leads New cars" if ctx.langue == "fr" else "New cars leads share"), [" · ".join(lignes) or "—"], taille=10)
    bandeau(ctx, s, an.s_projets(ctx, marques))
    return s


def trafic_marque(ctx, m):
    t, d, per = ctx.t, ctx.d, ctx.per
    if d.utilisateurs(per, m) is None and not sum(d.canaux(per, m).values()):
        ctx.avertissements.append(f"{ctx.nom(m)} : aucune donnée de trafic sur la période, diapositive non générée.")
        return None
    s = nouvelle(ctx, f"{ctx.nom(m)} — {t['trafic']} {ctx.et(per)}", ctx.perimetre, source_ga4(ctx),
                 notes=note_definitions(ctx, "Chaîne GA4 comme Looker, calculée sur la période entière : sessions (total GA4) ; In Journey = sessions sur une page formulaire ou lead (page_category « form page » / « lead page ») ; hot leads = évènements tradein_request. CVR = hot leads ÷ sessions. Canaux = Stellantis Custom Channel Group. « Via site marque » = sessions de source UTM Main-Website ou referral depuis l'URL de la marque, ÷ sessions totales."), cle=f"marque:{m}")
    ga = d.utilisateurs(per, m)
    y, h, w = 1.55, 1.25, 2.55
    if ga is None:
        g.tuile(s, X0, y, 3 * w + 1.2, h, t["sessions"], t["non_dispo"], t["ga4_indispo"])
    else:
        refs = [(c, d.utilisateurs(p, m)) for c, p in ctx.refs]
        def det(k):
            out = []
            for c, v in refs:
                out.append(f"{t.evol(ga[k], v[k])[0]} {libelle_ref(ctx, c)}" if v else f"{t['non_dispo']}")
            return "  ·  ".join(out) or None
        g.tuile(s, X0, y, w, h, t["sessions"], t.nb(ga["sessions"]), det("sessions"), taille_valeur=24)
        g.fleche(s, X0 + w + 0.05, y + 0.38, 0.5, 0.3, t.pct(t.taux(ga["in_journey"], ga["sessions"]), 0) if ga["sessions"] else None)
        g.tuile(s, X0 + w + 0.6, y, w, h, t["in_journey"], t.nb(ga["in_journey"]), det("in_journey"), taille_valeur=24)
        g.fleche(s, X0 + 2 * w + 0.65, y + 0.38, 0.5, 0.3, t.pct(t.taux(ga["hot_leads"], ga["in_journey"]), 0) if ga["in_journey"] else None)
        g.tuile(s, X0 + 2 * w + 1.2, y, w, h, t["hot_leads"], t.nb(ga["hot_leads"]), det("hot_leads"), taille_valeur=24)
    # CVR global et part du trafic venant du site de la marque (tuiles étroites : pts vs chaque référence, libellés courts)
    court = {"prec": ("vs préc.", "vs prev."), "n1": ("vs N-1", "vs LY")}
    def det_pts(cur, refs):
        out = []
        for cle, v in refs:
            if v is not None and cur is not None:
                out.append(f"{t.pts(cur - v)} {court[cle][0 if ctx.langue == 'fr' else 1]}")
        return "  ".join(out) or None
    if ga is not None and ga["sessions"] >= 100:
        cvr = ga["hot_leads"] / ga["sessions"] * 100
        refs_cvr = []
        for cle, p in ctx.refs:
            u = d.utilisateurs(p, m)
            refs_cvr.append((cle, (u["hot_leads"] / u["sessions"] * 100) if (u and u["sessions"] >= 100) else None))
        g.tuile(s, X0 + 8.95, y, 1.7, h, "CVR", t.pct(cvr, 1), det_pts(cvr, refs_cvr), taille_valeur=22)
    a_site, b_site = d.trafic_site_marque(per, m)
    if b_site >= 100:
        part = a_site / b_site * 100
        refs_site = []
        for cle, p in ctx.refs:
            a2, b2 = d.trafic_site_marque(p, m)
            refs_site.append((cle, (a2 / b2 * 100) if b2 >= 100 else None))
        g.tuile(s, X0 + 10.75, y, 1.7, h, "Via site marque" if ctx.langue == "fr" else "Via brand site", t.pct(part, 0), det_pts(part, refs_site), taille_valeur=22)
    # canaux : anneau + tableau
    canaux = d.canaux(per, m)
    tot = sum(canaux.values())
    ordre = sorted(canaux, key=lambda c: -canaux[c])
    if tot:
        top = ordre[:7]
        reste = sum(canaux[c] for c in ordre[7:])
        cats = top + ([t["autre"]] if reste else [])
        vals = [canaux[c] for c in top] + ([reste] if reste else [])
        g.texte(s, X0, 3.0, 4.6, 0.3, ("Trafic par canal" if ctx.langue == "fr" else "Traffic by channel"), taille=12, gras=True, couleur=g.BLEU)
        g.anneau(s, X0 - 0.1, 3.25, 5.0, 2.4, cats, vals, taille=9)
        ent = [t["canal"], t["sessions_col"]] + [libelle_ref(ctx, c) for c, _ in ctx.refs]
        lignes = [ent]
        for c in ordre[:7]:
            row = [c, t.nb(canaux[c])]
            for _, p in ctx.refs:
                row.append(t.evol(canaux[c], d.canaux(p, m).get(c, 0))[0])
            lignes.append(row)
        lignes.append([t["total"], t.nb(tot)] + [t.evol(tot, sum(d.canaux(p, m).values()))[0] for _, p in ctx.refs])
        nc = len(ent)
        g.tableau(s, 5.5, 3.1, 7.4, lignes, largeurs=[3.0] + [(7.4 - 3.0) / (nc - 1)] * (nc - 1), taille=10, hauteur_ligne=0.25, gras_derniere=True)
        # commentaire calculé sous le tableau
        phrase = [f"{t['sessions']} : {t.nb(tot)} — {ordre[0]} {t.pct(canaux[ordre[0]] / tot * 100, 0)}"
                  + (f", {ordre[1]} {t.pct(canaux[ordre[1]] / tot * 100, 0)}" if len(ordre) > 1 else "")]
        for cle, p in ctx.refs:
            lc = commentaire_evolutions(ctx, ordre[:6], [canaux[c] for c in ordre[:6]], [d.canaux(p, m).get(c, 0) for c in ordre[:6]], f"({ctx.et(p)})", 2)
            phrase += [x for x in lc if isinstance(x, str)][:2]
        if "analyse" not in ctx.modules:
            g.encadre(s, 5.5, 6.0, 7.4, 0.9, None, phrase[:3], taille=10)
    else:
        g.texte(s, X0, 3.2, 12, 0.5, "Aucun trafic mesuré sur cette période." if ctx.langue == "fr" else "No traffic measured over this period.", taille=13, couleur=g.GRIS)
    bandeau(ctx, s, an.s_trafic(ctx, m))
    return s


def leads_marque(ctx, m):
    t, d, per = ctx.t, ctx.d, ctx.per
    periodes = ctx.periodes
    s = nouvelle(ctx, f"{ctx.nom(m)} — {t['leads']} {ctx.et(per)}", ctx.perimetre, source_bo(ctx), notes=note_definitions(ctx), cle=f"marque:{m}")
    series = [(t[pj], [d.leads(p, m)[pj] for p in periodes], g.COULEURS_PROJETS[pj]) for pj in PROJETS]
    g.colonnes(s, X0, Y0, 6.2, 4.2, [ctx.et(p) for p in periodes], series, empile=True, taille=11, fmt=t.nb)
    tots = [d.leads_total(p, m) for p in periodes]
    lignes = [(f"{t['leads']} {ctx.et(per)} : {t.nb(tots[-1])}", True)]
    for (cle, p), tr in zip(ctx.refs, [d.leads_total(p, m) for _, p in ctx.refs]):
        lignes.append(f"{t.evol(tots[-1], tr)[0]} {libelle_ref(ctx, cle)} ({ctx.et(p)} : {t.nb(tr)})")
    c = d.leads(per, m)
    taux = t.taux(c["VN"], tots[-1])
    if taux is not None:
        l2 = f"{t['taux_nc']} : {t.pct(taux, 0)}"
        for cle, p in ctx.refs:
            r = d.leads(p, m); tr = sum(r.values())
            if tr >= 100 and tots[-1] >= 100:
                l2 += f" ({t.pts(taux - t.taux(r['VN'], tr))} {libelle_ref(ctx, cle)})"
        lignes.append(l2)
    g.encadre(s, 7.0, Y0 + 0.1, 5.9, 4.0, None, lignes, taille=12)
    bandeau(ctx, s, an.s_leads_marque(ctx, m))
    return s


def composition_sources(ctx):
    """Phrase qui détaille ce que contient chaque groupe de sources (les valeurs brutes du back-office regroupées)."""
    from .donnees import GROUPES_SOURCES
    parts = [f"{g} = {', '.join(v)}" for g, v in GROUPES_SOURCES.items()]
    tete = "Regroupement des sources (valeurs brutes du back-office) : " if ctx.langue == "fr" else "Source grouping (raw back-office values): "
    autre = " ; autres valeurs → Autre." if ctx.langue == "fr" else "; any other value → Other."
    return tete + " ; ".join(parts) + autre


def sources_marque(ctx, m):
    t, d, per = ctx.t, ctx.d, ctx.per
    periodes = ctx.periodes
    s = nouvelle(ctx, f"{ctx.nom(m)} — {'Sources d\'acquisition' if ctx.langue == 'fr' else 'Acquisition sources'} {ctx.et(per)}", ctx.perimetre,
                 source_bo(ctx), notes=note_definitions(ctx, "Sources d'acquisition : SOURCE_ACQUISITION du back-office regroupée (voir pipeline/deck/donnees.py)."), cle=f"marque:{m}")
    if not ctx.d.acquisition_disponible(periodes[0]):
        g.texte(s, X0, 2.0, 12, 0.6, t["acq_indispo"], taille=14, couleur=g.GRIS)
        return s
    src = [d.sources(p, m) for p in periodes]
    ent1 = [t["source"]]
    for pj in PROJETS:
        ent1 += [f"{t[pj]}\n{ctx.et(p)}" for p in periodes]
    lignes = [ent1]
    tot_pj = [[sum(sp[sg][pj] for sg in ORDRE_SOURCES) for pj in PROJETS] for sp in src]
    tot_src = lambda sp, sg: sum(sp[sg][pj] for pj in PROJETS)
    for sg in ORDRE_SOURCES:
        row = [sg if sg != "Autre" else t["autre"]]
        if sum(src[-1][sg][pj] for pj in PROJETS) + sum(sum(sp[sg][pj] for pj in PROJETS) for sp in src[:-1]) == 0:
            continue
        for k, pj in enumerate(PROJETS):
            for i, sp in enumerate(src):
                v = sp[sg][pj]; ts = tot_src(sp, sg)       # % = part du projet dans les leads de cette source
                row.append(f"{t.nb(v)} ({t.pct(v / ts * 100, 0)})" if ts else "–")
        lignes.append(row)
    row = [t["total"]]
    for k in range(len(PROJETS)):
        for i in range(len(src)):
            row.append(t.nb(tot_pj[i][k]))
    lignes.append(row)
    nc = len(ent1)
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[1.9] + [(12.4 - 1.9) / (nc - 1)] * (nc - 1), taille=9.5, hauteur_ligne=0.34, gras_derniere=True)
    note = ("(%) = part de chaque projet dans les leads de la source. " if ctx.langue == "fr" else "(%) = share of each project in the source's leads. ") + composition_sources(ctx)
    g.texte(s, X0, 6.62, 12.4, 0.5, note, taille=8.5, couleur=g.GRIS, italique=True)
    bandeau(ctx, s, an.s_sources(ctx, m), y=5.35, h=1.2)
    return s


def points_ouverts(ctx):
    for p in ctx.brief.get("pointsOuverts") or []:
        s = nouvelle(ctx, ctx.t["points_ouverts"], p.get("titre") or None)
        if p.get("texte"):
            g.puces(s, X0, Y0, 12.2, 5.0, [l for l in p["texte"].split("\n") if l.strip()], taille=16)


def prochaines_etapes(ctx):
    t = ctx.t
    et = ctx.brief.get("prochainesEtapes") or []
    if not et:
        return None
    s = nouvelle(ctx, t["prochaines_etapes"])
    lignes = [["Item" if ctx.langue == "en" else "Action", t["responsable"], t["statut"], t["echeance"]]]
    for e in et:
        lignes.append([e.get("item", ""), e.get("responsable", ""), t[e.get("statut", "a_faire")], e.get("echeance", "")])
    g.tableau(s, X0, Y0 + 0.1, 12.4, lignes, largeurs=[6.6, 2.4, 1.8, 1.6], taille=12, hauteur_ligne=0.42,
              alignements=[PP_ALIGN.LEFT] * 4)
    return s


def questions(ctx):
    s = nouvelle(ctx, ctx.t["questions"])
    return s


def contacts(ctx):
    s = ctx.prs.slides.add_slide(ctx.lay["1_Title and Content"])
    ctx.n += 1
    s.shapes.title.text = ctx.t["contacts"]
    for ph in list(s.placeholders):
        if ph.placeholder_format.idx == 12:
            ph._element.getparent().remove(ph._element)
    c = ctx.brief.get("contact") or {}
    lignes = [(c.get("nom") or "", {"taille": 26, "gras": True, "couleur": "FFFFFF"}),
              (c.get("fonction") or "", {"taille": 16, "couleur": "FFFFFF"}),
              (c.get("email") or "", {"taille": 16, "couleur": "FFFFFF"})]
    g.texte(s, 1.2, 3.0, 10, 2.5, [l for l in lignes if l[0]], taille=16, couleur="FFFFFF")
    return s


# ------------------------------------------------------------------ analyse / recommandation sur chaque diapositive de résultats
def bandeau(ctx, s, res, y=5.75, h=1.2):
    """Encadrés « Analyse » (bleu) et « Recommandation » (orange) en bas d'une diapositive qui affiche des résultats ; rien si le module est désactivé."""
    if "analyse" not in ctx.modules or not res:
        return
    a, r = res
    fr = ctx.langue == "fr"
    if a:
        g.encadre(s, X0, y, 6.1, h, "Analyse" if fr else "Analysis", a, taille=10.5, couleur=g.BLEU)
    if r:
        g.encadre(s, X0 + 6.3, y, 6.1, h, "Recommandation" if fr else "Recommendation", r, taille=10.5, couleur=g.ORANGE)


# ------------------------------------------------------------------ analyse globale (calculée par règles)
def diapo_analyse(ctx, titre, r):
    """Une diapositive « Analyse » (constats / lectures / recommandations) à partir du résultat des règles (analyse.py)."""
    if not r:
        return None
    fr = ctx.langue == "fr"
    s = nouvelle(ctx, titre, ctx.perimetre, ctx.t["source_bo_ga4"],
                 notes=("Analyse calculée par règles à partir des seuls chiffres de cette présentation ; les causes sont des hypothèses à confirmer. " + note_definitions(ctx)))
    box = s.shapes.add_shape(1, Inches(X0), Inches(1.55), Inches(X1 - X0), Inches(0.75))
    box.fill.solid(); box.fill.fore_color.rgb = g.rgb("1F3F7A"); box.line.fill.background(); box.shadow.inherit = False
    g.texte(s, X0 + 0.2, 1.58, X1 - X0 - 0.4, 0.7, r.get("message") or "", taille=15, gras=True, couleur="FFFFFF", ancre=MSO_ANCHOR.MIDDLE)
    cols = [("Ce que disent les chiffres" if fr else "What the numbers say", r["constats"]),
            ("Lecture et points d'attention" if fr else "Reading and watch points", r["lectures"])]
    x = X0
    for (tit, lignes), w in zip(cols, (6.4, 6.05)):
        if lignes:
            g.encadre(s, x, 2.5, w - 0.25, 4.5, tit, lignes, taille=12)
        x += w
    if r.get("historique") or r.get("recommandations"):
        s2 = nouvelle(ctx, titre + (" (suite)" if fr else " (continued)"), ctx.perimetre, ctx.t["source_bo_ga4"],
                      notes=("Contexte historique : mêmes périodes des années passées (leads BO depuis 2020, GA4 depuis 2022), 12 mois glissants, Search Console, V2. " + note_definitions(ctx)))
        cols2 = [("Contexte et historique" if fr else "Context and history", r.get("historique") or []),
                 ("Recommandations" if fr else "Recommendations", r["recommandations"])]
        x = X0
        for (tit, lignes), w in zip(cols2, (7.0, 5.45)):
            if lignes:
                g.encadre(s2, x, 1.6, w - 0.25, 5.3, tit, lignes, taille=12.5)
            x += w
    return s


# ------------------------------------------------------------------ assemblage
def construit(brief, donnees, sortie, gabarit=GABARIT):
    ctx = Ctx(brief, donnees, gabarit)
    m = ctx.modules
    avoir_global = "global" in m
    avoir_projets = "projets" in m
    avoir_marques = bool(m & {"trafic_marque", "sources", "cta", "conquete"})
    sections = []
    if avoir_global or avoir_projets:
        sections.append(("global", ctx.t["vue_globale"]))
    if avoir_marques:
        sections.append(("marques", ctx.t["detail_marques"]))
    if "points_ouverts" in m and (brief.get("pointsOuverts") or []):
        sections.append(("points", ctx.t["points_ouverts"]))
    if "prochaines_etapes" in m and (brief.get("prochainesEtapes") or []):
        sections.append(("etapes", ctx.t["prochaines_etapes"]))
    if m & {"nps", "utm"}:
        sections.append(("annexes", ctx.t["annexes"]))
    sections.append(("qa", ctx.t["questions"]))

    couverture(ctx)
    sommaire(ctx, sections, sections[0][0])
    if avoir_global:
        synthese(ctx)
        vue_groupes(ctx)
        for cle, ref in ctx.refs:
            leads_par_marque(ctx, cle, ref)
        leads_mensuels(ctx)
        leads_mensuels(ctx, "VN")
        projection_mois(ctx)
        classement_marches(ctx)
        vue_ensemble_table(ctx)
        apercu_marques(ctx)
    if avoir_projets:
        for nom_g, ms in (("xp", GROUPES_MARQUES["XP"]), ("xf", GROUPES_MARQUES["XF"])):
            projets_groupe(ctx, nom_g, ms)
        autres = [x for x in ctx.d.marques if x not in GROUPES_MARQUES["XP"] + GROUPES_MARQUES["XF"]]
        if autres:
            projets_groupe(ctx, "autres", autres)
    if "analyse" in m and (avoir_global or avoir_projets):
        diapo_analyse(ctx, "Analyse — vue d'ensemble" if ctx.langue == "fr" else "Analysis — overview", an.globale(ctx))
    if avoir_marques:
        sommaire(ctx, sections, "marques")
        for marque in ctx.d.marques:
            if ctx.d.leads_total(ctx.per, marque) + sum(ctx.d.canaux(ctx.per, marque).values()) == 0:
                continue
            if "trafic_marque" in m:
                trafic_marque(ctx, marque)
                leads_marque(ctx, marque)
            if "sources" in m:
                sources_marque(ctx, marque)
            if "cta" in m:
                cta_marque(ctx, marque)
            if "conquete" in m and marque not in ("SPOTICAR", "STELLANTIS &YOU"):
                conquete_marque(ctx, marque)
    if "points_ouverts" in m and (brief.get("pointsOuverts") or []):
        sommaire(ctx, sections, "points")
        points_ouverts(ctx)
    if "prochaines_etapes" in m and (brief.get("prochainesEtapes") or []):
        sommaire(ctx, sections, "etapes")
        prochaines_etapes(ctx)
    if m & {"nps", "utm"}:
        sommaire(ctx, sections, "annexes")
        for nom in ("nps", "utm"):
            if nom in m:
                blocs_fixes(ctx, nom)
    sommaire(ctx, sections, "qa")
    questions(ctx)
    contacts(ctx)
    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    ctx.prs.save(str(sortie))
    return ctx
