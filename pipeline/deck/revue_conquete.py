"""Revue mensuelle France : diapositive « Conquest & loyalty » (une par marque), graphiques et tableau natifs d'après la capture Tableau du deck de référence."""

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from . import graphiques as g
from .donnees import MARQUES_STELLANTIS, norme_marque
from .revue_commun import mois_label, nb as _nb, slide_revue


def nb(v):
    return _nb(v).replace(" ", "\u00a0")

COULEURS = ["4E79A7", "9C755F", "FF9DA7", "F28E2B", "76B7B2", "EDC948", "E15759", "76B7B2", "59A14F", "E15759"]
C_PIE = {"fideles": "4E79A7", "stla": "A0CBE8", "conq": "76B7B2"}
GRIS_PANNEAU = "BFBFBF"
DECK_NA = "n/a"


def _panneau(slide, x, y, w, h, titre):
    r = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.background(); r.shadow.inherit = False
    r.line.color.rgb = g.rgb(GRIS_PANNEAU); r.line.width = Pt(0.75)
    g.texte(slide, x + 0.03, y + 0.03, w - 0.1, 0.3, titre, taille=12, couleur="404040")


def _na(slide, x, y, w, h):
    g.texte(slide, x, y + h / 2 - 0.15, w, 0.3, DECK_NA, taille=12, couleur=g.GRIS, align=PP_ALIGN.CENTER)


def _barres_h(slide, x, y, w, h, cats, vals, taille=8, pct=False):
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("n", vals)
    ch = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    ch.has_legend = False; ch.has_title = False
    ch.font.size = Pt(taille); ch.font.color.rgb = g.rgb("404040")
    ch.value_axis.visible = False; ch.value_axis.has_major_gridlines = False
    ch.category_axis.reverse_order = True
    ch.category_axis.format.line.fill.background()
    ch.category_axis.has_major_gridlines = False
    pl = ch.plots[0]
    pl.gap_width = 40
    s = pl.series[0]
    s.invert_if_negative = False
    dl = s.data_labels
    dl.show_value = True; dl.number_format = "0%" if pct else "#,##0"; dl.number_format_is_linked = False
    dl.font.size = Pt(taille); dl.position = XL_LABEL_POSITION.OUTSIDE_END
    for i in range(len(cats)):
        s.points[i].format.fill.solid(); s.points[i].format.fill.fore_color.rgb = g.rgb(COULEURS[i % len(COULEURS)])


def _colonnes_couleurs(slide, x, y, w, h, cats, vals, taille=8):
    gf = g.colonnes(slide, x, y, w, h, cats, [("n", vals, COULEURS[0])], legende=False, taille=taille, largeur_barre=40)
    s = gf.chart.plots[0].series[0]
    for i in range(len(cats)):
        s.points[i].format.fill.solid(); s.points[i].format.fill.fore_color.rgb = g.rgb(COULEURS[i % len(COULEURS)])
    return gf


def _secteurs(slide, x, y, w, h, cats, vals, couleurs, taille=9):
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("Share", vals)
    ch = slide.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    ch.has_legend = False; ch.has_title = False
    ch.font.size = Pt(taille)
    pl = ch.plots[0]
    pl.has_data_labels = True
    dl = pl.data_labels
    dl.show_percentage = True; dl.show_category_name = True; dl.show_value = False
    dl.number_format = "0%"; dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(taille)
    s = pl.series[0]
    for i, c in enumerate(couleurs):
        s.points[i].format.fill.solid(); s.points[i].format.fill.fore_color.rgb = g.rgb(c)
    return ch


def _joli(brut):
    return (brut or "").strip().title()


# la marque du site peut s'écrire autrement dans les données de reprise / d'achat (DS : « DS AUTOMOBILES »)
PROPRES = {"DS": {"DS", "DS AUTOMOBILES"}}


