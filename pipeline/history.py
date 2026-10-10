"""Historique profond (leads BO, GA4, Search Console) pour Converge.

Les fichiers data/<site>.json du dashboard ne gardent que 16 mois : les
etendre ralentirait le dashboard. L'historique profond vit a part, dans
data/history/<source>/<site>.csv.gz (repo de donnees prive), au format CSV
compresse : lisible tel quel par pandas, Excel, Tableau ou Converge. Le
dashboard n'y touche pas.

Profondeur mesuree le 09/10/2026 :
  - leads BO : janvier 2020 (volume reel a partir de 2021)
  - GA4      : creation de la propriete (mars-septembre 2022 selon le site)
  - Search Console : 16 mois glissants cote API -> chaque passage FUSIONNE avec
    le fichier existant, ce qui archive ce que Google finit par effacer.

Jamais de donnee personnelle : les leads sont agreges par jour (source,
appareil, carburant, projet d'achat, marque reprise, statut), sans telephone,
commentaire ni identifiant.

Usage :
  python -m pipeline.history leads [--sites "OPEL FR" ...] [--depuis 2020-01-01]
  python -m pipeline.history ga4   [--sites "OPEL FR" ...] [--depuis 2022-01-01]
  python -m pipeline.history gsc   [--sites "OPEL FR" ...]
  python -m pipeline.history <source> --dry-run     # ecrit dans /tmp, rien de commite
"""

import argparse
import csv
import gzip
import io
import re
import socket
import sys
import time
import urllib.error
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from pipeline import leads_extract as L

RACINE = Path(__file__).resolve().parent.parent
DATA_DIR = RACINE / "data"
HIST = DATA_DIR / "history"


def _slug(nom):
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", nom.lower()))


def ecrit_csv_gz(chemin, entete, lignes):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tampon = io.StringIO()
    w = csv.writer(tampon, lineterminator="\n")
    w.writerow(entete)
    w.writerows(lignes)
    with gzip.open(chemin, "wt", encoding="utf-8", newline="") as f:
        f.write(tampon.getvalue())


def lit_csv_gz(chemin):
    if not chemin.exists():
        return []
    with gzip.open(chemin, "rt", encoding="utf-8", newline="") as f:
        return list(csv.reader(f))[1:]


def remplace_depuis(chemin, nouvelles, depuis_iso):
    """Fusion incrementale : garde les lignes existantes ANTERIEURES a depuis_iso
    (colonne 0 = date ou mois AAAA-MM), remplace tout ce qui est >= par les
    nouvelles lignes. Un re-passage sur une fenetre recente corrige donc les
    leads requalifies apres coup (doublon, test) sans jamais perdre l'ancien."""
    cle = depuis_iso[:len(depuis_iso)] if len(depuis_iso) == 10 else depuis_iso
    gardees = [l for l in lit_csv_gz(chemin) if l and l[0] < cle]
    return gardees + [[str(x) for x in l] for l in nouvelles]


def publie(chemins, message, dry_run):
    if dry_run:
        print(f"  (dry-run) {len(chemins)} fichier(s) ecrit(s), rien de commite")
        return
    from pipeline.build import _commit_et_pousse
    ok, detail = _commit_et_pousse([f"data/{Path(c).relative_to(DATA_DIR)}" for c in chemins], message)
    print(f"  {'publie' if ok else 'ECHEC commit/push (' + detail + ')'}")


# =====================================================================
# Leads BO
# =====================================================================

def _plages(debut, fin, pas_jours):
    d = debut
    while d <= fin:
        f = min(d + timedelta(days=pas_jours - 1), fin)
        yield d, f
        d = f + timedelta(days=1)


def telecharge_adaptatif(sid, st, d0, d1):
    """Telecharge [d0, d1] en une requete ; si l'API temporise (reponse trop
    lourde), coupe l'intervalle en deux. Les erreurs 500 sont deja gerees par
    leads_extract._telecharge_un (jour fautif saute). 429 -> pause puis retente."""
    for essai in range(6):
        try:
            return L._telecharge_un(sid, st, d0.isoformat(), d1.isoformat())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(30)
                continue
            raise
        except (TimeoutError, socket.timeout, urllib.error.URLError, OSError):
            if d0 >= d1:
                time.sleep(10)
                continue
            milieu = d0 + (d1 - d0) // 2
            return (telecharge_adaptatif(sid, st, d0, milieu)
                    + telecharge_adaptatif(sid, st, milieu + timedelta(days=1), d1))
    raise RuntimeError(f"extraction impossible pour siteId {sid} {d0}..{d1}")


def statut(l):
    if l.get(L.COL_DOUBLON) == "YES":
        return "doublon"
    if l.get(L.COL_TEST) == "YES" or l.get(L.COL_TEST_INTERNE) == "YES":
        return "test"
    if l.get(L.COL_MODE) != "MODE_PRODUCTION":
        return "preview"
    return "valide"


