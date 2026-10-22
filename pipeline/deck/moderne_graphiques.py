"""Graphiques de la refonte « éditoriale » des revues : dessinés avec matplotlib (images PNG nettes, rendu identique dans toutes les versions de PowerPoint,
Keynote et Google Slides), police Inter embarquée (`polices/`, licence OFL). Fond transparent : l'image se pose sur n'importe quelle diapositive."""

import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

POLICES = Path(__file__).with_name("polices")
for f in POLICES.glob("Inter-*.ttf"):
    font_manager.fontManager.addfont(str(f))
plt.rcParams["font.family"] = "Inter"

ENCRE, GRIS, TRAIT = "#0B1020", "#7A8099", "#E7E9F1"
INDIGO, LAVANDE, PALE = "#2F3DFF", "#C9CEFF", "#EEF0FF"
VN, SANS, VO = "#2F3DFF", "#FF4D6D", "#FFA23A"
DPI = 240


def _h(c):
    return c if str(c).startswith("#") else "#" + str(c)


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def _fig(w, h):
    fig = plt.figure(figsize=(w, h))
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.patch.set_alpha(0)
    return fig, ax


def _pchip(x, y, n=240):
    """Interpolation monotone (Fritsch-Carlson) : courbe lisse sans dépassement."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    h, d = np.diff(x), np.diff(y) / np.diff(x)
    m = np.zeros_like(y)
    m[1:-1] = (d[:-1] + d[1:]) / 2
    m[0], m[-1] = d[0], d[-1]
    for i in range(len(d)):
        if d[i] == 0:
            m[i] = m[i + 1] = 0
        else:
            a, b = m[i] / d[i], m[i + 1] / d[i]
            s = a * a + b * b
            if s > 9:
                t = 3 / np.sqrt(s)
                m[i], m[i + 1] = t * a * d[i], t * b * d[i]
    xs = np.linspace(x[0], x[-1], n)
    idx = np.clip(np.searchsorted(x, xs) - 1, 0, len(h) - 1)
    t = (xs - x[idx]) / h[idx]
    h00, h10, h01, h11 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t, -2 * t**3 + 3 * t**2, t**3 - t**2
    return xs, h00 * y[idx] + h10 * h[idx] * m[idx] + h01 * y[idx + 1] + h11 * h[idx] * m[idx + 1]


def _fmt(v):
    return f"{v / 1000:.1f}k" if abs(v) >= 1000 else f"{int(round(v))}"


def _degrade_sous_courbe(ax, xs, ys, couleur, haut=0.34):
    from matplotlib.colors import to_rgb
    r, g, b = to_rgb(couleur)
    img = np.zeros((256, 1, 4))
    img[..., 0], img[..., 1], img[..., 2] = r, g, b
    img[..., 3] = np.linspace(haut, 0, 256)[:, None]
    ymax = max(ys)
    im = ax.imshow(img, extent=[xs[0], xs[-1], 0, ymax], origin="upper", aspect="auto", zorder=1)
    poly = ax.fill_between(xs, 0, ys, color="none")
    im.set_clip_path(poly.get_paths()[0], ax.transData)


def courbes(w, h, mois, ancien, courant, ecoules, etiq_ancien="2025", etiq_courant="2026", couleur=INDIGO):
    """Deux années en courbes lisses : N-1 en lavande (aire pâle), N en couleur avec aire en dégradé, dernier point annoté d'une pastille."""
    couleur = _h(couleur)
    fig, ax = _fig(w, h)
    x = np.arange(12)
    top = max(max(ancien), max(courant[:ecoules] or [0])) * 1.22 or 1
    xs, ya = _pchip(x, ancien)
    ax.fill_between(xs, 0, ya, color=PALE, zorder=0)
    ax.plot(xs, ya, color=LAVANDE, lw=2.2, zorder=2, solid_capstyle="round")
    if ecoules >= 2:
        xc, yc = _pchip(x[:ecoules], courant[:ecoules])
        _degrade_sous_courbe(ax, xc, yc, couleur)
        ax.plot(xc, yc, color=couleur, lw=3.2, zorder=3, solid_capstyle="round")
    ax.scatter(x[:ecoules], courant[:ecoules], s=34, color="white", edgecolor=couleur, linewidth=2, zorder=4)
    if ecoules:
        i = ecoules - 1
        ax.annotate(_fmt(courant[i]), (x[i], courant[i]), xytext=(0, 16), textcoords="offset points", ha="center", fontsize=10.5, fontweight="bold", color="white",
                    bbox=dict(boxstyle="round,pad=0.38,rounding_size=0.8", fc=couleur, ec="none"), zorder=6)
    ax.set_xlim(-0.95, 11.35); ax.set_ylim(0, top)
    for v in np.linspace(0, top, 5)[1:-1]:
        ax.axhline(v, color=TRAIT, lw=0.9, zorder=0)
        ax.text(-0.85, v, _fmt(v), color=GRIS, fontsize=8.5, va="bottom", ha="left")
    for i, m in enumerate(mois):
        ax.text(i, -top * 0.06, m, ha="center", va="top", color=GRIS if i >= ecoules else ENCRE, fontsize=9)
    ax.set_ylim(-top * 0.12, top)
    ax.axis("off")
    # légende
    ax.scatter([0.1], [top * 0.99], s=0)
    ax.plot([0.0, 0.45], [top * 0.97] * 2, color=LAVANDE, lw=3, solid_capstyle="round"); ax.text(0.55, top * 0.97, etiq_ancien, fontsize=9.5, color=GRIS, va="center")
    ax.plot([1.6, 2.05], [top * 0.97] * 2, color=couleur, lw=3, solid_capstyle="round"); ax.text(2.15, top * 0.97, etiq_courant, fontsize=9.5, color=ENCRE, va="center", fontweight="medium")
    return _png(fig)


