# PSA Site Factory — Dashboard Analytics

Dashboard statique (HTML/CSS/JS, sans build) suivant les leads, le trafic et le
parcours de reprise de 5 sites PSA sur **avril → juillet 2026**.

## Sites couverts

OPEL FR · OPEL PT · PEUGEOT PT · DS PT · CITROEN PT

## Contenu

| Onglet | Métrique | Source |
|---|---|---|
| **Leads** | Leads générés, dimensions (marque reprise, carburant, source, code marketing, mode d'entrée, projet d'achat, appareil) | Back-office PSA Site Factory |
| **Trafic** | **Sessions** site parent et site de reprise | Google Analytics 4 |
| **Funnel** | **Utilisateurs actifs** par étape, comparaison pré/post V2 | Exploration de funnel GA4 |

## Points de méthode

- **Deux métriques distinctes.** Le trafic est en *sessions*, le funnel en
  *utilisateurs actifs* : l'exploration de funnel GA4 ne propose pas la métrique
  « sessions ». Les volumes des deux onglets ne sont donc pas comparables.
- **Taux de conversion leads** = leads ÷ sessions du site de reprise. C'est
  sur ce site que le lead est capté ; le site parent ne fait qu'y renvoyer du trafic.
- **Tout le trafic est en sessions**, extrait de GA4 via les onglets filtrés par
  nom d'hôte (site parent d'un côté, site de reprise de l'autre). Les données
  antérieures en *utilisateurs actifs* ont été retirées, de même que les
  indicateurs qui en dépendaient (nouveaux utilisateurs, durée d'engagement).
- **Les libellés d'onglets GA4 ne sont pas fiables** : sur Citroën PT, l'onglet
  nommé « Trafic V2 parent » contient en réalité le site de reprise et
  « Analyse traffic » le site parent. L'identification se fait sur le filtre
  hostname, jamais sur le nom.
- **Juillet est partiel** : 28 jours pour les leads et la reprise, 27 pour le
  trafic site (export GA4 arrêté au 27/07). Toutes les comparaisons entre mois
  sont donc calculées **en moyenne par jour**.
- **Le lancement V2 n'a pas la même date selon les sites** :

  | Site | Lancement V2 |
  |---|---|
  | OPEL PT | 02/06/2026 |
  | OPEL FR | 16/07/2026 |
  | PEUGEOT PT · DS PT · CITROEN PT | 22/07/2026 |

  Les graphes quotidiens affichent un trait vertical daté à la bascule et
  teintent la période postérieure.
- **Filtre leads** : hors doublons, hors tests (`TEST` / `TEST_INTERNE`) et
  limité à `MODE_PRODUCTION`.
- **Funnel juillet** : présenté en deux sous-périodes plutôt qu'en total
  mensuel, les deux exports GA4 se chevauchant d'une journée. Pour OPEL FR et
  les trois sites PT, ces sous-périodes correspondent bien au pré/post V2. Pour
  **OPEL PT en revanche, la V2 date du 02/06** : les deux sous-périodes de
  juillet sont toutes deux postérieures au lancement, ce n'est donc pas une
  comparaison avant/après (un avertissement le signale dans l'interface). Pour
  ce site, l'effet V2 se lit en comparant avril–mai à juin–juillet.

## Vue cumulée

Un bouton **Total** à droite du sélecteur de mois affiche la période complète
(01/04 → 28/07, 119 jours) : totaux de leads, trafic et reprise, séries
quotidiennes continues, et dimensions **recalculées depuis les CSV sources**
(et non additionnées à partir des tops mensuels, ce qui aurait tronqué les
valeurs sorties du top 8 certains mois).

Le **funnel n'y est pas cumulé** : GA4 dédoublonne les utilisateurs actifs,
additionner les mois compterait plusieurs fois une même personne. La vue Total
affiche donc le détail période par période, avec la moyenne avant / après V2.

## Structure

```
index.html          page unique
style.css           styles
script.js           rendu et calculs (Chart.js via CDN)
data/index.json     liste des sites
data/<site>.json    données par site (4 mois : leads, trafic, reprise, funnel)
```

## Connexion et assistant IA

- **Connexion** : Google Sign-In restreint au domaine `ALLOWED_DOMAIN` (voir
  `middleware.js`, `api/auth.js`). Un cookie de session signé (HttpOnly)
  protège `data/*.json`, `/api/agent` et `/api/refresh` — la protection est
  côté serveur, pas un simple écran client.
- **Assistant IA** (onglet « Assistant IA ») : `api/agent.js` orchestre 4
  agents spécialisés (`api/_lib/tools.js`) — Analytics, Business, UX (lecture
  des `data/*.json`, aucun appel GA4/GSC supplémentaire) et Dashboard (ouvre
  une pull request GitHub pour toute modification du dashboard — jamais de
  push direct sur `main`).
- Variables d'environnement Vercel requises : `GOOGLE_CLIENT_ID`,
  `ALLOWED_DOMAIN`, `AUTH_COOKIE_SECRET`, `ANTHROPIC_API_KEY`,
  `GITHUB_PR_TOKEN` (en plus de `GITHUB_TOKEN`/`GITHUB_REPO` déjà utilisés par
  `api/refresh.js`).

## Déploiement

Site statique : aucun build. Sur Vercel, importer le dépôt et laisser le
framework sur « Other », répertoire racine.
