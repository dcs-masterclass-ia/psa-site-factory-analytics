"""Format « revue trimestrielle pays » (format: "revue_trim") : reproduit le deck de référence « Stellantis Reporting Q3 2026 BE » (76 diapositives).

Sélection : brief["format"] == "revue_trim" (construit() délègue ici), période de type trimestre. Même socle de design que la revue mensuelle France
(revue_commun.py : Revue, slide_revue, boite_revue, pied ; revue_fr.py : agenda, séparateurs, contacts ; graphiques.py), mais les périodes comparées sont
le trimestre T, le trimestre précédent (QoQ) et le même trimestre de l'an dernier (YoY).

Les visuels du deck d'origine qui sont des captures Tableau / C1ST sont refaits en graphiques et tableaux NATIFS avec les vraies données (Donnees : leads du back-office,
GA4 / historique pour le trafic, C1ST via `c1st()` / `c1st_nsc()`, jamais de proxy). Une section sans données n'est pas créée (avertissement), rien n'est inventé.
Ordre : couverture, agenda, Global overview, leads par marque (YoY, QoQ), par mois, NC par mois (global puis par marque), projets d'achat (xP, xF), trafic et leads,
vue d'ensemble par marque ; Sales performance (C1ST) ; Traffic & lead deep dive (par marque : trafic, canaux, conquête) ; Open points / Next steps / Q&A ; contacts.
Pas d'annexe CTA ni de diapositives de contenu propre à un pays (POP IN, migration, BMS, RUN topics).
"""

from datetime import date

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from . import graphiques as g
from .construit import Ctx, GABARIT, PERIMETRE_C1ST, SANS_SUIVI_C1ST
from .donnees import PROJETS
from .periodes import MOIS_COURTS, Periode
from .revue_commun import (source_c1st, BOITE_BORD, C2025, C2026, C_SANS, C_VN, C_VO, GROUPE_XF, GROUPE_XP, MARINE, Revue, boite_revue, court, evol, mois_label, nb, pct,
                           pied, slide_revue)
from .revue_fr import _ajoute, _module, agenda_revue, contacts_revue
from .revue_global import COULEUR_MARQUE, GRIS_BANDEAU, NAVY_TABLEAU, _bandeau, _bloc_chiffre, _legende_projets, _liste, barres_marques
from .revue_resultats import VERT_TXT, ROUGE_TXT, _cellule, _sessions, _table

SECTIONS_TRIM = ["GLOBAL OVERVIEW", "SALES PERFORMANCE", "TRAFFIC & LEAD DEEP DIVE", "OPEN POINTS", "NEXT STEPS", "Q/A"]
NOMS_PAYS = {"FR": "FRANCE", "BE": "BELUX", "LU": "BELUX", "ES": "SPAIN", "PT": "PORTUGAL", "IT": "ITALY", "DE": "GERMANY", "PL": "POLAND", "AT": "AUSTRIA", "GB": "UNITED KINGDOM"}
# couleurs des graphiques Tableau du deck : 2024 bleu, 2025 jaune, 2026 vert d'eau ; QoQ : trimestre précédent orange, trimestre bleu
C24, C25, C26 = "4E79A7", "EDC948", "76B7B2"
C_QPREC, C_QCUR = "F28E2B", "4E79A7"
VERT, ROUGE = "2E9E4F", "D93025"
MARQUES_SANS_CONQUETE = ("SPOTICAR", "STELLANTIS &YOU")
GROUPE_XF_TRIM = ["FIAT", "JEEP", "ALFA ROMEO", "ABARTH", "FIAT PRO", "LANCIA", "LEAPMOTOR"]      # ordre du deck (diapositives 9 et 10)


# ------------------------------------------------------------------ utilitaires
def _trimestres(per, k):
    """Les k derniers trimestres (chronologique), le dernier étant `per`."""
    n = per.annee * 4 + per.indice - 1
    return [Periode("trimestre", *(lambda a, q: (a, q + 1))(*divmod(n - i, 4))) for i in range(k - 1, -1, -1)]


def _q(per):
    if per.type == "mois":
        from .periodes import MOIS_COURTS
        return f"{MOIS_COURTS['en'][per.indice - 1]}-{str(per.annee)[2:]}"
    return f"Q{per.indice}-{str(per.annee)[2:]}"


def _L(d, per, m=None):
    return d.leads_total(per, m)


def _actives(ctx, rv):
    """Marques du périmètre ayant des leads sur le trimestre, le précédent ou le même trimestre N-1."""
    return [m for m in ctx.d.marques if any(_L(ctx.d, p, m) for p in (rv.per, rv.prec, rv.n1))]


def _signe(v, n=0):
    return "n/a" if v is None else (f"{v:+.{n}f}%" if round(v, n) != 0 else f"{0:.{n}f}%")


def _col(v):
    v = round(v or 0)
    return VERT if v > 0 else ROUGE if v < 0 else "000000"


def _source(s, txt):
    g.texte(s, 1.08, 7.12, 11.0, 0.28, txt, taille=9, couleur="000000")


def _logo_petit(rv, s, marque, x, y, h_max=0.45, w_max=1.5):
    """Logo de la marque (aspect conservé) dont le coin haut-gauche est (x, y)."""
    spec = (rv.manifeste.get("logos") or {}).get(marque)
    if not spec:
        return None
    r = spec["w"] / spec["h"]
    h = min(h_max, w_max / r)
    return rv._image(s, spec, x=x, y=y, w=h * r, h=h)


def _liste_evol(items):
    return ", ".join(f"{n} {_signe(e)}" for n, e in items)


def _evols(ctx, items, ref_nom, base_min=20):
    """Commentaires « hausse / baisse » par marque : items = [(nom, courant, référence)], marques sous `base_min` leads de référence ignorées."""
    ev = [(n, evol(c, r)) for n, c, r in items if r and r >= base_min and c is not None]
    ups = sorted([(n, e) for n, e in ev if e >= 5], key=lambda x: -x[1])
    dws = sorted([(n, e) for n, e in ev if e <= -5], key=lambda x: x[1])
    out = []
    if ups and dws:
        out += [f"Good increase {ref_nom} for: {_liste_evol(ups)}", f"But also decrease for: {_liste_evol(dws)}"]
    elif ups:
        out.append(f"Increase {ref_nom} for all brands but stable ones: {_liste_evol(ups)}" if len(ups) < len(ev) else f"All brands increasing {ref_nom}: {_liste_evol(ups)}")
    elif dws:
        out.append(f"All brands decreasing {ref_nom}" + (f" except for stable ones: {_liste_evol(dws)}" if len(dws) < len(ev) else f": {_liste_evol(dws)}"))
    elif ev:
        out.append(f"All brands stable {ref_nom} (within ±5%).")
    return out


