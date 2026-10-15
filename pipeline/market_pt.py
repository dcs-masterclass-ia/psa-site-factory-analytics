"""Portugal (ACAP) : collecte DÉTERMINISTE des immatriculations de voitures particulières neuves, sans modèle de langage.

Source : les fichiers publiés par l'ACAP (Associação Automóvel de Portugal) sous https://www.acap.pt/pt/estatisticas :
  - « Matrículas de Veículos Automóveis por Marca » (.xlsx) : feuilles « RESUMO » (total, cumul, variations) et « Lig. Passageiros »
    (TOUTES les marques : unités du mois, mois de l'an dernier, variation, part de marché, cumul et variation du cumul) ;
  - « Matrículas de Veículos Automóveis por tipo de energia » (.pdf) : mix du mois et du cumul (essence, diesel, BEV, PHEV, HEV, GPL, GNC).
Les chiffres sont lus tels quels dans ces fichiers : aucun chiffre estimé ni retranscrit à la main. Sortie : un relevé au format attendu par
pipeline/market.py (validation et fusion identiques aux autres marchés), écrit dans market_in/PT.json.

Usage : python -m pipeline.market_pt market_in/PT.json
"""

import json
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://www.acap.pt"
PAGE_STATS = BASE + "/pt/estatisticas"
LIEN_MARQUES = "por Marca"
LIEN_ENERGIE = "por tipo de energia"

MOIS_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def telecharge(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def trouve_liens(html):
    """[(libellé, url absolue)] des documents de la page de statistiques."""
    out = []
    for m in re.finditer(r'<a[^>]+href="([^"]+\.(?:xlsx|pdf))"[^>]*>(.*?)</a>', html, flags=re.S | re.I):
        href, lib = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        out.append((lib, href if href.startswith("http") else BASE + href))
    return out


# ------------------------------------------------------------------ xlsx (sans dépendance : XML brut)

def _partages(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    x = z.read("xl/sharedStrings.xml").decode("utf8")
    return [re.sub(r"<[^>]+>", "", si) for si in re.findall(r"<si>(.*?)</si>", x, flags=re.S)]


def feuille(z, nom):
    """Cellules d'une feuille par son nom : {(ligne, colonne): valeur}."""
    wb = z.read("xl/workbook.xml").decode("utf8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf8")
    rid = None
    for m in re.finditer(r'<sheet [^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb):
        if m.group(1) == nom:
            rid = m.group(2)
    if rid is None:
        raise ValueError(f"feuille « {nom} » absente")
    cible = re.search(r'<Relationship [^>]*Id="%s"[^>]*Target="([^"]+)"' % rid, rels) or re.search(r'<Relationship [^>]*Target="([^"]+)"[^>]*Id="%s"' % rid, rels)
    chemin = "xl/" + cible.group(1).lstrip("/").replace("xl/", "")
    ss = _partages(z)
    cells = {}
    for r, corps in re.findall(r'<row [^>]*r="(\d+)"[^>]*>(.*?)</row>', z.read(chemin).decode("utf8"), flags=re.S):
        for m in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', corps, flags=re.S):
            v = re.search(r"<v>(.*?)</v>", m.group(3) or "")
            if not v:
                continue
            val = v.group(1)
            if 't="s"' in m.group(2):
                val = ss[int(val)]
            cells[(int(r), m.group(1))] = val
    return cells


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def lit_marques(z):
    """Feuille « Lig. Passageiros » -> (mois 'AAAA-MM', [marques]). Les variations sont en % ; la part de marché est celle du mois."""
    c = feuille(z, "Lig. Passageiros")
    mois_nom = str(c.get((6, "B"), "")).strip().lower()
    annee = str(c.get((8, "B"), "")).strip()
    if mois_nom not in MOIS_PT or not re.fullmatch(r"20\d\d", annee):
        raise ValueError(f"période illisible ({mois_nom!r} {annee!r})")
    mois = f"{annee}-{MOIS_PT.index(mois_nom) + 1:02d}"
    marques, r = [], 9
    while True:
        nom = c.get((r, "A"))
        if nom is None or str(nom).strip().lower() == "total":
            break
        u, u0, var, part, cum, cum0, cvar = (_num(c.get((r, k))) for k in "BCDEGHI")
        if u is not None and (u > 0 or (cum or 0) > 0):
            m = {"name": str(nom).strip(), "units": int(u)}
            if part is not None:
                m["share_pct"] = round(part, 2)
            if var is not None and u0:
                m["yoy_pct"] = round(var, 1)
            if cum is not None:
                m["ytd_units"] = int(cum)
            if cvar is not None and cum0:
                m["ytd_yoy_pct"] = round(cvar, 1)
            marques.append(m)
        r += 1
        if r > 400:
            raise ValueError("table des marques sans ligne « Total »")
    marques.sort(key=lambda m: -m["units"])
    return mois, marques


def lit_resume(z):
    """Feuille « RESUMO » : ligne « Lig Passageiros » -> total du mois, variation, cumul, variation du cumul."""
    c = feuille(z, "RESUMO")
    for r in range(1, 40):
        if str(c.get((r, "C"), "")).strip().lower().startswith("lig passageiros"):
            total, var, ytd, ytd_var = _num(c.get((r, "D"))), _num(c.get((r, "F"))), _num(c.get((r, "G"))), _num(c.get((r, "I")))
            return {"total": int(total), "yoy_pct": round(var * 100, 1), "ytd_total": int(ytd), "ytd_yoy_pct": round(ytd_var * 100, 1)}
    raise ValueError("ligne « Lig Passageiros » absente de la feuille RESUMO")


# ------------------------------------------------------------------ pdf (pdftotext -layout)

_NUM = re.compile(r"\d{1,3}(?: \d{3})*(?:,\d+)?%?")
_COLS = re.compile(r"Ligeiros Passageiros|Ligeiros Mercadorias|Pesados Mercadorias|Pesados Passageiros")
LIGNES_ENERGIE = {
    "gasolina": "petrol_pct", "gasóleo": "diesel_pct", "elétrico (bev)": "electric_pct",
}


def lit_energie(texte_page):
    """Page « Ligeiros Passageiros / Mercadorias… » du PDF d'énergie -> parts (en %) du mois et du cumul pour les voitures particulières.
    Les colonnes sont repérées par la position des intitulés de l'en-tête (certaines cellules sont vides)."""
    lignes = texte_page.split("\n")
    ent = next((l for l in lignes if l.count("Ligeiros Passageiros") >= 2), None)
    if ent is None:
        raise ValueError("en-tête à 8 colonnes introuvable")
    cols = [(m.start(), m.end()) for m in _COLS.finditer(ent)]
    c_mois, c_cum = cols[0], cols[4]

    def valeur(ligne, col, decalage=0):
        for m in _NUM.finditer(ligne):
            fin = m.end()
            if col[0] - 4 <= fin <= col[1] + 6:
                return float(m.group(0).rstrip("%").replace(" ", "").replace(",", "."))
        return None

    def pct(cle, col):
        # l'intitulé peut être précédé d'un mot de groupe (« Híbridos », « Plug-in ») : on cherche la ligne qui CONTIENT « % Étiquette » suivi d'au moins 2 espaces
        motif = re.compile(r"(?:^|\s)" + re.escape(cle) + r"(?=\s{2,})", re.I)
        for l in lignes:
            if motif.search(l):
                return valeur(l, col)
        return None

    def somme(cles, col):
        v = [pct(k, col) for k in cles]
        v = [x for x in v if x is not None]
        return round(sum(v), 1) if v else None

    sortie = {}
    for suffixe, col in (("", c_mois), ("ytd_", c_cum)):
        mix = {
            "electric_pct": pct("% Elétrico (BEV)", col),
            "petrol_pct": pct("% Gasolina", col),
            "diesel_pct": pct("% Gasóleo", col),
            "phev_pct": somme(["% PHEV/Gasolina", "% PHEV/Gasóleo"], col),
            "hybrid_pct": somme(["% HEV/Gasolina", "% HEV/Gasóleo"], col),
        }
        for k, v in mix.items():
            if v is not None:
                sortie[suffixe + k if suffixe else k] = v
    return sortie


def page_voitures(pdf_octets):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "e.pdf"
        f.write_bytes(pdf_octets)
        n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(f)], capture_output=True, text=True).stdout).group(1))
        for p in range(1, n + 1):
            t = subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), str(f), "-"], capture_output=True, text=True).stdout
            if any(l.count("Ligeiros Passageiros") >= 2 for l in t.split("\n")):
                return t
    raise ValueError("page « voitures particulières » absente du PDF d'énergie")


