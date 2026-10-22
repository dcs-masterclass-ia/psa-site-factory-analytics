"""Refonte « éditoriale » des revues mensuelles / trimestrielles : slides blanches et aérées, grands titres, grands chiffres, graphiques matplotlib (moderne_graphiques.py).

Cadre commun (`diapo`) : surtitre, titre, accroche, logo, drapeau, pied de page ; briques : `kpi`, `pastille`, `texte_riche`, `image`.
Le contenu (chiffres, phrases) vient des mêmes calculs que les revues d'origine ; seule la mise en page et le dessin des graphiques changent."""

from pathlib import Path

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from . import moderne_graphiques as mg

AIR = Path(__file__).parent
ENCRE, GRIS, INDIGO, PALE, TRAIT = "0B1020", "7A8099", "2F3DFF", "EEF0FF", "E7E9F1"
NUIT = "070B24"
VN, SANS, VO = "2F3DFF", "FF4D6D", "FFA23A"
POLICE = "Arial"


def rgb(h):
    return RGBColor.from_string(h)


def forme(s, genre, x, y, w, h, fond, rayon=None, contour=None, epaisseur=0.75):
    f = s.shapes.add_shape(genre, Inches(x), Inches(y), Inches(w), Inches(h))
    f.shadow.inherit = False
    if fond is None:
        f.fill.background()
    else:
        f.fill.solid(); f.fill.fore_color.rgb = rgb(fond)
    if contour:
        f.line.color.rgb = rgb(contour); f.line.width = Pt(epaisseur)
    else:
        f.line.fill.background()
    if rayon is not None and genre == MSO_SHAPE.ROUNDED_RECTANGLE:
        f.adjustments[0] = rayon
    return f


def texte(s, x, y, w, h, contenu, taille=12, gras=False, couleur=ENCRE, align=PP_ALIGN.LEFT, ancre=MSO_ANCHOR.TOP, espacement=None, interligne=None):
    """Boîte de texte ; `contenu` = str ou liste de segments [(texte, {gras, couleur})] pour un paragraphe riche."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = ancre
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]; p.alignment = align
    if interligne:
        p.line_spacing = interligne
    segs = [(contenu, {})] if isinstance(contenu, str) else contenu
    for t, o in segs:
        for k, morceau in enumerate(t.split("\n")):
            if k:                                                   # saut de ligne = nouveau paragraphe (alignement fiable dans toutes les versions de PowerPoint)
                p = tf.add_paragraph(); p.alignment = align
                if interligne:
                    p.line_spacing = interligne
            if not morceau:
                continue
            r = p.add_run(); r.text = morceau
            r.font.size = Pt(o.get("taille", taille)); r.font.bold = o.get("gras", gras); r.font.name = POLICE
            r.font.color.rgb = rgb(o.get("couleur", couleur))
            if espacement is not None:
                r._r.get_or_add_rPr().set("spc", str(espacement))
    return tb


def image(s, buf, x, y, w, h=None):
    return s.shapes.add_picture(buf, Inches(x), Inches(y), Inches(w), Inches(h) if h else None)


def epure_gabarit(prs):
    """Retire de la mise en page de données les décors d'origine (trait orange et son point, logo bleu) : le nouveau design pose les siens. Ne touche que cette présentation en mémoire."""
    for lay in prs.slide_layouts:
        if lay.name != "Title and Subtitle":
            continue
        for sh in list(lay.shapes):
            if sh.shape_type in (6, 13):               # groupes décoratifs, images
                sh._element.getparent().remove(sh._element)


def _vide(ctx, sombre=False):
    lay = ctx.lay["Title and Subtitle"]
    s = ctx.prs.slides.add_slide(lay)
    ctx.n += 1
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(NUIT if sombre else "FFFFFF")
    if sombre:
        forme(s, MSO_SHAPE.RECTANGLE, 0, 0, 13.333, 7.5, NUIT)       # fond plein (les décors du gabarit sont déjà retirés)
    return s


