"""Format « revue mensuelle France » : assemblage du deck (reproduit « Stellantis FR — Trade in review », 73 diapositives) avec les données du mois choisi.

Sélection : brief["format"] == "revue_fr" (construit() délègue ici). Ordre des diapositives = celui du deck de référence :
couverture, Ongoing actions, agenda, résumé exécutif (3), traffic & leads par groupe de marques (2), projection du mois, conversion des ventes NSC,
puis 6 diapositives par marque (séparateur, trafic, YTD, canaux, site principal, conquête & fidélité), annexe (séparateur + captures CTA) et contacts.
Les diapositives de données sont dans revue_global.py / revue_marque.py / revue_canaux.py / revue_conquete.py (fonctions `(ctx, rv, …)` qui renvoient la diapositive ou None).
"""

import importlib

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from . import graphiques as g
from .construit import Ctx, GABARIT
from .revue_commun import GROUPE_XF, GROUPE_XP, MARINE, MARQUES, SECTIONS, Revue, mois_label, pied, slide_revue

NOMS_SEPARATEUR = {"CITROEN": "CITROËN", "DS": "DS AUTOMOBILES"}


def _module(nom):
    try:
        return importlib.import_module(f".{nom}", __package__)
    except ImportError:
        return None


def _ajoute(ctx, f, *args, libelle=""):
    """Appelle un constructeur de diapositive ; une diapositive absente (module non écrit ou données manquantes) donne un avertissement, jamais une erreur."""
    if f is None:
        ctx.avertissements.append(f"Diapositive non disponible : {libelle}.")
        return None
    try:
        s = f(*args)
    except Exception as e:                      # une diapositive en échec n'empêche pas le reste du deck
        ctx.avertissements.append(f"Diapositive en échec ({libelle}) : {type(e).__name__}: {e}")
        return None
    if s is None:
        ctx.avertissements.append(f"Pas de données pour : {libelle}.")
    return s


# ------------------------------------------------------------------ pièces propres au format
def couverture_revue(ctx, rv):
    """Couverture : titre « Trade In Performance », mois, bloc blanc avec logo Stellantis et drapeau."""
    s = ctx.prs.slides.add_slide(ctx.lay["Title Slide"])
    ctx.n += 1
    g.texte(s, 0.62, 2.96, 7.1, 0.79, "Trade In Performance", taille=32, couleur="FFFFFF")
    g.texte(s, 0.62, 3.8, 7.0, 0.7, f"{mois_label(rv.per).split()[0][:3]}. {rv.per.annee}", taille=28, couleur="FFFFFF")
    boite = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7.79), Inches(2.89), Inches(6.35), Inches(2.34))
    boite.fill.solid(); boite.fill.fore_color.rgb = g.rgb("FFFFFF"); boite.line.fill.background(); boite.shadow.inherit = False
    rv._image(s, rv.manifeste.get("couverture_stellantis"))
    rv._drapeau_pays(s, rv.manifeste.get("couverture_drapeau"))
    g.texte(s, 4.4, 7.1, 4.5, 0.3, ctx.t["confidentiel"], taille=9, couleur="FFFFFF", align=PP_ALIGN.CENTER)
    g.texte(s, 0.12, 7.21, 1.8, 0.3, rv.date_deck, taille=9, couleur="FFFFFF")
    return s


def agenda_revue(ctx, rv, actif, sections=None):
    """Sommaire : 5 sections (ou `sections`), la section courante en bleu marine plein (géométrie relevée sur la diapositive 3 du deck de référence)."""
    s = slide_revue(ctx, rv, "Agenda", source=None)
    rv.drapeau(s)
    y = 1.67
    for i, libelle in enumerate(sections or SECTIONS):
        on = i == actif
        b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.45), Inches(y), Inches(10.1), Inches(0.47))
        b.adjustments[0] = 0.12
        b.fill.solid(); b.fill.fore_color.rgb = g.rgb(MARINE if on else "D9E2F3"); b.line.fill.background(); b.shadow.inherit = False
        g.texte(s, 1.6, y + 0.04, 9.8, 0.4, libelle, taille=11, gras=on, couleur="FFFFFF" if on else "1F3864", ancre=MSO_ANCHOR.MIDDLE)
        y += 0.78
    return s


def separateur(ctx, rv, libelle):
    """Séparateur de section : grand rectangle bleu marine arrondi avec le nom en blanc (0,96 / 2,59 / 10,99 x 1,40 po comme dans le deck)."""
    s = ctx.prs.slides.add_slide(ctx.lay["Title and Subtitle"])
    ctx.n += 1
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    rv.drapeau(s, grand=True)
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.96), Inches(2.59), Inches(10.99), Inches(1.40))
    b.fill.solid(); b.fill.fore_color.rgb = g.rgb(MARINE); b.line.fill.background(); b.shadow.inherit = False
    tf = b.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = libelle
    r.font.size = Pt(28); r.font.bold = True; r.font.color.rgb = g.rgb("FFFFFF")
    pied(s, rv, None)
    return s


