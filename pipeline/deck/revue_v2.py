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


def focus_v2(ctx, rv, marque):
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
