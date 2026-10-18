"""Collecte C1ST « Leads Network Vision » : suivi des leads de reprise par contrat concessionnaire -> c1st/reseau.json (repo de données).

Reproduit le tableau « Summary Table » du tableau de bord C1ST « Leads Network Vision » (requête SAQL fournie par l'équipe C1ST, 18/10/2026) :
jeux « PruebaDealer3MLNV » (leads envoyés, suivi, devis, commandes) ; fenêtre glissante « il y a 1 mois » -> « jour courant » ; mêmes filtres que le tableau de bord
(type 1, B2B / B2C, circuit BRAND ou Central, activité VN, hors « SOL ready for order », hors liste noire, hors tests) ; PLUS le périmètre reprise de Converge :
campagne Autobiz, marques standard, marchés suivis.

Mesures (clients uniques envoyés = dénominateur de tous les %) :
  leads    leads envoyés aux concessionnaires              unique(ACCLead.Id)
  clients  clients uniques envoyés                          unique(ACCLead.LeadUniqueCust)
  fca      1er appel dans les délais                        FreespeeTreatmentTimeRespect = « On Time »
  tot / tov / tr   traités dans les délais / hors délais / traités   TreatedOnTime = OnTime / OverTime / l'un des deux
  cot / cov / c    contactés dans les délais / hors délais / contactés   ContactedOnTime = OnTime / OverTime / l'un des deux
  eso / es         e-mails envoyés dans les délais / envoyés   Tech_SentOnTime
  q        clients avec devis                               HasQuotes = YES
  o        commandes liées au lead (1 à 90 jours)           unique(OrderIdwMailPhone)
  rel      leads à relancer                                 Status = ToRelaunch
Seuls des comptages par contrat (sociétés) sont écrits : aucune donnée sur un client. Usage : python -m pipeline.c1st_reseau [--sortie data/c1st/reseau.json]
"""

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from pipeline.c1st_collecte import MARQUES_STD, PAYS, Client, NonConfigure, _liste, jeton

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "data" / "c1st" / "reseau.json"
P = "ACCLead."

ENVOYE = f"'{P}SendToNetwork' == \"Yes\""
# (clé, condition en plus de « envoyé », champ compté)
MESURES = [
    ("fca", f"'{P}FreespeeTreatmentTimeRespect__c' == \"On Time\"", f"{P}LeadUniqueCust"),
    ("tot", f"'{P}TreatedOnTime__c' == \"OnTime\"", f"{P}LeadUniqueCust"),
    ("tov", f"'{P}TreatedOnTime__c' == \"OverTime\"", f"{P}LeadUniqueCust"),
    ("tr", f"('{P}TreatedOnTime__c' == \"OnTime\" || '{P}TreatedOnTime__c' == \"OverTime\")", f"{P}LeadUniqueCust"),
    ("cot", f"'{P}ContactedOnTime__c' == \"OnTime\"", f"{P}LeadUniqueCust"),
    ("cov", f"'{P}ContactedOnTime__c' == \"OverTime\"", f"{P}LeadUniqueCust"),
    ("c", f"('{P}ContactedOnTime__c' == \"OnTime\" || '{P}ContactedOnTime__c' == \"OverTime\")", f"{P}LeadUniqueCust"),
    ("eso", f"'{P}Tech_SentOnTime__c' == \"OnTime\"", f"{P}LeadUniqueCust"),
    ("es", f"('{P}Tech_SentOnTime__c' == \"OnTime\" || '{P}Tech_SentOnTime__c' == \"OverTime\")", f"{P}LeadUniqueCust"),
    ("q", "'HasQuotes' == \"YES\"", f"{P}LeadUniqueCust"),
    ("o", "'LeadConversionTimeMailPhone' >= 1 && 'LeadConversionTimeMailPhone' <= 90", "OrderIdwMailPhone"),
    ("rel", f"'{P}Status' in [\"ToRelaunch\", \"To Relaunch\"]", f"{P}Id"),
]
CLES = ("pays", "marque", "code", "nom")


