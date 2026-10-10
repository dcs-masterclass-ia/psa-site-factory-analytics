"""Éléments de présentation : graphiques PowerPoint NATIFS (éditables), tableaux, tuiles, textes."""

from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_TICK_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

BLEU = "1F3F7A"        # titres autobiz
ORANGE = "FF5A00"      # filet autobiz
TEXTE = "1F2937"
GRIS = "6B7280"
GRIS_CLAIR = "E5E7EB"
FOND_TUILE = "F3F6FB"
VERT, ROUGE = "2B8F62", "C0392B"

# séries : N-2, N-1, courante / projets
COULEURS_PERIODES = ["4E79A7", "E9C846", "76B7B2"]
COULEURS_PROJETS = {"VN": "4E79A7", "SANS": "E15759", "VO": "F28E2B"}
COULEURS_CANAUX = ["F28E2B", "4E79A7", "76B7B2", "E15759", "9C755F", "BAB0AC", "EDC948", "59A14F", "B07AA1", "FF9DA7"]


def rgb(h):
    return RGBColor.from_string(h)


def texte(slide, x, y, w, h, contenu, taille=12, gras=False, couleur=TEXTE, align=PP_ALIGN.LEFT, ancre=MSO_ANCHOR.TOP, italique=False):
    """Boîte de texte. `contenu` : str ou liste de paragraphes (str ou (str, {options}))."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = ancre
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    paras = contenu if isinstance(contenu, list) else [contenu]
    for i, p in enumerate(paras):
        opts = {}
        if isinstance(p, tuple):
            p, opts = p
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = opts.get("align", align)
        para.space_after = Pt(opts.get("apres", 4))
        run = para.add_run()
        run.text = p
        f = run.font
        f.size = Pt(opts.get("taille", taille))
        f.bold = opts.get("gras", gras)
        f.italic = opts.get("italique", italique)
        f.color.rgb = rgb(opts.get("couleur", couleur))
    return tb


def puces(slide, x, y, w, h, lignes, taille=12, couleur=TEXTE):
    """Liste à puces simple (caractère • dans le texte, retrait suspendu)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    for i, l in enumerate(lignes):
        gras = False
        if isinstance(l, tuple):
            l, gras = l
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.space_after = Pt(6)
        r = para.add_run()
        r.text = ("• " if not gras else "") + l
        r.font.size = Pt(taille)
        r.font.bold = gras
        r.font.color.rgb = rgb(couleur)
    return tb


def tuile(slide, x, y, w, h, etiquette, valeur, detail=None, couleur_detail=GRIS, taille_valeur=26):
    """Tuile de chiffre clé (rectangle arrondi + valeur + détail)."""
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.08
    s.fill.solid(); s.fill.fore_color.rgb = rgb(FOND_TUILE)
    s.line.color.rgb = rgb(GRIS_CLAIR); s.line.width = Pt(0.75)
    s.shadow.inherit = False
    texte(slide, x + 0.1, y + 0.06, w - 0.2, 0.3, etiquette, taille=10.5, couleur=GRIS)
    texte(slide, x + 0.1, y + 0.34, w - 0.2, 0.55, valeur, taille=taille_valeur, gras=True, couleur=BLEU)
    if detail:
        texte(slide, x + 0.1, y + h - 0.42, w - 0.2, 0.36, detail, taille=10.5, couleur=couleur_detail)
    return s


def fleche(slide, x, y, w, h, etiquette=None):
    s = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = rgb(ORANGE); s.line.fill.background(); s.shadow.inherit = False
    if etiquette:
        texte(slide, x - 0.25, y + h + 0.0, w + 0.5, 0.3, etiquette, taille=10.5, gras=True, couleur=ORANGE, align=PP_ALIGN.CENTER)
    return s


def _police(obj, taille, couleur=TEXTE, gras=False):
    obj.font.size = Pt(taille)
    obj.font.color.rgb = rgb(couleur)
    obj.font.bold = gras


