# PSA Site Factory — Dashboard Analytics

Dashboard statique (HTML/CSS/JS, sans build) suivant les leads, le trafic et le
parcours de reprise de 5 sites PSA sur **avril → juillet 2026**.

## Sites couverts

OPEL FR · OPEL PT · PEUGEOT PT · DS PT · CITROEN PT

## Contenu

| Onglet | Métrique | Source |
|---|---|---|
| **Leads** | Leads générés, dimensions (marque reprise, carburant, source, code marketing, mode d'entrée, projet d'achat) | Back-office PSA Site Factory |
| **Trafic** | **Sessions** site parent et outil de reprise | Google Analytics 4 |
| **Funnel** | **Utilisateurs actifs** par étape, comparaison pré/post V2 | Exploration de funnel GA4 |

## Points de méthode

- **Deux métriques distinctes.** Le trafic est en *sessions*, le funnel en
  *utilisateurs actifs* : l'exploration de funnel GA4 ne propose pas la métrique
  « sessions ». Les volumes des deux onglets ne sont donc pas comparables.
- **Taux de conversion leads** = leads ÷ sessions de l'outil de reprise. C'est
  sur l'outil que le lead est capté ; le site parent ne fait qu'y renvoyer du trafic.
- **Juillet est partiel** : 28 jours pour les leads et la reprise, 27 pour le
  trafic site (export GA4 arrêté au 27/07). Toutes les comparaisons entre mois
  sont donc calculées **en moyenne par jour**.
- **Filtre leads** : hors doublons, hors tests (`TEST` / `TEST_INTERNE`) et
  limité à `MODE_PRODUCTION`.
- **Funnel juillet** : présenté en pré-V2 / post-V2 (lancement du 22/07) plutôt
  qu'en total mensuel, les deux exports GA4 se chevauchant d'une journée.

## Structure

```
index.html          page unique
style.css           styles
script.js           rendu et calculs (Chart.js via CDN)
data/index.json     liste des sites
data/<site>.json    données par site (4 mois : leads, trafic, reprise, funnel)
```

## Déploiement

Site statique : aucun build. Sur Vercel, importer le dépôt et laisser le
framework sur « Other », répertoire racine.