def filtres(v="q"):
    """Filtres du tableau de bord Network Vision + périmètre reprise de Converge (campagne Autobiz, marques standard, marchés suivis)."""
    return "\n".join([
        f"{v} = filter {v} by '{P}LeadTypeLabelized' in [\"1-Leads (urgent)\"];",
        f"{v} = filter {v} by ('{P}MarketingCode__c' not in [\"SOL ready for order\"] || '{P}MarketingCode__c' is null);",
        f"{v} = filter {v} by '{P}CustomerType__c' in [\"B2B\", \"B2C\"];",
        f"{v} = filter {v} by '{P}CentralLocal_lead' in [\"BRAND\", \"Central\"];",
        f"{v} = filter {v} by '{P}Activity__c' in [\"VN\"];",
        f"{v} = filter {v} by ('{P}LeadQualificationResult__c' not in [\"Black list filtering\"] || '{P}LeadQualificationResult__c' is null);",
        f"{v} = filter {v} by 'Test_JustDealerT' in [\"No\"];",
        f"{v} = filter {v} by 'ACCLead.CampaignIDUSER__c' in [\"AUTOBIZ\", \"Autobiz\"];",
        f"{v} = filter {v} by '{P}PSABrand__c' in {_liste(MARQUES_STD)};",
        f"{v} = filter {v} by '{P}LeadCountry__c' in {_liste(PAYS)};",
        f"{v} = filter {v} by date('{P}CreatedDate_Year', '{P}CreatedDate_Month', '{P}CreatedDate_Day') in [\"1 month ago\"..\"current day\"];",
    ])


def saql(ds, condition=None, mesure=None, base=False):
    """Une requête par mesure, regroupée par pays, marque et contrat. base=True : leads et clients uniques de tous les leads envoyés."""
    cond = ENVOYE + (f" && {condition}" if condition else "")
    cle = f"'{P}LeadCountry__c', '{P}PSABrand__c', '{P}Partner_Contract', '{P}Marketing_Name'"
    sortie = f"'{P}LeadCountry__c' as 'pays', '{P}PSABrand__c' as 'marque', '{P}Partner_Contract' as 'code', '{P}Marketing_Name' as 'nom', "
    if base:
        calcul = f"unique('{P}Id') as 'leads', unique('{P}LeadUniqueCust') as 'clients'"
    else:
        calcul = f"unique('{mesure}') as 'v'"
    return f"""q = load "{ds}";
{filtres("q")}
q = filter q by {cond};
r = group q by ({cle});
r = foreach r generate {sortie}{calcul};
r = limit r 10000;"""


def collecte(client):
    """-> liste de contrats [{pays, marque, code, nom, leads, clients, fca, …}]."""
    ds = client.version("dealer")
    contrats = {}

    def ligne(r):
        k = tuple(r.get(c) for c in CLES)
        if k not in contrats:
            contrats[k] = dict(zip(CLES, k))
        return contrats[k]
    for r in client.requete(saql(ds, base=True)):
        ligne(r).update(leads=int(r.get("leads") or 0), clients=int(r.get("clients") or 0))
    for cle, cond, champ in MESURES:
        for r in client.requete(saql(ds, cond, champ)):
            ligne(r)[cle] = int(r.get("v") or 0)
        time.sleep(0.4)
    out = []
    for c in contrats.values():
        if not c.get("clients"):
            continue
        for cle, *_ in MESURES:
            c.setdefault(cle, 0)
        out.append(c)
    out.sort(key=lambda c: (-c["clients"], c["code"] or ""))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default=str(FICHIER))
    a = ap.parse_args(argv)
    try:
        token, instance = jeton()
    except NonConfigure as e:
        print(f"C1ST non configuré : {e}", file=sys.stderr)
        return 3
    client = Client(token, instance)
    contrats = collecte(client)
    if not contrats:
        print("Aucun contrat collecté : fichier existant conservé", file=sys.stderr)
        return 1
    sortie = Path(a.sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps({
        "collecte": {"date": date.today().isoformat(), "fenetre": "du même jour il y a 1 mois au jour de la collecte (fenêtre glissante, comme le tableau de bord C1ST Network Vision)",
                     "source": "C1ST (CRM Analytics), jeu PruebaDealer3MLNV ; comptages par contrat concessionnaire, aucune donnée sur un client"},
        "perimetre": "leads de reprise (campagne Autobiz), type 1, VN, B2B/B2C, circuit BRAND ou Central, hors « SOL ready for order », liste noire et tests",
        "contrats": contrats}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"C1ST réseau : {len(contrats)} lignes (contrat × marque × marché), {sum(c['clients'] for c in contrats)} clients uniques envoyés")
    return 0


if __name__ == "__main__":
    sys.exit(main())
