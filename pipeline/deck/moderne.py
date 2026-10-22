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


def image(s, buf, x, y, w, h=None, alt=None):
    """Image de graphique ; `alt` = texte alternatif listant les valeurs tracées (lecteurs d'écran, et contrôle « aucun chiffre perdu » de parite.py)."""
    pic = s.shapes.add_picture(buf, Inches(x), Inches(y), Inches(w), Inches(h) if h else None)
    if alt:
        pic._element.nvPicPr.cNvPr.set("descr", alt[:3000])
    return pic


def alt(titre, **series):
    """Texte alternatif : « titre. nom : v1 ; v2 ; … | nom2 : … » (valeurs arrondies à l'unité)."""
    def f(v):
        return "–" if v is None else (str(int(round(v))) if abs(v) >= 10 or float(v).is_integer() else f"{v:.1f}")
    return titre + ". " + " | ".join(f"{k.replace('_', ' ')} : " + " ; ".join(f(v) for v in vals) for k, vals in series.items())


def _vide(ctx, sombre=False):
    """Diapositive vierge : un rectangle plein cadre recouvre les décors du gabarit (trait orange, logo bleu), qui restent intacts pour les diapositives V1 du même deck."""
    lay = ctx.lay["Title and Subtitle"]
    s = ctx.prs.slides.add_slide(lay)
    ctx.n += 1
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(NUIT if sombre else "FFFFFF")
    forme(s, MSO_SHAPE.RECTANGLE, -0.05, -0.05, 13.5, 7.65, NUIT if sombre else "FFFFFF").name = "Fond V2"
    if not hasattr(ctx, "v2_slides"):
        ctx.v2_slides, ctx.v2_sections = set(), {}
    ctx.v2_slides.add(s.slide_id)
    return s


CONSERVE = {"NC": "NC", "YTD": "YTD", "C1ST": "C1ST", "VN": "VN", "VO": "VO", "V1": "V1", "V2": "V2", "QOQ": "QoQ", "YOY": "YoY", "MOM": "MoM", "GA": "GA", "S&Y": "S&Y", "STLA": "STLA",
            "XP": "xP", "XF": "xF", "CTA": "CTA", "SEA": "SEA", "UK": "UK", "NSC": "NSC", "CRM": "CRM", "SEO": "SEO", "Q/A": "Q/A", "AUTOBIZ": "autobiz", "OEM": "OEM", "DKAM": "DKAM"}
PROPRES_TITRES = {"SPAIN": "Spain", "FRANCE": "France", "ITALY": "Italy", "PORTUGAL": "Portugal", "POLAND": "Poland", "GERMANY": "Germany", "AUSTRIA": "Austria", "BELUX": "Belux",
                  "BELGIUM": "Belgium", "JANUARY": "January", "FEBRUARY": "February", "MARCH": "March", "APRIL": "April", "JUNE": "June", "JULY": "July", "AUGUST": "August",
                  "SEPTEMBER": "September", "OCTOBER": "October", "NOVEMBER": "November", "DECEMBER": "December", "PEUGEOT": "Peugeot", "CITROËN": "Citroën", "CITROEN": "Citroën",
                  "OPEL": "Opel", "FIAT": "Fiat", "JEEP": "Jeep", "SPOTICAR": "Spoticar", "ABARTH": "Abarth", "LANCIA": "Lancia", "LEAPMOTOR": "Leapmotor", "STELLANTIS": "Stellantis"}


def phrase(t):
    """Titre en minuscules avec majuscule à la première lettre ; sigles (NC, YTD, C1ST, V2…), marques, pays, mois et périodes (Q3-2026) conservés."""
    import re
    def mot(m, premier):
        w = m.group(0)
        up = w.upper()
        if up in CONSERVE:
            return CONSERVE[up]
        if up in PROPRES_TITRES:
            return PROPRES_TITRES[up]
        if re.fullmatch(r"Q[1-4](-\d{4})?", up) or any(c.isdigit() for c in w):
            return up if up.startswith("Q") else w
        w = w.lower()
        return w[:1].upper() + w[1:] if premier else w
    out, premier = [], True
    pos = 0
    for m in re.finditer(r"[\w&/\u00c0-\u017f]+", t):
        out.append(t[pos:m.start()])
        out.append(mot(m, premier))
        premier = False
        pos = m.end()
    out.append(t[pos:])
    return "".join(out)


def diapo(ctx, rv, surtitre, titre, accroche=None, sombre=False, marque=None):
    """Diapositive de données : surtitre en capitales indigo, grand titre, accroche à droite, logo et drapeau, pied de page discret."""
    s = _vide(ctx, sombre)
    titre = phrase(titre)
    fg = "FFFFFF" if sombre else ENCRE
    texte(s, 0.6, 0.42, 7.0, 0.25, surtitre.upper(), taille=10, gras=True, couleur="8E96FF" if sombre else INDIGO, espacement=160)
    n_t = len(titre)
    texte(s, 0.6, 0.7, 8.4 if not accroche else 6.8, 0.8, titre, taille=30 if n_t <= 24 else 26 if n_t <= 30 else 22 if n_t <= 38 else 18 if n_t <= 52 else 15, gras=True, couleur=fg, interligne=0.95)
    if accroche:
        texte(s, 7.5, 0.52, 3.5, 0.9, accroche, taille=11, couleur="B9BFD8" if sombre else GRIS, interligne=1.15)
    logo = AIR / ("logo_autobiz_blanc.png" if sombre else "logo_autobiz_encre.png")
    s.shapes.add_picture(str(logo), Inches(11.75), Inches(0.42), Inches(1.0), Inches(0.27))
    if getattr(rv, "code_pays", None):
        rv._drapeau_pays(s, {"x": 11.2, "y": 0.44, "w": 0.4, "h": 0.24})
    texte(s, 0.6, 7.08, 8.0, 0.2, f"Trade-in performance  ·  {rv.date_deck}", taille=8.5, couleur="6C7390" if sombre else "A0A5B8")
    texte(s, 12.0, 7.08, 0.75, 0.2, f"{ctx.n:02d}", taille=8.5, couleur="6C7390" if sombre else "A0A5B8", align=PP_ALIGN.RIGHT)
    return s


def pastille(s, x, y, valeur, taille=10, dec=0, base=0.55):
    """Évolution en pastille : verte si positive, rouge sinon."""
    if valeur is None:
        return
    pos = valeur >= 0
    w = base + 0.085 * len(f"{valeur:+.{dec}f}%")
    p = forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, 0.26, "E3F6EC" if pos else "FDE7EA", rayon=0.5)
    tf = p.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    para = tf.paragraphs[0]; para.alignment = PP_ALIGN.CENTER
    r = para.add_run(); r.text = f"{'▲' if pos else '▼'} {valeur:+.{dec}f}%"
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


# ============================================================ constructeurs de diapositive du design V2 (mêmes signatures que ceux du design V1)
def couverture(ctx, rv):
    """Couverture (revue mensuelle et trimestrielle)."""
    from .revue_commun import mois_label
    per = rv.per
    s = _vide(ctx, True)
    image(s, mg.points_decor(6, 6), 7.4, 0.55, 6.2, 6.2)
    s.shapes.add_picture(str(AIR / "logo_autobiz_blanc.png"), Inches(0.6), Inches(0.55), Inches(1.5), Inches(0.405))
    if rv.trim:
        from .revue_trim import NOMS_PAYS
        pays = " & ".join(dict.fromkeys(NOMS_PAYS.get(p, p) for p in rv.pays)) or "STELLANTIS"
        texte(s, 0.6, 2.3, 9.0, 0.4, f"STELLANTIS {pays}".upper(), taille=12, gras=True, couleur="8E96FF", espacement=200)
        texte(s, 0.6, 2.8, 8.0, 2.4, "Trade-in websites\nperformance review", taille=54, gras=True, couleur="FFFFFF", interligne=0.92)
        pastille_txt = f"Q{per.indice}-{per.annee}"
    else:
        texte(s, 0.6, 2.3, 7.5, 0.4, "STELLANTIS  \u00b7  TRADE-IN WEBSITES", taille=12, gras=True, couleur="8E96FF", espacement=200)
        texte(s, 0.6, 2.8, 8.0, 2.4, "Trade-in\nperformance", taille=66, gras=True, couleur="FFFFFF", interligne=0.92)
        pastille_txt = mois_label(per)
    forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 5.35, 2.5, 0.52, None, rayon=0.5, contour="4E5BFF", epaisseur=1.25)
    texte(s, 0.6, 5.35, 2.5, 0.52, pastille_txt, taille=15, gras=True, couleur="FFFFFF", align=PP_ALIGN.CENTER, ancre=MSO_ANCHOR.MIDDLE)
    rv._drapeau_pays(s, {"x": 3.3, "y": 5.43, "w": 0.55, "h": 0.36})
    spec = rv.manifeste.get("couverture_stellantis")
    if spec:
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, 9.0, 5.65, 3.6, 1.2, "FFFFFF", rayon=0.15)
        rv._image(s, {**spec, "x": 9.2, "y": 5.78, "w": 3.2, "h": 0.94})
    texte(s, 0.6, 6.95, 6.0, 0.25, f"{ctx.t['confidentiel']}  \u00b7  {rv.date_deck}", taille=9, couleur="6C7390")
    return s


def agenda(ctx, rv, actif, sections):
    """Sommaire : la section en cours en indigo et en gras."""
    s = diapo(ctx, rv, "Contents", "Agenda", "What this review covers.")
    if 0 <= actif < len(sections):
        ctx.v2_sections[s.slide_id] = sections[actif]           # section courante : sert de surtitre aux diapositives V1 habillées ensuite
    pas = min(0.95, 5.0 / max(1, len(sections)))
    for i, it in enumerate(sections):
        y = 1.7 + i * pas
        forme(s, MSO_SHAPE.RECTANGLE, 0.6, y + pas - 0.12, 12.15, 0.01, TRAIT)
        texte(s, 0.6, y, 1.2, pas - 0.15, f"{i + 1:02d}", taille=30, gras=True, couleur=INDIGO if i == actif else "C9CEFF", ancre=MSO_ANCHOR.MIDDLE)
        texte(s, 2.0, y, 8.0, pas - 0.15, phrase(it), taille=22, gras=(i == actif), couleur=ENCRE if i == actif else "5B6280", ancre=MSO_ANCHOR.MIDDLE)
    return s


def separateur(ctx, rv, libelle):
    """Séparateur de section (nom de marque) : plein écran sombre, grand numéro en filigrane."""
    ctx.n_sep = getattr(ctx, "n_sep", 0) + 1
    s = _vide(ctx, True)
    image(s, mg.points_decor(5, 5), 8.0, 1.2, 5.0, 5.0)
    texte(s, 0.8, 1.2, 6.0, 2.5, f"{ctx.n_sep:02d}", taille=150, gras=True, couleur="1B2260")
    forme(s, MSO_SHAPE.RECTANGLE, 0.9, 3.95, 1.2, 0.08, "FF5A00")
    texte(s, 0.85, 4.2, 11.0, 1.4, phrase(libelle), taille=54, gras=True, couleur="FFFFFF", interligne=0.92)
    rv._drapeau_pays(s, {"x": 12.2, "y": 0.45, "w": 0.55, "h": 0.36})
    texte(s, 0.6, 7.08, 8.0, 0.2, f"Trade-in performance  \u00b7  {rv.date_deck}", taille=8.5, couleur="6C7390")
    texte(s, 12.0, 7.08, 0.75, 0.2, f"{ctx.n:02d}", taille=8.5, couleur="6C7390", align=PP_ALIGN.RIGHT)
    return s


def _contexte(ctx, rv):
    from . import revue_global as rg
    f = rg._faits(ctx, rv)
    mois = [m.capitalize() for m in __import__("pipeline.deck.periodes", fromlist=["MOIS_COURTS"]).MOIS_COURTS["en"]]
    return rg, f, mois