def colonnes(slide, x, y, w, h, categories, series, empile=False, pourcentage=False, legende=True, taille=10, etiquettes=True,
             libelles_perso=None, format_nombre="#,##0", largeur_barre=60, axe_valeurs=False, fmt=None):
    """Histogramme natif. series = [(nom, [valeurs], couleur_hex)].
    libelles_perso = {indice_série: [texte par catégorie]} pour des étiquettes personnalisées (ex. valeur + évolution)."""
    if not categories:
        return texte(slide, x, y, w, 0.4, "Aucune donnée sur ce périmètre.", taille=11, couleur=GRIS, italique=True)
    cd = CategoryChartData()
    cd.categories = categories
    for nom, vals, _ in series:
        cd.add_series(nom, list(vals))
    typ = XL_CHART_TYPE.COLUMN_STACKED_100 if (empile and pourcentage) else XL_CHART_TYPE.COLUMN_STACKED if empile else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = slide.shapes.add_chart(typ, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.font.size = Pt(taille); ch.font.color.rgb = rgb(TEXTE)
    ch.has_title = False
    ch.has_legend = legende
    if legende:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
        _police(ch.legend, taille)
    va = ch.value_axis
    va.visible = axe_valeurs
    va.has_major_gridlines = axe_valeurs
    if axe_valeurs:
        va.major_gridlines.format.line.color.rgb = rgb(GRIS_CLAIR)
        va.format.line.fill.background()
        va.tick_labels.font.size = Pt(taille - 1)
    ca = ch.category_axis
    ca.format.line.color.rgb = rgb(GRIS_CLAIR)
    ca.tick_labels.font.size = Pt(taille)
    ca.has_major_gridlines = False
    plot = ch.plots[0]
    plot.gap_width = largeur_barre if not empile else 45
    if not empile:
        plot.overlap = -5
    for i, (nom, vals, coul) in enumerate(series):
        s = plot.series[i]
        s.format.fill.solid(); s.format.fill.fore_color.rgb = rgb(coul)
        s.invert_if_negative = False
        if etiquettes:
            dl = s.data_labels
            dl.show_value = True
            dl.number_format = format_nombre
            dl.number_format_is_linked = False
            dl.font.size = Pt(taille - 1)
            dl.font.color.rgb = rgb("FFFFFF" if empile else TEXTE)
            dl.position = XL_LABEL_POSITION.CENTER if empile else XL_LABEL_POSITION.OUTSIDE_END
            if fmt and not (libelles_perso and i in libelles_perso):
                # étiquettes écrites par nous : même format de nombre (langue) que le reste de la présentation
                libelles_perso = dict(libelles_perso or {})
                libelles_perso[i] = [fmt(v) if v else None for v in vals]
        if libelles_perso and i in libelles_perso:
            for j, t in enumerate(libelles_perso[i]):
                if t is None:
                    continue
                tf = s.points[j].data_label.text_frame
                tf.text = t
                for p in tf.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(taille - 1)
                        r.font.color.rgb = rgb("FFFFFF" if empile else TEXTE)
                s.points[j].data_label.position = XL_LABEL_POSITION.CENTER if empile else XL_LABEL_POSITION.OUTSIDE_END
    return gf


def anneau(slide, x, y, w, h, categories, valeurs, couleurs=None, taille=10):
    """Anneau natif avec étiquettes de pourcentage."""
    if not categories or not sum(valeurs):
        return texte(slide, x, y, w, 0.4, "Aucune donnée sur ce périmètre.", taille=11, couleur=GRIS, italique=True)
    total0 = sum(valeurs)
    cd = CategoryChartData()
    cd.categories = [f"{c} ({v / total0 * 100:.0f} %)" for c, v in zip(categories, valeurs)]   # parts dans la légende : pas d'étiquettes qui se chevauchent
    cd.add_series("Part", valeurs)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.has_title = False
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.RIGHT
    ch.legend.include_in_layout = False
    _police(ch.legend, taille)
    plot = ch.plots[0]
    plot.has_data_labels = False
    s = plot.series[0]
    total = sum(valeurs) or 1
    for j in range(len(categories)):
        pt = s.points[j]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb((couleurs or COULEURS_CANAUX)[j % len(couleurs or COULEURS_CANAUX)])
    return gf


def tableau(slide, x, y, w, lignes, largeurs=None, taille=10, hauteur_ligne=0.3, entete=True, alignements=None, gras_derniere=False, colonnes_gras=()):
    """Tableau natif. lignes = liste de listes de str. largeurs en pouces (somme = w)."""
    nl, nc = len(lignes), len(lignes[0])
    gf = slide.shapes.add_table(nl, nc, Inches(x), Inches(y), Inches(w), Inches(hauteur_ligne * nl))
    tb = gf.table
    tb.first_row = entete
    if largeurs:
        for j, lw in enumerate(largeurs):
            tb.columns[j].width = Inches(lw)
    for i in range(nl):
        tb.rows[i].height = Inches(hauteur_ligne)
        for j in range(nc):
            c = tb.cell(i, j)
            c.margin_left = c.margin_right = Inches(0.05)
            c.margin_top = c.margin_bottom = Inches(0.02)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.text = str(lignes[i][j])
            for p in c.text_frame.paragraphs:
                p.alignment = (alignements[j] if alignements else (PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT))
                for r in p.runs:
                    r.font.size = Pt(taille)
                    r.font.bold = (i == 0 and entete) or (gras_derniere and i == nl - 1) or (j in colonnes_gras)
                    r.font.color.rgb = rgb("FFFFFF" if (i == 0 and entete) else TEXTE)
            c.fill.solid()
            if i == 0 and entete:
                c.fill.fore_color.rgb = rgb(BLEU)
            elif gras_derniere and i == nl - 1:
                c.fill.fore_color.rgb = rgb(GRIS_CLAIR)
            else:
                c.fill.fore_color.rgb = rgb("FFFFFF" if i % 2 else "F8FAFC")
    return gf


def encadre(slide, x, y, w, h, titre, lignes, taille=11.5, couleur=None):
    """Encadré de commentaires (filet orange à gauche), pour les analyses calculées. La hauteur s'ajuste au contenu (h = maximum)."""
    cpl = max(20, int(w * 72 / (taille * 0.5)))           # caractères par ligne (approx.)
    nb = sum(max(1, -(-len(l if isinstance(l, str) else l[0]) // cpl)) for l in lignes)
    h = min(h, (0.34 if titre else 0.05) + nb * (taille * 1.45 / 72) + 0.1 * len(lignes) + 0.1)
    barre = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(0.05), Inches(h))
    barre.fill.solid(); barre.fill.fore_color.rgb = rgb(couleur or ORANGE); barre.line.fill.background(); barre.shadow.inherit = False
    if titre:
        texte(slide, x + 0.15, y, w - 0.15, 0.32, titre, taille=12, gras=True, couleur=couleur or BLEU)
    puces(slide, x + 0.1, y + (0.34 if titre else 0), w - 0.1, h - (0.34 if titre else 0), lignes, taille=taille)
