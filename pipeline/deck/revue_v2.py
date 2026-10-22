"""« V2 REDESIGN FOCUS » : une diapositive par marque, après sa section, pour les marchés PT, FR et ES où les sites sont passés en V2 (retour DKAM du 19/10/2026).

Par pays : date de bascule, fenêtres comparées (28 jours avant la bascule / depuis la bascule), sessions par jour, conversion accueil -> estimation, utilisateurs arrivés à l'estimation.
Dessous : le tunnel étape par étape (part de la page d'accueil) avant / après, pour l'ensemble des sites V2 de la marque dans ces marchés. Données : data/<site>.json -> v2, v2steps, v2_date."""

from datetime import date

from pptx.enum.text import PP_ALIGN

from . import graphiques as g
from .revue_commun import nb, pct, slide_revue
from .revue_resultats import ROUGE_TXT, VERT_TXT, _table

PAYS_V2 = {"FR": "France", "PT": "Portugal", "ES": "Spain"}
ORDRE_PAYS = ["FR", "PT", "ES"]
ETAPES_EN = {"Page d'accueil": "Home page", "Version": "Version", "Kilométrage": "Mileage", "Coordonnées": "Contact details", "Point de vente": "Dealer", "Estimation": "Estimate"}
BASE_MINI = 100            # moins de 100 utilisateurs à l'accueil, avant ou après : la conversion n'a pas de sens


def _date(iso):
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except Exception:
        return "n/a"


def _evol(a, b):
    return None if not a or b is None else (b - a) / a * 100


def _focus_data(ctx, marque):
    """(lignes par marché, étapes {étape: [avant, après]}, ordre des étapes) de « V2 REDESIGN FOCUS » (partagé V1 / V2) ; None sans site V2."""
    d = ctx.d
    lignes_pays, etapes, ordre = [], {}, []
    for nom, m, pays in d.sites:
        if m != marque or pays not in PAYS_V2:
            continue
        j = d._site_json(nom) or {}
        v, st = j.get("v2") or {}, j.get("v2steps") or []
        if not v.get("is_v2_split") or not st:
            continue
        lignes_pays.append((ORDRE_PAYS.index(pays), pays, j.get("v2_date"), v, st))
        for x in st:
            if x["step"] not in etapes:
                etapes[x["step"]] = [0, 0]
                ordre.append(x["step"])
            etapes[x["step"]][0] += x.get("a") or 0
            etapes[x["step"]][1] += x.get("b") or 0
    if not lignes_pays:
        return None
    lignes_pays.sort()
    return lignes_pays, etapes, ordre


