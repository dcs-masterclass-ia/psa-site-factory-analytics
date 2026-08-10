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

    # --- hotes de reprise confirmes par des mois de trafic GA4 reel (voir
    # discover.deduire, invoque a chaque execution de build.py) -- passes
    # verifie=True le 08/08/2026, ce champ n'etait a jour que pour OPEL FR ---
    Site("FIAT PT", "fiat-pt", "353122979",
         "www.fiat.pt", "www.retoma.fiat.pt",
         verifie=True, acces_api=True, pays="PT"),
    Site("JEEP PT", "jeep-pt", "353131452",
         "www.jeep.pt", "www.retoma.jeep.pt",
         verifie=True, acces_api=True, pays="PT"),
    Site("ALFA ROMEO PT", "alfa-romeo-pt", "353123668",
         "www.alfaromeo.pt", "www.retoma.alfaromeo.pt",
         verifie=True, acces_api=True, pays="PT"),
    Site("OPEL PT", "opel-pt", "276479753",
         "www.opel.pt", "www.retoma.opel.pt",
         verifie=True, acces_api=True, pays="PT"),
    Site("CITROEN PT", "citroen-pt", "276461319",
         "www.citroen.pt", "www.retoma-citroen.pt",
         verifie=True, acces_api=True, pays="PT"),
    Site("PEUGEOT PT", "peugeot-pt", "276505113",
         "www.peugeot.pt", "www.retoma.peugeot.pt",
         verifie=True, acces_api=True, pays="PT"),
    Site("DS PT", "ds-pt", "276470566",
         "www.dsautomobiles.pt", "retoma.dsautomobiles.pt",
         verifie=True, acces_api=True, pays="PT"),

    # --- decouvertes le 07/08/2026 via pipeline/discover_sites.py (API Admin
    # GA4 + pipeline/discover.deduire sur le volume reel, periode 2026-04-01
    # a J-2) puis verifiees une par une contre la liste d'URL de reprise
    # fournie marche par marche : 55/55 hotes decouverts correspondent
    # exactement aux URL attendues, aucun ecart. ---
    Site("CITROEN AT", "citroen-at", "276496699",
         "www.citroen.at", "www.citroen-kauft-ihr-auto.at",
         verifie=True, acces_api=True, pays="AT"),
    Site("OPEL AT", "opel-at", "276503993",
         "www.opel.at", "opel-kauft-dein-auto.opel.at",
         verifie=True, acces_api=True, pays="AT"),
    Site("PEUGEOT AT", "peugeot-at", "276460567",
         "www.peugeot.at", "www.wir-kaufen-ihr-auto.peugeot.at",
         verifie=True, acces_api=True, pays="AT"),
    Site("ABARTH BE", "abarth-be", "296320560",
         "www.abarthbelgium.be", "overname.abarthbelgium.be",
         verifie=True, acces_api=True, pays="BE"),
    Site("ALFA ROMEO BE", "alfa-romeo-be", "295344587",
         "www.alfaromeo.be", "reprise.alfaromeo.be",
         verifie=True, acces_api=True, pays="BE"),
    Site("CITROEN BE", "citroen-be", "276470270",
         "www.citroen.be", "overname.citroen.be",
         verifie=True, acces_api=True, pays="BE"),
    Site("DS BE", "ds-be", "276468069",
         "www.dsautomobiles.be", "reprise.dsautomobiles.be",
         verifie=True, acces_api=True, pays="BE"),
    Site("FIAT BE", "fiat-be", "311171602",
         "www.fiat.be", "overname.fiat.be",
         verifie=True, acces_api=True, pays="BE"),
    Site("JEEP BE", "jeep-be", "296344319",
         "www.jeep.be", "overname.jeep.be",
         verifie=True, acces_api=True, pays="BE"),
    Site("LANCIA BE", "lancia-be", "354003299",
         "www.lancia.be", "reprise.lancia.be",
         verifie=True, acces_api=True, pays="BE"),
    Site("OPEL BE", "opel-be", "276478921",
         "www.opel.be", "www.overname.opel.be",
         verifie=True, acces_api=True, pays="BE"),
    Site("PEUGEOT BE", "peugeot-be", "276507805",
         "www.peugeot.be", "overname.peugeot.be",
         verifie=True, acces_api=True, pays="BE"),
    Site("ALFA ROMEO DE", "alfa-romeo-de", "311327249",
         "www.alfaromeo.de", "autoankauf.alfaromeo.de",
         verifie=True, acces_api=True, pays="DE"),
    Site("CITROEN DE", "citroen-de", "276461318",
         "www.citroen.de", "www.citroen-kauft-ihr-auto.de",
         verifie=True, acces_api=True, pays="DE"),
    Site("DS DE", "ds-de", "276503271",
         "www.dsautomobiles.de", "www.autoankauf.dsautomobiles.de",
         verifie=True, acces_api=True, pays="DE"),
    Site("OPEL DE", "opel-de", "276481685",
         "www.opel.de", "www.opel-kauft-dein-auto.de",
         verifie=True, acces_api=True, pays="DE"),
    Site("PEUGEOT DE", "peugeot-de", "276501794",
         "www.peugeot.de", "www.autoankauf.peugeot.de",
         verifie=True, acces_api=True, pays="DE"),
    Site("ABARTH ES", "abarth-es", "311940003",
         "www.abarth.es", "tasacion.abarth.es",
         verifie=True, acces_api=True, pays="ES"),
    Site("ALFA ROMEO ES", "alfa-romeo-es", "304946525",
         "www.alfaromeo.es", "tasacion.alfaromeo.es",
         verifie=True, acces_api=True, pays="ES"),
    Site("CITROEN ES", "citroen-es", "276508049",
         "www.citroen.es", "www.tasacion.citroen.es",
         verifie=True, acces_api=True, pays="ES"),
    Site("DS ES", "ds-es", "276466257",
         "www.dsautomobiles.es", "www.tasacion.dsautomobiles.es",
         verifie=True, acces_api=True, pays="ES"),
    Site("FIAT ES", "fiat-es", "311695154",
         "www.fiat.es", "tasacion.fiat.es",
         verifie=True, acces_api=True, pays="ES"),
    Site("JEEP ES", "jeep-es", "311334473",
         "www.jeep.es", "tasacion.jeep.es",
         verifie=True, acces_api=True, pays="ES"),
    Site("OPEL ES", "opel-es", "276513247",
         "www.opel.es", "www.tasacion.opel.es",
         verifie=True, acces_api=True, pays="ES"),
    Site("PEUGEOT ES", "peugeot-es", "276516612",
         "www.peugeot.es", "tasacion.peugeot.es",
         verifie=True, acces_api=True, pays="ES"),
    Site("ALFA ROMEO FR", "alfa-romeo-fr", "300875243",
         "www.alfaromeo.fr", "reprise.alfaromeo.fr",
         verifie=True, acces_api=True, pays="FR"),
    Site("CITROEN FR", "citroen-fr", "276496103",
         "www.citroen.fr", "www.reprise.citroen.fr",
         verifie=True, acces_api=True, pays="FR"),
    Site("DS FR", "ds-fr", "276490670",
         "www.dsautomobiles.fr", "www.reprise.dsautomobiles.fr",
         verifie=True, acces_api=True, pays="FR"),
    Site("FIAT FR", "fiat-fr", "299459965",
         "www.fiat.fr", "reprise.fiat.fr",
         verifie=True, acces_api=True, pays="FR"),
    Site("JEEP FR", "jeep-fr", "311270340",
         "www.jeep.fr", "reprise.jeep.fr",
         verifie=True, acces_api=True, pays="FR"),
    Site("LANCIA FR", "lancia-fr", "353967616",
         "www.lancia.fr", "reprise.lancia.fr",
         verifie=True, acces_api=True, pays="FR"),
    Site("PEUGEOT FR", "peugeot-fr", "276506792",
         "www.peugeot.fr", "www.reprise.peugeot.fr",
         verifie=True, acces_api=True, pays="FR"),
    Site("DS GB", "ds-gb", "276467495",
         "www.dsautomobiles.co.uk", "www.tradein.dsautomobiles.co.uk",
         verifie=True, acces_api=True, pays="GB"),
    Site("ABARTH IT", "abarth-it", "311977965",
         "www.abarth.it", "www.valutazioneusato.abarth.it",
         verifie=True, acces_api=True, pays="IT"),
    Site("ALFA ROMEO IT", "alfa-romeo-it", "305384351",
         "www.alfaromeo.it", "www.valutazioneusato.alfaromeo.it",
         verifie=True, acces_api=True, pays="IT"),
    Site("CITROEN IT", "citroen-it", "251581776",
         "www.citroen.it", "www.valutazioneusato.citroen.it",
         verifie=True, acces_api=True, pays="IT"),
    Site("DS IT", "ds-it", "276495762",
         "www.dsautomobiles.it", "valutazioneusato.dsautomobiles.it",
         verifie=True, acces_api=True, pays="IT"),
    Site("FIAT IT", "fiat-it", "311710705",
         "www.fiat.it", "www.valutazioneusato.fiat.it",
         verifie=True, acces_api=True, pays="IT"),
    Site("JEEP IT", "jeep-it", "311335943",
         "www.jeep-official.it", "www.valutazioneusato.jeep-official.it",
         verifie=True, acces_api=True, pays="IT"),
    Site("LANCIA IT", "lancia-it", "312190500",
         "www.lancia.it", "valutazioneusato.lancia.it",
         verifie=True, acces_api=True, pays="IT"),
    Site("OPEL IT", "opel-it", "276494517",
         "www.opel.it", "www.valutazioneusato.opel.it",
         verifie=True, acces_api=True, pays="IT"),
    Site("PEUGEOT IT", "peugeot-it", "276513489",
         "www.peugeot.it", "www.valutiamoiltuousato.peugeot.it",
         verifie=True, acces_api=True, pays="IT"),
    # decouvert le 07/08/2026 : signale par l'utilisateur (propriete
    # 214933203) mais confirme sur trafic reel sous une propriete
    # differente (296318652) portant le meme hote de reprise -- verifiee
    # via pipeline/discover_sites.py, pas la propriete communiquee au
    # depart.
    Site("ABARTH LU", "abarth-lu", "296318652",
         "www.abarth.lu", "reprise.abarth.lu",
         verifie=True, acces_api=True, pays="LU"),
    Site("ALFA ROMEO LU", "alfa-romeo-lu", "295361431",
         "www.alfaromeo.lu", "reprise.alfaromeo.lu",
         verifie=True, acces_api=True, pays="LU"),
    Site("CITROEN LU", "citroen-lu", "312847405",
         "www.citroen.lu", "reprise.citroen.lu",
         verifie=True, acces_api=True, pays="LU"),
    Site("DS LU", "ds-lu", "310975143",
         "www.dsautomobiles.lu", "reprise.dsautomobiles.lu",
         verifie=True, acces_api=True, pays="LU"),
    Site("FIAT LU", "fiat-lu", "311157063",
         "www.fiat.lu", "reprise.fiat.lu",
         verifie=True, acces_api=True, pays="LU"),
    Site("JEEP LU", "jeep-lu", "296309849",
         "www.jeep.lu", "reprise.jeep.lu",
         verifie=True, acces_api=True, pays="LU"),
    Site("OPEL LU", "opel-lu", "311337951",
         "www.opel.lu", "www.reprise.opel.lu",
         verifie=True, acces_api=True, pays="LU"),
    Site("PEUGEOT LU", "peugeot-lu", "309614912",
         "www.peugeot.lu", "reprise.peugeot.lu",
         verifie=True, acces_api=True, pays="LU"),
    Site("ALFA ROMEO PL", "alfa-romeo-pl", "312139333",
         "www.alfaromeo.pl", "odkup.alfaromeo.pl",
         verifie=True, acces_api=True, pays="PL"),
    Site("CITROEN PL", "citroen-pl", "276482169",
         "www.citroen.pl", "odkup.citroen.pl",
         verifie=True, acces_api=True, pays="PL"),
    Site("JEEP PL", "jeep-pl", "311268142",
         "www.jeep.pl", "odkup.jeep.pl",
         verifie=True, acces_api=True, pays="PL"),
    Site("OPEL PL", "opel-pl", "276497968",
         "www.opel.pl", "www.odkup.opel.pl",
         verifie=True, acces_api=True, pays="PL"),
    Site("PEUGEOT PL", "peugeot-pl", "276507806",
         "www.peugeot.pl", "odkup.peugeot.pl",
         verifie=True, acces_api=True, pays="PL"),
    Site("ABARTH PT", "abarth-pt", "353147990",
         "www.abarth.pt", "www.retoma.abarth.pt",
         verifie=True, acces_api=True, pays="PT"),

    # --- Spoticar, decouvert le 10/08/2026 via pipeline/discover_sites.py une
    # fois l'acces GA4 accorde au compte de service -- 10/10 hotes confirmes
    # sans ambiguite contre le trafic reel, tous coherents avec la liste de
    # sites officielle fournie separement. ---
    Site("SPOTICAR AT", "spoticar-at", "314701939",
         "www.spoticar.at", "wir-kaufen-ihr-auto.spoticar.at",
         verifie=True, acces_api=True, pays="AT"),
    Site("SPOTICAR BE", "spoticar-be", "314457341",
         "www.spoticar.be", "www.reprise.spoticar.be",
         verifie=True, acces_api=True, pays="BE"),
    Site("SPOTICAR DE", "spoticar-de", "314730457",
         "www.spoticar.de", "autoankauf.spoticar.de",
         verifie=True, acces_api=True, pays="DE"),
    Site("SPOTICAR ES", "spoticar-es", "314728332",
         "www.spoticar.es", "tasacion.spoticar.es",
         verifie=True, acces_api=True, pays="ES"),
    Site("SPOTICAR FR", "spoticar-fr", "314732091",
         "www.spoticar.fr", "www.reprise.spoticar.fr",
         verifie=True, acces_api=True, pays="FR"),
    Site("SPOTICAR IT", "spoticar-it", "314733158",
         "www.spoticar.it", "www.valutazioneusato.spoticar.it",
         verifie=True, acces_api=True, pays="IT"),
    Site("SPOTICAR LU", "spoticar-lu", "314664281",
         "www.spoticar.lu", "www.reprise.spoticar.lu",
         verifie=True, acces_api=True, pays="LU"),
    Site("SPOTICAR PL", "spoticar-pl", "314818617",
         "www.spoticar.pl", "odkup.spoticar.pl",
         verifie=True, acces_api=True, pays="PL"),
    Site("SPOTICAR PT", "spoticar-pt", "313851325",
         "www.spoticar.pt", "www.retoma.spoticar.pt",
         verifie=True, acces_api=True, pays="PT"),
    Site("SPOTICAR UK", "spoticar-uk", "314821485",
         "www.spoticar.co.uk", "tradein.spoticar.co.uk",
         verifie=True, acces_api=True, pays="GB"),
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
