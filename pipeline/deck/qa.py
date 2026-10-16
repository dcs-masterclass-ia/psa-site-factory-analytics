"""Contrôle qualité des CHIFFRES d'une présentation, à partir de sa table de faits (faits.py).

Trois niveaux : erreur (le deck se contredit : à corriger avant d'envoyer), alerte (à regarder : donnée partielle, valeur douteuse), info (écart connu ou sans conséquence).
Les contrôles sont codés (rapides, reproductibles, sans modèle) :
  - coherence_sources   : un même chiffre (métrique, marque, période) doit être identique sur toutes les diapositives qui l'affichent ;
  - sommes              : un total affiché doit valoir la somme des marques qu'il couvre ;
  - projets             : leads VN + sans projet + used cars = leads, partout où les trois sont affichés ;
  - mensuel_trimestre   : les trois mois d'un trimestre somment au total du trimestre ;
  - entonnoir           : sessions >= In Journey >= GA leads ;
  - vraisemblance       : chute à zéro, rapport de 1 à 10 000 entre deux marques voisines, valeurs négatives ;
  - fraicheur           : la période est-elle terminée dans chaque source ?
"""

import re
from collections import defaultdict

SEUIL_ZERO_N1 = 50           # une marque à 0 alors qu'elle avait au moins autant de leads la période de comparaison : alerte
METRIQUES_PROJETS = ("leads_vn", "leads_sans", "leads_vo")


def _cle(f):
    return (f["metrique"], f.get("marque"), f["periode"])


def _msg(code, texte, **details):
    return {"code": code, "message": texte, **details}


def _mois_du_trimestre(periode):
    """« Q3-2026 » -> ['2026-07', '2026-08', '2026-09'] ; None si ce n'est pas un trimestre."""
    m = re.fullmatch(r"Q([1-4])-(\d{4})", periode or "")
    if not m:
        return None
    q, an = int(m.group(1)), int(m.group(2))
    return [f"{an}-{(q - 1) * 3 + k:02d}" for k in (1, 2, 3)]


def _par_cle(faits):
    out = defaultdict(list)
    for f in faits:
        out[_cle(f)].append(f)
    return out


def _fmt(f):
    return f"{f.get('slide') or f.get('source')}: {f['valeur']}"


def coherence_sources(faits):
    """-> (erreurs, infos). Deux valeurs différentes pour un même chiffre : erreur si elles portent sur le même périmètre, info si les périmètres annoncés diffèrent
    (ex. sessions « BE » du tableau d'ensemble et « BE+LU » du deep dive)."""
    erreurs, infos = [], []
    for (metrique, marque, periode), fs in _par_cle(faits).items():
        par_perim = defaultdict(list)
        for f in fs:
            par_perim[f.get("perimetre")].append(f)
        cible = marque or "total"
        for perim, g_ in par_perim.items():
            if len({f["valeur"] for f in g_}) > 1:
                erreurs.append(_msg("chiffre_different", f"{metrique} {cible} {periode} : valeurs différentes selon les diapositives",
                                    metrique=metrique, marque=marque, periode=periode, valeurs=[_fmt(f) for f in g_]))
        if len(par_perim) > 1 and len({f["valeur"] for f in fs}) > 1:
            infos.append(_msg("perimetres_differents", f"{metrique} {cible} {periode} : périmètres différents ({', '.join(str(p) for p in par_perim)}), valeurs différentes",
                              metrique=metrique, marque=marque, periode=periode, valeurs=[f"{f.get('perimetre')}: {_fmt(f)}" for f in fs]))
    return erreurs, infos


def sommes(faits):
    res = []
    par = _par_cle(faits)
    for (metrique, marque, periode), fs in par.items():
        if marque is not None:
            continue
        for f in fs:
            marques = f.get("marques")
            if not marques:
                continue
            vals = []
            manquantes = []
            for m in marques:
                v = par.get((metrique, m, periode))
                if v:
                    vals.append(v[0]["valeur"])
                else:
                    manquantes.append(m)
            if manquantes:
                continue                       # on ne compare que si toutes les marques couvertes ont une valeur affichée
            if sum(vals) != f["valeur"]:
                res.append(_msg("somme_incorrecte", f"{metrique} {periode} : le total affiché ({f['valeur']}, {f.get('slide')}) ≠ somme des marques ({sum(vals)})",
                                metrique=metrique, periode=periode, total=f["valeur"], somme=sum(vals), slide=f.get("slide")))
    return res