def actions_en_cours(ctx, rv):
    """« Ongoing actions » : tableau des actions en cours (brief["actionsEnCours"] : sujet, détails, date, pilote, statut = lignes), comme la diapositive 2 du deck."""
    actions = ctx.brief.get("actionsEnCours") or []      # sans action saisie : diapositive vide à compléter
    s = slide_revue(ctx, rv, "Ongoing actions", source=None, x_titre=0.14)
    entetes = ["#", "Subject", "Details", "Date", "Pilot", "Status"]
    largeurs = [0.38, 1.75, 2.57, 0.95, 2.1, 5.12]
    n = len(actions)
    gf = s.shapes.add_table(n + 1, 6, Inches(0.23), Inches(1.26), Inches(sum(largeurs)), Inches(min(5.5, 0.4 + 0.5 * n)))
    tb = gf.table
    for j, w in enumerate(largeurs):
        tb.columns[j].width = Inches(w)

    def cellule(c, lignes, taille=8, gras=False, couleur="000000", fond=None, centre=False, puces=False):
        c.margin_left = c.margin_right = Inches(0.05); c.margin_top = c.margin_bottom = Inches(0.02)
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf = c.text_frame; tf.word_wrap = True
        for i, l in enumerate(lignes if isinstance(lignes, list) else [lignes]):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER if centre else PP_ALIGN.LEFT
            r = p.add_run(); r.text = ("• " if puces else "") + str(l)
            r.font.size = Pt(taille); r.font.bold = gras; r.font.color.rgb = RGBColor.from_string(couleur)
        if fond:
            c.fill.solid(); c.fill.fore_color.rgb = RGBColor.from_string(fond)

    for j, h in enumerate(entetes):
        cellule(tb.cell(0, j), h, taille=10, gras=True, couleur="FFFFFF", fond="002060", centre=True)
    tb.rows[0].height = Inches(0.41)
    for i, a in enumerate(actions, 1):
        fond = "E9EEF7" if i % 2 else "F7F9FC"
        statut = a.get("statut") or []
        statut = statut if isinstance(statut, list) else [statut]
        cellule(tb.cell(i, 0), str(i), gras=True, fond=fond, centre=True)
        cellule(tb.cell(i, 1), a.get("sujet", ""), gras=True, fond=fond, centre=True)
        cellule(tb.cell(i, 2), a.get("details", ""), fond=fond, centre=True)
        cellule(tb.cell(i, 3), a.get("date", ""), fond=fond, centre=True)
        cellule(tb.cell(i, 4), a.get("pilote", ""), fond=fond, centre=True)
        cellule(tb.cell(i, 5), statut, fond=fond, puces=True)
        tb.rows[i].height = Inches(0.45)
    return s


def annexe_cta(ctx, rv):
    """Annexe « Trade-in CTA on main / brand website » : captures des sites avec légendes, reprises à l'identique du deck de référence (éléments statiques)."""
    out = []
    for spec in rv.manifeste.get("annexe") or []:
        titre = spec.get("titre") or ""
        if not titre:                             # titre vide : porté par une zone de texte du haut de la diapositive d'origine -> on la promeut en titre
            haut = [e for e in spec["elements"] if e["type"] == "texte" and e["y"] < 1.0]
            if haut:
                titre = haut[0]["texte"]
                spec = {**spec, "elements": [e for e in spec["elements"] if e is not haut[0]]}
        s = ctx.prs.slides.add_slide(ctx.lay["Title and Subtitle"])
        ctx.n += 1
        s.shapes.title.text = titre
        t = s.shapes.title
        t.left, t.top, t.width, t.height = Inches(0.14), Inches(0.27), Inches(8.0), Inches(0.65)
        for para in t.text_frame.paragraphs:
            for r in para.runs:
                r.font.size = Pt(24)
        for ph in list(s.placeholders):
            if ph.placeholder_format.idx == 12 or (not titre and ph.placeholder_format.idx == 0):
                ph._element.getparent().remove(ph._element)
        rv.drapeau(s)
        for e in spec["elements"]:
            if e["type"] == "image":
                rv._image(s, {"fichier": e["fichier"], "x": e["x"], "y": e["y"], "w": e["w"], "h": e["h"]})
            else:
                g.texte(s, e["x"], e["y"], e["w"], max(e["h"], 0.3), e["texte"], taille=e.get("taille") or 12, gras=e.get("gras", False), couleur="000000", align=PP_ALIGN.CENTER)
        pied(s, rv, None)
        out.append(s)
    return out


