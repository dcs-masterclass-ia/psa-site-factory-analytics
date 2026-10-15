"""Génère les drapeaux (PNG, coins arrondis, fond transparent) de pipeline/deck/drapeaux/ : python3 scripts/make-drapeaux.py
Dessins simplifiés (bandes de couleur, sans armoiries) : ils servent d'icône de marché en haut à droite des diapositives, comme dans les decks de référence."""

from pathlib import Path

from PIL import Image, ImageDraw

W, H, R = 484, 324, 28            # 2x l'affichage (1,21 x 0,81 po)
SORTIE = Path(__file__).resolve().parent.parent / "pipeline" / "deck" / "drapeaux"


def bandes(d, couleurs, vertical=True, poids=None):
    poids = poids or [1] * len(couleurs)
    total = sum(poids)
    pos = 0
    for c, p in zip(couleurs, poids):
        taille = (W if vertical else H) * p / total
        if vertical:
            d.rectangle([pos, 0, pos + taille, H], fill=c)
        else:
            d.rectangle([0, pos, W, pos + taille], fill=c)
        pos += taille


def drapeau_gb(d):
    d.rectangle([0, 0, W, H], fill="#012169")
    d.line([0, 0, W, H], fill="#FFFFFF", width=64)
    d.line([0, H, W, 0], fill="#FFFFFF", width=64)
    d.line([0, 0, W, H], fill="#C8102E", width=24)
    d.line([0, H, W, 0], fill="#C8102E", width=24)
    d.rectangle([W / 2 - 54, 0, W / 2 + 54, H], fill="#FFFFFF")
    d.rectangle([0, H / 2 - 54, W, H / 2 + 54], fill="#FFFFFF")
    d.rectangle([W / 2 - 32, 0, W / 2 + 32, H], fill="#C8102E")
    d.rectangle([0, H / 2 - 32, W, H / 2 + 32], fill="#C8102E")


DRAPEAUX = {
    "FR": lambda d: bandes(d, ["#0055A4", "#FFFFFF", "#EF4135"]),
    "BE": lambda d: bandes(d, ["#000000", "#FDDA24", "#EF3340"]),
    "IT": lambda d: bandes(d, ["#009246", "#FFFFFF", "#CE2B37"]),
    "DE": lambda d: bandes(d, ["#000000", "#DD0000", "#FFCE00"], vertical=False),
    "PL": lambda d: bandes(d, ["#FFFFFF", "#DC143C"], vertical=False),
    "AT": lambda d: bandes(d, ["#ED2939", "#FFFFFF", "#ED2939"], vertical=False),
    "LU": lambda d: bandes(d, ["#ED2939", "#FFFFFF", "#00A1DE"], vertical=False),
    "ES": lambda d: bandes(d, ["#AA151B", "#F1BF00", "#AA151B"], vertical=False, poids=[1, 2, 1]),
    "PT": lambda d: bandes(d, ["#006600", "#FF0000"], poids=[2, 3]),
    "GB": drapeau_gb,
}


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    for code, dessin in DRAPEAUX.items():
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        plat = Image.new("RGB", (W, H), "#FFFFFF")
        dessin(ImageDraw.Draw(plat))
        masque = Image.new("L", (W, H), 0)
        ImageDraw.Draw(masque).rounded_rectangle([0, 0, W - 1, H - 1], radius=R, fill=255)
        img.paste(plat, (0, 0), masque)
        # filet gris très fin pour les drapeaux à fond blanc
        ImageDraw.Draw(img).rounded_rectangle([0, 0, W - 1, H - 1], radius=R, outline=(200, 205, 212, 255), width=2)
        img.save(SORTIE / f"{code}.png", optimize=True)
        print(code, (SORTIE / f"{code}.png").stat().st_size)


if __name__ == "__main__":
    main()