def projets(faits):
    res = []
    par = _par_cle(faits)
    for (metrique, marque, periode), fs in list(par.items()):
        if metrique != "leads_vn":
            continue
        autres = [par.get((m, marque, periode)) for m in ("leads_sans", "leads_vo")]
        total = par.get(("leads", marque, periode))
        if not total or not all(autres):
            continue
        s = fs[0]["valeur"] + autres[0][0]["valeur"] + autres[1][0]["valeur"]
        if s != total[0]["valeur"]:
            res.append(_msg("projets_incoherents", f"leads {marque or 'total'} {periode} : VN + sans projet + used cars = {s} ≠ leads = {total[0]['valeur']}",
                            marque=marque, periode=periode, somme_projets=s, leads=total[0]["valeur"]))
    return res


def mensuel_trimestre(faits):
    res = []
    par = _par_cle(faits)
    for (metrique, marque, periode), fs in par.items():
        mois = _mois_du_trimestre(periode)
        if not mois:
            continue
        vals = [par.get((metrique, marque, m)) for m in mois]
        if not all(vals):
            continue
        s = sum(v[0]["valeur"] for v in vals)
        if s != fs[0]["valeur"]:
            res.append(_msg("mensuel_vs_trimestre", f"{metrique} {marque or 'total'} {periode} : somme des 3 mois = {s} ≠ total du trimestre = {fs[0]['valeur']}",
                            metrique=metrique, marque=marque, periode=periode, somme_mois=s, total=fs[0]["valeur"]))
    return res


def entonnoir(faits):
    res = []
    par = _par_cle(faits)
    cles = {(m, p) for (me, m, p) in par if me in ("sessions", "in_journey", "ga_leads")}
    for marque, periode in cles:
        s, ij, gl = (par.get((me, marque, periode)) for me in ("sessions", "in_journey", "ga_leads"))
        if s and ij and ij[0]["valeur"] > s[0]["valeur"]:
            res.append(_msg("entonnoir", f"{marque} {periode} : In Journey ({ij[0]['valeur']}) > sessions ({s[0]['valeur']})", marque=marque, periode=periode))
        if ij and gl and gl[0]["valeur"] > ij[0]["valeur"]:
            res.append(_msg("entonnoir", f"{marque} {periode} : GA leads ({gl[0]['valeur']}) > In Journey ({ij[0]['valeur']})", marque=marque, periode=periode))
    return res


def vraisemblance(faits, comparaisons=None):
    """comparaisons : [(periode, periode_de_comparaison)] pour repérer les marques tombées à zéro."""
    res = []
    par = _par_cle(faits)
    for f in faits:
        if isinstance(f["valeur"], (int, float)) and f["valeur"] < 0:
            res.append(_msg("valeur_negative", f"{f['metrique']} {f.get('marque')} {f['periode']} négatif ({f['valeur']}), {f.get('slide')}"))
    for per, ref in comparaisons or []:
        for (metrique, marque, periode), fs in par.items():
            if periode != per or marque is None or metrique not in ("leads", "sessions"):
                continue
            r = par.get((metrique, marque, ref))
            if r and fs[0]["valeur"] == 0 and r[0]["valeur"] >= SEUIL_ZERO_N1:
                res.append(_msg("chute_a_zero", f"{metrique} {marque} : 0 en {periode} contre {r[0]['valeur']} en {ref}", marque=marque, periode=periode))
    return res


def fraicheur(infos):
    """infos = {'fin_periode': 'AAAA-MM-JJ', 'dernier_jour_leads': ..., 'dernier_jour_ga4': ..., 'collecte_c1st': ...} (chaînes ISO ; clés absentes ignorées)."""
    res = []
    fin = infos.get("fin_periode")
    for cle, lib in (("dernier_jour_leads", "back-office (leads)"), ("collecte_c1st", "C1ST")):
        v = infos.get(cle)
        if fin and v and v < fin:
            res.append(_msg("donnee_partielle", f"{lib} : dernière donnée le {v}, la période se termine le {fin} : chiffres partiels", source=lib, date=v, fin=fin))
    return res


def controle(faits, infos_sources=None, comparaisons=None):
    """-> {erreurs, alertes, infos, nb_faits}. Chaque entrée : {code, message, ...}."""
    f = faits.lignes if hasattr(faits, "lignes") else faits
    e1, i1 = coherence_sources(f)
    erreurs = e1 + sommes(f) + projets(f) + mensuel_trimestre(f) + entonnoir(f)
    alertes = vraisemblance(f, comparaisons) + fraicheur(infos_sources or {})
    return {"erreurs": erreurs, "alertes": alertes, "infos": i1, "nb_faits": len(f)}


def resume(rapport):
    return {"erreurs": len(rapport["erreurs"]), "alertes": len(rapport["alertes"]), "infos": len(rapport["infos"]), "faits": rapport["nb_faits"]}