# ------------------------------------------------------------------ couverture et agenda
def couverture_trim(ctx, rv):
    """Couverture du deck BE : « STELLANTIS <pays> », « TRADE-IN WEBSITES PERFORMANCE REVIEW Qx-AAAA – <pays> » et la date, bloc blanc avec logo Stellantis et drapeau."""
    s = ctx.prs.slides.add_slide(ctx.lay["Title Slide"])
    ctx.n += 1
    pays = " & ".join(dict.fromkeys(NOMS_PAYS.get(p, p) for p in rv.pays)) or "STELLANTIS"
    ligne1 = f"STELLANTIS {pays}"
    g.texte(s, 0.62, 3.15, 7.0, 0.7, ligne1, taille=32, gras=True, couleur="FFFFFF")
    ligne2 = f"TRADE-IN WEBSITES PERFORMANCE REVIEW Q{rv.per.indice}-{rv.per.annee} – {pays}"
    g.texte(s, 0.62, 5.1, 7.4, 0.9, ligne2, taille=20 if len(ligne2) <= 62 else 16, gras=True, couleur="FFFFFF")
    g.texte(s, 0.62, 5.95, 5.0, 0.5, ctx.aujourdhui.strftime("%d/%m/%Y"), taille=20, gras=True, couleur="FFFFFF")
    boite = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7.79), Inches(2.89), Inches(5.3), Inches(2.34))
    boite.fill.solid(); boite.fill.fore_color.rgb = g.rgb("FFFFFF"); boite.line.fill.background(); boite.shadow.inherit = False
    rv._image(s, rv.manifeste.get("couverture_stellantis"))
    rv._drapeau_pays(s, rv.manifeste.get("couverture_drapeau"))
    g.texte(s, 4.4, 7.1, 4.5, 0.3, ctx.t["confidentiel"], taille=9, couleur="FFFFFF", align=PP_ALIGN.CENTER)
    g.texte(s, 0.12, 7.21, 1.8, 0.3, rv.date_deck, taille=9, couleur="FFFFFF")
    return s


# ------------------------------------------------------------------ 3. Global overview
def global_overview(ctx, rv):
    d, per = ctx.d, rv.per
    L, Lp, Ln = (_L(d, p) for p in (per, rv.prec, rv.n1))
    if not L:
        return None
    an = per.annee
    fin_m = per.mois()[-1][1]
    ytd = sum(d.leads_mensuels(an)[:fin_m])
    ytd_n1 = sum(d.leads_mensuels(an - 1)[:fin_m])
    e_q, e_y, e_ytd = evol(L, Lp), evol(L, Ln), evol(ytd, ytd_n1)
    vn, vn_n1 = d.leads(per)["VN"], d.leads(rv.n1)["VN"]
    q = f"Q{per.indice}"
    ctx.faits.ajoute("leads", L, None, per.etiquette("en"), "global_overview", marques=d.marques)
    s = slide_revue(ctx, rv, "Global Overview", source=None)
    DY = 0.22                            # retour DKAM : tout le contenu descend pour ne plus toucher le filet orange du titre
    _bandeau(s, 0.35, 1.14 + DY, 12.55, 0.26, f"EXEC SUMMARY - TRADE IN SITUATION {q}-{an}", NAVY_TABLEAU, couleur="FFFFFF", taille=9)
    _bloc_chiffre(s, 0.35, "REPORTING QUARTERLY", f"Total generated leads {q}-{an}", L, "Evolution vs last quarter", e_q, 2.3, DY)
    _bloc_chiffre(s, 2.75, "REPORTING YTD", f"Total generated leads {an}", ytd, f"Evolution vs last year ({an - 1} vs {an})", e_ytd, 2.3, DY)
    _bandeau(s, 5.2, 1.43 + DY, 7.7, 0.27, f"Generated leads YTD {q}-{an}: split by brand", GRIS_BANDEAU, taille=8)
    ym = []
    for m in d.marques:
        a = sum(d.leads_mensuels(an, m)[:fin_m])
        if a > 0:
            ym.append((m, a))
    ym.sort(key=lambda x: -x[1])
    if ym:
        lignes = [("S&Y" if m == "STELLANTIS &YOU" else ctx.nom(m).replace(" ", "_").upper(), a, a / ytd * 100, COULEUR_MARQUE.get(m, "BAB0AC")) for m, a in ym]
        barres_marques(s, 5.2, 1.72 + DY, 7.7, 2.2, lignes)
    _bandeau(s, 0.35, 3.95 + DY, 12.55, 0.26, "Trend YTD", GRIS_BANDEAU, taille=8)
    qs = _trimestres(per, 8)
    cats = [f"{p.annee} Q{p.indice}" for p in qs]
    for p_ in qs:
        pj_ = d.leads(p_)
        for k_, nom_ in (("VN", "leads_vn"), ("SANS", "leads_sans"), ("VO", "leads_vo")):
            ctx.faits.ajoute(nom_, pj_[k_], None, p_.etiquette("en"), "global_trend")
        ctx.faits.ajoute("leads", sum(pj_.values()), None, p_.etiquette("en"), "global_trend", marques=d.marques)
    gf = g.lignes_chart(s, 0.35, 4.22 + DY, 11.0, 1.9, cats, [("New cars & Demo cars", [d.leads(p)["VN"] for p in qs], C_VN), ("Trade-in only", [d.leads(p)["SANS"] for p in qs], C_SANS),
                                                       ("Used cars", [d.leads(p)["VO"] for p in qs], C_VO)], taille=8, legende=False, etiquettes=True)
    try:
        gf.chart.plots[0].series[2].data_labels.position = XL_LABEL_POSITION.BELOW
    except Exception:
        pass
    _legende_projets(s, 11.5, 5.5 + DY)
    mot = lambda e: "increasing" if (e or 0) >= 0 else "decreasing"
    nc = f"NC leads {mot(evol(vn, vn_n1))} ({_signe(evol(vn, vn_n1))} YoY)" if evol(vn, vn_n1) is not None else ""
    txt = f"{q}-{an} performance {mot(e_q)} by {_signe(e_q)} QoQ & {mot(e_ytd)} by {_signe(e_ytd)} YoY" + (f", {nc}" if nc else "") + "."
    g.boite_pointillee(s, 0.35, 6.45, 8.4, 0.38, [txt], taille=11, fond="FFFFFF", bord="000000", espace_apres=0, largeur_trait=0.75)
    _source(s, "Source: autobiz")
    return s


# ------------------------------------------------------------------ 4-5. Leads par marque : trimestre vs YoY / vs QoQ
def leads_par_marque(ctx, rv, ref):
    d, per = ctx.d, rv.per
    pref = rv.n1 if ref == "n1" else rv.prec
    marques = [m for m in _actives(ctx, rv)]
    if not marques:
        return None
    nom_ref = "YoY" if ref == "n1" else "QoQ"
    cur = [_L(d, per, m) for m in marques]
    old = [_L(d, pref, m) for m in marques]
    for m, v, o in zip(marques, cur, old):
        ctx.faits.ajoute("leads", v, m, per.etiquette("en"), f"leads_par_marque_{ref}")
        ctx.faits.ajoute("leads", o, m, pref.etiquette("en"), f"leads_par_marque_{ref}")
    etiq = [None if not v else (f"{nb(v)}\n{_signe(evol(v, o))}" if o else nb(v)) for v, o in zip(cur, old)]
    puces = _evols(ctx, [(ctx.nom(m), c, o) for m, c, o in zip(marques, cur, old)], nom_ref)
    if ref == "prec":
        a, b = _L(d, rv.n1), _L(d, rv.prec.n1())
        if a and b:
            puces.append(f"Seasonality check: last year, {_q(rv.n1)} was {_signe(evol(a, b))} vs {_q(rv.prec.n1())} for these brands.")
    s = slide_revue(ctx, rv, f"Global Leads by brand / Q{per.indice} Vs {nom_ref}", puces=puces, source=None, boite_pleine=False)
    g.colonnes(s, 0.15, 1.3, 10.85, 5.7, [ctx.nom(m).upper() for m in marques],
               [(_q(pref), old, C25 if ref == "n1" else C_QPREC), (_q(per), cur, C26 if ref == "n1" else C_QCUR)], taille=8, libelles_perso={1: etiq}, legende=True, largeur_barre=30)
    _source(s, "Source: autobiz")
    return s