def barres_annuelles(w, h, mois, ancien, courant, ecoules, couleur=INDIGO, etiq=("2025", "2026"), valeurs=False, taille_val=7):
    """Barres arrondies groupées N-1 (lavande) / N (couleur) ; au-dessus de chaque barre N, l'évolution en pastille."""
    couleur = _h(couleur)
    fig, ax = _fig(w, h)
    top = max(max(ancien), max(courant[:ecoules] or [0])) * (1.42 if valeurs else 1.3) or 1
    bw = 0.34
    for i in range(12):
        for k, (val, col) in enumerate(((ancien[i], LAVANDE), (courant[i] if i < ecoules else None, couleur))):
            if not val:
                continue
            x0 = i + (k - 1) * bw - (0 if k else 0.02) + 0.5 * bw * (1 if k else 0)
            x0 = i - bw + k * (bw + 0.04)
            ax.add_patch(FancyBboxPatch((x0, 0), bw, val, boxstyle=f"round,pad=0,rounding_size={bw / 2.2}", fc=col, ec="none", mutation_aspect=top / 12 / 1.0 * 0 + 1))
        if valeurs and ancien[i]:
            ax.text(i - bw / 2, ancien[i] + top * 0.02, f"{int(round(ancien[i])):,}".replace(",", " "), ha="center", va="bottom", fontsize=taille_val, color=GRIS)
        if i < ecoules and ancien[i]:
            e = (courant[i] - ancien[i]) / ancien[i] * 100
            ax.text(i + bw / 2 + 0.04, courant[i] + top * 0.02, (f"{int(round(courant[i])):,}".replace(",", " ") + "\n" if valeurs else "") + f"{e:+.0f}%", ha="center", va="bottom", fontsize=taille_val if valeurs else 7.6,
                    color="#0F9D58" if e >= 0 else "#D93025", fontweight="bold", linespacing=1.15)
    for i, m in enumerate(mois):
        ax.text(i + 0.02, -top * 0.05, m, ha="center", va="top", color=ENCRE if i < ecoules else GRIS, fontsize=9)
    ax.set_xlim(-0.8, 11.8); ax.set_ylim(-top * 0.2, top)
    ax.axhline(0, color=TRAIT, lw=1)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((-0.7, top * 0.955), 0.4, top * 0.03, boxstyle="round,pad=0,rounding_size=0.05", fc=LAVANDE, ec="none"))
    ax.text(-0.2, top * 0.97, etiq[0], fontsize=9.5, color=GRIS, va="center")
    ax.add_patch(FancyBboxPatch((1.1, top * 0.955), 0.4, top * 0.03, boxstyle="round,pad=0,rounding_size=0.05", fc=couleur, ec="none"))
    ax.text(1.6, top * 0.97, etiq[1], fontsize=9.5, color=ENCRE, va="center", fontweight="medium")
    return _png(fig)