def diapo(ctx, rv, surtitre, titre, accroche=None, sombre=False, marque=None):
    """Diapositive de données : surtitre en capitales indigo, grand titre, accroche à droite, logo et drapeau, pied de page discret."""
    s = _vide(ctx, sombre)
    fg = "FFFFFF" if sombre else ENCRE
    texte(s, 0.6, 0.42, 7.0, 0.25, surtitre.upper(), taille=10, gras=True, couleur="8E96FF" if sombre else INDIGO, espacement=160)
    texte(s, 0.6, 0.7, 8.4 if not accroche else 6.6, 0.8, titre, taille=30, gras=True, couleur=fg, interligne=0.95)
    if accroche:
        texte(s, 7.5, 0.52, 3.5, 0.9, accroche, taille=11, couleur="B9BFD8" if sombre else GRIS, interligne=1.15)
    logo = AIR / ("logo_autobiz_blanc.png" if sombre else "logo_autobiz_encre.png")
    s.shapes.add_picture(str(logo), Inches(11.75), Inches(0.42), Inches(1.0), Inches(0.27))
    if getattr(rv, "code_pays", None):
        rv._drapeau_pays(s, {"x": 11.2, "y": 0.44, "w": 0.4, "h": 0.24})
    texte(s, 0.6, 7.08, 8.0, 0.2, f"Trade-in performance  ·  {rv.date_deck}", taille=8.5, couleur="6C7390" if sombre else "A0A5B8")
    texte(s, 12.0, 7.08, 0.75, 0.2, f"{ctx.n:02d}", taille=8.5, couleur="6C7390" if sombre else "A0A5B8", align=PP_ALIGN.RIGHT)
    return s


def pastille(s, x, y, valeur, taille=10):
    """Évolution en pastille : verte si positive, rouge sinon."""
    if valeur is None:
        return
    pos = valeur >= 0
    w = 0.55 + 0.085 * len(f"{valeur:+.0f}%")
    p = forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, 0.26, "E3F6EC" if pos else "FDE7EA", rayon=0.5)
    tf = p.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    para = tf.paragraphs[0]; para.alignment = PP_ALIGN.CENTER
    r = para.add_run(); r.text = f"{'▲' if pos else '▼'} {valeur:+.0f}%"
    r.font.size = Pt(taille - 1); r.font.bold = True; r.font.name = POLICE; r.font.color.rgb = rgb("0F7B45" if pos else "C62839")
    return w


def kpi(s, x, y, valeur, libelle, evol=None, sous=None, w=3.6, couleur=ENCRE, taille=54, clair=False):
    """Grand chiffre, libellé, pastille d'évolution."""
    texte(s, x, y, w, 0.95, valeur, taille=taille, gras=True, couleur=couleur)
    texte(s, x, y + 0.95, w, 0.3, libelle, taille=11.5, couleur="B9BFD8" if clair else GRIS)
    if evol is not None:
        pastille(s, x, y + 1.32, evol)
    if sous:
        texte(s, x + 1.0, y + 1.34, w - 1.0, 0.25, sous, taille=9.5, couleur="B9BFD8" if clair else GRIS, ancre=MSO_ANCHOR.MIDDLE)


def _k(v):
    if v is None:
        return "n/a"
    return f"{v / 1000:.1f}k" if abs(v) >= 1000 else f"{int(round(v))}"


def pct_(v):
    return "n/a" if v is None else f"{v:+.0f}%"


def nb_(v):
    return "\u2013" if v is None else f"{int(round(v)):,}".replace(",", " ")


def grille(s, x, y, largeurs, hauteurs, lignes, hairline=True):
    """Tableau dessiné en formes : lignes = liste de lignes de cellules {t, taille, gras, couleur, fond, align, t2 (2e ligne grise)} ; trait fin sous chaque ligne."""
    yy = y
    for r, (ligne, hh) in enumerate(zip(lignes, hauteurs)):
        xx = x
        for c, (cell, ww) in enumerate(zip(ligne, largeurs)):
            if cell is None:
                xx += ww
                continue
            if cell.get("fond"):
                forme(s, MSO_SHAPE.RECTANGLE, xx, yy, ww, hh, cell["fond"])
            segs = [(cell.get("t", ""), {})]
            if cell.get("t2"):
                segs = [(cell.get("t", "") + "\n", {}), (cell["t2"], {"taille": cell.get("taille2", 7.5), "gras": False, "couleur": GRIS})]
            texte(s, xx + 0.05, yy, ww - 0.1, hh, segs, taille=cell.get("taille", 9.5), gras=cell.get("gras", False), couleur=cell.get("couleur", ENCRE),
                  align=cell.get("align", PP_ALIGN.CENTER), ancre=MSO_ANCHOR.MIDDLE, interligne=0.95)
            xx += ww
        if hairline:
            forme(s, MSO_SHAPE.RECTANGLE, x, yy + hh - 0.004, sum(largeurs), 0.008, TRAIT)
        yy += hh
    return yy


