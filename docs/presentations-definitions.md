# Présentations client — règles de cohérence et définitions (10/10/2026)

Principe : **chaque chiffre d'une présentation répond aux mêmes règles**, quel que soit le module. Le deck de
référence « Stellantis_Reporting_Q3_2026_BE.pptx » (BELUX, T3-2026) sert à *valider* nos calculs, pas à copier ses
incohérences. Les écarts avec lui sont attendus et listés plus bas.

## 1. Règles transverses (jamais de dérogation)
1. **Un seul périmètre par présentation**, affiché en pied de chaque diapositive. BELUX = Belgique (néerlandais + français)
   + Luxembourg, pour **toutes** les sources (GA4 comme back-office). Option possible : Belgique seule, ou Luxembourg seul,
   appliquée à toute la présentation, jamais à une diapositive isolée.
2. **Périodes** : trimestres civils. QoQ = trimestre précédent, YoY = même trimestre de l'année précédente. Les deux
   comparaisons utilisent exactement les mêmes définitions et le même périmètre que la période courante.
3. **Une source par indicateur, toujours nommée** (« Source : back-office autobiz » ou « Source : GA4 »). On ne divise jamais
   un chiffre GA4 par un chiffre back-office.
4. **Une unité par chaîne** : une chaîne de conversion n'enchaîne que des **utilisateurs distincts** (ou que des sessions).
   Les utilisateurs distincts sont calculés sur la période entière directement dans GA4, jamais en additionnant des jours.
5. **Petites bases** : pas de pourcentage d'évolution affiché sous 100 leads ou 100 sessions dans la période de référence
   (on affiche « n.s. », valeurs absolues) — évite les « +1 038 % » sur 8 leads.
6. **Textes calculés, jamais saisis** : signes, sens (« hausse / baisse »), points de pourcentage (« pt ») et trimestres sont
   générés depuis les données, puis relus par le DKAM.

## 2. Définitions
| Indicateur | Source | Définition |
|---|---|---|
| Leads | Back-office | Leads valides : production, hors doublons, tests et tests internes. Périmètre BELUX. |
| New cars / Trade-in only / Used cars | Back-office | `PURCHASE PROJECT` : VN / « No purchase project » / VO. NC = New cars. |
| Source d'acquisition | Back-office | `SOURCE_ACQUISITION` regroupée : Search = {Search, Google Ads} ; Emailing = {sfmc} ; LLM = {chatgpt.com, …} ; Display ; Main-Website ; Autre = vide. |
| CTA du site | Back-office | `SUPPORT` (menu, HP-B, footer, page offre) × `CAMPAGNE` = « CTA », pour la source Main-Website. |
| Utilisateurs trade-in | GA4 | Utilisateurs distincts des sites de reprise (Belgique : nl + fr ; Luxembourg), sur la période. |
| Sessions trade-in | GA4 | Sessions des mêmes sites de reprise. |
| Canaux du trafic | GA4 | `sessionPrimaryChannelGroup` (Display, Paid Search, Organic Search…). |
| In Journey | GA4 | Utilisateurs distincts ayant déclenché `form_step_view` sur les sites de reprise. |
| Hot leads | GA4 | Utilisateurs distincts de l'étape « estimation » (`tradein_request`). |
| Taux In Journey | GA4 | In Journey ÷ utilisateurs trade-in. |
| CVR | GA4 | Hot leads ÷ In Journey. |

Les leads du back-office (module « Leads ») et les hot leads GA4 (module « Trafic ») sont deux mesures différentes de deux
outils différents ; elles ne sont jamais comparées ni rapportées l'une à l'autre.

## 3. Écarts attendus avec le deck de référence (BELUX T3-2026)
Le deck mélange des périmètres : ses sessions sont Belgique seule, ses In Journey / Hot leads sont BE + LU, et la flèche
« 37 % » divise des utilisateurs par des sessions. Nos chiffres cohérents diffèrent donc de lui :
- **Sessions trade-in** : +5 à +7 % (le Luxembourg est inclus). Peugeot 25 323 contre 23 620.
- **Taux In Journey** : calculé en utilisateurs sur utilisateurs, donc plus élevé que le 37 % du deck.
- Leads, sources d'acquisition, In Journey et Hot leads : à 0,2–2 % du deck (vérifié, voir historique de validation).

## 4. Validation (T3-2026, Peugeot BELUX)
Leads 3 623 / 3 631 · New cars par source 241/57/261/420/597 contre 241/57/262/421/598 · In Journey 8 721 / 8 811 ·
Hot leads 2 903 / 2 968 · Citroën : In Journey 4 101 / 4 172, Hot leads 1 234 / 1 237.

## 5. Pièges et points à investiguer
- **Belgique** : deux sites de reprise par marque ; avant le 10/10/2026 un seul était mesuré (trafic sous-compté ~50 %). Corrigé dans
  `pipeline/discover.py` (`hotes_reprise_complets`).
- **Fiat BE** (sessions 3 134 chez nous contre 4 047 dans le deck), **Abarth BE** (aucun hôte de reprise détecté dans GA4),
  **Opel T3-2025** (−4 % en leads) : à investiguer.
- Hot lead défini côté back-office (leads VN dont la marque d'achat = marque du site) : 1 574 pour Peugeot BELUX T3 ; non retenu
  (mesure différente), la marque d'achat reste en base (`leads_acq`).