def resume_executif(ctx, rv):
    rg, f, mois = _contexte(ctx, rv)
    if not f:
        return None
    from .revue_commun import mois_label
    per, an = rv.per, rv.per.annee
    s = diapo(ctx, rv, mois_label(per), "Executive Summary", "Leads generated by the trade-in sites, all brands of the perimeter.")
    kpi(s, 0.6, 1.75, rg._k(f["mois"]), f"Total leads \u00b7 {mois_label(per)}", f["e_mois_n1"], "YoY", w=3.7)
    kpi(s, 4.75, 1.75, rg._k(f["vn_mois"]), "New cars leads", f["e_vn_n1"], "YoY", w=3.7, couleur=INDIGO)
    kpi(s, 8.9, 1.75, rg._k(f["ytd"]), f"Year to date \u00b7 {an}", f["e_ytd"], f"vs {an - 1}", w=3.7)
    forme(s, MSO_SHAPE.RECTANGLE, 0.6, 3.62, 12.15, 0.012, TRAIT)
    texte(s, 0.6, 3.78, 5.0, 0.25, "TOTAL LEADS PER MONTH", taille=9, gras=True, couleur=GRIS, espacement=140)
    image(s, mg.courbes(6.4, 2.85, mois, f["old_m"], f["cur_m"], f["n"], str(an - 1), str(an)), 0.45, 4.05, 6.4, 2.85, alt=alt("Total leads per month", **{str(an - 1): f["old_m"], str(an): f["cur_m"][:f["n"]]}))
    y = 3.8
    for runs in rg._puces_resume(ctx, rv, f):
        forme(s, MSO_SHAPE.OVAL, 7.35, y + 0.07, 0.1, 0.1, INDIGO)
        segs = [(t, {"gras": g_, "couleur": ENCRE if g_ else GRIS}) for t, g_ in runs if t]
        texte(s, 7.6, y, 5.15, 0.6, segs, taille=10, interligne=1.05)
        y += 0.2 + 0.17 * (1 + sum(len(t) for t, _ in segs) // 78)
    return s


def vue_globale(ctx, rv):
    from .periodes import MOIS_COURTS
    from .revue_commun import mois_label
    rg, f, mois = _contexte(ctx, rv)
    if not f:
        return None
    per, an = rv.per, rv.per.annee
    d = ctx.d
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
    if lignes_m:
        image(s, mg.barres_marques(7.6, 2.5, lignes_m, taille=8.8 if len(lignes_m) > 8 else 10.5), 5.0, 1.85, 7.6, 2.5, alt=alt("Generated leads YTD by brand", **{n_: [v, p_] for n_, v, p_, _ in lignes_m}))
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
    image(s, mg.courbes_projets(8.9, 2.3, cats, [("New cars & Demo cars", serie("VN"), VN), ("Trade-in only", serie("SANS"), SANS), ("Used cars", serie("VO"), VO)]), 0.45, 4.75, 8.9, 2.3,
          alt=alt("Trend YTD by purchase project", **{"New cars": serie("VN"), "Trade-in only": serie("SANS"), "Used cars": serie("VO")}))
    for i, (nom, col) in enumerate((("New cars & Demo cars", VN), ("Trade-in only", SANS), ("Used cars", VO))):
        forme(s, MSO_SHAPE.OVAL, 2.1 + i * 2.1, 4.55, 0.12, 0.12, col)
        texte(s, 2.3 + i * 2.1, 4.5, 1.9, 0.22, nom, taille=8.5, couleur=ENCRE)
    y = 4.7
    for t in rg._puces_global(ctx, rv, f, ytd_m):
        forme(s, MSO_SHAPE.OVAL, 9.7, y + 0.07, 0.1, 0.1, INDIGO)
        texte(s, 9.95, y, 2.8, 0.7, t, taille=9, interligne=1.05)
        y += 0.78
    return s


def tendance_leads(ctx, rv):
    rg, f, mois = _contexte(ctx, rv)
    if not f:
        return None
    an = rv.per.annee
    ld = ctx.d.dernier_jour_leads()
    n = f["n"]
    ecoules = n if (ld and ld >= rv.per.debut.isoformat()) else n - 1
    s = diapo(ctx, rv, "Executive summary", "Executive Summary", "Lead trend \u2013 all brands.")
    texte(s, 0.6, 1.45, 6.0, 0.28, [("Total leads year trend", {"gras": True, "taille": 12})], taille=12)
    image(s, mg.barres_annuelles(12.2, 2.05, mois, f["old_m"], f["cur_m"], ecoules, INDIGO, (str(an - 1), str(an)), valeurs=True, taille_val=7), 0.45, 1.68, 12.3, 2.05, alt=alt("Total leads year trend", **{str(an - 1): f["old_m"], str(an): f["cur_m"][:ecoules]}))
    texte(s, 0.6, 3.78, 6.0, 0.28, [("NC leads year trend", {"gras": True, "taille": 12})], taille=12)
    image(s, mg.barres_annuelles(12.2, 2.05, mois, f["old_vn"], f["cur_vn"], ecoules, "#00A3FF", (str(an - 1), str(an)), valeurs=True, taille_val=7), 0.45, 4.01, 12.3, 2.05, alt=alt("NC leads year trend", **{str(an - 1): f["old_vn"], str(an): f["cur_vn"][:ecoules]}))
    for i, t in enumerate(rg._puces_tendance(ctx, rv, f)):
        x = 0.6 + i * 4.1
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 6.28, 3.95, 0.68, PALE, rayon=0.1)
        texte(s, x + 0.15, 6.28, 3.7, 0.68, t, taille=8.2, ancre=MSO_ANCHOR.MIDDLE, interligne=1.0)
    return s


def projets_groupe(ctx, rv, groupe, marques):
    from . import revue_trim as rt
    from .revue_commun import mois_label
    d, per, an = ctx.d, rv.per, rv.per.annee
    marques = [m for m in marques if m in d.marques and any(rt._L(d, p, m) for p in (per, rv.n1))]
    if not marques:
        return None
    pers = [rv.prec.n1(), rv.n1, rv.prec, per]
    pj = lambda p, m=None: {k: sum(d.leads(p, mm)[k] for mm in ([m] if m else marques)) for k in rt.PROJETS}
    s = diapo(ctx, rv, "Sales performance", "Leads by Purchase Project", f"{mois_label(per)} for {groupe}, by brand and period.")
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
    image(s, mg.colonnes_empilees(8.9, 4.7, cats, ser, groupes=grp, surligne=sur, taille=7 if len(marques) <= 5 else 6), 0.4, 1.55, 8.9, 4.7,
          alt=alt(f"Leads by purchase project {groupe}", **{f"{ctx.nom(m)} {c}": [vals["VN"][i], vals["SANS"][i], vals["VO"][i], vals["VN"][i] + vals["SANS"][i] + vals["VO"][i]] for i, (m, c) in enumerate((m, cats[4 * j + k]) for j, m in enumerate(marques) for k in range(4))}))
    t1, t2 = pj(rv.n1), pj(per)
    ser2 = [("Used cars", [t1["VO"], t2["VO"]], VO), ("Trade-in only", [t1["SANS"], t2["SANS"]], SANS), ("New cars & Demo.", [t1["VN"], t2["VN"]], VN)]
    texte(s, 9.7, 1.55, 3.0, 0.25, f"TOTAL PURCHASE {groupe.upper()}", taille=9, gras=True, couleur=GRIS, espacement=120)
    image(s, mg.colonnes_empilees(3.1, 4.4, [rt._q(rv.n1) if per.type == "mois" else str(rv.n1.annee), rt._q(per) if per.type == "mois" else str(per.annee)], ser2, surligne=[1], taille=8), 9.65, 1.85, 3.1, 4.4,
          alt=alt(f"Total purchase {groupe}", **{"Prev year": [t1["VN"], t1["SANS"], t1["VO"], sum(t1.values())], "Year": [t2["VN"], t2["SANS"], t2["VO"], sum(t2.values())]}))
    for i, (nom, col) in enumerate((("New cars & Demo.", VN), ("Trade-in only", SANS), ("Used cars", VO))):
        forme(s, MSO_SHAPE.OVAL, 9.8, 6.33 + i * 0.22, 0.1, 0.1, col)
        texte(s, 9.98, 6.27 + i * 0.22, 2.6, 0.22, nom, taille=8, couleur=GRIS)
    sh = lambda p, m=None: (lambda t: t["VN"] / sum(t.values()) * 100 if sum(t.values()) else None)(pj(p, m))
    a_, b_ = sh(per), sh(rv.n1)
    txt = []
    if a_ is not None and b_ is not None:
        txt.append(f"NC share {'up' if a_ >= b_ else 'down'} {abs(a_ - b_):.0f}pt YoY for {groupe} ({a_:.0f}%)")
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
    return s