# ============================================================ deck court : mêmes informations que les diapositives d'origine, nouveau design
def deck_court(ctx, rv):
    import calendar
    from . import revue_global as rg
    from . import revue_trim as rt
    from . import revue_canaux as rc
    from .periodes import MOIS_NOMS
    from .revue_commun import MOIS_COURTS, evol, mois_label, nb
    epure_gabarit(ctx.prs)
    f = rg._faits(ctx, rv)
    per, an, n = rv.per, rv.per.annee, rv.per.indice
    d = ctx.d
    mois = [m.capitalize() for m in MOIS_COURTS["en"]]
    ecoules = f["n"]
    ids = ctx.prs.slides._sldIdLst

    # 1. couverture ------------------------------------------------------------------------------------------------
    s = _vide(ctx, True)
    image(s, mg.points_decor(6, 6), 7.4, 0.55, 6.2, 6.2)
    s.shapes.add_picture(str(AIR / "logo_autobiz_blanc.png"), Inches(0.6), Inches(0.55), Inches(1.5), Inches(0.405))
    texte(s, 0.6, 2.3, 7.5, 0.4, "STELLANTIS  \u00b7  TRADE-IN WEBSITES", taille=12, gras=True, couleur="8E96FF", espacement=200)
    texte(s, 0.6, 2.8, 8.0, 2.4, "Trade-in\nperformance", taille=66, gras=True, couleur="FFFFFF", interligne=0.92)
    forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 5.35, 2.5, 0.52, None, rayon=0.5, contour="4E5BFF", epaisseur=1.25)
    texte(s, 0.6, 5.35, 2.5, 0.52, mois_label(per), taille=15, gras=True, couleur="FFFFFF", align=PP_ALIGN.CENTER, ancre=MSO_ANCHOR.MIDDLE)
    rv._drapeau_pays(s, {"x": 3.3, "y": 5.43, "w": 0.55, "h": 0.36})
    forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, 9.0, 5.65, 3.6, 1.2, "FFFFFF", rayon=0.15)
    rv._image(s, {**(rv.manifeste.get("couverture_stellantis") or {}), "x": 9.2, "y": 5.78, "w": 3.2, "h": 0.94} if rv.manifeste.get("couverture_stellantis") else None)
    texte(s, 0.6, 6.95, 6.0, 0.25, f"{ctx.t['confidentiel']}  \u00b7  {rv.date_deck}", taille=9, couleur="6C7390")

    # 2. agenda (mêmes sections que le deck) ------------------------------------------------------------------------------
    from .revue_fr import SECTIONS_FR
    s = diapo(ctx, rv, "Contents", "Agenda", "What this review covers.")
    pas = min(0.95, 5.0 / len(SECTIONS_FR))
    for i, it in enumerate(SECTIONS_FR):
        y = 1.7 + i * pas
        forme(s, MSO_SHAPE.RECTANGLE, 0.6, y + pas - 0.12, 12.15, 0.01, TRAIT)
        texte(s, 0.6, y, 1.2, pas - 0.15, f"{i + 1:02d}", taille=30, gras=True, couleur=INDIGO if i == 0 else "C9CEFF", ancre=MSO_ANCHOR.MIDDLE)
        texte(s, 2.0, y, 8.0, pas - 0.15, it.capitalize(), taille=22, gras=(i == 0), couleur=ENCRE if i == 0 else "5B6280", ancre=MSO_ANCHOR.MIDDLE)

    # 3. résumé exécutif : les 5 constats + chiffres clés ---------------------------------------------------------------------------
    s = diapo(ctx, rv, mois_label(per), "Executive Summary", "Leads generated by the trade-in sites, all brands of the perimeter.")
    kpi(s, 0.6, 1.75, rg._k(f["mois"]), f"Total leads \u00b7 {mois_label(per)}", f["e_mois_n1"], "YoY", w=3.7)
    kpi(s, 4.75, 1.75, rg._k(f["vn_mois"]), "New cars leads", f["e_vn_n1"], "YoY", w=3.7, couleur=INDIGO)
    kpi(s, 8.9, 1.75, rg._k(f["ytd"]), f"Year to date \u00b7 {an}", f["e_ytd"], f"vs {an - 1}", w=3.7)
    forme(s, MSO_SHAPE.RECTANGLE, 0.6, 3.62, 12.15, 0.012, TRAIT)
    texte(s, 0.6, 3.78, 5.0, 0.25, "TOTAL LEADS PER MONTH", taille=9, gras=True, couleur=GRIS, espacement=140)
    image(s, mg.courbes(6.4, 2.85, mois, f["old_m"], f["cur_m"], ecoules, str(an - 1), str(an)), 0.45, 4.05, 6.4, 2.85)
    y = 3.8
    for runs in rg._puces_resume(ctx, rv, f):
        forme(s, MSO_SHAPE.OVAL, 7.35, y + 0.07, 0.1, 0.1, INDIGO)
        segs = [(t, {"gras": g_, "couleur": ENCRE if g_ else GRIS}) for t, g_ in runs if t]
        texte(s, 7.6, y, 5.15, 0.6, segs, taille=10, interligne=1.05)
        y += 0.2 + 0.17 * (1 + sum(len(t) for t, _ in segs) // 78)

    # 4. vue globale : TOUTES les informations de la diapositive d'origine ------------------------------------------------------------
    ytd_m = rg._ytd_marques(ctx, rv)
    s = diapo(ctx, rv, "Global overview", "Global Overview", f"Exec summary \u2013 trade-in situation {mois_label(per)}.")
    mois_maj = MOIS_COURTS["en"][per.indice - 1].upper()
    cartes = [("REPORTING MONTHLY", f"Total generated leads {mois_maj}. {an}", f["mois"], "Evolution vs last month", f["e_mois_prec"]),
              ("REPORTING YTD", f"Total generated leads {an}", f["ytd"], f"Evolution vs last year ({an - 1} and {an})", f["e_ytd"])]
    for i, (t1, t2, val, t3, ev) in enumerate(cartes):
        x = 0.6 + i * 2.2
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 1.6, 2.05, 2.7, PALE, rayon=0.07)
        texte(s, x + 0.2, 1.75, 1.7, 0.25, t1, taille=8, gras=True, couleur=INDIGO, espacement=100)
        texte(s, x + 0.2, 2.05, 1.7, 0.45, t2, taille=9, couleur=GRIS, interligne=1.0)
        texte(s, x + 0.2, 2.65, 1.7, 0.6, nb_(val), taille=30, gras=True)
        texte(s, x + 0.2, 3.4, 1.7, 0.45, t3, taille=8.5, couleur=GRIS, interligne=1.0)
        pastille(s, x + 0.2, 3.85, ev)
    texte(s, 5.1, 1.62, 7.6, 0.25, f"GENERATED LEADS YTD {mois_label(per).upper()}: SPLIT BY BRAND", taille=9, gras=True, couleur=GRIS, espacement=120)
    tot = f["ytd"] or 1
    lignes_m = [("S&Y" if m == "STELLANTIS &YOU" else ctx.nom(m), a, a / tot * 100, b) for m, a, b in ytd_m]
    image(s, mg.barres_marques(7.6, 2.5, lignes_m, taille=8.8 if len(lignes_m) > 8 else 10.5), 5.0, 1.85, 7.6, 2.5)
    texte(s, 0.6, 4.5, 1.2, 0.25, "TREND YTD", taille=9, gras=True, couleur=GRIS, espacement=140)
    gl = rg._mois_glissants(per)
    cache = {}

    def serie(projet):
        out = []
        for a_, m0 in gl:
            if a_ not in cache:
                cache[a_] = {p_: d.leads_mensuels(a_, projet=p_) for p_ in ("VN", "SANS", "VO")}
            out.append(cache[a_][projet][m0])
        return out
    cats = [f"{MOIS_COURTS['en'][m0].capitalize()} {str(a_)[2:]}" for a_, m0 in gl]
    image(s, mg.courbes_projets(8.9, 2.3, cats, [("New cars & Demo cars", serie("VN"), VN), ("Trade-in only", serie("SANS"), SANS), ("Used cars", serie("VO"), VO)]), 0.45, 4.75, 8.9, 2.3)
    for i, (nom, col) in enumerate((("New cars & Demo cars", VN), ("Trade-in only", SANS), ("Used cars", VO))):
        forme(s, MSO_SHAPE.OVAL, 2.1 + i * 2.1, 4.55, 0.12, 0.12, col)
        texte(s, 2.3 + i * 2.1, 4.5, 1.9, 0.22, nom, taille=8.5, couleur=ENCRE)
    y = 4.7
    for t in rg._puces_global(ctx, rv, f, ytd_m):
        forme(s, MSO_SHAPE.OVAL, 9.7, y + 0.07, 0.1, 0.1, INDIGO)
        texte(s, 9.95, y, 2.8, 0.7, t, taille=9, interligne=1.05)
        y += 0.78

    # 5. tendance des leads : barres avec toutes les valeurs + les 3 commentaires exacts ----------------------------------------------------
    s = diapo(ctx, rv, "Executive summary", "Executive Summary", "Lead trend \u2013 all brands.")
    texte(s, 0.6, 1.45, 6.0, 0.28, [("Total leads year trend", {"gras": True, "taille": 12})], taille=12)
    image(s, mg.barres_annuelles(12.2, 2.05, mois, f["old_m"], f["cur_m"], ecoules, INDIGO, (str(an - 1), str(an)), valeurs=True, taille_val=7), 0.45, 1.68, 12.3, 2.05)
    texte(s, 0.6, 3.78, 6.0, 0.28, [("NC leads year trend", {"gras": True, "taille": 12})], taille=12)
    image(s, mg.barres_annuelles(12.2, 2.05, mois, f["old_vn"], f["cur_vn"], ecoules, "#00A3FF", (str(an - 1), str(an)), valeurs=True, taille_val=7), 0.45, 4.01, 12.3, 2.05)
    for i, t in enumerate(rg._puces_tendance(ctx, rv, f)):
        x = 0.6 + i * 4.1
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 6.28, 3.95, 0.68, PALE, rayon=0.1)
        texte(s, x + 0.15, 6.28, 3.7, 0.68, t, taille=8.2, ancre=MSO_ANCHOR.MIDDLE, interligne=1.0)

    # 6. leads par projet d'achat, par marque (xP) : comme la diapositive d'origine ---------------------------------------------------
    marques = [m for m in rt.GROUPE_XP + ["SPOTICAR"] if m in d.marques and any(rt._L(d, p, m) for p in (per, rv.n1))]
    if marques:
        pers = [rv.prec.n1(), rv.n1, rv.prec, per]
        pj = lambda p, m=None: {k: sum(d.leads(p, mm)[k] for mm in ([m] if m else marques)) for k in rt.PROJETS}
        s = diapo(ctx, rv, "Sales performance", f"Leads by Purchase Project", f"{mois_label(per)} for xP, by brand and period.")
        cats, vals = [], {k: [] for k in ("VN", "SANS", "VO")}
        for m in marques:
            for p in pers:
                cats.append(rt._q(p))
                t = pj(p, m)
                for k in vals:
                    vals[k].append(t[k])
        ser = [("Used cars", vals["VO"], VO), ("Trade-in only", vals["SANS"], SANS), ("New cars & Demo.", vals["VN"], VN)]
        grp = [(ctx.nom(m).upper(), 4 * i, 4) for i, m in enumerate(marques)]
        sur = [4 * i + k for i in range(len(marques)) for k in (2, 3)]
        image(s, mg.colonnes_empilees(8.9, 4.7, cats, ser, groupes=grp, surligne=sur, taille=7), 0.4, 1.55, 8.9, 4.7)
        t1, t2 = pj(rv.n1), pj(per)
        ser2 = [("Used cars", [t1["VO"], t2["VO"]], VO), ("Trade-in only", [t1["SANS"], t2["SANS"]], SANS), ("New cars & Demo.", [t1["VN"], t2["VN"]], VN)]
        texte(s, 9.7, 1.55, 3.0, 0.25, "TOTAL PURCHASE xP", taille=9, gras=True, couleur=GRIS, espacement=120)
        image(s, mg.colonnes_empilees(3.1, 4.4, [rt._q(rv.n1), rt._q(per)], ser2, surligne=[1], taille=8), 9.65, 1.85, 3.1, 4.4)
        for i, (nom, col) in enumerate((("New cars & Demo.", VN), ("Trade-in only", SANS), ("Used cars", VO))):
            forme(s, MSO_SHAPE.OVAL, 9.8, 6.33 + i * 0.22, 0.1, 0.1, col)
            texte(s, 9.98, 6.27 + i * 0.22, 2.6, 0.22, nom, taille=8, couleur=GRIS)
        sh = lambda p, m=None: (lambda t: t["VN"] / sum(t.values()) * 100 if sum(t.values()) else None)(pj(p, m))
        a_, b_ = sh(per), sh(rv.n1)
        txt = []
        if a_ is not None and b_ is not None:
            txt.append(f"NC share {'up' if a_ >= b_ else 'down'} {abs(a_ - b_):.0f}pt YoY for xP ({a_:.0f}%)")
        dm = []
        for m in marques:
            am, bm = sh(per, m), sh(rv.n1, m)
            if am is not None and bm is not None and rt._L(d, rv.n1, m) >= 50:
                dm.append((ctx.nom(m), am - bm, am))
        ups = [f"{n_} +{dd:.0f}pt ({am:.0f}%)" for n_, dd, am in sorted(dm, key=lambda x: -x[1]) if dd >= 3][:4]
        dws = [f"{n_} {dd:.0f}pt ({am:.0f}%)" for n_, dd, am in sorted(dm, key=lambda x: x[1]) if dd <= -3][:3]
        if ups:
            txt.append("Increase: " + ", ".join(ups))
        if dws:
            txt.append("Decrease: " + ", ".join(dws))
        if txt:
            forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 6.42, 8.7, 0.55, PALE, rayon=0.12)
            texte(s, 0.8, 6.42, 8.4, 0.55, " \u00b7 ".join(txt), taille=9.5, ancre=MSO_ANCHOR.MIDDLE)

    # 7. projets d'achat du mois (diapo de synthèse en plus) ------------------------------------------------------------------------------
    L, L1 = d.leads(per), d.leads(rv.n1)
    tt, t1_ = sum(L.values()) or 1, sum(L1.values()) or 1
    s = diapo(ctx, rv, "Purchase projects", "Leads by purchase project", f"{mois_label(per)} against the same month of {an - 1}.", sombre=True)
    for i, (nom, col, k) in enumerate((("New cars & demo cars", VN, "VN"), ("Trade-in only", SANS, "SANS"), ("Used cars", VO, "VO"))):
        x = 0.6 + i * 4.1
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 1.9, 3.85, 4.5, "10173F", rayon=0.06, contour="1E2760")
        forme(s, MSO_SHAPE.RECTANGLE, x + 0.35, 2.25, 0.5, 0.07, col)
        texte(s, x + 0.35, 2.45, 3.2, 0.3, nom, taille=13, gras=True, couleur="FFFFFF")
        texte(s, x + 0.35, 3.0, 3.3, 1.0, nb_(L[k]), taille=56, gras=True, couleur="FFFFFF")
        texte(s, x + 0.35, 4.05, 3.2, 0.3, f"leads in {mois_label(per)}  \u00b7  {nb_(L1[k])} in {an - 1}", taille=10.5, couleur="B9BFD8")
        pastille(s, x + 0.35, 4.5, evol(L[k], L1[k]))
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x + 0.35, 5.35, 3.15, 0.12, "1E2760", rayon=0.5)
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x + 0.35, 5.35, max(0.12, 3.15 * L[k] / tt), 0.12, col, rayon=0.5)
        texte(s, x + 0.35, 5.6, 3.2, 0.3, f"{L[k] / tt * 100:.0f}% of leads  \u00b7  {L1[k] / t1_ * 100:.0f}% in {an - 1}", taille=10, couleur="B9BFD8")

    # 8. séparateur -------------------------------------------------------------------------------------------------------------------
    s = _vide(ctx, True)
    image(s, mg.points_decor(5, 5), 8.0, 1.2, 5.0, 5.0)
    texte(s, 0.8, 1.2, 6.0, 2.5, f"{min(4, len(SECTIONS_FR)):02d}", taille=150, gras=True, couleur="1B2260")
    forme(s, MSO_SHAPE.RECTANGLE, 0.9, 3.95, 1.2, 0.08, "FF5A00")
    texte(s, 0.85, 4.2, 9.0, 1.4, "Performance\nby brand", taille=54, gras=True, couleur="FFFFFF", interligne=0.92)
    texte(s, 0.6, 7.08, 8.0, 0.2, f"Trade-in performance  \u00b7  {rv.date_deck}", taille=8.5, couleur="6C7390")
    texte(s, 12.0, 7.08, 0.75, 0.2, f"{ctx.n:02d}", taille=8.5, couleur="6C7390", align=PP_ALIGN.RIGHT)

    # 9. « Leads by marketing channel » de la première marque : matrice complète, colonnes empilées, commentaires ----------------------------------
    m0 = ytd_m[0][0] if ytd_m else None
    per_list = [rv.prec.n1(), rv.n1, rv.prec, per]
    data = [rc._sources(ctx, p, m0) for p in per_list] if m0 else []
    if m0 and any(x is not None for x in data):
        vide = {g_: {p_: 0 for p_ in rc.PROJETS} for g_ in rc.ORDRE_SOURCES}
        data = [x if x is not None else vide for x in data]
        tp = [{p_: sum(x[sg][p_] for sg in x) for p_ in rc.PROJETS} for x in data]
        srcs = [sg for sg in rc.ORDRE_SOURCES if sg in data[0] and any(sum(x[sg].values()) for x in data)]
        s = diapo(ctx, rv, f"{ctx.nom(m0)}  \u00b7  Lead deep dive", "Leads by marketing channel", mois_label(per), marque=None)
        lw = [1.15] + [0.62] * 12
        x0, y0 = 0.5, 1.6
        coul = {"VN": VN, "SANS": SANS, "VO": VO}
        noms_p = {"VN": "New cars & Demo cars", "SANS": "Trade-in only", "VO": "Used cars"}
        tete = [None] + [None] * 12
        tete = [{"t": "SOURCE", "taille": 7.5, "gras": True, "couleur": GRIS, "align": PP_ALIGN.LEFT}]
        for pj_ in rc.PROJETS:
            tete += [{"t": noms_p[pj_] if k == 0 else "", "taille": 8.5, "gras": True, "couleur": coul[pj_], "align": PP_ALIGN.LEFT} for k in range(1)] + [None] * 3
        # en-têtes : projet puis période
        yh = y0
        for j, pj_ in enumerate(rc.PROJETS):
            forme(s, MSO_SHAPE.RECTANGLE, x0 + lw[0] + j * 4 * 0.62 + 0.05, yh + 0.02, 4 * 0.62 - 0.1, 0.05, coul[pj_])
            texte(s, x0 + lw[0] + j * 4 * 0.62 + 0.05, yh + 0.1, 4 * 0.62 - 0.1, 0.25, noms_p[pj_], taille=9, gras=True, couleur=ENCRE)
        for j in range(12):
            texte(s, x0 + lw[0] + j * 0.62, yh + 0.38, 0.62, 0.22, rc._mois_court(per_list[j % 4]) + f" {str(per_list[j % 4].annee)[2:]}", taille=7, couleur=GRIS, align=PP_ALIGN.CENTER)
        lignes_g, hs = [], []
        for sg in srcs + ["Total"]:
            tot_ligne = sg == "Total"
            row = [{"t": "Total" if tot_ligne else rc.NOM_SOURCE.get(sg, sg), "taille": 9, "gras": tot_ligne, "align": PP_ALIGN.LEFT, "fond": "F4F5FB" if tot_ligne else None}]
            for pj_ in rc.PROJETS:
                for k in range(4):
                    v = tp[k][pj_] if tot_ligne else data[k][sg][pj_]
                    tt_ = tp[k][pj_] or 1
                    row.append({"t": nb_(v) if v else "\u2013", "t2": f"{v / tt_ * 100:.0f}%" if v else None, "taille": 9, "gras": tot_ligne, "couleur": ENCRE if v else "B4B9CC",
                                "fond": ("EDEFFF" if k >= 2 else None) if not tot_ligne else ("E3E6FF" if k >= 2 else "F4F5FB")})
            lignes_g.append(row); hs.append(0.5)
        grille(s, x0, y0 + 0.68, lw, hs, lignes_g)
        cats = [f"{rc._mois_court(p)} {str(p.annee)[2:]}" for p in per_list]
        ser = [("Used cars", [t["VO"] for t in tp], VO), ("Trade-in only", [t["SANS"] for t in tp], SANS), ("New cars & Demo.", [t["VN"] for t in tp], VN)]
        image(s, mg.colonnes_empilees(3.0, 2.7, cats, ser, surligne=[2, 3], taille=7), 9.75, 1.55, 3.0, 2.7)
        y = 4.4
        for t in rc._puces_canaux(data, tp, srcs, rv):
            forme(s, MSO_SHAPE.OVAL, 9.8, y + 0.06, 0.09, 0.09, INDIGO)
            texte(s, 10.0, y, 2.75, 0.5, t, taille=8.5, interligne=1.0)
            y += 0.5 + 0.14 * (len(t) // 40)

    # 10. NC Sales Conversion : le tableau complet (10 colonnes) ------------------------------------------------------------------------------------
    from . import revue_resultats as rr
    infos = {}
    ordre = [("xP", ["PEUGEOT", "CITROEN", "DS", "OPEL"]), ("Xf", ["FIAT", "JEEP", "ALFA ROMEO", "ABARTH", "FIAT PRO", "LANCIA"])]
    a1 = an - 1
    for _, ms in ordre:
        for m in ms:
            if m not in d.marques:
                continue
            c26, c25 = d.c1st(rr._Cumul(an, n), m), d.c1st(rr._Cumul(a1, n), m)
            e26, e25 = d.leads_envoyes_mensuels(an, m, "VN"), d.leads_envoyes_mensuels(a1, m, "VN")
            l26 = c26["leads"] if c26 else sum((e26 if e26 is not None else d.leads_mensuels(an, m, "VN"))[:n])
            l25 = c25["leads"] if c25 else sum((e25 if e25 is not None else d.leads_mensuels(a1, m, "VN"))[:n])
            u26, u25 = d.c1st_clients_cumul(rr._Cumul(an, n), m), d.c1st_clients_cumul(rr._Cumul(a1, n), m)
            if u26 is not None and u25 is not None:
                l26, l25 = u26, u25
            infos[m] = (l26, l25, d.c1st_nsc(rr._Cumul(an, n), m), d.c1st_nsc(rr._Cumul(a1, n), m))
    if infos:
        def agrege(ms):
            v = [infos[m] for m in ms if m in infos]
            if not v:
                return None
            ok = all(x[2] is not None and x[3] is not None for x in v)
            return (sum(x[0] for x in v), sum(x[1] for x in v), sum(x[2] for x in v) if ok else None, sum(x[3] for x in v) if ok else None)
        groupes = {nom: agrege(ms) for nom, ms in ordre}
        tous = agrege([m for _, ms in ordre for m in ms])
        tx = lambda o, l_: o / l_ * 100 if (o is not None and l_) else None
        jours_fin = calendar.monthrange(an, n)[1]
        s = diapo(ctx, rv, "Sales performance", "NC Sales Conversion", f"Leads from Jan. to {MOIS_NOMS['en'][n - 1].capitalize()} {jours_fin}th. {str(an)[2:]} incl.")
        if tous and tous[2] is not None:
            kpi(s, 0.6, 1.3, nb_(tous[2]), f"NSC orders {an}", evol(tous[2], tous[3]), f"vs {nb_(tous[3])} in {a1}", w=3.6, taille=38, couleur=INDIGO)
            kpi(s, 4.6, 1.3, nb_(tous[0]), f"Leads generated {an}", evol(tous[0], tous[1]), f"vs {nb_(tous[1])} in {a1}", w=3.6, taille=38)
            c26_, c25_ = tx(tous[2], tous[0]), tx(tous[3], tous[1])
            kpi(s, 8.6, 1.3, f"{c26_:.1f}%" if c26_ is not None else "n/a", f"% NSC orders {an}", None, None, w=3.6, taille=38)
            if c26_ is not None and c25_ is not None:
                texte(s, 8.6, 2.62, 4.0, 0.3, f"{c26_ - c25_:+.1f} pt vs {c25_:.1f}% in {a1}", taille=10.5, couleur="0F7B45" if c26_ >= c25_ else "C62839", gras=True)
        entete = ["", f"# Leads\n{an}", f"# Leads\n{a1}", "\u0394 Leads", f"% NSC\n{an}", f"% NSC\n{a1}", "\u0394 %", f"# NSC\n{an}", f"# NSC\n{a1}", "\u0394 # NSC"]
        lw2 = [1.9, 1.15, 1.15, 1.1, 1.1, 1.1, 1.0, 1.1, 1.1, 1.1]
        rows = [[{"t": h, "taille": 8.5, "gras": True, "couleur": GRIS, "align": PP_ALIGN.LEFT if i == 0 else PP_ALIGN.RIGHT} for i, h in enumerate(entete)]]
        hs = [0.42]

        def ligne(nom, v, sous=False):
            l26, l25, o26, o25 = v
            el = evol(l26, l25)
            t26, t25 = tx(o26, l26), tx(o25, l25)
            dt = t26 - t25 if t26 is not None and t25 is not None else None
            do = o26 - o25 if o26 is not None and o25 is not None else None
            fd = "F4F5FB" if sous else None
            cell = lambda t, **k: dict({"t": t, "taille": 9.5, "gras": sous, "fond": fd, "align": PP_ALIGN.RIGHT}, **k)
            pc = lambda x: f"{x:.1f}%" if x is not None else "n/a"
            sg = lambda x, t: cell(t, couleur="0F7B45" if (x or 0) >= 0 else "C62839", gras=True)
            return [cell(nom, align=PP_ALIGN.LEFT, gras=True), cell(nb_(l26)), cell(nb_(l25)), sg(el, f"{el:+.0f}%" if el is not None else "n/a"), cell(pc(t26), couleur=INDIGO, gras=True), cell(pc(t25)),
                    sg(dt, f"{dt:+.1f} pt" if dt is not None else "n/a"), cell(nb_(o26), couleur=INDIGO, gras=True), cell(nb_(o25)), sg(do, f"{do:+,}".replace(",", " ") if do is not None else "n/a")]
        for nom, ms in ordre:
            for m in ms:
                if m in infos:
                    rows.append(ligne(ctx.nom(m), infos[m])); hs.append(0.27)
            if groupes[nom]:
                rows.append(ligne(nom, groupes[nom], True)); hs.append(0.3)
        if tous:
            rows.append(ligne("Total " + "/".join(rv.pays), tous, True)); hs.append(0.32)
        grille(s, 0.6, 2.95, lw2, hs, rows)
    return s