def barres_marques(w, h, lignes, couleur=INDIGO, taille=10.5):
    """Barres horizontales arrondies : (nom, valeur, part %, valeur N-1) ; valeur en gras à droite, part en gris."""
    couleur = _h(couleur)
    fig, ax = _fig(w, h)
    n = len(lignes)
    vmax = max(l[1] for l in lignes) or 1
    pas = 1.0
    for i, (nom, val, part, v1) in enumerate(lignes):
        y = (n - 1 - i) * pas
        ax.add_patch(FancyBboxPatch((0, y - 0.19), vmax * 1.0, 0.38, boxstyle="round,pad=0,rounding_size=0.19", fc=PALE, ec="none", mutation_aspect=vmax / n / 1.2))
        ax.add_patch(FancyBboxPatch((0, y - 0.19), max(val, vmax * 0.012), 0.38, boxstyle="round,pad=0,rounding_size=0.19", fc=couleur if i == 0 else "#5C67FF" if i < 3 else "#8E96FF", ec="none", mutation_aspect=vmax / n / 1.2))
        ax.text(-vmax * 0.02, y, nom, ha="right", va="center", fontsize=taille, color=ENCRE, fontweight="medium")
        ax.text(vmax * 1.04, y, f"{int(round(val)):,}".replace(",", " "), ha="left", va="center", fontsize=taille, color=ENCRE, fontweight="bold")
        ax.text(vmax * 1.3, y, f"{part:.0f}%", ha="left", va="center", fontsize=taille - 0.5, color=GRIS)
    ax.set_xlim(-vmax * 0.42, vmax * 1.45); ax.set_ylim(-0.6, n - 0.4)
    ax.axis("off")
    return _png(fig)


def anneau(w, h, valeurs, couleurs, centre, sous_centre=""):
    couleurs = [_h(c) for c in couleurs]
    fig, ax = _fig(w, h)
    ax.pie(valeurs, colors=couleurs, startangle=90, counterclock=False, wedgeprops=dict(width=0.26, edgecolor="white", linewidth=3))
    ax.text(0, 0.06, centre, ha="center", va="center", fontsize=26, fontweight="bold", color=ENCRE)
    ax.text(0, -0.2, sous_centre, ha="center", va="center", fontsize=9.5, color=GRIS)
    ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05); ax.set_aspect("equal"); ax.axis("off")
    return _png(fig)


def points_decor(w, h):
    """Décor de couverture : grille de points dont la taille et l'opacité décroissent du centre vers le bord (cercle)."""
    fig, ax = _fig(w, h)
    n = 25
    c = (n - 1) / 2
    for i in range(n):
        for j in range(n):
            d = np.hypot(i - c, j - c) / c
            if d > 1:
                continue
            ax.scatter(i, j, s=(1 - d) ** 1.2 * 90 + 2, color="#4E5BFF", alpha=0.25 + 0.75 * (1 - d), linewidths=0)
    ax.set_xlim(-1, n); ax.set_ylim(-1, n); ax.set_aspect("equal"); ax.axis("off")
    return _png(fig)