# ------------------------------------------------------------------ 6-7. Leads par mois (3 années)
def _serie_annee(d, an, fin, projet=None, marque=None):
    v = d.leads_mensuels(an, marque, projet)
    return v if an < fin[0] else [x if i < fin[1] else None for i, x in enumerate(v)]


def _colonnes_mois(ctx, rv, s, x, y, w, h, projet=None, marque=None, taille=7, etiquettes=True, legende=True):
    d, per = ctx.d, rv.per
    fin = (per.annee, per.mois()[-1][1])
    series = []
    for an, coul in ((per.annee - 2, C24), (per.annee - 1, C25), (per.annee, C26)):
        v = _serie_annee(d, an, fin, projet, marque)
        if sum(x_ or 0 for x_ in v) > 0:
            series.append((an, v, coul))
    if not series:
        return None
    labels = {}
    for i, (an, v, _) in enumerate(series):
        prev = next((vv for a2, vv, _ in series if a2 == an - 1), None)
        if etiquettes:
            labels[i] = [None if (x_ is None) else (f"{nb(x_)}\n{_signe(evol(x_, prev[k]))}" if prev and prev[k] else nb(x_)) for k, x_ in enumerate(v)]
    return g.colonnes(s, x, y, w, h, [f"{k + 1:02d}" for k in range(12)], [(str(an), v, c) for an, v, c in series], taille=taille, libelles_perso=labels if etiquettes else None,
                      legende=legende, largeur_barre=20, etiquettes=etiquettes, quadrillage=True)


def leads_par_mois(ctx, rv, projet=None):
    d, per = ctx.d, rv.per
    ms = per.mois()
    cur = [d.leads_mensuels(a, None, projet)[m - 1] for a, m in ms]
    n1 = [d.leads_mensuels(a - 1, None, projet)[m - 1] for a, m in ms]
    if not sum(cur):
        return None
    for (a_, m_), c_ in zip(ms, cur):
        ctx.faits.ajoute("leads_vn" if projet else "leads", c_, None, f"{a_}-{m_:02d}", "leads_par_mois")
    for (a_, m_), o_ in zip(ms, n1):
        ctx.faits.ajoute("leads_vn" if projet else "leads", o_, None, f"{a_ - 1}-{m_:02d}", "leads_par_mois")
    nom = "NC leads" if projet else "Leads"
    ups = [MOIS_COURTS["en"][m - 1] for (a, m), c, o in zip(ms, cur, n1) if o and c > o]
    lq, lp = sum(cur), (sum(d.leads_mensuels(a, None, projet)[m - 1] for a, m in rv.prec.mois()))
    puces = [f"{nom} above {per.annee - 1} in {len(ups)} of the {len(ms)} months of {_q(per)}" + (f" ({', '.join(ups)})." if ups else "."),
             f"Quarter total: {nb(lq)} ({_signe(evol(lq, sum(n1)))} YoY, {_signe(evol(lq, lp))} QoQ)."]
    s = slide_revue(ctx, rv, "Global NC leads by Month" if projet else "Global leads by Month", puces=puces, source=None)
    if _colonnes_mois(ctx, rv, s, 0.15, 1.3, 10.9, 5.7, projet) is None:
        return None
    _source(s, "Source: autobiz")
    return s


# ------------------------------------------------------------------ 8-10. NC leads par mois et par marque (4 petits graphiques par diapositive)
def nc_par_mois_marque(ctx, rv, titre, marques):
    if not marques:
        return None
    s = slide_revue(ctx, rv, titre, source=None)
    cases = [(0.2, 1.3), (6.75, 1.3), (0.2, 4.15), (6.75, 4.15)]
    fait = 0
    for m, (x, y) in zip(marques, cases):
        _logo_petit(rv, s, m, x, y, h_max=0.4, w_max=1.3)
        if (rv.manifeste.get("logos") or {}).get(m) is None:
            g.texte(s, x, y + 0.02, 3.0, 0.3, ctx.nom(m).upper(), taille=11, gras=True, couleur=MARINE)
        if _colonnes_mois(ctx, rv, s, x, y + 0.42, 6.35, 2.3, "VN", m, taille=5, etiquettes=True, legende=True) is not None:
            fait += 1
    _source(s, "Source: autobiz")
    return s if fait else None


def nc_par_mois_groupes(ctx, rv):
    """Diapositives NC par mois et par marque : xP (4 marques), puis xF par lots de 4, puis les autres marques."""
    d = ctx.d
    ok = lambda m: m in d.marques and any(sum(d.leads_mensuels(a, m, "VN")) for a in (rv.per.annee - 2, rv.per.annee - 1, rv.per.annee))
    out = []
    xp = [m for m in GROUPE_XP if ok(m)]
    xf = [m for m in GROUPE_XF_TRIM if ok(m)]
    autres = [m for m in d.marques if m not in GROUPE_XP and m not in GROUPE_XF_TRIM and ok(m)]
    for titre, lot in (("Global NC leads by Month xP brand", xp), ("Global NC leads by Month xF brand", xf), ("Global NC leads by Month – other brands", autres)):
        for i in range(0, len(lot), 4):
            out.append(_ajoute(ctx, nc_par_mois_marque, ctx, rv, titre, lot[i:i + 4], libelle=titre))
    return out