def contacts_revue(ctx, rv):
    """Contacts : titre blanc en haut à gauche, carte claire centrée avec avatar orange, nom en gras marine, fonction et e-mail (diapositive 73 du deck)."""
    c = ctx.brief.get("contact") or {}
    s = ctx.prs.slides.add_slide(ctx.lay["1_Title and Content"])
    ctx.n += 1
    s.shapes.title.text = ctx.t["contacts"]
    for ph in list(s.placeholders):
        if ph.placeholder_format.idx == 12:
            ph._element.getparent().remove(ph._element)
    carte = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(5.35), Inches(4.3), Inches(2.65), Inches(1.65))
    carte.fill.solid(); carte.fill.fore_color.rgb = g.rgb("EEF3FB"); carte.line.fill.background(); carte.shadow.inherit = False
    rond = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(6.28), Inches(3.62), Inches(0.8), Inches(0.8))
    rond.fill.solid(); rond.fill.fore_color.rgb = g.rgb("FF5A00"); rond.line.fill.background(); rond.shadow.inherit = False
    tete = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(6.55), Inches(3.78), Inches(0.26), Inches(0.26))
    tete.fill.solid(); tete.fill.fore_color.rgb = g.rgb("FFFFFF"); tete.line.fill.background(); tete.shadow.inherit = False
    corps = s.shapes.add_shape(MSO_SHAPE.ROUND_2_SAME_RECTANGLE, Inches(6.45), Inches(4.07), Inches(0.46), Inches(0.26))
    corps.fill.solid(); corps.fill.fore_color.rgb = g.rgb("FFFFFF"); corps.line.fill.background(); corps.shadow.inherit = False
    g.texte(s, 5.4, 4.5, 2.55, 1.4, [(c.get("nom") or "", {"taille": 11, "gras": True, "couleur": MARINE, "align": PP_ALIGN.CENTER}),
                                     (c.get("fonction") or "", {"taille": 10, "couleur": "333333", "align": PP_ALIGN.CENTER}),
                                     (c.get("email") or "", {"taille": 10, "couleur": "333333", "align": PP_ALIGN.CENTER})], taille=10)
    g.texte(s, 0.12, 7.21, 1.8, 0.3, rv.date_deck, taille=9, couleur="FFFFFF")
    return s


# ------------------------------------------------------------------ assemblage
def construit_revue(brief, donnees, sortie, gabarit=GABARIT):
    from pathlib import Path
    ctx = Ctx(brief, donnees, gabarit)
    rv = Revue(ctx)
    if not rv.manifeste:
        ctx.avertissements.append("Éléments statiques du format absents (data/presentations/assets/revue_fr) : logos de marque, drapeau et annexe CTA non affichés.")
    modules = [m for m in (_module(n) for n in ("revue_global", "revue_resultats", "revue_marque", "revue_canaux", "revue_conquete")) if m]
    d = ctx.d

    def f(_, nom):                              # constructeur de diapositive `nom`, cherché dans les modules du format
        return next((getattr(m, nom) for m in modules if hasattr(m, nom)), None)
    rg = rm = rc = rq = None

    couverture_revue(ctx, rv)
    actions_en_cours(ctx, rv)
    agenda_revue(ctx, rv, 0)
    _ajoute(ctx, f(rg, "resume_executif"), ctx, rv, libelle="résumé exécutif")
    _ajoute(ctx, f(rg, "vue_globale"), ctx, rv, libelle="Executive summary — global view")
    _ajoute(ctx, f(rg, "tendance_leads"), ctx, rv, libelle="Executive summary — lead trend all brands")
    agenda_revue(ctx, rv, 1)
    _ajoute(ctx, f(rg, "trafic_leads_groupe"), ctx, rv, "xP", [m for m in GROUPE_XP if m in d.marques], libelle="traffic and leads xP")
    _ajoute(ctx, f(rg, "trafic_leads_groupe"), ctx, rv, "xF", [m for m in GROUPE_XF if m in d.marques], libelle="traffic and leads xF")
    agenda_revue(ctx, rv, 2)
    _ajoute(ctx, f(rg, "projection_nc"), ctx, rv, libelle="projection du mois")
    agenda_revue(ctx, rv, 3)
    _ajoute(ctx, f(rg, "conversion_ventes_nc"), ctx, rv, libelle="NC sales conversion")
    agenda_revue(ctx, rv, 4)
    for marque in MARQUES:
        if marque not in d.marques or d.leads_total(rv.per, marque) == 0:
            ctx.avertissements.append(f"{marque} : aucun lead sur la période, section non générée.")
            continue
        separateur(ctx, rv, NOMS_SEPARATEUR.get(marque, marque))
        _ajoute(ctx, f(rm, "trafic"), ctx, rv, marque, libelle=f"{marque} — traffic")
        _ajoute(ctx, f(rm, "ytd"), ctx, rv, marque, libelle=f"{marque} — YTD leads trends")
        _ajoute(ctx, f(rc, "canaux"), ctx, rv, marque, libelle=f"{marque} — leads by marketing channel")
        _ajoute(ctx, f(rc, "site_principal"), ctx, rv, marque, libelle=f"{marque} — leads from main website")
        _ajoute(ctx, f(rq, "conquete"), ctx, rv, marque, libelle=f"{marque} — conquest & loyalty")
    contacts_revue(ctx, rv)
    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    ctx.prs.save(str(sortie))
    return ctx
