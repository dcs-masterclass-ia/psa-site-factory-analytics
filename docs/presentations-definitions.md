# Présentations client — définitions retenues (10/10/2026)

Calées sur le deck de référence « Stellantis_Reporting_Q3_2026_BE.pptx » (BELUX, T3-2026).
Chaque définition est celle qui reproduit le mieux les chiffres du deck ; l'écart observé est indiqué.

| Indicateur | Définition retenue | Écart au deck |
|---|---|---|
| Leads (par marque, mois, trimestre) | Leads BO valides (production, hors doublons, tests et tests internes), BE + LU | Peugeot 3 623 / 3 631 (0,2 %) ; Opel T3-2025 −4 % (à investiguer) |
| NC leads / projets | `PURCHASE PROJECT` : VN = « New cars & Demo cars », VO = « Used cars », « No purchase project » = « Trade-in only » | Peugeot VN 1 576 / 1 579 |
| Sources d'acquisition | `SOURCE_ACQUISITION` regroupée : Search = {Search, Google Ads} ; Emailing = {sfmc} ; LLM = {chatgpt.com, …} ; Display ; Main-Website ; Autre = vide | Peugeot New cars : 241/57/261/420/597 contre 241/57/262/421/598 |
| CTA du site | `SUPPORT` (Header-Menu/er-Menu, HP-B, Footer, Offer-Page) × `CAMPAGNE` = « CTA » | champs présents, jamais conservés avant le 10/10/2026 |
| Sessions « Trade-in » | Sessions GA4 des hôtes de reprise de la **Belgique seule** (nl + fr) | Peugeot 23 957 / 23 620 (1,4 %), Citroën 6 489 / 6 561, Opel 12 831 / 12 694, DS 7 169 / 7 101, Jeep 11 603 / 11 535, Lancia 1 107 / 1 108 |
| Canaux du trafic | `sessionPrimaryChannelGroup` (groupe principal : Display, Paid Search…), pas le groupe par défaut | Peugeot Display 11 246 / 11 821 |
| « In Journey » | **Utilisateurs** (distincts sur la période) ayant déclenché l'événement `form_step_view`, BE + LU | Peugeot 8 721 / 8 811, Citroën 4 101 / 4 172 |
| « Hot leads » | Utilisateurs de l'étape « estimation » du funnel GA4 (`tradein_request`), BE + LU | Peugeot 2 903 / 2 968, Citroën 1 234 / 1 237 |
| CVR (sessions engagées) | Hot leads ÷ In Journey | Peugeot 33,0 % / 33,7 % |
| Hot leads — définition BO (proposée, non retenue) | Leads VN dont la marque d'achat = marque du site | Peugeot 1 574 : ne colle pas au deck |

## Pièges connus
- **Utilisateurs distincts** : In Journey et Hot leads sont des utilisateurs distincts sur la période, pas des sommes de
  valeurs quotidiennes. Le générateur les interroge directement dans GA4 pour la période demandée.
- **Périmètre incohérent dans le deck** : les sessions sont Belgique seule, In Journey / Hot leads sont BE + LU.
  Le générateur reproduit ce mode « fidèle au deck » par défaut et propose un mode BELUX cohérent.
- **Belgique** : deux sites de reprise par marque (nl + fr) ; avant le 10/10/2026 un seul était mesuré (trafic sous-compté ~50 %).
  Corrigé dans `pipeline/discover.py` (`hotes_reprise_complets`).
- **À investiguer** : Fiat BE (sessions 3 134 contre 4 047 dans le deck), Abarth BE (aucun hôte de reprise détecté dans GA4),
  Opel T3-2025 (−4 % en leads).