# ------------------------------------------------------------------ 11-12. Leads par projet d'achat (xP / xF)
def projets_groupe(ctx, rv, groupe, marques):
    d, per = ctx.d, rv.per
    marques = [m for m in marques if m in d.marques and any(_L(d, p, m) for p in (per, rv.n1))]
    if not marques:
        return None
    pers = [rv.prec.n1(), rv.n1, rv.prec, per]
    pj = lambda p, m=None: {k: sum(d.leads(p, mm)[k] for mm in ([m] if m else marques)) for k in PROJETS}
    s = slide_revue(ctx, rv, f"Leads by Purchase Project: {mois_label(per)} for {groupe}", source=None)
    cd = CategoryChartData()
    for m in marques:
        c = cd.add_category(ctx.nom(m).upper())
        for p in pers:
            c.add_sub_category(_q(p))
    ordre = [("VO", "Used cars", C_VO), ("SANS", "Trade-in only", C_SANS), ("VN", "New cars & Demo.", C_VN)]
    vals = {k: [pj(p, m)[k] for m in marques for p in pers] for k, _, _ in ordre}
    tot = [sum(vals[k][i] for k in vals) for i in range(len(marques) * 4)]
    for k, nom, _ in ordre:
        cd.add_series(nom, vals[k])
    nom_f = {"VN": "leads_vn", "SANS": "leads_sans", "VO": "leads_vo"}
    for i_, (m_, p_) in enumerate([(m, p) for m in marques for p in pers]):
        for k, _n, _c in ordre:
            ctx.faits.ajoute(nom_f[k], vals[k][i_], m_, p_.etiquette("en"), f"projets_{groupe}")
        ctx.faits.ajoute("leads", sum(vals[k][i_] for k in vals), m_, p_.etiquette("en"), f"projets_{groupe}")
    x, y, w, h = 0.15, 1.3, 8.7, 4.9
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_STACKED, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    zx, zy, zw, zh = g.zone_fixe(gf)
    nb_cols = len(marques) * 4
    fente = zw / nb_cols
    for i in range(len(marques)):                      # surlignage orangé : les deux trimestres de l'année en cours de chaque marque (sépare aussi les marques)
        g.bande_derriere(s, gf, zx + (4 * i + 2) * fente, zy, 2 * fente, zh + 0.45)
    ch.has_title = False; ch.has_legend = False
    ch.font.size = Pt(7)
    ch.value_axis.visible = False; ch.value_axis.has_major_gridlines = False
    ch.category_axis.tick_labels.font.size = Pt(7)
    plot = ch.plots[0]
    plot.gap_width = 25; plot.overlap = 100
    for si, (k, nom, coul) in enumerate(ordre):
        ser = plot.series[si]
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = g.rgb(coul)
        for i, v in enumerate(vals[k]):
            if not v or not tot[i]:
                continue
            dl = ser.points[i].data_label
            dl.position = XL_LABEL_POSITION.CENTER
            tf = dl.text_frame
            tf.text = f"{nb(v)}\n{v / tot[i] * 100:.0f}%" if v / tot[i] >= 0.07 else ""
            for p in tf.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(6.5); r.font.color.rgb = g.rgb("FFFFFF")
    # total du groupe : N-1 vs N
    g.texte(s, 8.95, 1.3, 2.1, 0.25, f"Total Purchase {groupe}", taille=9, gras=True, couleur="595959")
    t1, t2 = pj(rv.n1), pj(per)
    labels = {}
    series = []
    for k, nom, coul in ordre:
        v = [t1[k], t2[k]]
        tt = [sum(t1.values()), sum(t2.values())]
        labels[len(series)] = [f"{nb(a)}\n{a / b * 100:.0f}%" if a and b else None for a, b in zip(v, tt)]
        series.append((nom, v, coul))
    gf2 = g.colonnes(s, 8.95, 1.55, 2.1, 4.6, [_q(rv.n1) if per.type == "mois" else str(rv.n1.annee), _q(per) if per.type == "mois" else str(per.annee)], series, empile=True, legende=False, taille=8, libelles_perso=labels)
    z2x, z2y, z2w, z2h = g.zone_fixe(gf2)
    g.bande_derriere(s, gf2, z2x + z2w / 2, z2y, z2w / 2, z2h + 0.3)
    # légende
    for i, (k, nom, coul) in enumerate(reversed(ordre)):
        yy = 6.3 + i * 0.2
        c = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(11.3), Inches(yy + 0.04), Inches(0.1), Inches(0.1))
        c.fill.solid(); c.fill.fore_color.rgb = g.rgb(coul); c.line.fill.background(); c.shadow.inherit = False
        g.texte(s, 11.45, yy - 0.02, 1.7, 0.22, nom, taille=8, couleur="000000")
    # commentaire : part New cars (pts) par marque
    sh = lambda p, m=None: (lambda t: t["VN"] / sum(t.values()) * 100 if sum(t.values()) else None)(pj(p, m))
    a, b = sh(per), sh(rv.n1)
    txt = []
    if a is not None and b is not None:
        txt.append(f"NC share {'up' if a >= b else 'down'} {abs(a - b):.0f}pt YoY for {groupe} ({a:.0f}%)")
    dm = []
    for m in marques:
        am, bm = sh(per, m), sh(rv.n1, m)
        if am is not None and bm is not None and _L(d, rv.n1, m) >= 50:
            dm.append((ctx.nom(m), am - bm, am))
    ups = [f"{n} +{dd:.0f}pt ({am:.0f}%)" for n, dd, am in sorted(dm, key=lambda x: -x[1]) if dd >= 3][:4]
    dws = [f"{n} {dd:.0f}pt ({am:.0f}%)" for n, dd, am in sorted(dm, key=lambda x: x[1]) if dd <= -3][:3]
    if ups:
        txt.append("Increase: " + ", ".join(ups))
    if dws:
        txt.append("Decrease: " + ", ".join(dws))
    if txt:
        g.boite_pointillee(s, 0.15, 6.3, 10.8, 0.7, [" · ".join(txt)], taille=10, fond="FFFFFF", bord="000000", espace_apres=0, largeur_trait=0.75)
    _source(s, "Source: autobiz")
    return s


# ------------------------------------------------------------------ 13. Traffic & leads overview
def trafic_leads_apercu(ctx, rv, ordre=None, mensuel=False):
    """`ordre` : liste de marques imposant l'ordre des colonnes. `mensuel` : revue mensuelle (MoM contre le mois civil précédent, au lieu de QoQ)."""
    d, per = ctx.d, rv.per
    marques = _actives(ctx, rv)
    if ordre:
        marques = sorted(marques, key=lambda m: ordre.index(m) if m in ordre else len(ordre))
    if not marques:
        return None
    prec_ses = rv.prec if mensuel else per.precedente_jours()
    lib_prec = "MoM" if mensuel else "QoQ"
    # sessions : « période précédente » = les mêmes nombres de jours juste avant (définition de Looker, tableaux de référence) ; leads : trimestre civil précédent
    trafic = {m: tuple(_sessions(d, p, m) for p in (per, prec_ses, rv.n1)) for m in marques}
    leads = {m: tuple(_L(d, p, m) for p in (per, rv.prec, rv.n1)) for m in marques}
    pays_ses = "+".join(p for p in d.pays if p != "LU") or "+".join(d.pays)
    for m in marques:
        for p_, v_ in zip((per, prec_ses, rv.n1), trafic[m]):
            ctx.faits.ajoute("sessions", v_ or None, m, p_.etiquette("en"), "traffic_leads_overview", perimetre=pays_ses)
        for p_, v_ in zip((per, rv.prec, rv.n1), leads[m]):
            ctx.faits.ajoute("leads", v_, m, p_.etiquette("en"), "traffic_leads_overview")
    s = slide_revue(ctx, rv, f"Traffic & leads Overview {mois_label(per)}", source=None)
    n = len(marques)
    w0 = 0.85
    wc = min(1.1, (12.4 - w0) / n)
    ev = lambda cur, ref: evol(cur, ref) if cur and ref else None

    def tableau(y, titre, vals, dec):
        g.texte(s, 0.25, y, 4.0, 0.35, titre, taille=16, gras=True, couleur="000000")
        lignes = [[{"t": "", "taille": 9}] + [{"t": ctx.nom(m), "taille": 9, "gras": True} for m in marques]]
        lignes.append([{"t": mois_label(per), "taille": 8}] + [{"t": nb(vals[m][0]) if vals[m][0] else "", "taille": 13, "gras": False} for m in marques])
        for nom, k in ((lib_prec, 1), ("YoY", 2)):
            row = [{"t": nom, "taille": 8}]
            for m in marques:
                e = ev(vals[m][0], vals[m][k])
                row.append({"t": ("" if e is None else ("▼ " if e < 0 else "▲ ") + _signe(e, dec)), "taille": 8, "couleur": ROUGE_TXT if (e or 0) < 0 else VERT_TXT})
            lignes.append(row)
        _table(s, 0.25, y + 0.4, [w0] + [wc] * n, [0.3, 0.5, 0.28, 0.28], lignes)

    tableau(1.3, "Traffic (Sessions)", trafic, 1)
    tableau(3.2, "Leads", leads, 0)
    # commentaires calculés
    def phrases(vals, nom):
        out = []
        for lib, k in ((lib_prec, 1), ("YoY", 2)):
            ups = [ctx.nom(m) for m in marques if ev(vals[m][0], vals[m][k]) is not None and ev(vals[m][0], vals[m][k]) > 0]
            dws = [ctx.nom(m) for m in marques if ev(vals[m][0], vals[m][k]) is not None and ev(vals[m][0], vals[m][k]) < 0]
            if ups and dws:
                out.append(f"{nom} {lib}: increase for {_liste(ups)}; decrease for the other brands with data.") if len(ups) <= len(dws) else \
                    out.append(f"{nom} {lib}: decrease for {_liste(dws)}; increase for the other brands with data.")
            elif ups:
                out.append(f"{nom} {lib}: increase for all brands ({_liste(ups)}).")
            elif dws:
                out.append(f"{nom} {lib}: decrease for all brands ({_liste(dws)}).")
        return out
    haut = [("Traffic:", True)] + [(p, False) for p in phrases(trafic, "Sessions")] + [("Leads:", True)] + [(p, False) for p in phrases(leads, "Leads")]
    boite = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.25), Inches(5.3), Inches(8.5), Inches(1.65))
    boite.fill.background(); boite.shadow.inherit = False
    from pptx.enum.dml import MSO_LINE
    boite.line.color.rgb = g.rgb("1F3F7A"); boite.line.width = Pt(1); boite.line.dash_style = MSO_LINE.DASH
    tf = boite.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.1)
    for i, (t, gras) in enumerate(haut):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        r = p.add_run(); r.text = t
        r.font.size = Pt(10); r.font.bold = gras; r.font.underline = gras; r.font.color.rgb = g.rgb("000000")
    if mensuel:
        _source(s, "Source: autobiz + GA")
        return s
    _source(s, f"Source: GA4 / autobiz — sessions QoQ vs the previous {per.jours} days ({per.precedente_jours().debut.strftime('%d/%m')}-{per.precedente_jours().fin.strftime('%d/%m')}), as in Looker")
    return s