def canaux(ctx, rv, marque):
    from . import revue_canaux as rc
    from .revue_commun import mois_label
    per_list = [rv.prec.n1(), rv.n1, rv.prec, rv.per]
    data = [rc._sources(ctx, p, marque) for p in per_list]
    if all(x is None for x in data):
        return None
    vide = {g_: {p_: 0 for p_ in rc.PROJETS} for g_ in rc.ORDRE_SOURCES}
    data = [x if x is not None else vide for x in data]
    tp = [{p_: sum(x[sg][p_] for sg in x) for p_ in rc.PROJETS} for x in data]
    if not sum(sum(t.values()) for t in tp):
        return None
    srcs = [sg for sg in rc.ORDRE_SOURCES if sg in data[0] and any(sum(x[sg].values()) for x in data)]
    titre = "LEAD DEEP DIVE" if rv.trim else "Leads by marketing channel"
    sous = f"Trade-in situation {mois_label(rv.per)}" if rv.trim else mois_label(rv.per)
    s = diapo(ctx, rv, f"{ctx.nom(marque)}  \u00b7  Lead deep dive", titre, sous)
    lw = [1.15] + [0.62] * 12
    x0, y0 = 0.5, 1.6
    coul = {"VN": VN, "SANS": SANS, "VO": VO}
    noms_p = {"VN": "New cars & Demo cars", "SANS": "Trade-in only", "VO": "Used cars"}
    for j, pj_ in enumerate(rc.PROJETS):
        forme(s, MSO_SHAPE.RECTANGLE, x0 + lw[0] + j * 4 * 0.62 + 0.05, y0 + 0.02, 4 * 0.62 - 0.1, 0.05, coul[pj_])
        texte(s, x0 + lw[0] + j * 4 * 0.62 + 0.05, y0 + 0.1, 4 * 0.62 - 0.1, 0.25, noms_p[pj_], taille=9, gras=True, couleur=ENCRE)
    for j in range(12):
        texte(s, x0 + lw[0] + j * 0.62, y0 + 0.38, 0.62, 0.22, rc._mois_court(per_list[j % 4]) + f" {str(per_list[j % 4].annee)[2:]}", taille=7, couleur=GRIS, align=PP_ALIGN.CENTER)
    lignes_g, hs = [], []
    h_ligne = min(0.5, 4.3 / (len(srcs) + 1))
    for sg in srcs + ["Total"]:
        tot_ligne = sg == "Total"
        row = [{"t": "Total" if tot_ligne else rc.NOM_SOURCE.get(sg, sg), "taille": 9, "gras": tot_ligne, "align": PP_ALIGN.LEFT, "fond": "F4F5FB" if tot_ligne else None}]
        for pj_ in rc.PROJETS:
            for k in range(4):
                v = tp[k][pj_] if tot_ligne else data[k][sg][pj_]
                tt_ = tp[k][pj_] or 1
                row.append({"t": nb_(v) if v else "\u2013", "t2": f"{v / tt_ * 100:.0f}%" if v else None, "taille": 9, "gras": tot_ligne, "couleur": ENCRE if v else "B4B9CC",
                            "fond": ("EDEFFF" if k >= 2 else None) if not tot_ligne else ("E3E6FF" if k >= 2 else "F4F5FB")})
        lignes_g.append(row); hs.append(h_ligne)
    grille(s, x0, y0 + 0.68, lw, hs, lignes_g)
    cats = [f"{rc._mois_court(p)} {str(p.annee)[2:]}" for p in per_list]
    ser = [("Used cars", [t["VO"] for t in tp], VO), ("Trade-in only", [t["SANS"] for t in tp], SANS), ("New cars & Demo.", [t["VN"] for t in tp], VN)]
    image(s, mg.colonnes_empilees(3.0, 2.7, cats, ser, surligne=[2, 3], taille=7), 9.75, 1.55, 3.0, 2.7,
          alt=alt("Leads by purchase project", **{c: [tp[k]["VN"], tp[k]["SANS"], tp[k]["VO"]] for k, c in enumerate(cats)}))
    y = 4.4
    for t in rc._puces_canaux(data, tp, srcs, rv)[:5]:
        forme(s, MSO_SHAPE.OVAL, 9.8, y + 0.06, 0.09, 0.09, INDIGO)
        texte(s, 10.0, y, 2.75, 0.5, t, taille=8.5, interligne=1.0)
        y += 0.5 + 0.14 * (len(t) // 40)
    return s


def conversion_ventes_nc(ctx, rv):
    import calendar
    from . import revue_resultats as rr
    from .periodes import MOIS_NOMS
    from .revue_commun import evol
    d, per, n = ctx.d, rv.per, rv.per.indice
    an, a1 = per.annee, per.annee - 1
    infos = {}
    ordre = [("xP", ["PEUGEOT", "CITROEN", "DS", "OPEL"]), ("Xf", ["FIAT", "JEEP", "ALFA ROMEO", "ABARTH", "FIAT PRO", "LANCIA"])]
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
    if not infos or not any(v[0] or v[1] for v in infos.values()):
        return None

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


def _evols(s, x, y, lib_prec, e_prec, e_n1, dec=1):
    """Deux pastilles d'évolution (vs période précédente, YoY) avec leur libellé."""
    cur = x
    for lib, e in ((lib_prec, e_prec), ("YoY", e_n1)):
        if e is None:
            texte(s, cur, y + 0.02, 1.2, 0.24, f"n/a {lib}", taille=8, couleur=GRIS)
            cur += 1.25
            continue
        w = pastille(s, cur, y, e, taille=9, dec=dec, base=0.34) or 0.8
        texte(s, cur + w + 0.03, y + 0.03, 0.42, 0.22, lib, taille=7.5, couleur=GRIS)
        cur += w + 0.5


def trafic(ctx, rv, marque):
    from . import revue_marque as rm
    from .revue_commun import mois_label
    D = rm._trafic_data(ctx, rv, marque)
    if D is None:
        return None
    nom, puces, site, ses, ij, hl, e_site, e_s, e_ij, e_hl, t1, t2, cvr, ct, ordre, can, can_p, can_n, orig, rep = (D[k] for k in rm.CLES_TRAFIC)
    mm = rv.vs_prec
    s = diapo(ctx, rv, f"{nom}  \u00b7  Traffic deep dive", "Traffic DEEP DIVE", f"Trade-in situation {mois_label(rv.per)}")
    cartes = [("BRAND WEBSITE \u00b7 SESSIONS", "n/a" if not site else nb_(site), e_site, None),
              ("TRADE-IN WEBSITE \u00b7 SESSIONS", nb_(ses), e_s, None),
              ("IN JOURNEY", "n/a" if ij is None else nb_(ij), e_ij, None if t1 is None else f"{t1:.1f}% of sessions"),
              ("GA LEADS", "n/a" if hl is None else nb_(hl), e_hl, None if t2 is None else f"{t2:.1f}% of in-journey")]
    for i, (lib, val, ev, note) in enumerate(cartes):
        x = 0.6 + i * 3.08
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 1.55, 2.9, 1.55, PALE if i else "F6F7FB", rayon=0.07)
        texte(s, x + 0.2, 1.68, 2.6, 0.22, lib, taille=8, gras=True, couleur=INDIGO if i else GRIS, espacement=100)
        texte(s, x + 0.2, 1.95, 2.6, 0.55, val, taille=28, gras=True)
        _evols(s, x + 0.2, 2.6, mm, ev[0], ev[1])
        if note:
            texte(s, x + 1.75, 1.68, 1.05, 0.22, note, taille=7.5, couleur=GRIS, align=PP_ALIGN.RIGHT)
    if cvr is not None:
        texte(s, 0.6, 3.18, 12.0, 0.24, [("Overall conversion (GA leads / sessions) : ", {"couleur": GRIS}), (f"{cvr:.1f}%", {"gras": True, "couleur": INDIGO})], taille=9.5)
    # tableau des canaux
    texte(s, 0.6, 3.5, 5.0, 0.22, "TRAFFIC LANDING ON TRADE IN", taille=9, gras=True, couleur=GRIS, espacement=130)
    if ct:
        rows = [[{"t": "Channel group", "taille": 8, "gras": True, "couleur": GRIS, "align": PP_ALIGN.LEFT}, {"t": "Sessions", "taille": 8, "gras": True, "couleur": GRIS, "align": PP_ALIGN.RIGHT},
                 {"t": mm, "taille": 8, "gras": True, "couleur": GRIS, "align": PP_ALIGN.RIGHT}, {"t": "YoY", "taille": 8, "gras": True, "couleur": GRIS, "align": PP_ALIGN.RIGHT}]]
        def ev_cell(e):
            if e is None:
                return {"t": "n/a", "taille": 8.5, "couleur": GRIS, "align": PP_ALIGN.RIGHT}
            return {"t": f"{e:+.1f}%", "taille": 8.5, "gras": True, "couleur": "0F7B45" if e >= 0 else "C62839", "align": PP_ALIGN.RIGHT}
        for i, c in enumerate(ordre[:12], 1):
            em = rm._d(can[c], can_p.get(c)) if can_p else None
            ey = rm._d(can[c], can_n.get(c)) if can_n else None
            rows.append([{"t": f"{i}. {c}", "taille": 8.5, "align": PP_ALIGN.LEFT}, {"t": nb_(can[c]), "taille": 8.5, "gras": True, "align": PP_ALIGN.RIGHT}, ev_cell(em), ev_cell(ey)])
        h = min(0.27, 3.15 / len(rows))
        grille(s, 0.6, 3.78, [2.0, 1.0, 0.95, 0.95], [h] * len(rows), rows)
        top = ordre[:9]
        reste = sum(can[c] for c in ordre[9:])
        libs = top + (["Other"] if reste else [])
        vals = [can[c] for c in top] + ([reste] if reste else [])
        image(s, mg.anneau_legende(4.0, 3.2, libs, vals, centre=rg_k(ct), sous_centre="sessions"), 5.7, 3.6, 4.0, 3.2,
              alt=alt("Traffic landing on Trade In by channel", **{"sessions": vals}) + " (" + ", ".join(libs) + ")")
    if orig:
        texte(s, 9.95, 3.5, 2.9, 0.22, "ENTRIES BY ORIGIN", taille=9, gras=True, couleur=GRIS, espacement=130)
        image(s, mg.anneau_legende(2.9, 1.4, ["Brand websites", "Trade In Entry"], [orig[0], orig[1]], couleurs=["#2F3DFF", "#12B5A6"], taille=8), 9.95, 3.75, 2.9, 1.4,
              alt=alt("Trade-in entries by origin", **{"Brand websites": [orig[0]], "Trade In Entry": [orig[1]]}))
    y = 5.3
    for t in puces[:5]:
        forme(s, MSO_SHAPE.OVAL, 9.98, y + 0.06, 0.09, 0.09, INDIGO)
        texte(s, 10.15, y, 2.65, 0.5, t, taille=8, interligne=1.0)
        y += 0.1 + 0.14 * (1 + len(t) // 46)
    return s


def rg_k(v):
    return f"{v / 1000:.1f}k" if v >= 1000 else str(int(v))


def ytd(ctx, rv, marque):
    from . import revue_marque as rm
    from .periodes import MOIS_COURTS
    D = rm._ytd_data(ctx, rv, marque)
    if D is None:
        return None
    tot, vn, n, an, puces = D["tot"], D["vn"], D["n"], D["an"], D["puces"]
    mois = [m.capitalize() for m in MOIS_COURTS["en"]]
    s = diapo(ctx, rv, f"{ctx.nom(marque)}  \u00b7  Year to date", "YTD Leads Trends", f"Monthly leads, {an - 1} vs {an}.")
    texte(s, 0.6, 1.45, 6.0, 0.28, [("Total leads year trend", {"gras": True, "taille": 12})], taille=12)
    image(s, mg.barres_annuelles(12.2, 2.05, mois, tot[0], tot[1], n, INDIGO, (str(an - 1), str(an)), valeurs=True, taille_val=7), 0.45, 1.68, 12.3, 2.05,
          alt=alt("Total leads year trend", **{str(an - 1): tot[0], str(an): tot[1][:n]}))
    texte(s, 0.6, 3.78, 6.0, 0.28, [("NC leads year trend", {"gras": True, "taille": 12})], taille=12)
    image(s, mg.barres_annuelles(12.2, 2.05, mois, vn[0], vn[1], n, "#00A3FF", (str(an - 1), str(an)), valeurs=True, taille_val=7), 0.45, 4.01, 12.3, 2.05,
          alt=alt("NC leads year trend", **{str(an - 1): vn[0], str(an): vn[1][:n]}))
    for i, t in enumerate(puces):
        x = 0.6 + i * 4.1
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 6.28, 3.95, 0.68, PALE, rayon=0.1)
        texte(s, x + 0.15, 6.28, 3.7, 0.68, t, taille=8.2, ancre=MSO_ANCHOR.MIDDLE, interligne=1.0)
    return s