def barres_empilees_h(w, h, lignes):
    """Barres horizontales empilées par projet d'achat (bleu / rouge / orange) : (nom, {VN, SANS, VO}) ; total en gras à droite."""
    fig, ax = _fig(w, h)
    n = len(lignes)
    vmax = max(sum(v.values()) for _, v in lignes) or 1
    for i, (nom, v) in enumerate(lignes):
        y = n - 1 - i
        x = 0
        tot = sum(v.values()) or 1
        for k, col in (("VN", VN), ("SANS", SANS), ("VO", VO)):
            val = v.get(k, 0)
            if not val:
                continue
            ax.add_patch(FancyBboxPatch((x + 0.004 * vmax, y - 0.2), max(val - 0.008 * vmax, 0.001), 0.4, boxstyle="round,pad=0,rounding_size=0.1", fc=col, ec="none", mutation_aspect=vmax / n / 1.2))
            if val / vmax > 0.07:
                ax.text(x + val / 2, y, f"{val / tot * 100:.0f}%", ha="center", va="center", fontsize=8.5, color="white", fontweight="bold")
            x += val
        ax.text(-vmax * 0.02, y, nom, ha="right", va="center", fontsize=10.5, color=ENCRE, fontweight="medium")
        ax.text(x + vmax * 0.02, y, f"{int(round(tot)):,}".replace(",", " "), ha="left", va="center", fontsize=10.5, color=ENCRE, fontweight="bold")
    ax.set_xlim(-vmax * 0.3, vmax * 1.14); ax.set_ylim(-0.6, n - 0.4); ax.axis("off")
    return _png(fig)


def croissance(w, h, lignes):
    """Évolution annuelle par marque : (nom, % , valeur). Tige + pastille, verte au-dessus de zéro, rouge en dessous."""
    fig, ax = _fig(w, h)
    n = len(lignes)
    vmax = max(abs(l[1]) for l in lignes) or 1
    ax.axvline(0, color=TRAIT, lw=1.2)
    for i, (nom, e, val) in enumerate(lignes):
        y = n - 1 - i
        col = "#12A150" if e >= 0 else "#E5384F"
        ax.plot([0, e], [y, y], color=col, lw=5, solid_capstyle="round", alpha=0.28)
        ax.scatter([e], [y], s=150, color=col, zorder=3)
        ax.text(e + (vmax * 0.04 if e >= 0 else -vmax * 0.04), y, f"{e:+.0f}%", ha="left" if e >= 0 else "right", va="center", fontsize=10.5, fontweight="bold", color=col)
        ax.text(-vmax * 0.06 if vmax else 0, y, nom, ha="right", va="center", fontsize=10.5, color=ENCRE, fontweight="medium") if False else None
        ax.text(-vmax * 0.02, y, "", fontsize=1)
    ax.set_xlim(-vmax * 0.35, vmax * 1.2); ax.set_ylim(-0.6, n - 0.4); ax.axis("off")
    for i, (nom, e, val) in enumerate(lignes):
        ax.text(-vmax * 0.38, n - 1 - i, nom, ha="left", va="center", fontsize=10.5, color=ENCRE, fontweight="medium")
        ax.text(-vmax * 0.38 + vmax * 0.01, n - 1 - i - 0.34, f"{_fmt(val)} leads", ha="left", va="center", fontsize=8, color=GRIS)
    ax.set_xlim(-vmax * 0.5, vmax * 1.2)
    return _png(fig)


def barres_duo(w, h, lignes, etiq=("N-1", "N"), couleur=INDIGO):
    """Barres horizontales jumelées N-1 (lavande) / N : (nom, valeur N-1, valeur N)."""
    couleur = _h(couleur)
    fig, ax = _fig(w, h)
    n = len(lignes)
    vmax = max(max(a, b) for _, a, b in lignes) or 1
    for i, (nom, a, b) in enumerate(lignes):
        y = n - 1 - i
        ax.add_patch(FancyBboxPatch((0, y + 0.02), max(a, vmax * 0.01), 0.27, boxstyle="round,pad=0,rounding_size=0.1", fc=LAVANDE, ec="none", mutation_aspect=vmax / n / 1.2))
        ax.add_patch(FancyBboxPatch((0, y - 0.3), max(b, vmax * 0.01), 0.27, boxstyle="round,pad=0,rounding_size=0.1", fc=couleur, ec="none", mutation_aspect=vmax / n / 1.2))
        ax.text(a + vmax * 0.015, y + 0.155, _fmt(a), va="center", fontsize=8.5, color=GRIS)
        ax.text(b + vmax * 0.015, y - 0.165, _fmt(b), va="center", fontsize=9.5, color=ENCRE, fontweight="bold")
        ax.text(-vmax * 0.02, y, nom, ha="right", va="center", fontsize=10.5, color=ENCRE, fontweight="medium")
    ax.set_xlim(-vmax * 0.3, vmax * 1.12); ax.set_ylim(-0.7, n - 0.3); ax.axis("off")
    return _png(fig)