def collecte_leads(nom, depuis, fin, dry_run=False):
    depuis = depuis.replace(day=1)   # codes marketing agreges par mois : fenetre en mois entiers
    quotidien = Counter()
    codes = Counter()
    for sid, st in L.SITE_EXTRACT[nom]:
        # un an par requete d'abord ; coupe automatiquement si trop lourd
        for d0, d1 in _plages(depuis, fin, 366):
            lignes = telecharge_adaptatif(sid, st, d0, d1)
            for l in lignes:
                jour = (l.get(L.COL_DATE) or "")[:10]
                if len(jour) != 10:
                    continue
                s = statut(l)
                quotidien[(jour, sid, l.get(L.COL_SOURCE) or "", (l.get(L.COL_DEVICE) or "").lower(),
                           l.get(L.COL_FUEL) or "", l.get(L.COL_PROJECT) or "",
                           l.get(L.COL_BRAND) or "", s)] += 1
                if s == "valide":
                    codes[(jour[:7], l.get(L.COL_CODE) or "")] += 1
            time.sleep(1)
    if not quotidien:
        print(f"{nom} : aucun lead sur la periode")
        return []   # rien a remplacer : on ne touche pas au fichier existant
    slug = _slug(nom)
    racine = (Path("/tmp/history") if dry_run else HIST)
    p1 = racine / "leads" / f"{slug}.csv.gz"
    p2 = racine / "leads_codes" / f"{slug}.csv.gz"
    ent1 = ["date", "site_id", "source", "appareil", "carburant", "projet_achat",
            "marque_reprise", "statut", "n"]
    ecrit_csv_gz(p1, ent1, sorted(remplace_depuis(p1, sorted((*k, v) for k, v in quotidien.items()),
                                                  depuis.isoformat())))
    ecrit_csv_gz(p2, ["mois", "code_marketing", "valides"],
                 sorted(remplace_depuis(p2, sorted((*k, v) for k, v in codes.items()),
                                        depuis.isoformat()[:7])))
    valides = sum(v for k, v in quotidien.items() if k[-1] == "valide")
    jours = sorted({k[0] for k in quotidien})
    print(f"{nom} : {sum(quotidien.values())} leads bruts, {valides} valides, du {jours[0]} au {jours[-1]}")
    return [p1, p2]


# =====================================================================
# GA4
# =====================================================================

def collecte_ga4(s, depuis, fin, dry_run=False):
    from pipeline import funnel_daily, ga4
    cli = ga4.client()
    d0, d1 = depuis.isoformat(), fin.isoformat()
    lignes = []
    for lib, hote in (("parent", s.hote_parent), ("reprise", s.hote_reprise)):
        rows = ga4._rapport(cli, s.propriete, d0, d1,
                            ["date", "sessionDefaultChannelGroup", "deviceCategory"],
                            ["sessions", "activeUsers", "newUsers"],
                            ga4._egal("hostName", hote))
        for r in rows:
            j = r[0]
            lignes.append((f"{j[:4]}-{j[4:6]}-{j[6:]}", lib, r[1], r[2], int(r[3]), int(r[4]), int(r[5])))
    funnel = {}
    # funnel : par tranches d'un an (5 requetes GA4 par tranche)
    for a, b in _plages(depuis, fin, 366):
        try:
            funnel.update(funnel_daily.funnel_quotidien(cli, s.propriete, s.hote_reprise, a, b))
        except Exception as e:
            print(f"  {s.nom} funnel {a}..{b} : {type(e).__name__} ({str(e)[:80]})")
        time.sleep(1)
    racine = (Path("/tmp/history") if dry_run else HIST)
    out = []
    if lignes:
        p = racine / "ga4_sessions" / f"{s.slug}.csv.gz"
        ecrit_csv_gz(p, ["date", "site", "canal", "appareil", "sessions", "utilisateurs", "nouveaux_utilisateurs"],
                     sorted(remplace_depuis(p, lignes, d0)))
        out.append(p)
    if funnel:
        p = racine / "ga4_funnel" / f"{s.slug}.csv.gz"
        ecrit_csv_gz(p, ["date", "accueil", "version", "kilometrage", "coordonnees", "point_de_vente", "estimation"],
                     sorted(remplace_depuis(p, [(j, *v) for j, v in sorted(funnel.items())], d0)))
        out.append(p)
    jours = sorted({l[0] for l in lignes})
    print(f"{s.nom} : {len(lignes)} lignes de sessions"
          + (f" du {jours[0]} au {jours[-1]}" if jours else "") + f", funnel {len(funnel)} jours")
    return out


# =====================================================================
# Search Console (fusion avec l'existant : Google n'expose que 16 mois)
# =====================================================================