# ------------------------------------------------------------------ 14-15. Leads overview par marque : tendance, moteurs, actions
def apercu_marques_trim(ctx, rv):
    from . import analyse as an
    d, per = ctx.d, rv.per
    marques = _actives(ctx, rv)
    if not marques:
        return []
    perso = ctx.brief.get("actionsMarques") or {}
    out = []
    xf = [m for m in marques if m in GROUPE_XF_TRIM]
    lots = [[m for m in marques if m not in GROUPE_XF_TRIM], xf]
    morceaux = []
    for lot in lots:
        if lot:
            k = -(-len(lot) // 6)
            t_ = -(-len(lot) // k)
            morceaux += [lot[i:i + t_] for i in range(0, len(lot), t_)]
    for morceau in morceaux:
        s = slide_revue(ctx, rv, f"Leads Overview {mois_label(per)}", source=None)
        for x, w, t in ((0.2, 3.2, "LEAD TREND & NC SHARE"), (3.5, 4.55, "DRIVERS OF INCREASE / DECREASE"), (8.15, 4.8, "RECOMMENDED ACTION")):
            g.texte(s, x, 1.28, w, 0.25, t, taille=8, gras=True, couleur="2F5597")
        y = 1.55
        h = 0.82
        for m in morceau:
            a = an.apercu_marque(ctx, m)
            e_q, e_y = evol(_L(d, per, m), _L(d, rv.prec, m)), evol(_L(d, per, m), _L(d, rv.n1, m))
            base_q, base_y = _L(d, rv.prec, m) >= 20, _L(d, rv.n1, m) >= 20
            cellules = [(0.2, 3.2), (3.5, 4.55), (8.15, 4.8)]
            for x, w in cellules:
                c = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
                c.adjustments[0] = 0.08
                c.fill.solid(); c.fill.fore_color.rgb = g.rgb("EAF1FB"); c.line.color.rgb = g.rgb("DCE6F5"); c.shadow.inherit = False
            _logo_petit(rv, s, m, 0.3, y + 0.14, h_max=0.58, w_max=0.8)
            runs = [(ctx.nom(m), {"taille": 10, "gras": True, "couleur": "000000", "apres": 0})]
            tend = []
            g.texte(s, 1.15, y + 0.04, 2.3, 0.3, [runs[0]], taille=10)
            if base_q and e_q is not None:
                tend.append((f"{_signe(e_q)} {rv.vs_prec}", _col(e_q)))
            if base_y and e_y is not None:
                tend.append((f"{_signe(e_y)} YoY", _col(e_y)))
            if not tend:
                tend.append(("low base", "6B7280"))
            tb = s.shapes.add_textbox(Inches(1.15), Inches(y + 0.3), Inches(2.3), Inches(0.28))
            p = tb.text_frame.paragraphs[0]
            for k, (t, c) in enumerate(tend):
                if k:
                    r = p.add_run(); r.text = " | "; r.font.size = Pt(9); r.font.bold = True; r.font.color.rgb = g.rgb("000000")
                r = p.add_run(); r.text = t; r.font.size = Pt(9); r.font.bold = True; r.font.color.rgb = g.rgb(c)
            if a["nc"]:
                g.texte(s, 1.15, y + 0.55, 2.3, 0.26, a["nc"][0], taille=8, couleur="595959")
            acts = perso.get(m) or a["actions"]
            for (x, w), lignes in (((3.55, 4.45), a["moteurs"]), ((8.2, 4.7), acts)):
                g.texte(s, x, y + 0.04, w, h - 0.06, [("• " + l, {"taille": 7.5, "apres": 1}) for l in lignes[:4]], taille=7.5, couleur="000000", ancre=MSO_ANCHOR.MIDDLE)
            y += h + 0.1
        _source(s, "Source: autobiz")
        out.append(s)
    return out


# ------------------------------------------------------------------ Sales performance (C1ST)
def _mois_c1st(rv):
    """[(année, mois)] de janvier de l'année précédente à la fin du trimestre."""
    fin = rv.per.mois()[-1]
    out, (a, m) = [], (rv.per.annee - 1, 1)
    while (a, m) <= fin:
        out.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def _c1st_somme(d, per, marques):
    """Totaux C1ST sur la période pour les marques (None si aucune n'a de donnée complète)."""
    tot, vu = None, False
    for m in marques:
        c = d.c1st(per, m)
        if c is None:
            continue
        vu = True
        tot = dict(c) if tot is None else {k: tot[k] + c[k] for k in tot}
    return tot if vu else None


def _panneau(s, x, y, w, h, titre):
    c = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    c.fill.solid(); c.fill.fore_color.rgb = g.rgb("FFFFFF"); c.line.color.rgb = g.rgb("1F3864"); c.line.width = Pt(1.5); c.shadow.inherit = False
    g.texte(s, x + 0.03, y + 0.02, w - 0.06, 0.22, titre, taille=7.5, gras=True, couleur="000000")


def _boite_bas(s, texte, y=6.52, h=0.45, x=0.15, w=10.9):
    g.boite_pointillee(s, x, y, w, h, [texte], taille=10, fond="FFFFFF", bord="1F3F7A", espace_apres=0, largeur_trait=0.75)


def lead_management_c1st(ctx, rv, groupe, marques):
    """« autobiz lead management – VN type 1 <groupe> brands – C1ST » : suivi des leads envoyés par mois (contactés, 1er appel dans les délais, devis, commandes NSC)."""
    d, per = ctx.d, rv.per
    marques = [m for m in marques if m in d.marques and m not in SANS_SUIVI_C1ST]
    mois = _mois_c1st(rv)
    ser = []
    for a, m in mois:
        t = _c1st_somme(d, Periode("mois", a, m), marques)
        ser.append((a, m, t))
    ok = [x for x in ser if x[2] and x[2]["clients_envoyes"]]
    tq = _c1st_somme(d, per, marques)
    if not ok or not tq or not tq["clients_envoyes"]:
        return None
    s = slide_revue(ctx, rv, "SALES PERFORMANCE", sous_titre=f"autobiz lead management - VN type 1 {groupe} brands - C1ST", source=None)
    g.texte(s, 0.15, 1.27, 12.9, 0.22, mois_label(per), taille=9, gras=True, couleur="000000", align=PP_ALIGN.CENTER)
    cats = [f"{m:02d}/{a % 100}" for a, m, t in ok]
    div = lambda a, b: (a / b) if b else None
    W, H = 4.25, 2.5
    X = [0.15, 0.15 + W + 0.05, 0.15 + 2 * (W + 0.05)]
    Y = [1.5, 1.5 + H + 0.05]
    _panneau(s, X[0], Y[0], W, H, "# Leads Generated by Month")
    g.colonnes(s, X[0] + 0.02, Y[0] + 0.25, W - 0.04, H - 0.28, cats, [("Leads", [t["leads"] for _, _, t in ok], "5B9BD5")], legende=False, taille=6, etiquettes=True, largeur_barre=15, axe_valeurs=True, fmt=nb)
    from .revue_conquete import _barres_h
    st = d.c1st_statuts(per, marques)
    if st:        # « # Leads Generated by Status » : part des leads par statut (Status_ProcessLogic, « 5.Qualified » -> Qualified)
        tot = sum(st.values())
        ordre = sorted(st, key=lambda k: k.split(".")[0].zfill(2) if k.split(".")[0].isdigit() else "99")
        _panneau(s, X[1], Y[0], W, H, "# Leads Generated by Status")
        _barres_h(s, X[1] + 0.05, Y[0] + 0.28, W - 0.1, H - 0.32, [k.split(".", 1)[-1].strip() for k in ordre], [st[k] / tot for k in ordre], taille=7, pct=True)
    else:
        _panneau(s, X[1], Y[0], W, H, f"# Customers sent by follow-up stage ({mois_label(per)})")
        etapes = [("Sent to dealers", tq["clients_envoyes"]), ("Contacted", tq["contactes"]), ("Contacted on time", tq["contactes_delai"]), ("1st call on time", tq["premier_appel_delai"]),
                  ("Treated", tq["traites"]), ("With opportunity", tq["avec_opp"])]
        _barres_h(s, X[1] + 0.05, Y[0] + 0.28, W - 0.1, H - 0.32, [e[0] for e in etapes], [e[1] for e in etapes], taille=7)
    suivi = lambda t: t["contactes"] or t["premier_appel_delai"] or t["traites"]          # mois sans aucun statut saisi : suivi non déployé, pas un 0 % réel
    graphes = [("% 1st Call Attempt On Time", lambda t: div(t["premier_appel_delai"], t["clients_envoyes"]) if suivi(t) else None, X[2], Y[0]),
               ("% Contacted", lambda t: div(t["contactes"], t["clients_envoyes"]) if suivi(t) else None, X[0], Y[1]),
               ("% With Quotes", lambda t: div(t["avec_devis"], t["clients_uniques"]), X[1], Y[1]),
               ("% NSC Orders", lambda t: div(t["commandes"], t["clients_uniques"]), X[2], Y[1])]
    for titre, f, x, y in graphes:
        _panneau(s, x, y, W, H, titre)
        g.lignes_chart(s, x + 0.02, y + 0.25, W - 0.04, H - 0.28, cats, [(titre, [f(t) for _, _, t in ok], "5B9BD5")], taille=6, legende=False, etiquettes=True, format_nombre="0%", axe_valeurs=True, axe_pct=True)
    # commentaire : leads non traités sur le trimestre vs trimestre précédent
    nt = 1 - tq["traites"] / tq["clients_envoyes"]
    tp = _c1st_somme(d, rv.prec, marques)
    txt = f"{nt * 100:.0f}% of leads not managed in {mois_label(per)}"
    if tp and tp["clients_envoyes"]:
        dd = (nt - (1 - tp["traites"] / tp["clients_envoyes"])) * 100
        txt += f" ({'+' if dd >= 0 else '-'}{abs(dd):.0f}pt QoQ)"
    if set(rv.pays) & {"DE", "PL", "AT", "GB"}:
        txt += " Note: dealers' follow-up statuses are barely filled in C1ST for this market (contact / treatment rates are not reliable)."
    txt += f"; {tq['contactes'] / tq['clients_envoyes'] * 100:.0f}% contacted, {tq['commandes'] / tq['clients_uniques'] * 100:.0f}% NSC orders (still maturing: orders are linked up to 90 days after the lead)." if tq["clients_uniques"] else "."
    _boite_bas(s, txt, y=6.62, h=0.42, w=12.9)
    g.texte(s, 1.08, 7.12, 11.5, 0.28, source_c1st(d, "Source: C1ST, VN type 1 leads sent to dealers (Autobiz campaign) — C1ST scope, not comparable with the back-office", lien="; data as of "), taille=9, couleur="000000")
    s.notes_slide.notes_text_frame.text = ("Rates computed on unique customers sent to dealers (C1ST). % NSC orders = NSC orders (SUB set, 1 to 90 days after the lead) / unique customers; "
                                           "recent months are provisional. Spoticar excluded (no follow-up tracked by C1ST). " + PERIMETRE_C1ST[1])
    return s


def _etiq_segments(series, seuil=0.2):
    """Étiquettes des barres empilées : valeur du segment seulement s'il est assez haut pour être lisible (>= seuil du plus grand empilement)."""
    n = len(series[0][1]) if series else 0
    haut = max((sum(v[i] or 0 for _, v, _ in series) for i in range(n)), default=0) or 1
    return {k: [nb(x) if x and x / haut >= seuil else None for x in v] for k, (_, v, _) in enumerate(series)}


def leads_vn_c1st(ctx, rv, groupe, marques):
    """« SALES PERFORMANCE : leads VN <groupe> autobiz » : leads, % de commandes NSC et commandes NSC par mois et par marque, tableau du trimestre."""
    d, per = ctx.d, rv.per
    marques = [m for m in marques if m in d.marques and m not in SANS_SUIVI_C1ST]
    mois = _mois_c1st(rv)
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
    for m in marques:
        for i_, (a_, mo_) in enumerate(mois):
            if data[m][i_][0] is not None:
                ctx.faits.ajoute("c1st_leads", data[m][i_][0], m, f"{a_}-{mo_:02d}", "c1st_leads_vn")
                ctx.faits.ajoute("c1st_orders", data[m][i_][1], m, f"{a_}-{mo_:02d}", "c1st_leads_vn")
    if not any(c for c, n in tq.values()):
        return None
    cats = [f"{mois[i][1]:02d}/{mois[i][0] % 100}" for i in vues]
    s = slide_revue(ctx, rv, f"SALES PERFORMANCE: leads VN {groupe} autobiz", source=None)
    coul = lambda m: COULEUR_MARQUE.get(m, "BAB0AC")
    g.texte(s, 0.15, 1.28, 5.0, 0.22, "# Leads Generated", taille=8, gras=True, couleur="000000")
    sl, so = [(ctx.nom(m), [data[m][i][0] or 0 for i in vues], coul(m)) for m in marques], [(ctx.nom(m), [data[m][i][1] or 0 for i in vues], coul(m)) for m in marques]
    g.colonnes(s, 0.15, 1.48, 10.8, 1.7, cats, sl, empile=True, legende=True, taille=6, etiquettes=True, axe_valeurs=True, libelles_perso=_etiq_segments(sl), fmt=nb)
    g.texte(s, 0.15, 3.2, 5.0, 0.22, "% NSC Orders (NSC orders / leads, months with at least 20 leads)", taille=8, gras=True, couleur="000000")
    g.lignes_chart(s, 0.15, 3.4, 10.8, 1.75, cats, [(ctx.nom(m), [(data[m][i][1] / data[m][i][0]) if (data[m][i][0] and data[m][i][0] >= 20 and data[m][i][1] is not None) else None for i in vues], coul(m))
                                                    for m in marques], taille=6, legende=False, etiquettes=False, format_nombre="0%", axe_valeurs=True, axe_pct=True)
    g.texte(s, 0.15, 5.2, 5.0, 0.22, "NSC Orders", taille=8, gras=True, couleur="000000")
    g.colonnes(s, 0.15, 5.4, 10.8, 1.65, cats, so, empile=True, legende=False, taille=6, etiquettes=True, axe_valeurs=True, libelles_perso=_etiq_segments(so), fmt=nb)
    # commentaires + tableau du trimestre
    lignes = [["Brand", "# Leads", "# Orders", "% Orders"]]
    taux = []
    for m in marques:
        c, n = tq[m]
        if c is None or n is None:
            continue
        lignes.append([ctx.nom(m), nb(c["leads"]), nb(n), f"{n / c['leads'] * 100:.1f}%" if c["leads"] else "–"])
        if c["leads"] >= 50:
            taux.append((ctx.nom(m), n / c["leads"] * 100))
    tl = sum(tq[m][0]["leads"] for m in marques if tq[m][0] and tq[m][1] is not None)
    to = sum(tq[m][1] for m in marques if tq[m][0] and tq[m][1] is not None)
    puces = [f"{nb(to)} NSC orders from {nb(tl)} leads in {_q(per)} ({to / tl * 100:.1f}%)." if tl else "No lead in the quarter."]
    if taux:
        best = sorted(taux, key=lambda x: -x[1])[:2]
        puces.append("Best order rate: " + ", ".join(f"{n} {v:.1f}%" for n, v in best) + ".")
    puces.append("Orders are linked to leads up to 90 days after the lead: recent months are provisional.")
    boite_revue(s, puces, x=11.12, y=1.45, w=2.11, h=3.1, taille=9)
    if len(lignes) > 1:
        g.tableau(s, 11.12, 4.6, 2.11, lignes, largeurs=[0.75, 0.45, 0.45, 0.46], taille=6.5, hauteur_ligne=0.26, alignements=[PP_ALIGN.LEFT] + [PP_ALIGN.CENTER] * 3)
    g.texte(s, 1.08, 7.12, 11.5, 0.28, source_c1st(d, "Source: C1ST, VN type 1 leads sent to dealers (Autobiz campaign) — C1ST scope, not comparable with the back-office", lien="; data as of "), taille=9, couleur="000000")
    return s


def ventes_additionnelles(ctx, rv):
    """« SALES PERFORMANCE: additional business » : leads, taux et commandes NSC du trimestre vs N-1 par marque, ventes additionnelles."""
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
        for p_, v_, o_ in ((per, a["leads"], na), (rv.n1, b["leads"], nb_)):
            ctx.faits.ajoute("c1st_leads", v_, m, p_.etiquette("en"), "c1st_ventes_additionnelles")
            ctx.faits.ajoute("c1st_orders", o_, m, p_.etiquette("en"), "c1st_ventes_additionnelles")
        tot = [tot[0] + b["leads"], tot[1] + a["leads"], tot[2] + nb_, tot[3] + na]
    if not lignes:
        return None
    s = slide_revue(ctx, rv, "SALES PERFORMANCE: additional business", source=None)
    g.texte(s, 0.15, 1.27, 4.0, 0.3, f"{_q(per).replace('-', ' ')}*", taille=11, gras=True, couleur="000000")
    ent = ["Brand", f"# Leads {rv.n1.annee}", f"# Leads {per.annee}", f"Evol lead {per.annee} vs {rv.n1.annee}", f"% Orders {rv.n1.annee}", f"# Orders {rv.n1.annee}",
           f"% Orders {per.annee}", f"# Orders {per.annee}", "Increase sales", f"Evol {per.annee} vs {rv.n1.annee}"]
    rows = [[{"t": h, "taille": 8, "gras": True, "couleur": "FFFFFF", "fond": "1F4E9C"} for h in ent]]
    pc = lambda a, b: f"{a / b * 100:.1f}%".replace(".", ",") if b else "–"

    def ligne(nom, l1, l2, o1, o2, gras=False):
        inc = o2 - o1
        e_l, e_o = evol(l2, l1), evol(o2, o1)
        fond_inc = "92D050" if inc > 0 else "FF0000" if inc < 0 else "FFFFFF"
        cellules = [nom, nb(l1), nb(l2), _signe(e_l) if e_l is not None else "–", pc(o1, l1), nb(o1), pc(o2, l2), nb(o2), f"{inc:+d}" if inc else "0", _signe(e_o) if e_o is not None else "–"]
        out = []
        for j, t in enumerate(cellules):
            spec = {"t": t, "taille": 8, "gras": gras or j == 0, "align": PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER, "fond": "FFFFFF"}
            if j == 3 and e_l is not None:
                spec["couleur"] = ROUGE_TXT if e_l < 0 else VERT_TXT
            if j == 8:
                spec["fond"] = fond_inc
            out.append(spec)
        return out
    for m, l1, l2, o1, o2 in lignes:
        rows.append(ligne(ctx.nom(m), l1, l2, o1, o2))
    rows.append(ligne("Total", tot[0], tot[1], tot[2], tot[3], gras=True))
    _table(s, 0.15, 1.65, [1.45] + [1.18] * 9, [0.42] + [0.3] * (len(rows) - 1), rows)
    plus = [ctx.nom(m) for m, l1, l2, o1, o2 in lignes if o2 - o1 > 0]
    moins = [ctx.nom(m) for m, l1, l2, o1, o2 in lignes if o2 - o1 < 0]
    inc = tot[3] - tot[2]
    txt = f"On {_q(per).split('-')[0]}, {abs(inc)} {'additional' if inc >= 0 else 'fewer'} sales vs {rv.n1.annee}" + (f", except for {_liste(moins)}" if moins and inc >= 0 else "") + "."
    _boite_bas(s, txt, y=1.65 + 0.42 + 0.3 * (len(rows) - 1) + 0.3, h=0.45, w=10.9)
    g.texte(s, 0.15, 6.8, 8, 0.25, "*figures are still moving: NSC orders are linked to the lead up to 90 days after its creation", taille=8, couleur="000000")
    g.texte(s, 1.08, 7.12, 11.5, 0.28, "Source: C1ST, VN type 1 leads sent to dealers (Autobiz campaign) — C1ST scope; orders = NSC orders (SUB set)", taille=9, couleur="000000")
    return s


# ------------------------------------------------------------------ Open points / Next steps / Q&A
def open_points(ctx, rv):
    out = []
    for p in ctx.brief.get("pointsOuverts") or [{}]:        # sans point saisi : diapositive vide à compléter
        s = slide_revue(ctx, rv, "OPEN POINTS", sous_titre=p.get("titre") or None, source=None)
        if p.get("texte"):
            g.puces(s, 0.5, 1.3, 12.2, 5.4, [l for l in p["texte"].split("\n") if l.strip()], taille=16)
        out.append(s)
    return out


def next_steps(ctx, rv):
    et = ctx.brief.get("prochainesEtapes") or []        # sans étape saisie : tableau vide à compléter
    t = ctx.t
    s = slide_revue(ctx, rv, "NEXT STEPS", source=None)
    lignes = [["Item", t["responsable"], t["statut"], t["echeance"]]]
    for e in et:
        lignes.append([e.get("item", ""), e.get("responsable", ""), t[e.get("statut", "a_faire")], e.get("echeance", "")])
    g.tableau(s, 0.5, 1.3, 12.3, lignes, largeurs=[6.6, 2.4, 1.8, 1.5], taille=12, hauteur_ligne=0.42, alignements=[PP_ALIGN.LEFT] * 4)
    return s


def questions_trim(ctx, rv):
    return slide_revue(ctx, rv, "Q/A", source=None)


# ------------------------------------------------------------------ assemblage
def construit_revue_trim(brief, donnees, sortie, gabarit=GABARIT):
    from pathlib import Path
    # le format reprend le deck de référence BELUX : titres et libellés sont en anglais, les commentaires calculés le sont donc aussi quelle que soit la langue du brief
    brief = dict(brief, langue="en")
    ctx = Ctx(brief, donnees, gabarit)
    if ctx.per.type != "trimestre":
        raise ValueError("Le format « revue trimestrielle » exige une période de type trimestre.")
    rv = Revue(ctx)
    d = ctx.d
    if not rv.manifeste:
        ctx.avertissements.append("Éléments statiques du format absents (data/presentations/assets/revue_fr) : logos de marque et drapeau de couverture non affichés.")
    modules = [m for m in (_module(n) for n in ("revue_marque", "revue_canaux", "revue_conquete")) if m]
    f = lambda nom: next((getattr(m, nom) for m in modules if hasattr(m, nom)), None)
    pts = nxt = True          # slides conservées même vides (à compléter à la main)
    # sections disponibles (une section sans données n'est pas créée)
    avoir_c1st = any(d.c1st(rv.per, m) for m in d.marques if m not in SANS_SUIVI_C1ST)
    if not avoir_c1st:
        ctx.avertissements.append("Aucune donnée C1ST complète sur le trimestre (jeu c1st/kpi.json, marchés suivis : FR, BE, ES, PT, IT) : section « Sales performance » non générée.")
    actives = _actives(ctx, rv)
    sections = [SECTIONS_TRIM[0]] + ([SECTIONS_TRIM[1]] if avoir_c1st else []) + [SECTIONS_TRIM[2]] + ([SECTIONS_TRIM[3]] if pts else []) + ([SECTIONS_TRIM[4]] if nxt else []) + [SECTIONS_TRIM[5]]
    agenda = lambda nom: agenda_revue(ctx, rv, sections.index(nom), sections)

    couverture_trim(ctx, rv)
    agenda(SECTIONS_TRIM[0])
    A = lambda fn, *a, libelle="": _ajoute(ctx, fn, ctx, rv, *a, libelle=libelle)
    A(global_overview, libelle="Global overview")
    A(leads_par_marque, "n1", libelle="leads by brand YoY")
    A(leads_par_marque, "prec", libelle="leads by brand QoQ")
    A(leads_par_mois, libelle="leads by month")
    A(leads_par_mois, "VN", libelle="NC leads by month")
    nc_par_mois_groupes(ctx, rv)
    A(projets_groupe, "xP", GROUPE_XP + ["SPOTICAR"], libelle="leads by purchase project xP")
    A(projets_groupe, "xF", [m for m in GROUPE_XF_TRIM if m != "LEAPMOTOR"], libelle="leads by purchase project xF")
    A(trafic_leads_apercu, libelle="traffic & leads overview")
    for s_ in (apercu_marques_trim(ctx, rv) or [None]):
        if s_ is None:
            ctx.avertissements.append("Pas de données pour : leads overview par marque.")
    if avoir_c1st:
        agenda(SECTIONS_TRIM[1])
        for grp, lot in (("XP", GROUPE_XP), ("XF", GROUPE_XF_TRIM)):
            A(lead_management_c1st, grp, lot, libelle=f"C1ST lead management {grp}")
        for grp, lot in (("xP", GROUPE_XP), ("xF", GROUPE_XF_TRIM)):
            A(leads_vn_c1st, grp, lot, libelle=f"leads VN {grp} autobiz (C1ST)")
        A(ventes_additionnelles, libelle="additional business (C1ST)")
    agenda(SECTIONS_TRIM[2])
    for marque in actives:
        if not _L(d, rv.per, marque):
            ctx.avertissements.append(f"{marque} : aucun lead sur le trimestre, section non générée.")
            continue
        A(f("trafic"), marque, libelle=f"{marque} — traffic deep dive")
        A(f("canaux"), marque, libelle=f"{marque} — lead deep dive")
        if marque not in MARQUES_SANS_CONQUETE:
            A(f("conquete"), marque, libelle=f"{marque} — conquest vs loyalty")
        from .revue_v2 import focus_v2
        A(focus_v2, marque, libelle=f"{marque} — V2 redesign focus")
        from .revue_v2 import focus_v2_entree
        A(focus_v2_entree, marque, libelle=f"{marque} — V2 redesign focus (entry mode)")
    if pts:
        agenda(SECTIONS_TRIM[3])
        open_points(ctx, rv)
    if nxt:
        agenda(SECTIONS_TRIM[4])
        next_steps(ctx, rv)
    agenda(SECTIONS_TRIM[5])
    questions_trim(ctx, rv)
    contacts_revue(ctx, rv)
    ctx.qa = _qa_trim(ctx, rv)
    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    g.tient_dans_la_diapo(ctx.prs)
    ctx.prs.save(str(sortie))
    return ctx


def _qa_trim(ctx, rv):
    """Contrôle qualité des chiffres affichés (voir qa.py) ; ne doit jamais empêcher la génération."""
    from . import qa
    try:
        d, per = ctx.d, rv.per
        d.c1st_date()
        j = getattr(d, "_c1st_jour", "") or ""
        infos = {"fin_periode": per.fin.isoformat(), "dernier_jour_leads": d.dernier_jour_leads(), "collecte_c1st": j[:10] or None}
        lab = lambda p: p.etiquette("en")
        return qa.controle(ctx.faits, infos, [(lab(per), lab(rv.prec)), (lab(per), lab(rv.n1))])
    except Exception as e:
        return {"erreurs": [], "alertes": [{"code": "qa_indisponible", "message": f"Contrôle qualité non exécuté : {type(e).__name__}: {e}"}], "infos": [], "nb_faits": len(ctx.faits.lignes)}