def construit(url_xlsx, xlsx_octets, url_pdf=None, pdf_octets=None):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "m.xlsx"
        f.write_bytes(xlsx_octets)
        z = zipfile.ZipFile(f)
        mois, marques = lit_marques(z)
        resume = lit_resume(z)
    releve = {"periode": mois, "source_url": url_xlsx,
              "citation": f"ACAP, « Matrículas de Veículos Automóveis por Marca », feuilles « RESUMO » et « Lig. Passageiros » ({mois})",
              **resume, "marques": marques}
    if pdf_octets:
        try:
            for k, v in lit_energie(page_voitures(pdf_octets)).items():
                releve[k] = v
            releve["citation"] += " ; ACAP, « Matrículas … por tipo de energia »"
        except Exception as e:     # le mix est un complément : son absence ne bloque pas le relevé
            print(f"PT : mix par énergie indisponible ({type(e).__name__}: {e})", file=sys.stderr)
    return releve


def main():
    sortie = Path(sys.argv[1] if len(sys.argv) > 1 else "market_in/PT.json")
    liens = trouve_liens(telecharge(PAGE_STATS).decode("utf8", errors="replace"))
    xl = next((u for l, u in liens if LIEN_MARQUES.lower() in l.lower() and u.lower().endswith(".xlsx")), None)
    pdf = next((u for l, u in liens if LIEN_ENERGIE.lower() in l.lower() and u.lower().endswith(".pdf")), None)
    if not xl:
        print("PT : fichier « par Marca » introuvable sur la page de statistiques", file=sys.stderr)
        return 1
    releve = construit(xl, telecharge(xl), pdf, telecharge(pdf) if pdf else None)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps({"releves": [releve]}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"PT : {releve['periode']} — {releve['total']} voitures, {len(releve['marques'])} marques, mix {'oui' if 'electric_pct' in releve else 'non'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
