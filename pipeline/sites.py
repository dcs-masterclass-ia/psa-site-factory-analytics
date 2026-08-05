"""Configuration du perimetre : sites, proprietes GA4, noms d'hote.

Regle absolue heritee du projet : un nom d'hote n'est jamais deduit d'un libelle
ni suppose. Il est releve dans GA4 puis inscrit ici avec `verifie=True`.

Pour relever les hotes d'une propriete :
    python3 -m pipeline.ga4 --propriete <id> --hotes
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    nom: str
    slug: str
    propriete: str
    hote_parent: str
    hote_reprise: str
    verifie: bool          # les deux hotes ont-ils ete releves dans GA4 ?
    acces_api: bool        # le compte de service repond-il sur cette propriete ?
    pays: str


SITES = [
    # --- releve et confirme le 04/08/2026 contre le fichier de production ---
    Site("OPEL FR", "opel-fr", "276495192",
         "www.opel.fr", "www.reprise.opel.fr",
         verifie=True, acces_api=True, pays="FR"),

    # --- hotes de reprise connus par le monitoring, hotes parents releves dans GA4 ---
    Site("FIAT PT", "fiat-pt", "353122979",
         "www.fiat.pt", "www.retoma.fiat.pt",
         verifie=False, acces_api=True, pays="PT"),
    Site("JEEP PT", "jeep-pt", "353131452",
         "www.jeep.pt", "www.retoma.jeep.pt",
         verifie=False, acces_api=True, pays="PT"),
    Site("ALFA ROMEO PT", "alfa-romeo-pt", "353123668",
         "www.alfaromeo.pt", "www.retoma.alfaromeo.pt",
         verifie=False, acces_api=True, pays="PT"),

    # --- hotes a relever : le prefixe www n'est pas garanti, cf. OPEL FR ---
    Site("OPEL PT", "opel-pt", "276479753",
         "www.opel.pt", "www.retoma.opel.pt",
         verifie=False, acces_api=True, pays="PT"),
    Site("CITROEN PT", "citroen-pt", "276461319",
         "www.citroen.pt", "www.retoma-citroen.pt",
         verifie=False, acces_api=True, pays="PT"),
    Site("PEUGEOT PT", "peugeot-pt", "276505113",
         "www.peugeot.pt", "www.retoma.peugeot.pt",
         verifie=False, acces_api=True, pays="PT"),

    # --- acces accorde le 05/08/2026, hotes a confirmer contre le volume reel ---
    Site("DS PT", "ds-pt", "276470566",
         "www.dsautomobiles.pt", "retoma.dsautomobiles.pt",
         verifie=False, acces_api=True, pays="PT"),
]

PAR_SLUG = {s.slug: s for s in SITES}
PAR_NOM = {s.nom: s for s in SITES}


def site(ref):
    """Retourne un Site depuis son nom ou son slug."""
    if ref in PAR_NOM:
        return PAR_NOM[ref]
    if ref in PAR_SLUG:
        return PAR_SLUG[ref]
    raise KeyError(f"site inconnu : {ref} — connus : {sorted(PAR_SLUG)}")


def exploitables():
    """Sites que le pipeline peut traiter : acces API et hotes verifies."""
    return [s for s in SITES if s.acces_api and s.verifie]