def conquete(ctx, rv, marque):
    """Diapositive « Conquest & loyalty – <mois> » de la marque (voir le module). None si aucune donnée de reprise sur le mois."""
    d, per = ctx.d, ctx.per
    libelle_per = mois_label(per)
    if True:                                     # retour DKAM : cette diapo porte sur l'année en cours, de janvier à la fin de la période (trimestriel ET mensuel)
        from datetime import date
        from .periodes import MOIS_COURTS, PeriodeJours
        per = PeriodeJours(date(per.annee, 1, 1), per.fin)
        libelle_per = f"Jan–{MOIS_COURTS['en'][per.fin.month - 1]} {per.fin.year} (YTD)"
    try:
        rep = d.reprises(per, marque) or {}
    except Exception:
        rep = {}
    total = sum(rep.values())
    if total <= 0:
        return None
    nm = norme_marque(marque)
    propres = PROPRES.get(marque, {nm})
    nom = ctx.nom(marque)
    fideles = sum(rep.get(k, 0) for k in propres)
    autres = sum(n for k, n in rep.items() if k not in propres and (k in MARQUES_STELLANTIS or k == "DS AUTOMOBILES"))
    conq = total - fideles - autres
    try:
        mods = d.modeles(per, marque)
    except Exception:
        mods = None

    try:
        mods_vn = d.modeles(per, marque, "VN")
    except Exception:
        mods_vn = None
    stla, hors, achat, paires = {}, {}, {}, {}
    for mr, mo, ma, mo_a, n in (mods or []):
        if mo:
            dest = stla if (mr in MARQUES_STELLANTIS or mr == "DS AUTOMOBILES") else hors
            dest[mo.upper()] = dest.get(mo.upper(), 0) + n
    if mods_vn:
        for mr, mo, ma, mo_a, n in mods_vn:
            if mo_a and ma in propres:
                achat[mo_a.upper()] = achat.get(mo_a.upper(), 0) + n
                if mo:
                    paires[(mo_a.upper(), (mr, mo.upper()))] = paires.get((mo_a.upper(), (mr, mo.upper())), 0) + n
    top_s = sorted(stla.items(), key=lambda kv: -kv[1])[:8]
    top_h = sorted(hors.items(), key=lambda kv: -kv[1])[:8]

    puces = [(f"{fideles / total * 100:.0f}% of trade-in website customers are loyalty customers ({nom} owners), {autres / total * 100:.0f}% are Stellantis customers "
              f"and {conq / total * 100:.0f}% are owners from competitors' brands.", True)]
    if top_s:
        puces.append("The top " + (f"{min(3, len(top_s))} Stellantis trade-in cars are " if len(top_s) > 1 else "Stellantis trade-in car is ")
                     + ", ".join(k.title() if False else k for k, _ in top_s[:3]) + ".")
    if top_h:
        puces.append(f"The top competitor trade-in model is the {_joli(top_h[0][0])} ({nb(top_h[0][1])} leads).")
    top_a = sorted(achat.items(), key=lambda kv: -kv[1])[:5]
    if top_a:
        pa = max(((tr, n) for (a, tr), n in paires.items() if a == top_a[0][0]), key=lambda t: t[1], default=None)
        t = f"The most requested purchase model is the {nom.title()} {_joli(top_a[0][0])} ({nb(top_a[0][1])} leads)"
        if pa:
            t += f", mostly from {_joli(pa[0][0])} {_joli(pa[0][1])} owners"
        puces.append(t + ".")

    s = slide_revue(ctx, rv, "LEAD DEEP DIVE", sous_titre=f"Conquest Vs Loyalty {libelle_per}", marque=marque, puces=puces)

    # --- panneaux (positions relevées sur la diapositive de référence)
    X1, X2, W1, W2 = 0.6, 5.7, 5.05, 5.05
    _panneau(s, X1, 1.3, W1, 2.75, "TOP Brand")
    _panneau(s, X2, 1.3, W2, 1.55, "TOP Model STLA")
    _panneau(s, X2, 2.88, W2, 1.17, "TOP Model out STLA")
    _panneau(s, X1, 4.1, W1, 2.7, "Conquest Vs Loyalty")
    _panneau(s, X2, 4.1, W2, 2.7, "NC lead by purchase project / trade-in model")

    top_b = sorted(rep.items(), key=lambda kv: (kv[0] not in propres, -kv[1]))[:10]
    _barres_h(s, X1 + 0.05, 1.6, W1 - 0.15, 2.4, [k for k, _ in top_b], [v for _, v in top_b])

    for (x, y, w, h), top in (((X2 + 0.05, 1.6, W2 - 0.1, 1.25), top_s), ((X2 + 0.05, 3.12, W2 - 0.1, 0.9), top_h)):
        if top:
            _colonnes_couleurs(s, x, y, w, h, [k for k, _ in top], [v for _, v in top])
        else:
            _na(s, x, y, w, h)

    _secteurs(s, X1 + 0.4, 4.4, W1 - 0.8, 2.35, [f"{nom.upper()}", "STELLANTIS", "Conq/Extra"], [fideles, autres, conq],
              [C_PIE["fideles"], C_PIE["stla"], C_PIE["conq"]])

    # --- tableau : modèles d'achat (lignes) x modèles repris (colonnes)
    if top_a and mods_vn:
        reprise = {}
        for mr, mo, ma, mo_a, n in mods_vn:
            if mo:
                reprise[mo.upper()] = reprise.get(mo.upper(), 0) + n
        cols = [k for k, _ in sorted(reprise.items(), key=lambda kv: -kv[1])[:7]]
        croise = {}
        for (a, (mr, mo)), n in paires.items():
            croise[(a, mo)] = croise.get((a, mo), 0) + n
        lignes = [["Purchase Model"] + [_joli(c) for c in cols]]
        # lignes = les 5 modèles d'achat qui totalisent le plus SUR LES COLONNES AFFICHÉES (comme la feuille Tableau), pas sur tous les modèles repris
        # (retour DKAM, Peugeot ES : le 408 devait être 5e)
        somme = {a: sum(croise.get((a, c), 0) for c in cols) for a in achat}
        top_tab = sorted(achat, key=lambda a: (-somme[a], -achat[a]))[:5]
        for a in top_tab:
            lignes.append([_joli(a)[:20]] + [nb(croise.get((a, c), 0)) if croise.get((a, c)) else "" for c in cols])
        lignes.append(["Total"] + [nb(reprise[c]) for c in cols])
        lw = 1.25
        g.tableau(s, X2 + 0.1, 4.5, W2 - 0.2, lignes, largeurs=[lw] + [(W2 - 0.2 - lw) / len(cols)] * len(cols), taille=8, hauteur_ligne=0.29,
                  alignements=[PP_ALIGN.LEFT] + [PP_ALIGN.CENTER] * len(cols), gras_derniere=True)
    else:
        _na(s, X2, 4.1, W2, 2.7)
    return s