def site_principal(ctx, rv, marque):
    from . import revue_canaux as rc
    D = rc._site_data(ctx, rv, marque)
    if D is None:
        return None
    cur, prec, supports = D
    z = {p: 0 for p in rc.PROJETS}
    coul = {"VN": VN, "SANS": SANS, "VO": VO}
    noms_p = {"VN": "New cars & Demo cars", "SANS": "Trade-in only", "VO": "Used cars"}
    s = diapo(ctx, rv, f"{ctx.nom(marque)}  \u00b7  Lead deep dive", "Leads from main website", "Call-to-action placements, month vs same month last year.")
    lw = [2.1] + [1.05] * 6
    x0, y0 = 0.6, 1.6
    for j, pj_ in enumerate(rc.PROJETS):
        forme(s, MSO_SHAPE.RECTANGLE, x0 + lw[0] + j * 2.1 + 0.05, y0 + 0.02, 2.0, 0.05, coul[pj_])
        texte(s, x0 + lw[0] + j * 2.1 + 0.05, y0 + 0.1, 2.0, 0.25, noms_p[pj_], taille=9, gras=True, couleur=ENCRE)
        for k, per in enumerate((rv.n1, rv.per)):
            texte(s, x0 + lw[0] + j * 2.1 + k * 1.05, y0 + 0.38, 1.05, 0.22, rc._mois_label_long(per), taille=7.5, couleur=GRIS, align=PP_ALIGN.CENTER)
    h_ligne = min(0.42, 4.5 / (len(supports) + 1))
    lignes_g, hs = [], []
    for sp in supports + ["Total"]:
        tot_ligne = sp == "Total"
        row = [{"t": "Total" if tot_ligne else sp, "taille": 9.5, "gras": tot_ligne, "align": PP_ALIGN.LEFT, "fond": "F4F5FB" if tot_ligne else None}]
        for pj_ in rc.PROJETS:
            for k, dd in enumerate((prec, cur)):
                v = sum(dd.get(x, z)[pj_] for x in supports) if tot_ligne else dd.get(sp, z)[pj_]
                tt_ = sum(dd.get(x, z)[pj_] for x in supports) or 1
                row.append({"t": nb_(v) if v else "\u2013", "t2": f"{v / tt_ * 100:.0f}%" if v else None, "taille": 9.5, "gras": tot_ligne or k == 1, "couleur": ENCRE if v else "B4B9CC",
                            "fond": ("EDEFFF" if k == 1 else None) if not tot_ligne else ("E3E6FF" if k == 1 else "F4F5FB")})
        lignes_g.append(row); hs.append(h_ligne)
    grille(s, x0, y0 + 0.68, lw, hs, lignes_g)
    y = 1.8
    for t in rc._puces_site(cur, prec, supports):
        forme(s, MSO_SHAPE.OVAL, 10.0, y + 0.06, 0.09, 0.09, INDIGO)
        texte(s, 10.2, y, 2.6, 0.9, t, taille=9.5, interligne=1.05)
        y += 0.3 + 0.18 * (1 + len(t) // 34)
    return s


def conquete(ctx, rv, marque):
    from . import revue_conquete as rq
    D = rq._conquete_data(ctx, rv, marque)
    if D is None:
        return None
    rep, total, propres, nom, fideles, autres, conq, mods_vn, achat, paires, top_s, top_h, puces, libelle_per, top_a = (D[k] for k in rq.CLES_CONQ)
    s = diapo(ctx, rv, f"{nom}  \u00b7  Lead deep dive", "LEAD DEEP DIVE", f"Conquest vs loyalty {libelle_per}")
    # rangée 1 : marques reprises, répartition fidélité / conquête, commentaires
    texte(s, 0.6, 1.45, 4.0, 0.22, "TOP TRADE-IN BRANDS", taille=9, gras=True, couleur=GRIS, espacement=130)
    top_b = sorted(rep.items(), key=lambda kv: (kv[0] not in propres, -kv[1]))[:10]
    lignes = [(k.title() if k.isupper() else k, v, v / total * 100, 0) for k, v in top_b]
    image(s, mg.barres_marques(4.2, 2.6, lignes, taille=8.5), 0.5, 1.7, 4.2, 2.6, alt=alt("Top trade-in brands", **{k: [v] for k, v in top_b}))
    texte(s, 4.9, 1.45, 3.0, 0.22, "CONQUEST VS LOYALTY", taille=9, gras=True, couleur=GRIS, espacement=130)
    image(s, mg.anneau_legende(3.1, 2.4, [nom.upper(), "STELLANTIS", "Conq / Extra"], [fideles, autres, conq], couleurs=["#2F3DFF", "#9AA3C7", "#12B5A6"], centre=f"{fideles / total * 100:.0f}%", sous_centre="loyal", taille=8), 4.85, 1.75, 3.1, 2.4,
          alt=alt("Conquest vs loyalty", **{nom: [fideles], "Stellantis": [autres], "Conquest": [conq]}))
    y = 1.55
    for t, *_ in [(p if isinstance(p, str) else p[0],) for p in puces]:
        forme(s, MSO_SHAPE.OVAL, 8.3, y + 0.06, 0.09, 0.09, INDIGO)
        texte(s, 8.5, y, 4.3, 0.8, t, taille=9, interligne=1.05)
        y += 0.2 + 0.17 * (1 + len(t) // 62)
    # rangée 2 : modèles Stellantis / hors Stellantis, tableau d'achat
    texte(s, 0.6, 4.45, 3.9, 0.22, "TOP MODEL STLA", taille=9, gras=True, couleur=GRIS, espacement=130)
    if top_s:
        image(s, mg.colonnes_simples(3.9, 2.25, [k for k, _ in top_s], [v for _, v in top_s]), 0.5, 4.68, 3.9, 2.25, alt=alt("Top model STLA", **{k: [v] for k, v in top_s}))
    else:
        texte(s, 0.6, 5.5, 3.8, 0.3, "n/a", taille=12, couleur=GRIS, align=PP_ALIGN.CENTER)
    texte(s, 4.6, 4.45, 3.9, 0.22, "TOP MODEL OUT STLA", taille=9, gras=True, couleur=GRIS, espacement=130)
    if top_h:
        image(s, mg.colonnes_simples(3.9, 2.25, [k for k, _ in top_h], [v for _, v in top_h], couleur="#12B5A6"), 4.5, 4.68, 3.9, 2.25, alt=alt("Top model out of STLA", **{k: [v] for k, v in top_h}))
    else:
        texte(s, 4.6, 5.5, 3.8, 0.3, "n/a", taille=12, couleur=GRIS, align=PP_ALIGN.CENTER)
    texte(s, 8.7, 4.45, 4.1, 0.22, "NC LEAD BY PURCHASE PROJECT / TRADE-IN MODEL", taille=9, gras=True, couleur=GRIS, espacement=100)
    if top_a and mods_vn:
        reprise = {}
        for mr, mo, ma, mo_a, n in mods_vn:
            if mo:
                reprise[mo.upper()] = reprise.get(mo.upper(), 0) + n
        cols = [k for k, _ in sorted(reprise.items(), key=lambda kv: -kv[1])[:7]]
        croise = {}
        for (a, (mr, mo)), n in paires.items():
            croise[(a, mo)] = croise.get((a, mo), 0) + n
        somme = {a: sum(croise.get((a, c), 0) for c in cols) for a in achat}
        top_tab = sorted(achat, key=lambda a: (-somme[a], -achat[a]))[:5]
        lw = [0.95] + [(4.1 - 0.95) / len(cols)] * len(cols)
        rows = [[{"t": "Purchase model", "taille": 7, "gras": True, "couleur": GRIS, "align": PP_ALIGN.LEFT}] + [{"t": rq._joli(c)[:8], "taille": 6.5, "gras": True, "couleur": GRIS} for c in cols]]
        for a in top_tab:
            rows.append([{"t": rq._joli(a)[:14], "taille": 8, "align": PP_ALIGN.LEFT}] + [{"t": nb_(croise.get((a, c), 0)) if croise.get((a, c)) else "", "taille": 8.5, "gras": True} for c in cols])
        rows.append([{"t": "Total", "taille": 8, "gras": True, "align": PP_ALIGN.LEFT, "fond": "F4F5FB"}] + [{"t": nb_(reprise[c]), "taille": 8, "gras": True, "fond": "F4F5FB"} for c in cols])
        grille(s, 8.7, 4.75, lw, [0.36] + [0.34] * (len(rows) - 2) + [0.34], rows)
    else:
        texte(s, 8.7, 5.5, 4.0, 0.3, "n/a", taille=12, couleur=GRIS, align=PP_ALIGN.CENTER)
    return s


def focus_v2(ctx, rv, marque):
    from . import revue_v2 as v2
    from .revue_commun import nb
    D = v2._focus_data(ctx, marque)
    if D is None:
        return None
    lignes_pays, etapes, ordre = D
    s = diapo(ctx, rv, f"{ctx.nom(marque)}  \u00b7  V2 redesign focus", "V2 REDESIGN FOCUS", f"{ctx.nom(marque)} \u2013 before / after the V2 switch")
    tete = [{"t": t, "taille": 8, "gras": True, "couleur": GRIS, "align": PP_ALIGN.LEFT if i == 0 else PP_ALIGN.CENTER} for i, t in
            enumerate(("Market", "V2 go-live", "Before (28 days)", "After (since go-live)", "Sessions / day", "Conversion home \u2192 estimate", "Estimates (users)"))]
    rows, peu = [tete], False
    for _, pays, dv, v, st in lignes_pays:
        a0, b0 = st[0].get("a") or 0, st[0].get("b") or 0
        fiable = a0 >= v2.BASE_MINI and b0 >= v2.BASE_MINI
        peu = peu or not fiable
        spd = v2._evol(v.get("pre_users_per_day"), v.get("post_users_per_day"))
        conv = f"{v['pre_conversion_pct']:.1f}% \u2192 {v['post_conversion_pct']:.1f}%  ({v['delta_conversion_pts']:+.1f} pt)" if fiable and v.get("pre_conversion_pct") is not None else "low base"
        rows.append([{"t": v2.PAYS_V2[pays], "taille": 10, "gras": True, "align": PP_ALIGN.LEFT}, {"t": v2._date(dv), "taille": 9.5},
                     {"t": v.get("pre_label", "n/a"), "taille": 8.5}, {"t": f"{v.get('post_label', 'n/a')} ({v.get('post_days', '?')} d)", "taille": 8.5},
                     {"t": f"{v['pre_users_per_day']:,.0f} \u2192 {v['post_users_per_day']:,.0f}".replace(",", " ") + (f"  ({spd:+.0f}%)" if spd is not None else ""), "taille": 9.5, "gras": True,
                      "couleur": ("0F7B45" if (spd or 0) >= 0 else "C62839") if spd is not None else ENCRE},
                     {"t": conv, "taille": 9.5, "gras": fiable, "couleur": ("0F7B45" if (v.get("delta_conversion_pts") or 0) > 0 else "C62839") if fiable else GRIS},
                     {"t": f"{nb(v.get('pre_final_users'))} \u2192 {nb(v.get('post_final_users'))}", "taille": 9.5}])
    hs = [0.42] + [0.42] * (len(rows) - 1)
    yy = grille(s, 0.6, 1.55, [1.2, 1.2, 1.8, 2.0, 1.9, 2.3, 1.75], hs, rows)
    a0, b0 = etapes[ordre[0]]
    if a0 >= v2.BASE_MINI and b0 >= v2.BASE_MINI and len(ordre) >= 2:
        texte(s, 0.6, yy + 0.2, 10.0, 0.25, "FUNNEL \u2013 SHARE OF HOMEPAGE VISITORS REACHING EACH STEP", taille=9, gras=True, couleur=GRIS, espacement=120)
        avant = [etapes[k][0] / a0 * 100 for k in ordre]
        apres = [etapes[k][1] / b0 * 100 for k in ordre]
        cats = [v2.ETAPES_EN.get(k, k) for k in ordre]
        h = min(3.2, 6.55 - (yy + 0.5))
        image(s, mg.colonnes_groupees(12.1, h, cats, [("Before V2", avant, "#C9CEFF"), ("After V2", apres, "#2F3DFF")], taille=9), 0.5, yy + 0.5, 12.2, h,
              alt=alt("Funnel share of homepage visitors", **{"Before V2": avant, "After V2": apres}) + " (" + ", ".join(cats) + ")")
    texte(s, 0.6, 6.62, 12.1, 0.4, ("Windows differ per market (before = the 28 days preceding the go-live; after = since the go-live): the later the go-live, the shorter the observation. "
          "Other factors may have moved at the same time (traffic mix, paid traffic): the gap cannot be attributed to V2 alone." + (" Markets with fewer than 100 visitors are shown as 'low base'." if peu else "")),
          taille=7.5, couleur=GRIS, interligne=1.0)
    return s


def focus_v2_entree(ctx, rv, marque):
    from . import revue_v2 as v2
    D = v2._entree_data(ctx, marque)
    if D is None:
        return None
    lignes, tot = D
    s = diapo(ctx, rv, f"{ctx.nom(marque)}  \u00b7  V2 redesign focus", "V2 REDESIGN FOCUS", f"{ctx.nom(marque)} \u2013 funnel by entry mode (plate / brand & model)")
    tete = [{"t": t, "taille": 8, "gras": True, "couleur": GRIS, "align": PP_ALIGN.LEFT if i == 0 else PP_ALIGN.CENTER} for i, t in
            enumerate(("Market", "V2 go-live", "Month before \u2192 latest month after", "Brand/model share of leads", "Plate: Version \u2192 Estimate", "Brand/model: Version \u2192 Estimate"))]
    rows = [tete] + [[{"t": r[1], "taille": 10, "gras": True, "align": PP_ALIGN.LEFT}, {"t": v2._date(r[2]), "taille": 9.5}, {"t": r[3], "taille": 9},
                      {"t": r[4], "taille": 9.5}, {"t": r[5], "taille": 9.5, "gras": True}, {"t": r[6], "taille": 9.5, "gras": True}] for r in lignes]
    yy = grille(s, 0.6, 1.55, [1.3, 1.3, 2.7, 2.1, 2.3, 2.4], [0.42] * len(rows), rows)
    texte(s, 0.6, yy + 0.2, 11.0, 0.25, "FUNNEL \u2013 SHARE OF VERSION-STEP VISITORS REACHING EACH STEP, BY ENTRY MODE", taille=9, gras=True, couleur=GRIS, espacement=120)
    pct_ = lambda v: [x / v[0] * 100 if v[0] else 0 for x in v]
    series = [("Plate \u2013 before V2", pct_(tot["immat"][0]), "#C9CEFF"), ("Plate \u2013 after V2", pct_(tot["immat"][1]), "#2F3DFF")]
    if all(v[0] >= v2.BASE_MINI and max(v) <= v[0] * 1.005 for v in tot["marque_modele"]):
        series += [("Brand/model \u2013 before V2", pct_(tot["marque_modele"][0]), "#FFD3A3"), ("Brand/model \u2013 after V2", pct_(tot["marque_modele"][1]), "#FFA23A")]
    h = min(3.2, 6.55 - (yy + 0.5))
    image(s, mg.colonnes_groupees(12.1, h, v2.ETAPES_ENTREE, series, taille=9), 0.5, yy + 0.5, 12.2, h,
          alt=alt("Funnel by entry mode", **{n_: v_ for n_, v_, _ in series}) + " (" + ", ".join(v2.ETAPES_ENTREE) + ")")
    texte(s, 0.6, 6.62, 12.1, 0.4, "Monthly active users per entry path (GA4). 'Before' = the full month preceding the go-live month; 'after' = the latest month since the go-live (may be partial). "
          "Brand/model shown only when its steps are consistent before and after (n/a otherwise: tracking of that path may differ). Other factors may have moved at the same time: the gap cannot be attributed to V2 alone.",
          taille=7.5, couleur=GRIS, interligne=1.0)
    return s


# ------------------------------------------------------------ diapositives de gestion et de synthèse
def _statut_style(code):
    return {"fait": ("E3F6EC", "0F7B45"), "en_cours": ("EEF0FF", INDIGO), "a_faire": ("F1F2F6", GRIS)}.get(code, ("F1F2F6", GRIS))


def actions_en_cours(ctx, rv):
    actions = ctx.brief.get("actionsEnCours") or []
    s = diapo(ctx, rv, "Contents", "Ongoing actions", "Actions in progress, owners and status.")
    lw = [0.45, 1.9, 2.7, 1.0, 2.1, 4.0]
    tete = [{"t": t, "taille": 8.5, "gras": True, "couleur": GRIS, "align": PP_ALIGN.LEFT if i in (1, 2, 4, 5) else PP_ALIGN.CENTER} for i, t in enumerate(("#", "Subject", "Details", "Date", "Pilot", "Status"))]
    rows, hs = [tete], [0.38]
    for i, a in enumerate(actions, 1):
        statut = a.get("statut") or []
        statut = statut if isinstance(statut, list) else [statut]
        lignes = max(len(statut), 1 + len(str(a.get("details", ""))) // 38)
        rows.append([{"t": str(i), "taille": 9, "gras": True, "couleur": INDIGO}, {"t": a.get("sujet", ""), "taille": 9, "gras": True, "align": PP_ALIGN.LEFT},
                     {"t": a.get("details", ""), "taille": 8.5, "align": PP_ALIGN.LEFT}, {"t": a.get("date", ""), "taille": 8.5}, {"t": a.get("pilote", ""), "taille": 8.5, "align": PP_ALIGN.LEFT},
                     {"t": "\n".join("\u2022 " + str(x) for x in statut), "taille": 8, "align": PP_ALIGN.LEFT}])
        hs.append(max(0.42, 0.17 * lignes + 0.12))
    if sum(hs) > 5.3:
        k = 5.3 / sum(hs)
        hs = [h * k for h in hs]
    grille(s, 0.6, 1.55, lw, hs, rows)
    return s


def open_points(ctx, rv):
    out = []
    for p in ctx.brief.get("pointsOuverts") or [{}]:
        s = diapo(ctx, rv, "Contents", ctx.t["points_ouverts"], p.get("titre") or None)
        y = 1.8
        for l in [l for l in (p.get("texte") or "").split("\n") if l.strip()]:
            forme(s, MSO_SHAPE.OVAL, 0.75, y + 0.13, 0.13, 0.13, INDIGO)
            texte(s, 1.05, y, 11.5, 0.6, l, taille=17, interligne=1.1)
            y += 0.35 + 0.3 * (1 + len(l) // 95)
        out.append(s)
    return out


def next_steps(ctx, rv):
    et = ctx.brief.get("prochainesEtapes") or []
    t = ctx.t
    s = diapo(ctx, rv, "Contents", "NEXT STEPS", "Items, owners, status and deadlines.")
    lw = [6.4, 2.4, 1.9, 1.5]
    rows = [[{"t": h, "taille": 8.5, "gras": True, "couleur": GRIS, "align": PP_ALIGN.LEFT} for h in ("Item", t["responsable"], t["statut"], t["echeance"])]]
    hs = [0.4]
    for e in et:
        fond, coul = _statut_style(e.get("statut", "a_faire"))
        rows.append([{"t": e.get("item", ""), "taille": 11, "gras": True, "align": PP_ALIGN.LEFT}, {"t": e.get("responsable", ""), "taille": 10.5, "align": PP_ALIGN.LEFT},
                     {"t": t[e.get("statut", "a_faire")], "taille": 10, "gras": True, "couleur": coul, "fond": fond}, {"t": e.get("echeance", ""), "taille": 10.5, "align": PP_ALIGN.LEFT}])
        hs.append(0.5)
    grille(s, 0.6, 1.6, lw, hs, rows)
    return s


def contacts(ctx, rv):
    c = ctx.brief.get("contact") or {}
    s = _vide(ctx, True)
    image(s, mg.points_decor(5, 5), 8.2, 1.3, 5.0, 5.0)
    texte(s, 0.85, 1.9, 7.0, 0.3, ctx.t["contacts"].upper(), taille=12, gras=True, couleur="8E96FF", espacement=200)
    forme(s, MSO_SHAPE.OVAL, 0.85, 2.6, 1.1, 1.1, "FF5A00")
    forme(s, MSO_SHAPE.OVAL, 1.26, 2.8, 0.28, 0.28, "FFFFFF")
    forme(s, MSO_SHAPE.ROUND_2_SAME_RECTANGLE, 1.13, 3.15, 0.54, 0.3, "FFFFFF")
    texte(s, 2.2, 2.6, 7.0, 0.6, c.get("nom") or "", taille=34, gras=True, couleur="FFFFFF")
    texte(s, 2.2, 3.25, 7.0, 0.4, c.get("fonction") or "", taille=16, couleur="B9BFD8")
    texte(s, 2.2, 3.7, 7.0, 0.4, c.get("email") or "", taille=14, couleur="8E96FF")
    s.shapes.add_picture(str(AIR / "logo_autobiz_blanc.png"), Inches(0.85), Inches(0.7), Inches(1.5), Inches(0.405))
    texte(s, 0.6, 7.08, 8.0, 0.2, f"Trade-in performance  \u00b7  {rv.date_deck}", taille=8.5, couleur="6C7390")
    return s


def questions(ctx, rv):
    s = _vide(ctx, True)
    image(s, mg.points_decor(5, 5), 8.0, 1.2, 5.0, 5.0)
    forme(s, MSO_SHAPE.RECTANGLE, 0.9, 3.0, 1.2, 0.08, "FF5A00")
    texte(s, 0.85, 3.25, 8.0, 1.6, "Q/A", taille=96, gras=True, couleur="FFFFFF")
    s.shapes.add_picture(str(AIR / "logo_autobiz_blanc.png"), Inches(0.85), Inches(0.7), Inches(1.5), Inches(0.405))
    return s


# ------------------------------------------------------------ vues d'ensemble par marque
def apercu_marques(ctx, rv):
    from . import analyse as an
    from . import revue_trim as rt
    from .revue_commun import evol, mois_label, nb
    d, per = ctx.d, rv.per
    marques = rt._actives(ctx, rv)
    if not marques:
        return []
    perso = ctx.brief.get("actionsMarques") or {}
    xf = [m for m in marques if m in rt.GROUPE_XF_TRIM]
    morceaux = []
    for lot in ([m for m in marques if m not in rt.GROUPE_XF_TRIM], xf):
        if lot:
            k = -(-len(lot) // 6)
            t_ = -(-len(lot) // k)
            morceaux += [lot[i:i + t_] for i in range(0, len(lot), t_)]
    out = []
    for morceau in morceaux:
        titre = f"Leads Overview {mois_label(per)}" if rv.trim or len(rv.pays) != 1 else f"Leads Overview - {mois_label(per)} | {rt.NOMS_PAYS.get(rv.pays[0], rv.pays[0]).title()}"
        s = diapo(ctx, rv, "Performance by brand", titre)
        for x, w, t in ((0.6, 3.6, "LEAD TREND & NC SHARE"), (4.4, 4.2, "DRIVERS OF INCREASE / DECREASE"), (8.8, 4.0, "RECOMMENDED ACTION")):
            texte(s, x, 1.4, w, 0.22, t, taille=8.5, gras=True, couleur=INDIGO, espacement=120)
        h = min(0.88, 5.2 / len(morceau))
        y = 1.72
        for m in morceau:
            a = an.apercu_marque(ctx, m)
            forme(s, MSO_SHAPE.RECTANGLE, 0.6, y + h - 0.01, 12.2, 0.008, TRAIT)
            rt._logo_petit(rv, s, m, 0.62, y + 0.12, h_max=min(0.55, h - 0.2), w_max=0.8)
            texte(s, 1.5, y + 0.05, 2.7, 0.25, ctx.nom(m), taille=11, gras=True)
            tot_c, tot_1, tot_p = rt._L(d, per, m), rt._L(d, rv.n1, m), rt._L(d, rv.prec, m)
            nc_c, nc_1, nc_p = d.leads(per, m)["VN"], d.leads(rv.n1, m)["VN"], d.leads(rv.prec, m)["VN"]
            for dy, lib, v, v1, vp in ((0.3, "Total", tot_c, tot_1, tot_p), (0.5, "NC", nc_c, nc_1, nc_p)):
                segs = [(f"{lib}: {nb(v)}   ", {"gras": True})]
                for k, (ref, nom) in enumerate(((vp, rv.vs_prec), (v1, "YoY"))):
                    e = evol(v, ref) if ref >= 20 else None
                    if k:
                        segs.append(("  |  ", {"couleur": GRIS}))
                    segs.append((f"{'\u25b2' if e > 0 else '\u25bc'} {e:+.0f}% {nom}" if e is not None else f"low base {nom}",
                                 {"gras": True, "couleur": ("0F7B45" if e >= 0 else "C62839") if e is not None else GRIS}))
                texte(s, 1.5, y + dy, 2.8, 0.2, segs, taille=8.5)
            if a["nc"]:
                texte(s, 1.5, y + 0.7, 2.8, 0.18, a["nc"][0].replace("New cars leads share", "NC share:"), taille=8, couleur=GRIS)
            acts = perso.get(m) or a["actions"]
            for x, w, lignes in ((4.4, 4.2, a["moteurs"]), (8.8, 4.0, acts)):
                texte(s, x, y + 0.06, w, h - 0.1, "\n".join("\u2022 " + l for l in lignes[:4]), taille=8, interligne=1.0, ancre=MSO_ANCHOR.MIDDLE)
            y += h
        out.append(s)
    return out


def trafic_leads_apercu(ctx, rv, ordre=None, mensuel=False):
    from . import revue_trim as rt
    from .revue_commun import evol, mois_label, nb
    d, per = ctx.d, rv.per
    marques = rt._actives(ctx, rv)
    if ordre:
        marques = sorted(marques, key=lambda m: ordre.index(m) if m in ordre else len(ordre))
    if not marques:
        return None
    prec_ses = rv.prec if mensuel else per.precedente_jours()
    lib_prec = "MoM" if mensuel else "QoQ"
    trafic = {m: tuple(rt._sessions(d, p, m) for p in (per, prec_ses, rv.n1)) for m in marques}
    leads = {m: tuple(rt._L(d, p, m) for p in (per, rv.prec, rv.n1)) for m in marques}
    s = diapo(ctx, rv, "Traffic & lead deep dive", f"Traffic & leads Overview {mois_label(per)}")
    n = len(marques)
    w0 = 1.3
    wc = min(1.05, (12.2 - w0) / n)
    ev = lambda cur, ref: evol(cur, ref) if cur and ref else None

    def bloc(y, titre, vals, dec):
        texte(s, 0.6, y, 4.0, 0.3, titre.upper(), taille=9, gras=True, couleur=GRIS, espacement=130)
        rows = [[{"t": "", "taille": 8}] + [{"t": ctx.nom(m), "taille": 8.5, "gras": True, "couleur": INDIGO} for m in marques]]
        rows.append([{"t": mois_label(per), "taille": 8, "couleur": GRIS, "align": PP_ALIGN.LEFT}] + [{"t": nb(vals[m][0]) if vals[m][0] else "\u2013", "taille": 13, "gras": True} for m in marques])
        for nom, k in ((lib_prec, 1), ("YoY", 2)):
            row = [{"t": nom, "taille": 8, "couleur": GRIS, "align": PP_ALIGN.LEFT}]
            for m in marques:
                e = ev(vals[m][0], vals[m][k])
                row.append({"t": "" if e is None else ("\u25bc " if e < 0 else "\u25b2 ") + f"{e:+.{dec}f}%", "taille": 8.5, "gras": True, "couleur": ("C62839" if (e or 0) < 0 else "0F7B45")})
            rows.append(row)
        grille(s, 0.6, y + 0.32, [w0] + [wc] * n, [0.3, 0.46, 0.28, 0.28], rows)
    bloc(1.5, "Traffic (sessions)", trafic, 1)
    bloc(3.3, "Leads", leads, 0)
    texte(s, 0.6, 5.35, 3.0, 0.22, "WHAT MOVED", taille=9, gras=True, couleur=GRIS, espacement=130)
    lignes = [("Traffic", rt._phrases_evol(ctx, marques, trafic, "Sessions", lib_prec)), ("Leads", rt._phrases_evol(ctx, marques, leads, "Leads", lib_prec))]
    for i, (t, ph) in enumerate(lignes):
        x = 0.6 + i * 6.15
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 5.62, 6.0, 1.3, PALE, rayon=0.08)
        texte(s, x + 0.2, 5.7, 5.6, 0.22, t.upper(), taille=8, gras=True, couleur=INDIGO, espacement=120)
        texte(s, x + 0.2, 5.95, 5.6, 0.95, "\n".join(ph), taille=8.5, interligne=1.05)
    return s


def projection_nc(ctx, rv, tous=False):
    from . import revue_resultats as rr
    from .periodes import MOIS_COURTS, MOIS_NOMS
    from .revue_commun import evol, mois_label, nb
    D = rr._projection_data(ctx, rv, tous)
    if D is None:
        return None
    suiv, n1, jours_ecoules, jours_mois, lignes_v, tot, mois_c = (D[k] for k in ("suiv", "n1", "jours_ecoules", "jours_mois", "lignes_v", "tot", "mois_c"))
    s = diapo(ctx, rv, "Projection current month", mois_label(suiv), "Total Leads projection" if tous else "NC Leads projection")
    s.notes_slide.notes_text_frame.text = f"Projection = leads {'all purchase projects' if tous else 'New cars'} from 1 to {jours_ecoules} {mois_c} / {jours_ecoules} days x {jours_mois} days (constant average pace, indicative)."
    lw = [2.4, 1.7, 1.7, 2.1, 1.7, 1.5]
    mois = lambda p: MOIS_NOMS["en"][p.indice - 1].capitalize()
    tete = [{"t": "", "taille": 8}] + [{"t": t, "t2": u, "taille": 10, "gras": True, "taille2": 8.5, "fond": f, "couleur": c} for t, u, f, c in (
        (str(rv.prec.annee), mois(rv.prec), None, ENCRE), (str(rv.per.annee), mois(rv.per), None, ENCRE),
        (str(suiv.annee), f"Projection {MOIS_COURTS['en'][suiv.indice - 1]}", "EEF0FF", INDIGO), (str(n1.annee), mois(n1), None, ENCRE), ("Var", f"{n1.annee}/{str(suiv.annee)[2:]}", "2F3DFF", "FFFFFF"))]
    rows, hs = [tete], [0.55]
    nom_p = rr._nom_projection
    for i, (m, a, b, pr, r1) in enumerate(lignes_v + [("Total", tot[0], tot[1], tot[2], tot[3])]):
        e = evol(pr, r1)
        total = m == "Total"
        fd = "F4F5FB" if total else None
        rows.append([{"t": nom_p(m) if not total else "Total", "taille": 10.5, "gras": True, "align": PP_ALIGN.LEFT, "fond": fd},
                     {"t": nb(a), "taille": 10.5, "fond": fd}, {"t": nb(b), "taille": 10.5, "fond": fd},
                     {"t": nb(pr), "taille": 10.5, "gras": True, "couleur": INDIGO, "fond": "EEF0FF"}, {"t": nb(r1), "taille": 10.5, "fond": fd},
                     {"t": f"{e:+.0f}%" if e is not None else "n/a", "taille": 10, "gras": True, "couleur": ("0F7B45" if e >= 0 else "C62839") if e is not None else GRIS, "fond": fd}])
        hs.append(min(0.4, 4.9 / (len(lignes_v) + 1)))
    grille(s, 0.6, 1.55, lw, hs, rows)
    jour = f"{mois_c} {jours_ecoules}"
    texte(s, 0.6, 6.7, 8.0, 0.25, f"Source: autobiz data till {jour}", taille=9, couleur=GRIS)
    return s


def nc_marches(ctx, rv):
    from . import revue_nc_marches as nm
    D = nm._marches_data(ctx, rv)
    if D is None:
        return None
    marches, par_code, puces, tot26, tot25 = D
    s = diapo(ctx, rv, "Sales performance", "NC Sales Conversion", nm._sous_titre(ctx, rv))
    e = (tot26 / tot25 - 1) * 100 if tot25 else None
    kpi(s, 0.6, 1.5, nb_(tot26), "NC leads \u00b7 all autobiz markets", e, "YoY", w=3.6, taille=40, couleur=INDIGO)
    texte(s, 0.6, 3.3, 4.0, 0.22, "NC LEADS BY COUNTRY AND SHARE", taille=9, gras=True, couleur=GRIS, espacement=120)
    lignes = [(m["etiq"].title(), m["leads"], m["part"], m["leads_n1"]) for m in marches]
    image(s, mg.barres_marques(4.2, min(3.3, 0.3 * len(lignes) + 0.3), lignes, taille=8.5), 0.45, 3.55, 4.2, min(3.3, 0.3 * len(lignes) + 0.3),
          alt=alt("NC leads by country", **{m["etiq"]: [m["leads"], m["part"]] for m in marches}))
    texte(s, 4.9, 1.5, 6.0, 0.22, "NC LEADS BY COUNTRY AND YOY GROWTH", taille=9, gras=True, couleur=GRIS, espacement=120)
    nm._carte(s, 4.9, 1.75, 6.6, 5.0, par_code)
    crs = [m["croiss"] for m in marches if m["croiss"] is not None]
    if crs:
        lx, ly = 9.3, 6.6
        texte(s, lx - 0.3, ly - 0.25, 2.2, 0.2, "% growth vs Y-1", taille=7, gras=True, couleur=GRIS)
        for i, (_, _, c) in enumerate(nm.CLASSES):
            forme(s, MSO_SHAPE.RECTANGLE, lx + i * 0.32, ly, 0.32, 0.14, c)
        texte(s, lx - 0.35, ly + 0.15, 0.7, 0.2, f"{min(crs):+.0f}%", taille=7, couleur=GRIS)
        texte(s, lx + 1.2, ly + 0.15, 0.7, 0.2, f"{max(crs):+.0f}%", taille=7, couleur=GRIS, align=PP_ALIGN.RIGHT)
    y = 1.65
    for t in puces:
        forme(s, MSO_SHAPE.OVAL, 11.7, y + 0.07, 0.09, 0.09, INDIGO)
        texte(s, 11.88, y, 1.0, 1.4, t, taille=7.5, interligne=1.0)
        y += 0.15 + 0.13 * (1 + len(t) // 15)
    texte(s, 0.6, 7.0, 11.0, 0.2, "Source: autobiz \u2014 back-office leads (New cars projects, valid leads, Spoticar excluded)", taille=7.5, couleur="A0A5B8")
    return s


def nc_entonnoirs(ctx, rv):
    from . import revue_nc_marches as nm
    marches = nm.donnees(ctx, rv)
    if not marches or not any(m["commandes"] for m in marches):
        return None
    noms = [{"UK": "United Kingdom", "Belux": "Belgium"}.get(m["nom"], m["nom"]) for m in marches]
    s = diapo(ctx, rv, "Sales performance", "NC Sales Conversion", nm._sous_titre(ctx, rv))
    fk = nm._fmt_k
    h = 2.45
    image(s, mg.entonnoir(12.4, h, noms, [m["leads"] for m in marches], [m["commandes"] for m in marches], fk, fk, "# LEADS GENERATED", "# NSC ORDERS"), 0.45, 1.5, 12.4, h,
          alt=alt("Leads and NSC orders by market", **{"leads": [m["leads"] for m in marches], "NSC orders": [m["commandes"] for m in marches]}) + " (" + ", ".join(noms) + ")")
    image(s, mg.entonnoir(12.4, h, noms, [m["leads"] for m in marches], [m["taux"] for m in marches], fk, lambda v: f"{v:.1f}%".replace(".0%", "%"), "# LEADS GENERATED", "% NSC ORDERS"), 0.45, 4.15, 12.4, h,
          alt=alt("Leads and NSC order rate by market", **{"leads": [m["leads"] for m in marches], "rate": [m["taux"] for m in marches]}) + " (" + ", ".join(noms) + ")")
    texte(s, 0.6, 7.0, 11.0, 0.2, nm._pied(ctx), taille=7.5, couleur="A0A5B8")
    return s


# ------------------------------------------------------------ revue trimestrielle : vues globales et C1ST
def global_overview(ctx, rv):
    from . import revue_trim as rt
    from .periodes import MOIS_COURTS
    from .revue_commun import evol, mois_label, nb
    d, per = ctx.d, rv.per
    L, Lp, Ln = (rt._L(d, p) for p in (per, rv.prec, rv.n1))
    if not L:
        return None
    an = per.annee
    fin_m = per.mois()[-1][1]
    ytd = sum(d.leads_mensuels(an)[:fin_m])
    ytd_n1 = sum(d.leads_mensuels(an - 1)[:fin_m])
    e_q, e_y, e_ytd = evol(L, Lp), evol(L, Ln), evol(ytd, ytd_n1)
    vn, vn_n1 = d.leads(per)["VN"], d.leads(rv.n1)["VN"]
    q = f"Q{per.indice}"
    s = diapo(ctx, rv, "Global overview", "Global Overview", f"Exec summary \u2013 trade-in situation {q}-{an}.")
    cartes = [("REPORTING QUARTERLY", f"Total generated leads {q}-{an}", L, "Evolution vs last quarter", e_q),
              ("REPORTING YTD", f"Total generated leads {an}", ytd, f"Evolution vs last year ({an - 1} vs {an})", e_ytd)]
    for i, (t1, t2, val, t3, ev) in enumerate(cartes):
        x = 0.6 + i * 2.2
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 1.6, 2.05, 2.7, PALE, rayon=0.07)
        texte(s, x + 0.2, 1.75, 1.7, 0.25, t1, taille=8, gras=True, couleur=INDIGO, espacement=100)
        texte(s, x + 0.2, 2.05, 1.7, 0.45, t2, taille=9, couleur=GRIS, interligne=1.0)
        texte(s, x + 0.2, 2.65, 1.7, 0.6, nb_(val), taille=30, gras=True)
        texte(s, x + 0.2, 3.4, 1.7, 0.45, t3, taille=8.5, couleur=GRIS, interligne=1.0)
        pastille(s, x + 0.2, 3.85, ev)
    ym = []
    for m in d.marques:
        a = sum(d.leads_mensuels(an, m)[:fin_m])
        if a > 0:
            ym.append((m, a))
    ym.sort(key=lambda x: -x[1])
    texte(s, 5.1, 1.62, 7.6, 0.25, f"GENERATED LEADS YTD {q}-{an}: SPLIT BY BRAND", taille=9, gras=True, couleur=GRIS, espacement=120)
    if ym:
        lignes_m = [("S&Y" if m == "STELLANTIS &YOU" else ctx.nom(m), a, a / ytd * 100, 0) for m, a in ym]
        image(s, mg.barres_marques(7.6, 2.5, lignes_m, taille=8.8 if len(lignes_m) > 8 else 10.5), 5.0, 1.85, 7.6, 2.5, alt=alt("Generated leads YTD by brand", **{n_: [v, p_] for n_, v, p_, _ in lignes_m}))
    texte(s, 0.6, 4.5, 1.6, 0.25, "TREND YTD", taille=9, gras=True, couleur=GRIS, espacement=140)
    qs = rt._trimestres(per, 8)
    cats = [f"{p.annee} Q{p.indice}" for p in qs]
    sv = [("New cars & Demo cars", [d.leads(p)["VN"] for p in qs], VN), ("Trade-in only", [d.leads(p)["SANS"] for p in qs], SANS), ("Used cars", [d.leads(p)["VO"] for p in qs], VO)]
    image(s, mg.lignes_multi(8.9, 2.3, cats, sv, taille=7.5), 0.45, 4.75, 8.9, 2.3, alt=alt("Trend YTD by purchase project", **{n_: v_ for n_, v_, _ in sv}))
    mot = lambda e: "increasing" if (e or 0) >= 0 else "decreasing"
    sg = lambda e: rt._signe(e)
    nc = f"NC leads {mot(evol(vn, vn_n1))} ({sg(evol(vn, vn_n1))} YoY)" if evol(vn, vn_n1) is not None else ""
    txt = f"{q}-{an} performance {mot(e_q)} by {sg(e_q)} QoQ & {mot(e_ytd)} by {sg(e_ytd)} YoY" + (f", {nc}" if nc else "") + "."
    forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, 9.7, 4.75, 3.1, 2.1, PALE, rayon=0.07)
    texte(s, 9.9, 4.9, 2.7, 1.8, txt, taille=10.5, interligne=1.1, ancre=MSO_ANCHOR.MIDDLE)
    return s


def leads_par_marque(ctx, rv, ref):
    from . import revue_trim as rt
    from .revue_commun import evol, nb
    d, per = ctx.d, rv.per
    pref = rv.n1 if ref == "n1" else rv.prec
    marques = list(rt._actives(ctx, rv))
    if not marques:
        return None
    nom_ref = "YoY" if ref == "n1" else "QoQ"
    cur = [rt._L(d, per, m) for m in marques]
    old = [rt._L(d, pref, m) for m in marques]
    puces = rt._evols(ctx, [(ctx.nom(m), c, o) for m, c, o in zip(marques, cur, old)], nom_ref)
    if ref == "prec":
        a, b = rt._L(d, rv.n1), rt._L(d, rv.prec.n1())
        if a and b:
            puces.append(f"Seasonality check: last year, {rt._q(rv.n1)} was {rt._signe(evol(a, b))} vs {rt._q(rv.prec.n1())} for these brands.")
    s = diapo(ctx, rv, "Global overview", f"Global Leads by brand / Q{per.indice} Vs {nom_ref}", f"{rt._q(per)} against {rt._q(pref)}, all brands.")
    evs = [(f"{evol(v, o):+.0f}%", evol(v, o)) if (v and o) else None for v, o in zip(cur, old)]
    image(s, mg.colonnes_groupees(10.4, 4.6, [ctx.nom(m).upper() for m in marques], [(rt._q(pref), old, "#C9CEFF"), (rt._q(per), cur, "#2F3DFF")], taille=8, evols=evs, entiers=True), 0.4, 1.55, 10.4, 4.6,
          alt=alt(f"Leads by brand {nom_ref}", **{rt._q(pref): old, rt._q(per): cur}) + " (" + ", ".join(ctx.nom(m) for m in marques) + ") " + ", ".join(e[0] for e in evs if e))
    y = 1.7
    for t in puces:
        forme(s, MSO_SHAPE.OVAL, 11.0, y + 0.07, 0.09, 0.09, INDIGO)
        texte(s, 11.18, y, 1.7, 1.4, t, taille=8, interligne=1.05)
        y += 0.2 + 0.15 * (1 + len(t) // 24)
    return s


def leads_par_mois(ctx, rv, projet=None):
    from . import revue_trim as rt
    from .revue_commun import evol, nb
    d, per = ctx.d, rv.per
    ms = per.mois()
    cur = [d.leads_mensuels(a, None, projet)[m - 1] for a, m in ms]
    n1 = [d.leads_mensuels(a - 1, None, projet)[m - 1] for a, m in ms]
    if not sum(cur):
        return None
    nom = "NC leads" if projet else "Leads"
    ups = [rt.MOIS_COURTS["en"][m - 1] for (a, m), c, o in zip(ms, cur, n1) if o and c > o]
    lq, lp = sum(cur), (sum(d.leads_mensuels(a, None, projet)[m - 1] for a, m in rv.prec.mois()))
    puces = [f"{nom} above {per.annee - 1} in {len(ups)} of the {len(ms)} months of {rt._q(per)}" + (f" ({', '.join(ups)})." if ups else "."),
             f"Quarter total: {nb(lq)} ({rt._signe(evol(lq, sum(n1)))} YoY, {rt._signe(evol(lq, lp))} QoQ)."]
    series = _series_mois(ctx, rv, projet, None)
    if not series:
        return None
    s = diapo(ctx, rv, "Global overview", "Global NC leads by Month" if projet else "Global leads by Month", f"Monthly {nom.lower()}, last three years.")
    image(s, mg.colonnes_mois(10.4, 5.0, series, taille=6.5), 0.4, 1.55, 10.4, 5.0, alt=alt("Leads by month", **{str(a_): [v or 0 for v in vals] for a_, vals, _ in series}))
    y = 1.8
    for t in puces:
        forme(s, MSO_SHAPE.OVAL, 11.0, y + 0.07, 0.09, 0.09, INDIGO)
        texte(s, 11.18, y, 1.7, 1.6, t, taille=8.5, interligne=1.05)
        y += 0.3 + 0.17 * (1 + len(t) // 24)
    return s


def _series_mois(ctx, rv, projet, marque):
    from . import revue_trim as rt
    d, per = ctx.d, rv.per
    fin = (per.annee, per.mois()[-1][1])
    series = []
    for an, coul in ((per.annee - 2, "#DDE0FF"), (per.annee - 1, "#8E96FF"), (per.annee, "#2F3DFF")):
        v = rt._serie_annee(d, an, fin, projet, marque)
        if sum(x_ or 0 for x_ in v) > 0:
            series.append((an, v, coul))
    return series


def nc_par_mois_marque(ctx, rv, titre, marques):
    from . import revue_trim as rt
    if not marques:
        return None
    s = diapo(ctx, rv, "Global overview", titre, "New cars leads by month and by brand, last three years.")
    cases = [(0.5, 1.5), (6.9, 1.5), (0.5, 4.2), (6.9, 4.2)]
    fait = 0
    for m, (x, y) in zip(marques, cases):
        series = _series_mois(ctx, rv, "VN", m)
        texte(s, x, y, 4.0, 0.3, ctx.nom(m).upper(), taille=11, gras=True, couleur=INDIGO)
        if series:
            image(s, mg.colonnes_mois(6.0, 2.4, series, taille=4.8, legende=True), x - 0.05, y + 0.3, 6.0, 2.4,
                  alt=alt(f"{ctx.nom(m)} NC leads by month", **{str(a_): [v or 0 for v in vals] for a_, vals, _ in series}))
            fait += 1
    return s if fait else None


def lead_management_c1st(ctx, rv, groupe, marques):
    from . import revue_trim as rt
    from .revue_commun import mois_label, nb
    from .periodes import Periode
    from .revue_trim import SANS_SUIVI_C1ST
    d, per = ctx.d, rv.per
    marques = [m for m in marques if m in d.marques and m not in SANS_SUIVI_C1ST]
    mois = rt._mois_c1st(rv)
    ser = [(a, m, rt._c1st_somme(d, Periode("mois", a, m), marques)) for a, m in mois]
    ok = [x for x in ser if x[2] and x[2]["clients_envoyes"]]
    tq = rt._c1st_somme(d, per, marques)
    if not ok or not tq or not tq["clients_envoyes"]:
        return None
    s = diapo(ctx, rv, "Sales performance", "SALES PERFORMANCE", f"autobiz lead management - VN type 1 {groupe} brands - C1ST \u00b7 {mois_label(per)}")
    cats = [f"{m:02d}/{a % 100}" for a, m, t in ok]
    div = lambda a, b: (a / b) if b else None
    W, H = 4.0, 2.55
    X = [0.6, 0.6 + W + 0.1, 0.6 + 2 * (W + 0.1)]
    Y = [1.5, 1.5 + H + 0.12]

    def panneau(x, y, titre):
        forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, W, H, "FFFFFF", rayon=0.03, contour="E3E7EE")
        texte(s, x + 0.15, y + 0.08, W - 0.3, 0.22, titre.upper(), taille=7.5, gras=True, couleur=GRIS, espacement=100)
    panneau(X[0], Y[0], "# Leads generated by month")
    image(s, mg.colonnes_simples(W - 0.2, H - 0.4, cats, [t["leads"] for _, _, t in ok], taille=6), X[0] + 0.1, Y[0] + 0.32, W - 0.2, H - 0.4, alt=alt("Leads generated by month", leads=[t["leads"] for _, _, t in ok]))
    st = d.c1st_statuts(per, marques)
    if st:
        tot = sum(st.values())
        ordre = sorted(st, key=lambda k: k.split(".")[0].zfill(2) if k.split(".")[0].isdigit() else "99")
        panneau(X[1], Y[0], "# Leads generated by status")
        lig = [(k.split(".", 1)[-1].strip(), st[k] / tot * 100, 0, 0) for k in ordre]
        image(s, mg.barres_marques(W - 0.2, H - 0.4, lig, taille=7, fmt=lambda v: f"{v:.0f}%", parts=False), X[1] + 0.1, Y[0] + 0.32, W - 0.2, H - 0.4,
              alt=alt("Leads by status", **{n_: [v] for n_, v, _, _ in lig}))
    else:
        panneau(X[1], Y[0], f"# Customers sent by follow-up stage ({mois_label(per)})")
        etapes = [("Sent to dealers", tq["clients_envoyes"]), ("Contacted", tq["contactes"]), ("Contacted on time", tq["contactes_delai"]), ("1st call on time", tq["premier_appel_delai"]),
                  ("Treated", tq["traites"]), ("With opportunity", tq["avec_opp"])]
        lig = [(n_, v, v / tq["clients_envoyes"] * 100, 0) for n_, v in etapes]
        image(s, mg.barres_marques(W - 0.2, H - 0.4, lig, taille=7), X[1] + 0.1, Y[0] + 0.32, W - 0.2, H - 0.4, alt=alt("Customers by follow-up stage", **{n_: [v] for n_, v, _, _ in lig}))
    suivi = lambda t: t["contactes"] or t["premier_appel_delai"] or t["traites"]
    graphes = [("% 1st call attempt on time", lambda t: div(t["premier_appel_delai"], t["clients_envoyes"]) if suivi(t) else None, X[2], Y[0]),
               ("% Contacted", lambda t: div(t["contactes"], t["clients_envoyes"]) if suivi(t) else None, X[0], Y[1]),
               ("% With quotes", lambda t: div(t["avec_devis"], t["clients_uniques"]), X[1], Y[1]),
               ("% NSC orders", lambda t: div(t["commandes"], t["clients_uniques"]), X[2], Y[1])]
    for titre, f, x, y in graphes:
        panneau(x, y, titre)
        vals = [f(t) for _, _, t in ok]
        image(s, mg.lignes_multi(W - 0.2, H - 0.4, cats, [(titre, vals, "#2F3DFF")], pct=True, taille=6.5), x + 0.1, y + 0.32, W - 0.2, H - 0.4,
              alt=alt(titre, **{"pct": [None if v is None else v * 100 for v in vals]}))
    nt = 1 - tq["traites"] / tq["clients_envoyes"]
    tp = rt._c1st_somme(d, rv.prec, marques)
    txt = f"{nt * 100:.0f}% of leads not managed in {mois_label(per)}"
    if tp and tp["clients_envoyes"]:
        dd = (nt - (1 - tp["traites"] / tp["clients_envoyes"])) * 100
        txt += f" ({'+' if dd >= 0 else '-'}{abs(dd):.0f}pt QoQ)"
    if set(rv.pays) & {"DE", "PL", "AT", "GB"}:
        txt += " Note: dealers' follow-up statuses are barely filled in C1ST for this market (contact / treatment rates are not reliable)."
    txt += f"; {tq['contactes'] / tq['clients_envoyes'] * 100:.0f}% contacted, {tq['commandes'] / tq['clients_uniques'] * 100:.0f}% NSC orders (still maturing: orders are linked up to 90 days after the lead)."
    forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, 6.52, 12.2, 0.46, PALE, rayon=0.1)
    texte(s, 0.8, 6.52, 11.8, 0.46, txt, taille=8.5, ancre=MSO_ANCHOR.MIDDLE, interligne=1.0)
    return s


def leads_vn_c1st(ctx, rv, groupe, marques):
    from . import revue_trim as rt
    from .periodes import Periode
    from .revue_commun import nb
    from .revue_global import COULEUR_MARQUE
    from .revue_trim import SANS_SUIVI_C1ST
    d, per = ctx.d, rv.per
    marques = [m for m in marques if m in d.marques and m not in SANS_SUIVI_C1ST]
    mois = rt._mois_c1st(rv)
    data = {}
    for m in marques:
        data[m] = []
        for a, mo in mois:
            p = Periode("mois", a, mo)
            c, n = d.c1st(p, m), d.c1st_nsc(p, m)
            data[m].append((c["leads"] if c else None, n))
    vues = [i for i in range(len(mois)) if any(data[m][i][0] is not None for m in marques)]
    marques = [m for m in marques if any(data[m][i][0] for i in vues)]
    if not vues or not marques:
        return None
    tq = {m: (d.c1st(per, m), d.c1st_nsc(per, m)) for m in marques}
    if not any(c for c, n in tq.values()):
        return None
    cats = [f"{mois[i][1]:02d}/{mois[i][0] % 100}" for i in vues]
    coul = lambda m: "#" + COULEUR_MARQUE.get(m, "BAB0AC")
    s = diapo(ctx, rv, "Sales performance", f"SALES PERFORMANCE: leads VN {groupe} autobiz", "Leads, % NSC orders and NSC orders by month and brand.")
    sl, so = [(ctx.nom(m), [data[m][i][0] or 0 for i in vues], coul(m)) for m in marques], [(ctx.nom(m), [data[m][i][1] or 0 for i in vues], coul(m)) for m in marques]
    texte(s, 0.6, 1.45, 5.0, 0.22, "# LEADS GENERATED", taille=8.5, gras=True, couleur=GRIS, espacement=120)
    image(s, mg.colonnes_empilees(10.3, 1.75, cats, sl, taille=5.5), 0.45, 1.65, 10.3, 1.75, alt=alt("Leads generated by brand and month", **{n_: v_ for n_, v_, _ in sl}) + " (" + ", ".join(cats) + ")")
    texte(s, 0.6, 3.45, 8.0, 0.22, "% NSC ORDERS (NSC ORDERS / LEADS, MONTHS WITH AT LEAST 20 LEADS)", taille=8.5, gras=True, couleur=GRIS, espacement=100)
    sp = [(ctx.nom(m), [(data[m][i][1] / data[m][i][0]) if (data[m][i][0] and data[m][i][0] >= 20 and data[m][i][1] is not None) else None for i in vues], coul(m)) for m in marques]
    image(s, mg.lignes_multi(10.3, 1.7, cats, sp, pct=True, taille=6.5, etiquettes=False), 0.45, 3.65, 10.3, 1.7, alt=alt("% NSC orders by brand", **{n_: [None if x is None else x * 100 for x in v_] for n_, v_, _ in sp}))
    texte(s, 0.6, 5.4, 5.0, 0.22, "NSC ORDERS", taille=8.5, gras=True, couleur=GRIS, espacement=120)
    image(s, mg.colonnes_empilees(10.3, 1.55, cats, so, taille=5.5), 0.45, 5.6, 10.3, 1.45, alt=alt("NSC orders by brand and month", **{n_: v_ for n_, v_, _ in so}) + " (" + ", ".join(cats) + ")")
    lignes = [[{"t": h, "taille": 7, "gras": True, "couleur": GRIS, "align": PP_ALIGN.LEFT if i == 0 else PP_ALIGN.CENTER} for i, h in enumerate(("Brand", "# Leads", "# Orders", "% Orders"))]]
    taux = []
    for m in marques:
        c, n = tq[m]
        if c is None or n is None:
            continue
        lignes.append([{"t": ctx.nom(m), "taille": 7.5, "align": PP_ALIGN.LEFT, "gras": True}, {"t": nb(c["leads"]), "taille": 7.5}, {"t": nb(n), "taille": 7.5}, {"t": f"{n / c['leads'] * 100:.1f}%" if c["leads"] else "\u2013", "taille": 7.5, "gras": True, "couleur": INDIGO}])
        if c["leads"] >= 50:
            taux.append((ctx.nom(m), n / c["leads"] * 100))
    tl = sum(tq[m][0]["leads"] for m in marques if tq[m][0] and tq[m][1] is not None)
    to = sum(tq[m][1] for m in marques if tq[m][0] and tq[m][1] is not None)
    puces = [f"{nb(to)} NSC orders from {nb(tl)} leads in {rt._q(per)} ({to / tl * 100:.1f}%)." if tl else "No lead in the quarter."]
    if taux:
        best = sorted(taux, key=lambda x: -x[1])[:2]
        puces.append("Best order rate: " + ", ".join(f"{n_} {v:.1f}%" for n_, v in best) + ".")
    puces.append("Orders are linked to leads up to 90 days after the lead: recent months are provisional.")
    y = 1.6
    for t in puces:
        forme(s, MSO_SHAPE.OVAL, 10.95, y + 0.06, 0.09, 0.09, INDIGO)
        texte(s, 11.12, y, 1.75, 1.2, t, taille=8, interligne=1.0)
        y += 0.2 + 0.14 * (1 + len(t) // 24)
    if len(lignes) > 1:
        grille(s, 10.95, max(y + 0.1, 4.3), [0.7, 0.4, 0.4, 0.4], [0.3] + [0.26] * (len(lignes) - 1), lignes)
    return s


def ventes_additionnelles(ctx, rv):
    from . import revue_trim as rt
    from .revue_commun import evol, nb
    from .revue_trim import SANS_SUIVI_C1ST
    d, per = ctx.d, rv.per
    lignes, tot = [], [0] * 6
    for m in d.marques:
        if m in SANS_SUIVI_C1ST:
            continue
        a, b = d.c1st(per, m), d.c1st(rv.n1, m)
        na, nb_ = d.c1st_nsc(per, m), d.c1st_nsc(rv.n1, m)
        if a is None or b is None or na is None or nb_ is None:
            continue
        lignes.append((m, b["leads"], a["leads"], nb_, na))
        tot = [tot[0] + b["leads"], tot[1] + a["leads"], tot[2] + nb_, tot[3] + na]
    if not lignes:
        return None
    s = diapo(ctx, rv, "Sales performance", "SALES PERFORMANCE: additional business", f"{rt._q(per).replace('-', ' ')}* \u2013 orders linked to leads, vs {rv.n1.annee}.")
    ent = ["Brand", f"# Leads {rv.n1.annee}", f"# Leads {per.annee}", f"Evol lead {per.annee} vs {rv.n1.annee}", f"% Orders {rv.n1.annee}", f"# Orders {rv.n1.annee}",
           f"% Orders {per.annee}", f"# Orders {per.annee}", "Increase sales", f"Evol {per.annee} vs {rv.n1.annee}"]
    rows = [[{"t": h, "taille": 8, "gras": True, "couleur": GRIS, "align": PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER} for j, h in enumerate(ent)]]
    pc = lambda a, b: f"{a / b * 100:.1f}%" if b else "\u2013"

    def ligne(nom, l1, l2, o1, o2, total=False):
        inc = o2 - o1
        e_l, e_o = evol(l2, l1), evol(o2, o1)
        cells = [nom, nb(l1), nb(l2), rt._signe(e_l) if e_l is not None else "\u2013", pc(o1, l1), nb(o1), pc(o2, l2), nb(o2), f"{inc:+d}" if inc else "0", rt._signe(e_o) if e_o is not None else "\u2013"]
        out = []
        for j, t in enumerate(cells):
            sp = {"t": t, "taille": 9.5, "gras": total or j in (0, 7, 8), "align": PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER, "fond": "F4F5FB" if total else None}
            if j == 3 and e_l is not None:
                sp["couleur"] = "C62839" if e_l < 0 else "0F7B45"
            if j in (8, 9) and (inc if j == 8 else (e_o or 0)) != 0:
                sp["couleur"] = "0F7B45" if (inc if j == 8 else e_o) > 0 else "C62839"
            if j == 8:
                sp["fond"] = "E3F6EC" if inc > 0 else "FDE7EA" if inc < 0 else sp["fond"]
            out.append(sp)
        return out
    for m, l1, l2, o1, o2 in lignes:
        rows.append(ligne(ctx.nom(m), l1, l2, o1, o2))
    rows.append(ligne("Total", tot[0], tot[1], tot[2], tot[3], True))
    hs = [0.5] + [min(0.36, 4.2 / (len(rows) - 1))] * (len(rows) - 1)
    yy = grille(s, 0.6, 1.55, [1.7] + [1.17] * 9, hs, rows)
    moins = [ctx.nom(m) for m, l1, l2, o1, o2 in lignes if o2 - o1 < 0]
    inc = tot[3] - tot[2]
    txt = f"On {rt._q(per).split('-')[0]}, {abs(inc)} {'additional' if inc >= 0 else 'fewer'} sales vs {rv.n1.annee}" + (f", except for {rt._liste(moins)}" if moins and inc >= 0 else "") + "."
    forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, yy + 0.2, 12.2, 0.5, PALE, rayon=0.1)
    texte(s, 0.8, yy + 0.2, 11.8, 0.5, txt, taille=11, gras=True, ancre=MSO_ANCHOR.MIDDLE)
    texte(s, 0.6, 6.75, 11.0, 0.25, "*figures are still moving: NSC orders are linked to the lead up to 90 days after its creation. Source: C1ST, VN type 1 leads sent to dealers (Autobiz campaign) \u2014 C1ST scope; orders = NSC orders (SUB set)", taille=7.5, couleur=GRIS)
    return s


# Correspondance « constructeur V1 -> constructeur V2 » (clé = nom de la fonction d'origine) ; ce qui n'y figure pas reste au design V1 dans un deck V2.
REMPLACANTS = {
    "resume_executif": resume_executif, "vue_globale": vue_globale, "tendance_leads": tendance_leads,
    "projets_groupe": projets_groupe, "canaux": canaux, "conversion_ventes_nc": conversion_ventes_nc,
    "trafic": trafic, "ytd": ytd, "site_principal": site_principal, "conquete": conquete, "focus_v2": focus_v2, "focus_v2_entree": focus_v2_entree,
    "trafic_leads_apercu": trafic_leads_apercu, "projection_nc": projection_nc, "nc_marches": nc_marches, "nc_entonnoirs": nc_entonnoirs,
    "global_overview": global_overview, "leads_par_marque": leads_par_marque, "leads_par_mois": leads_par_mois, "nc_par_mois_marque": nc_par_mois_marque,
    "lead_management_c1st": lead_management_c1st, "leads_vn_c1st": leads_vn_c1st, "ventes_additionnelles": ventes_additionnelles,
}


def remplacant(f):
    """Constructeur V2 équivalent de `f` (constructeur V1), ou `f` lui-même s'il n'y en a pas encore."""
    return REMPLACANTS.get(getattr(f, "__name__", ""), f)


# ============================================================ habillage des diapositives encore au design V1 (même contenu, cadre V2)
CORRESP_PROJETS = {"4E79A7": "2F3DFF", "E15759": "FF4D6D", "F28E2B": "FFA23A"}          # bleu / rouge / orange des projets d'achat, en teintes V2
CORRESP_ANNEES = {"76B7B2": "C9CEFF", "F28E2B": "2F3DFF"}                                  # barres N-1 (vert d'eau) et N (orange) -> lavande et indigo
SOMBRES_V1 = {"000080", "043882", "002060", "1F3864", "1F3F7A", "1F2A6B"}
GRIS_V1 = {"E6E6E6", "D9D9D9", "F2F2F2", "EDEDED", "E7E6E6"}
EMU = 914400


def _pouces(sh):
    return sh.left / EMU, sh.top / EMU, sh.width / EMU, sh.height / EMU


def _police(sh_ou_tf, taille=None, gras=None, couleur=None, nom=POLICE):
    tf = sh_ou_tf.text_frame if hasattr(sh_ou_tf, "text_frame") else sh_ou_tf
    for p in tf.paragraphs:
        for r in p.runs:
            if nom:
                r.font.name = nom
            if taille is not None:
                r.font.size = Pt(taille)
            if gras is not None:
                r.font.bold = gras
            if couleur:
                r.font.color.rgb = rgb(couleur)


def _recolore_graphique(chart):
    """Palette V2 sur un graphique natif (données inchangées) : couleurs des projets d'achat ; barres N-1 / N en lavande / indigo."""
    from pptx.oxml.ns import qn
    cs = chart._chartSpace
    for ser in cs.iter(qn("c:ser")):
        tx = ser.find(qn("c:tx"))
        nom = "".join(t.text or "" for t in (tx.iter(qn("c:v")) if tx is not None else [])).strip()
        annee = nom.isdigit() and len(nom) == 4
        tab = CORRESP_ANNEES if annee else CORRESP_PROJETS
        for c in ser.iter(qn("a:srgbClr")):
            v = (c.get("val") or "").upper()
            if v in tab:
                c.set("val", tab[v])


def _habille_une(ctx, rv, s, idx, section):
    from pptx.enum.dml import MSO_LINE
    from pptx.oxml.ns import qn
    titre_sh = s.shapes.title
    titre = titre_sh.text_frame.text.strip().replace("\n", " ") if titre_sh is not None else ""
    sous_sh = next((ph for ph in s.placeholders if ph.placeholder_format.idx == 12), None)
    sous = sous_sh.text_frame.text.strip().replace("\n", " ") if sous_sh is not None else ""
    photos = [sh for sh in s.shapes if sh.shape_type == 13]
    logo_marque = next((sh for sh in photos if 4.3 <= _pouces(sh)[0] <= 8.4 and _pouces(sh)[1] < 1.0 and _pouces(sh)[3] < 1.0), None)
    drapeau = next((sh for sh in photos if sh is not logo_marque and _pouces(sh)[0] >= 9.4 and _pouces(sh)[1] < 1.0 and _pouces(sh)[2] < 1.4), None)
    pied = sorted([sh for sh in s.shapes if sh.shape_type == 17 and sh.top / EMU >= 7.0], key=lambda sh: sh.left)
    boite = next((sh for sh in s.shapes if sh.shape_type == 1 and abs(sh.left / EMU - 11.12) < 0.06 and abs(sh.width / EMU - 2.11) < 0.06), None)
    # 1. fond blanc plein cadre : recouvre les décors du gabarit
    s.background.fill.solid(); s.background.fill.fore_color.rgb = rgb("FFFFFF")
    cache = forme(s, MSO_SHAPE.RECTANGLE, -0.05, -0.05, 13.5, 7.65, "FFFFFF")
    cache.name = "Fond V2"
    tree = s.shapes._spTree
    tree.remove(cache._element); tree.insert(2, cache._element)
    # 2. surtitre, titre, sous-titre
    if titre_sh is not None:
        n = len(titre)
        taille = 24 if n <= 32 else 20 if n <= 46 else 17
        largeur = 6.0 if (sous or logo_marque) else 9.4
        titre_sh.left, titre_sh.top, titre_sh.width, titre_sh.height = Inches(0.6), Inches(0.66), Inches(largeur), Inches(0.5)
        tf = titre_sh.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.TOP
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        _police(tf, taille, True, ENCRE)
    if section:
        texte(s, 0.6, 0.38, 7.0, 0.22, section.upper(), taille=9, gras=True, couleur=INDIGO, espacement=140)
    if sous_sh is not None and sous:
        sous_sh.left, sous_sh.top, sous_sh.width, sous_sh.height = Inches(6.8), Inches(0.42), Inches(2.9 if logo_marque else 4.3), Inches(0.6)
        tf = sous_sh.text_frame; tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        _police(tf, 10.5, False, GRIS)
    # 3. logos et drapeau
    s.shapes.add_picture(str(AIR / "logo_autobiz_encre.png"), Inches(11.75), Inches(0.42), Inches(1.0), Inches(0.27))
    if drapeau is not None:
        drapeau.left, drapeau.top, drapeau.width, drapeau.height = Inches(11.2), Inches(0.44), Inches(0.4), Inches(0.24)
    if logo_marque is not None:
        x0, y0, w0, h0 = _pouces(logo_marque)
        k = min(0.55 / h0, 1.1 / w0)
        logo_marque.left, logo_marque.top, logo_marque.width, logo_marque.height = Inches(9.95 - (w0 * k - 1.0) if w0 * k > 1.0 else 9.95), Inches(0.3), Inches(w0 * k), Inches(h0 * k)
    # 4. pied de page
    for i, sh in enumerate(pied):
        sh.top = Inches(7.08); sh.height = Inches(0.25)
        sh.left = Inches(0.6 if i == 0 else 1.9)
        if i == 0:
            sh.width = Inches(1.2)
        _police(sh, 8.5, False, "A0A5B8", nom=None)
    texte(s, 12.0, 7.08, 0.75, 0.2, f"{idx:02d}", taille=8.5, couleur="A0A5B8", align=PP_ALIGN.RIGHT)
    # 5. encadré de commentaires et encadrés pointillés
    for sh in s.shapes:
        if sh.shape_type != 1:
            continue
        try:
            dash = sh.line.dash_style is not None
        except Exception:
            dash = False
        if sh is boite:
            sh.fill.solid(); sh.fill.fore_color.rgb = rgb(PALE); sh.line.fill.background()
            geom = sh._element.spPr.find(qn("a:prstGeom"))
            if geom is not None:
                geom.set("prst", "roundRect")
                av = geom.find(qn("a:avLst"))
                if av is None:
                    av = geom.makeelement(qn("a:avLst"), {}); geom.append(av)
                for e in list(av):
                    av.remove(e)
                gd = av.makeelement(qn("a:gd"), {"name": "adj", "fmla": "val 4000"}); av.append(gd)
            _police(sh, None, None, ENCRE, nom=None)
        elif dash:
            sh.line.dash_style = MSO_LINE.SOLID; sh.line.color.rgb = rgb("DFE4EE"); sh.line.width = Pt(0.75)
        else:
            try:
                if sh.fill.type == 1:
                    v = str(sh.fill.fore_color.rgb).upper()
                    if v in SOMBRES_V1:
                        sh.fill.fore_color.rgb = rgb("10173F")
                    elif v in GRIS_V1:
                        sh.fill.fore_color.rgb = rgb("F4F5FB")
            except Exception:
                pass
    # 6. graphiques et tableaux : palette V2, données intactes
    for sh in s.shapes:
        if sh.has_chart:
            _recolore_graphique(sh.chart)
        elif getattr(sh, "has_table", False) and sh.has_table:
            for row in sh.table.rows:
                for c in row.cells:
                    try:
                        if c.fill.type == 1:
                            v = str(c.fill.fore_color.rgb).upper()
                            if v in SOMBRES_V1:
                                c.fill.fore_color.rgb = rgb("10173F")
                            elif v in GRIS_V1:
                                c.fill.fore_color.rgb = rgb("F4F5FB")
                    except Exception:
                        pass


def habille(ctx, rv):
    """Dernière passe d'un deck V2 : chaque diapositive restée au design V1 reçoit le cadre V2 (fond, surtitre, titre, logo, pied de page, encadrés, palette), sans toucher aux données."""
    section = ""
    faites = 0
    for idx, s in enumerate(ctx.prs.slides, 1):
        if s.slide_id in getattr(ctx, "v2_slides", set()):
            section = getattr(ctx, "v2_sections", {}).get(s.slide_id, section)
            continue
        try:
            _habille_une(ctx, rv, s, idx, section)
            faites += 1
        except Exception as e:
            ctx.avertissements.append(f"Habillage V2 impossible pour la diapositive {idx} : {type(e).__name__}: {e}")
    if faites:
        ctx.avertissements.append(f"Design V2 : {len(ctx.prs.slides) - faites} diapositive(s) redessinée(s), {faites} habillée(s) au cadre V2 en attendant leur refonte.")
    return faites