def fusionne(chemin, entete, nouvelles, nb_cles):
    """Union des lignes existantes et nouvelles ; la cle = nb_cles premieres
    colonnes, la ligne la plus recente (nouvelle) l'emporte."""
    fus = {tuple(l[:nb_cles]): list(l) for l in lit_csv_gz(chemin)}
    for l in nouvelles:
        fus[tuple(str(x) for x in l[:nb_cles])] = [str(x) for x in l]
    return [fus[k] for k in sorted(fus)]


def collecte_gsc(s, fin, dry_run=False):
    from pipeline import search_console as sc
    cli = sc.client()
    dispo = sc.sites_accessibles(cli)
    prop = sc.propriete_pour_hote(dispo, s.hote_reprise)
    if not prop:
        print(f"{s.nom} : propriete Search Console introuvable, ignore")
        return []
    debut = "2024-01-01"      # l'API plafonne seule a ~16 mois
    fin_iso = fin.isoformat()
    racine = (Path("/tmp/history") if dry_run else HIST)
    out = []

    rows = sc._requete(cli, prop, debut, fin_iso, ["date", "device"])
    quot = [(r["keys"][0], r["keys"][1].lower(), r["clicks"], r["impressions"],
             round(r["ctr"] * 100, 3), round(r["position"], 2)) for r in rows]
    if quot:
        p = racine / "gsc_daily" / f"{s.slug}.csv.gz"
        ent = ["date", "appareil", "clics", "impressions", "ctr_pct", "position"]
        ecrit_csv_gz(p, ent, fusionne(p, ent, quot, 2))
        out.append(p)

    premier = min((q[0] for q in quot), default=None)
    mois = []
    if premier:
        d = date.fromisoformat(premier[:7] + "-01")
        while d <= fin:
            f = (date(d.year + (d.month == 12), d.month % 12 + 1, 1) - timedelta(days=1))
            mois.append((d, min(f, fin)))
            d = f + timedelta(days=1)
    for dim, dossier in (("query", "gsc_queries"), ("page", "gsc_pages")):
        lignes = []
        for a, b in mois:
            r = sc._requete(cli, prop, a.isoformat(), b.isoformat(), [dim])
            r = sorted(r, key=lambda x: -x["clicks"])[:2000]
            lignes += [(a.isoformat()[:7], x["keys"][0], x["clicks"], x["impressions"],
                        round(x["ctr"] * 100, 3), round(x["position"], 2)) for x in r]
            time.sleep(0.4)
        if lignes:
            p = racine / dossier / f"{s.slug}.csv.gz"
            ent = ["mois", dim, "clics", "impressions", "ctr_pct", "position"]
            ecrit_csv_gz(p, ent, fusionne(p, ent, lignes, 2))
            out.append(p)
    print(f"{s.nom} : {len(quot)} lignes quotidiennes ({premier} ->), {len(mois)} mois requetes/pages")
    return out


# =====================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=["leads", "ga4", "gsc"])
    ap.add_argument("--sites", nargs="*")
    ap.add_argument("--depuis", help="AAAA-MM-JJ (defaut : 2020-01-01 leads, 2022-01-01 ga4)")
    ap.add_argument("--jusqua", help="AAAA-MM-JJ (defaut : hier)")
    ap.add_argument("--fenetre-jours", type=int,
                    help="re-collecte seulement les N derniers jours (mode planifie, incremental) ; "
                         "remplace --depuis")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    fin = date.fromisoformat(a.jusqua) if a.jusqua else date.today() - timedelta(days=1)
    if a.fenetre_jours:
        a.depuis = (fin - timedelta(days=a.fenetre_jours)).isoformat()
    if not a.dry_run:
        from pipeline.build import _configure_git
        _configure_git()

    echecs = []
    if a.source == "leads":
        depuis = date.fromisoformat(a.depuis or "2020-01-01")
        for nom in (a.sites or sorted(L.SITE_EXTRACT)):
            try:
                fich = collecte_leads(nom, depuis, fin, a.dry_run)
                if fich:
                    publie(fich, f"Historique profond leads BO — {nom}", a.dry_run)
            except Exception as e:
                echecs.append(nom)
                print(f"{nom} : ECHEC {type(e).__name__}: {e}")
    else:
        from pipeline import sites as sites_mod
        cibles = [s for s in sites_mod.SITES if not a.sites or s.nom in a.sites]
        depuis = date.fromisoformat(a.depuis or "2022-01-01")
        for s in cibles:
            try:
                fich = (collecte_ga4(s, depuis, fin, a.dry_run) if a.source == "ga4"
                        else collecte_gsc(s, fin, a.dry_run))
                if fich:
                    publie(fich, f"Historique profond {a.source.upper()} — {s.nom}", a.dry_run)
            except Exception as e:
                echecs.append(s.nom)
                print(f"{s.nom} : ECHEC {type(e).__name__}: {str(e)[:150]}")
    print(f"\n=== termine ; echecs : {echecs or 'aucun'} ===")
    sys.exit(0)


if __name__ == "__main__":
    main()