def focus_v2(ctx, rv, marque):
    D = _focus_data(ctx, marque)
    if D is None:
        return None
    lignes_pays, etapes, ordre = D
    s = slide_revue(ctx, rv, "V2 REDESIGN FOCUS", sous_titre=f"{ctx.nom(marque)} – before / after the V2 switch", marque=marque, source=None)
    ent = [{"t": t, "taille": 8, "gras": True, "fond": "1F3864", "couleur": "FFFFFF"} for t in
           ("Market", "V2 go-live", "Before (28 days)", "After (since go-live)", "Sessions / day", "Conversion home → estimate", "Estimates (users)")]
    rows = [ent]
    peu = False
    for _, pays, dv, v, st in lignes_pays:
        a0, b0 = st[0].get("a") or 0, st[0].get("b") or 0
        fiable = a0 >= BASE_MINI and b0 >= BASE_MINI
        peu = peu or not fiable
        spd = _evol(v.get("pre_users_per_day"), v.get("post_users_per_day"))
        conv = f"{v['pre_conversion_pct']:.1f}% → {v['post_conversion_pct']:.1f}%  ({v['delta_conversion_pts']:+.1f} pt)" if fiable and v.get("pre_conversion_pct") is not None else "low base"
        cc = {"couleur": VERT_TXT if (v.get("delta_conversion_pts") or 0) > 0 else ROUGE_TXT} if fiable else {}
        cs = {"couleur": VERT_TXT if (spd or 0) >= 0 else ROUGE_TXT} if spd is not None else {}
        rows.append([{"t": PAYS_V2[pays], "taille": 9, "gras": True, "align": PP_ALIGN.LEFT},
                     {"t": _date(dv), "taille": 9},
                     {"t": v.get("pre_label", "n/a"), "taille": 8}, {"t": f"{v.get('post_label', 'n/a')} ({v.get('post_days', '?')} d)", "taille": 8},
                     {"t": f"{v['pre_users_per_day']:,.0f} → {v['post_users_per_day']:,.0f}".replace(",", " ") + (f"  ({spd:+.0f}%)" if spd is not None else ""), "taille": 8.5, **cs},
                     {"t": conv, "taille": 8.5, "gras": fiable, **cc},
                     {"t": f"{nb(v.get('pre_final_users'))} → {nb(v.get('post_final_users'))}", "taille": 8.5}])
    _table(s, 0.2, 1.3, [1.15, 1.0, 1.4, 1.9, 1.9, 2.2, 1.55], [0.42] + [0.38] * (len(rows) - 1), rows)
    # tunnel avant / après (part de la page d'accueil)
    y_ch = 1.3 + 0.42 + 0.38 * (len(rows) - 1) + 0.35
    a0, b0 = etapes[ordre[0]]
    if a0 >= BASE_MINI and b0 >= BASE_MINI and len(ordre) >= 2:
        g.texte(s, 0.2, y_ch - 0.05, 8, 0.28, "Funnel – share of homepage visitors reaching each step", taille=11, gras=True, couleur="000000")
        avant = [etapes[k][0] / a0 * 100 for k in ordre]
        apres = [etapes[k][1] / b0 * 100 for k in ordre]
        g.colonnes(s, 0.2, y_ch + 0.25, 10.4, 6.75 - y_ch - 0.25, [ETAPES_EN.get(k, k) for k in ordre], [("Before V2", avant, "A5A5A5"), ("After V2", apres, "4472C4")], taille=9,
                   etiquettes=True, format_nombre='0"%"', legende=True, largeur_barre=40)
    note = ("Windows differ per market (before = the 28 days preceding the go-live; after = since the go-live): the later the go-live, the shorter the observation. "
            "Other factors may have moved at the same time (traffic mix, paid traffic): the gap cannot be attributed to V2 alone."
            + (" Markets with fewer than 100 visitors are shown as 'low base'." if peu else ""))
    g.texte(s, 0.2, 6.75, 10.8, 0.4, note, taille=7.5, couleur="595959", italique=True)
    return s


# ------------------------------------------------------------------ diapo 2 : tunnel par mode d'entrée (immatriculation / marque-modèle), avant / après
MOIS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ETAPES_ENTREE = ["Version", "Mileage", "Contact details", "Dealer", "Estimate"]


def _mois_lib(ym):
    return f"{MOIS_EN[int(ym[5:7]) - 1]} {ym[:4]}"


def _mois_avant(ym):
    a, m = int(ym[:4]), int(ym[5:7])
    return f"{a - 1}-12" if m == 1 else f"{a}-{m - 1:02d}"


def _entree_data(ctx, marque):
    """(lignes par marché, cumul des étapes par mode et par période) de « V2 REDESIGN FOCUS (entry mode) » (partagé V1 / V2) ; None sans marché affichable."""
    d = ctx.d
    tot = {"immat": [[0] * 5, [0] * 5], "marque_modele": [[0] * 5, [0] * 5]}      # [avant, après] par mode
    lignes = []
    parts = [0, 0, 0, 0]                                                          # leads plaque / marque-modèle avant, plaque / marque-modèle après
    for nom, m, pays in d.sites:
        if m != marque or pays not in PAYS_V2:
            continue
        j = d._site_json(nom) or {}
        dv, fe = j.get("v2_date"), j.get("funnelEntree") or {}
        if not dv or not fe:
            continue
        pre = _mois_avant(dv[:7])
        apres = [k for k in sorted(fe) if k > dv[:7]]
        if pre not in fe or not apres:
            continue
        post = apres[-1]
        if fe[pre]["immat"][0] < BASE_MINI or fe[post]["immat"][0] < BASE_MINI:        # base suffisante sur le parcours plaque, avant et après
            continue
        for mode in tot:
            for k in range(5):
                tot[mode][0][k] += fe[pre][mode][k]
                tot[mode][1][k] += fe[post][mode][k]
        ent = lambda mois: (j.get("leads", {}).get(mois, {}).get("entry") or {})
        e0, e1 = ent(pre), ent(post)
        p0, p1 = e0.get("Avec immatriculation", 0), e1.get("Avec immatriculation", 0)
        q0, q1 = e0.get("Marque / modele", 0), e1.get("Marque / modele", 0)
        parts = [parts[0] + p0, parts[1] + q0, parts[2] + p1, parts[3] + q1]
        sh = lambda p, q: (q / (p + q) * 100) if (p + q) else None
        coherent = lambda v: v[0] >= BASE_MINI and max(v) <= v[0] * 1.005      # un tunnel ne remonte pas : sinon le suivi des étapes a changé, on n'affiche pas
        c = lambda mode, w: (fe[w][mode][4] / fe[w][mode][0] * 100) if coherent(fe[w][mode]) else None
        f = lambda a, b: "n/a" if a is None or b is None else f"{a:.0f}% → {b:.0f}%"
        lignes.append((ORDRE_PAYS.index(pays), PAYS_V2[pays], dv, f"{_mois_lib(pre)} → {_mois_lib(post)}", f(sh(p0, q0), sh(p1, q1)),
                       f(c("immat", pre), c("immat", post)), f(c("marque_modele", pre), c("marque_modele", post))))
    if not lignes:
        return None
    lignes.sort()
    return lignes, tot


