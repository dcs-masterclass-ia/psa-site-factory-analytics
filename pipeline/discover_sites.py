#!/usr/bin/env python3
"""Decouverte automatique des sites GA4/Search Console accessibles au compte
de service, au-dela des quelques sites deja configures a la main dans
pipeline/sites.py.

Le compte de service voit potentiellement des dizaines de proprietes GA4 et
Search Console hors perimetre (portefeuille Stellantis entier) -- ce script
ne fait qu'aider a trier : il ne modifie jamais pipeline/sites.py lui-meme.
Meme discipline que le reste du pipeline (cf. pipeline/discover.py) : jamais
de nom d'hote suppose, jamais d'ecriture automatique en configuration de
production sans relecture humaine. Un site "ambigu" est affiche a part,
jamais devine.

Usage :
    python3 -m pipeline.discover_sites
    python3 -m pipeline.discover_sites --debut 2026-06-01 --fin 2026-07-31

Sortie : deux listes -- proprietes identifiees sans ambiguite (bloc Python
pret a coller dans pipeline/sites.py, a verifier avant de committer) et
proprietes ambigues (raison donnee par pipeline/discover.py, a trancher a la
main comme les sites deja en configuration).
"""

import argparse
import sys
from datetime import date, timedelta

from google.analytics.admin_v1beta import AnalyticsAdminServiceClient

from pipeline import discover, ga4, search_console
from pipeline.sites import SITES

# ccTLD -> code pays. Trie par longueur decroissante a l'usage pour que
# "co.uk" matche avant "uk". Etendre au besoin plutot que deviner.
TLD_PAYS = {
    "fr": "FR", "pt": "PT", "es": "ES", "it": "IT", "de": "DE",
    "at": "AT", "be": "BE", "nl": "NL", "pl": "PL", "lu": "LU",
    "ch": "CH", "co.uk": "GB", "uk": "GB", "ie": "IE",
}


def pays_depuis_hote(hote):
    if not hote:
        return None
    h = hote.lower()
    for tld in sorted(TLD_PAYS, key=len, reverse=True):
        if h.endswith("." + tld):
            return TLD_PAYS[tld]
    return None


def proprietes_disponibles():
    """Toutes les proprietes GA4 (id, nom affiche) visibles par le compte de
    service, via l'API Admin (comptes -> proprietes en un seul appel pagine).
    """
    admin = AnalyticsAdminServiceClient()
    out = []
    for compte in admin.list_account_summaries():
        for prop in compte.property_summaries:
            pid = prop.property.rsplit("/", 1)[-1]
            out.append((pid, prop.display_name))
    return out


def slug_depuis_nom(nom):
    return "".join(c if c.isalnum() else "-" for c in nom.lower()).strip("-")


def main():
    ap = argparse.ArgumentParser(description="Decouverte des sites GA4/GSC accessibles au compte de service")
    ap.add_argument("--debut", default=(date.today() - timedelta(days=35)).isoformat(),
                     help="plage de mesure du volume, pour deduire hote parent/reprise")
    ap.add_argument("--fin", default=(date.today() - timedelta(days=2)).isoformat())
    a = ap.parse_args()

    connues = {s.propriete for s in SITES}

    print(f"Perimetre deja configure : {len(SITES)} site(s) -- {', '.join(s.nom for s in SITES)}\n")

    print("Liste des proprietes GA4 accessibles (API Admin)...")
    try:
        proprietes = proprietes_disponibles()
    except Exception as e:
        sys.exit(f"Echec de l'appel a l'API Admin GA4 : {type(e).__name__}: {e}")
    nouvelles = [(pid, nom) for pid, nom in proprietes if pid not in connues]
    print(f"{len(proprietes)} propriete(s) GA4 visibles au total, "
          f"{len(nouvelles)} nouvelle(s) hors perimetre deja configure.\n")

    print("Liste des proprietes Search Console accessibles...")
    try:
        gsc_cli = search_console.client()
        gsc_sites = search_console.sites_accessibles(gsc_cli)
        print(f"{len(gsc_sites)} propriete(s) Search Console visibles.\n")
    except SystemExit:
        raise
    except Exception as e:
        print(f"Search Console indisponible ({type(e).__name__}: {e}) -- "
              f"la decouverte continue sans correspondance GSC.\n")
        gsc_sites = None

    cli = ga4.client()
    confirmes, ambigus = [], []

    for i, (pid, nom) in enumerate(nouvelles, 1):
        print(f"[{i}/{len(nouvelles)}] {nom} (propriete {pid})...", file=sys.stderr)
        try:
            hotes = ga4.hotes(cli, pid, a.debut, a.fin)
            indice_pays = pays_depuis_hote(hotes[0][0]) if hotes else None
            hote_parent, hote_reprise, journal = discover.deduire(hotes, indice_pays)
            pays = pays_depuis_hote(hote_reprise) or pays_depuis_hote(hote_parent) or "?"
            gsc_site = (search_console.propriete_pour_hote(gsc_sites, hote_reprise)
                        if gsc_sites is not None else None)
            confirmes.append({
                "nom": nom, "propriete": pid, "pays": pays,
                "hote_parent": hote_parent, "hote_reprise": hote_reprise,
                "gsc": gsc_site, "journal": journal,
            })
        except discover.Ambigu as e:
            ambigus.append({"nom": nom, "propriete": pid, "raison": str(e)})
        except Exception as e:
            ambigus.append({"nom": nom, "propriete": pid, "raison": f"erreur : {type(e).__name__}: {e}"})

    print(f"\n{'=' * 70}")
    print(f"{len(confirmes)} site(s) identifie(s) sans ambiguite -- a relire avant de coller dans pipeline/sites.py")
    print(f"{'=' * 70}\n")
    for c in confirmes:
        slug = slug_depuis_nom(c["nom"])
        print(f'    Site("{c["nom"]}", "{slug}", "{c["propriete"]}",')
        print(f'         "{c["hote_parent"]}", "{c["hote_reprise"]}",')
        print(f'         verifie=True, acces_api=True, pays="{c["pays"]}"),')
        if c["gsc"]:
            print(f'    # Search Console : {c["gsc"]}')
        else:
            print(f'    # ATTENTION -- aucune propriete Search Console trouvee pour {c["hote_reprise"]}')
        for ligne in c["journal"]:
            print(f"    # {ligne}")
        print()

    if ambigus:
        print(f"{'=' * 70}")
        print(f"{len(ambigus)} site(s) ambigu(s) -- a trancher a la main")
        print(f"{'=' * 70}\n")
        for x in ambigus:
            print(f"  {x['nom']} (propriete {x['propriete']}) : {x['raison']}")

    print(f"\nRecapitulatif : {len(SITES)} deja configures + {len(confirmes)} confirmes "
          f"+ {len(ambigus)} ambigus = {len(SITES) + len(confirmes) + len(ambigus)} "
          f"proprietes GA4 vues au total.")


if __name__ == "__main__":
    main()