def courbes_projets(w, h, cats, series):
    """Tendance par projet d'achat sur 14 mois : trois courbes lisses, toutes les valeurs étiquetées. series = [(nom, valeurs, couleur)]."""
    fig, ax = _fig(w, h)
    x = np.arange(len(cats))
    top = max(max(v) for _, v, _ in series) * 1.18 or 1
    for nom, vals, col in series:
        col = _h(col)
        xs, ys = _pchip(x, vals)
        ax.plot(xs, ys, color=col, lw=2.6, solid_capstyle="round", zorder=3)
        ax.scatter(x, vals, s=22, color="white", edgecolor=col, linewidth=1.6, zorder=4)
        for xi, v in zip(x, vals):
            ax.text(xi, v + top * 0.035, f"{int(round(v)):,}".replace(",", " "), ha="center", va="bottom", fontsize=6.6, color=col, fontweight="medium")
    for v in np.linspace(0, top, 4)[1:-1]:
        ax.axhline(v, color=TRAIT, lw=0.8, zorder=0)
    for xi, c in zip(x, cats):
        ax.text(xi, -top * 0.05, c, ha="center", va="top", fontsize=7.6, color=GRIS)
    ax.set_xlim(-0.6, len(cats) - 0.4); ax.set_ylim(-top * 0.14, top); ax.axis("off")
    return _png(fig)


def colonnes_empilees(w, h, cats, series, groupes=None, surligne=(), taille=7.5):
    """Colonnes empilées (une couleur par projet) avec valeur et part dans chaque segment, total au-dessus. series = [(nom, valeurs, couleur)] du bas vers le haut ;
    groupes = [(libellé, premier index, nombre)] pour étiqueter des groupes de colonnes (ex. une marque = 4 périodes) ; surligne = indices de colonnes à fond pâle."""
    fig, ax = _fig(w, h)
    n = len(cats)
    tot = [sum(s[1][i] for s in series) for i in range(n)]
    top = max(tot) * 1.14 or 1
    for i in surligne:
        ax.add_patch(FancyBboxPatch((i - 0.5, 0), 1, top * 1.03, boxstyle="round,pad=0,rounding_size=0.08", fc=PALE, ec="none", zorder=0, mutation_aspect=top / n / 1.2))
    bw = 0.62
    for i in range(n):
        base = 0
        for nom, vals, col in series:
            v = vals[i]
            if not v:
                continue
            ax.add_patch(FancyBboxPatch((i - bw / 2, base + top * 0.002), bw, max(v - top * 0.004, 0.001), boxstyle="round,pad=0,rounding_size=0.04", fc=_h(col), ec="none", zorder=2, mutation_aspect=top / n / 1.2))
            if v / top > 0.07:
                ax.text(i, base + v / 2, f"{int(round(v)):,}".replace(",", " ") + f"\n{v / tot[i] * 100:.0f}%", ha="center", va="center", fontsize=taille - 0.8, color="white", fontweight="bold", linespacing=1.1, zorder=3)
            base += v
        if tot[i]:
            ax.text(i, tot[i] + top * 0.015, f"{int(round(tot[i])):,}".replace(",", " "), ha="center", va="bottom", fontsize=taille, color=ENCRE, fontweight="bold")
    for i, c in enumerate(cats):
        ax.text(i, -top * 0.03, c, ha="center", va="top", fontsize=taille, color=GRIS)
    for lib, i0, k in (groupes or []):
        ax.text(i0 + (k - 1) / 2, -top * 0.115, lib, ha="center", va="top", fontsize=taille + 1.2, color=ENCRE, fontweight="bold")
    ax.axhline(0, color=TRAIT, lw=1)
    ax.set_xlim(-0.6, n - 0.4); ax.set_ylim(-top * 0.2, top * 1.05); ax.axis("off")
    return _png(fig)