def focus_v2_entree(ctx, rv, marque):
    """Tunnel par mode de saisie du véhicule (plaque / marque-modèle), le mois qui précède la bascule contre le mois le plus récent après ; mêmes marchés (PT, FR, ES) que la diapo 1."""
    D = _entree_data(ctx, marque)
    if D is None:
        return None
    lignes, tot = D
    s = slide_revue(ctx, rv, "V2 REDESIGN FOCUS", sous_titre=f"{ctx.nom(marque)} – funnel by entry mode (plate / brand & model)", marque=marque, source=None)
    ent = [{"t": t, "taille": 8, "gras": True, "fond": "1F3864", "couleur": "FFFFFF"} for t in
           ("Market", "V2 go-live", "Month before → latest month after", "Brand/model share of leads", "Plate: Version → Estimate", "Brand/model: Version → Estimate")]
    rows = [ent] + [[{"t": r[1], "taille": 9, "gras": True, "align": PP_ALIGN.LEFT}, {"t": _date(r[2]), "taille": 9}, {"t": r[3], "taille": 8.5},
                     {"t": r[4], "taille": 8.5}, {"t": r[5], "taille": 8.5, "gras": True}, {"t": r[6], "taille": 8.5, "gras": True}] for r in lignes]
    _table(s, 0.2, 1.3, [1.2, 1.1, 2.6, 1.9, 2.0, 2.3], [0.42] + [0.38] * (len(rows) - 1), rows)
    y_ch = 1.3 + 0.42 + 0.38 * (len(rows) - 1) + 0.35
    g.texte(s, 0.2, y_ch - 0.05, 9, 0.28, "Funnel – share of Version-step visitors reaching each step, by entry mode (the home page is common to both)", taille=11, gras=True, couleur="000000")
    pct_ = lambda v: [x / v[0] * 100 if v[0] else 0 for x in v]
    series = [("Plate – before V2", pct_(tot["immat"][0]), "A5A5A5"), ("Plate – after V2", pct_(tot["immat"][1]), "4472C4")]
    if all(v[0] >= BASE_MINI and max(v) <= v[0] * 1.005 for v in tot["marque_modele"]):
        series += [("Brand/model – before V2", pct_(tot["marque_modele"][0]), "F4B183"), ("Brand/model – after V2", pct_(tot["marque_modele"][1]), "ED7D31")]
    g.colonnes(s, 0.2, y_ch + 0.25, 10.4, 6.75 - y_ch - 0.25, ETAPES_ENTREE, series, taille=9, etiquettes=True, format_nombre='0"%"', legende=True, largeur_barre=30)
    g.texte(s, 0.2, 6.75, 10.8, 0.4, "Monthly active users per entry path (GA4). 'Before' = the full month preceding the go-live month; 'after' = the latest month since the go-live (may be partial). "
            "Brand/model shown only when its steps are consistent before and after (n/a otherwise: tracking of that path may differ). Other factors may have moved at the same time: the gap cannot be attributed to V2 alone.", taille=7.5, couleur="595959", italique=True)
    return s
