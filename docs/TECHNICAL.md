# Documentation technique — psa-site-factory-analytics

Doc d'architecture expliquée : comment le système est construit, comment le
faire tourner en local, où vivent les secrets, et comment se répartissent
les deux dépôts Git. Pour l'usage côté KAM (onglets, KamIA, ce qu'on peut
lui demander), voir le guide fonctionnel séparé — ce document-ci est pour
quiconque touche au code.

> Ce fichier documente l'état du **2026-09-02**. `CLAUDE.md` à la racine du
> repo reste la référence "vivante" (mise à jour à chaque changement
> d'architecture) ; ce document est une explication plus posée du même
> système, à relire quand `CLAUDE.md` a trop grossi pour un premier contact.

---

## 1. Vue d'ensemble

**Ce que c'est** : un dashboard interne (autobiz) pour les KAM qui suivent
~64 sites "reprise" (rachat de véhicule) du réseau Stellantis (Peugeot,
Citroën, Opel, DS, Fiat, Jeep, Alfa Romeo, Abarth, Lancia, Spoticar…). Il
affiche du trafic GA4, des leads back-office, du Search Console, du
PageSpeed, et embarque "Hermes"/"KamIA", un assistant conversationnel
propulsé par Claude qui répond à partir des mêmes données réelles.

**Deux dépôts Git séparés, un seul déployé** :

| Dépôt | Contenu | Public ? |
|---|---|---|
| `dcs-masterclass-ia/psa-site-factory-analytics` (**celui-ci**) | Tout le code : front, API serverless, pipeline Python, workflows | Peut être public — aucune donnée business dedans |
| `dcs-masterclass-ia/psa-site-factory-data` | Uniquement les `data/<slug>.json` produits par le pipeline | Privé — c'est là que vivent les vraies données |

La séparation date du 12/08/2026 (avant, `data/` était versionné dans ce
repo). Ce repo-ci est déployé sur Vercel ; le repo data ne l'est jamais
directement, il est simplement cloné au moment du build (§4) et par les
workflows qui en ont besoin.

**Pas de build front** : `index.html` + `script.js` + `support.js` +
`style.css` sont servis tels quels par Vercel (fichiers statiques). Pas de
React, pas de Webpack/Vite pour le dashboard principal — `index.html`
utilise un petit DSL de templating maison (`sc-if`, `sc-for`,
interpolation `{{ }}`) piloté par une seule grosse méthode `toState()` qui
construit tout l'état affiché à partir de `this.data`. La seule exception
avec un vrai build est le panneau KamIA bêta (§3.6).

---

## 2. Arborescence

```
├── index.html            # l'app entière (front, DSL de templating maison)
├── script.js / support.js / style.css   # runtime du DSL, styles
├── middleware.js         # Vercel Edge Middleware — vrai contrôle d'accès
├── vercel.json            # config Vercel (build command, headers, functions)
├── package.json           # minimal exprès (voir §4)
├── requirements.txt        # deps Python du pipeline
├── hermes-agui.js          # bundle GÉNÉRÉ du panneau KamIA bêta (§3.6)
│
├── api/                    # fonctions serverless Vercel (Node, un fichier = une route)
│   ├── auth.js / logout.js / config.js
│   ├── agent.js             # orchestrateur KamIA (§3.1)
│   ├── kamia-conversations.js
│   ├── gsc-compare.js
│   ├── perf-ticket.js
│   ├── refresh.js
│   └── _lib/                # helpers partagés, pas des routes
│       ├── anthropic.js       # wrapper Messages API Claude (fetch brut)
│       ├── auth.js             # signature/vérif cookie session (Node)
│       ├── data.js             # lecture des data/<slug>.json
│       ├── google.js           # JWT bearer compte de service Google
│       ├── github.js           # branche + PR (Agent Dashboard)
│       ├── store.js            # magasin JSON sur le repo data (§3.5)
│       └── tools.js            # agents spécialistes KamIA (§3.2)
│
├── pipeline/                # tout Python — extraction + assemblage des data/*.json
│   ├── build.py              # point d'entrée principal (§5.1)
│   ├── sites.py               # config statique du périmètre (§5.4)
│   ├── ga4.py / funnel.py / funnel_weekly.py / channel.py
│   ├── search_console.py / insights.py
│   ├── leads_extract.py / backfill_leads*.py / backfill_rebond.py
│   ├── pagespeed.py
│   ├── controls.py            # contrôles bloquants avant publication (§5.2)
│   ├── watch.py                # pré-tri veille quotidienne (§5.5)
│   ├── v2_report.py            # agrégats avant/après refonte V2
│   ├── discover.py / discover_sites.py / metadata.py
│   └── compare_ga4.py / _diag_*.py   # scripts de diagnostic ponctuels
│
├── scripts/
│   ├── fetch-data.sh          # clone data/ (build command Vercel, §4)
│   └── hermes_watch.js         # génère l'analyse narrative de la veille (§5.5)
│
├── panel/hermes-agui/          # source du panneau KamIA bêta (§3.6)
├── tests/e2e/smoke.spec.js     # Playwright, seule suite de tests (§6)
└── .github/workflows/          # tout l'automatisé (§7)
```

---

## 3. Les fonctions serverless (`api/`)

Chaque fichier de `api/` (hors `_lib/`) est une route Vercel — le nom du
fichier est le chemin (`api/agent.js` → `/api/agent`). Toutes utilisent
`fetch` natif, zéro dépendance npm (voir §4, pourquoi).

### 3.1 `api/agent.js` — l'orchestrateur KamIA

Le cœur de l'assistant. Reçoit une question (+ périmètre optionnel +
pièces jointes), boucle en tool-use avec Claude jusqu'à obtenir une
réponse finale.

- **Modèle** : `claude-sonnet-5`, `thinking:{type:"adaptive"}`,
  `output_config:{effort:"medium"}`.
- **`KAM_MAX_TOKENS = 16000`** — partagé entre le budget de réflexion
  (thinking) et le texte de la réponse. **Piège réel rencontré** : à
  4096, une question qui enchaîne plusieurs outils pouvait épuiser tout le
  budget en réflexion et repartir avec `stop_reason:"max_tokens"` et un
  texte vide — silencieusement affiché "(pas de réponse)" côté front.
  Corrigé le 2026-09-02 (budget monté + message de repli explicite au
  lieu d'un texte vide).
- **Boucle** (`runAgentLoop`, `MAX_ITERATIONS = 6`) : appelle
  `callClaudeStream`, exécute les `tool_use` demandés via `runTool()`
  (§3.2), repousse les résultats, recommence jusqu'à ce que
  `stop_reason !== "tool_use"`.
- **Deux modes de réponse sur le même endpoint** :
  - Par défaut : JSON bufferisé `{answer, agentsConsultes, charts,
    history}` — c'est ce que consomme le chat production dans
    `index.html`.
  - `?stream=1` : vrai protocole **AG-UI** (SSE, `RunAgentInput` en
    entrée → événements `TEXT_MESSAGE_*`/`TOOL_CALL_*`/`RUN_*` en
    sortie) — consommé uniquement par le panneau bêta (§3.6).
    `ask_agent_dashboard` (qui édite `index.html` et ouvre une PR — voir
    `_lib/github.js`) déclenche un **interrupt AG-UI** dans ce mode : le
    run se met en pause, le client doit confirmer/annuler via `resume`
    avant exécution. En mode JSON, cet outil s'exécute directement, sans
    confirmation.
- **Contexte injecté automatiquement** (`buildInitialContent`) : si un
  site/onglet est déjà ouvert à l'écran (`view`), une ligne "(Actuellement
  affiché dans le dashboard : …)" est ajoutée — distincte du "Périmètre
  sélectionné" manuel (`scope`), jamais fusionnés.

### 3.2 `api/_lib/tools.js` — les agents spécialistes

Définit les outils exposés à Claude dans `agent.js` :

| Outil | Rôle |
|---|---|
| `list_sites` | Liste des sites (pour lever une ambiguïté de nom) |
| `ask_agent_analytics` | Sous-agent Haiku, lecture GA4 fine |
| `ask_agent_business` | Sous-agent Haiku, impact business/leads |
| `ask_agent_ux` | Sous-agent Haiku, parcours/friction/PageSpeed |
| `get_series` | Renvoie une vraie série de valeurs (jamais approximée) |
| `compare_to_peers` | Classe un site vs tout le parc, ou vs même marque uniquement (`marqueDeSite()`) — jamais un chiffre qualifié "bon/mauvais" sans base de comparaison |
| `show_chart` | Déclenche l'affichage d'un graphique côté front, à partir de données déjà obtenues via `get_series` |
| `ask_agent_dashboard` | Seul outil qui **modifie du code** — édite `index.html` et ouvre une PR (`_lib/github.js`) |

Les sous-agents (`askSpecialist()`) tournent sur `claude-haiku-4-5` — pas
de paramètre `effort` sur ce modèle (rejeté, contrairement à Sonnet).
`compare_to_peers` a ses propres planchers de fiabilité
(`PEERS_PLANCHER_ENTREES=30`, `PEERS_PLANCHER_JOURS=20`) pour ne jamais
classer un site sur un mois de données trop clairsemé.

### 3.3 `api/_lib/anthropic.js` — wrapper Messages API

Fetch brut vers `https://api.anthropic.com/v1/messages`, deux fonctions :
`callClaude` (non-stream) et `callClaudeStream` (SSE, reconstruit les
blocks au fil de l'eau).

**Piège réel corrigé le 2026-09-02** : le parseur SSE doit traiter
explicitement les blocs `thinking`/`redacted_thinking` (deltas
`thinking_delta`/`signature_delta`, jamais `text_delta`). Les confondre
avec le cas générique "pas tool_use ⇒ texte" laissait un bloc
`{type:"text", text:""}` vide dans l'historique renvoyé à l'API au tour
suivant — que Claude rejette avec *"text content blocks must be
non-empty"*. Tout futur type de bloc ajouté par Anthropic doit recevoir le
même traitement explicite, jamais un repli silencieux sur "text".

### 3.4 `api/_lib/auth.js` (Node) + `middleware.js` (Edge) — authentification

Deux implémentations du **même** HMAC-SHA256 (secret `AUTH_COOKIE_SECRET`
partagé), parce que `middleware.js` tourne en Edge Runtime (Web Crypto) et
les fonctions `api/*.js` en runtime Node (`crypto` natif) :

1. `api/auth.js` vérifie un ID token Google (endpoint `tokeninfo`, pas de
   lib JWT), vérifie le domaine (`ALLOWED_DOMAIN`), signe un cookie
   `psf_session` (HMAC, 7 jours).
2. `middleware.js` (`export const config = {matcher: [...]}`) est le
   **vrai** contrôle d'accès — un écran de connexion côté client seul ne
   bloquerait rien, n'importe qui pourrait appeler `/data/*.json`
   directement. Le matcher actuel :
   `["/data/:path*", "/api/agent", "/api/refresh", "/api/perf-ticket",
   "/api/kamia-conversations"]`.
   **Point d'attention** : `api/gsc-compare.js` fait sa propre vérification
   de session en interne (défense en profondeur, même pattern que les
   autres) mais n'est **pas** dans ce matcher — à ajouter si une faille de
   contournement y est un jour identifiée. Tout nouvel endpoint sensible
   doit être ajouté au tableau `matcher`.

### 3.5 `api/_lib/store.js` — magasin clé/JSON sur le repo data

Petit "KV store" adossé au repo **data** (pas ce repo-ci) via l'API
Contents de GitHub — `readJson(path)` / `writeJson(path, obj, message,
sha)`. Sert aujourd'hui à `api/kamia-conversations.js` (un fichier JSON
par utilisateur, `kamia/<sha256(email)>.json`).

- Réutilise **`DATA_REPO_TOKEN`** (déjà là pour `fetch-data.sh`, en
  lecture) — doit maintenant avoir **Contents: Read and write** sur
  `psa-site-factory-data`.
- Gère les collisions d'écriture concurrente : sur 409/422 (sha périmé),
  relit et réessaie jusqu'à 3 fois — dernier écrivain gagne, acceptable
  car un même utilisateur écrit rarement depuis 2 onglets à la
  milliseconde près.
- Variables optionnelles : `KAMIA_STORE_REPO` (défaut
  `dcs-masterclass-ia/psa-site-factory-data`), `KAMIA_STORE_BRANCH`
  (défaut `main`).

### 3.6 Le panneau KamIA bêta (AG-UI)

`hermes-agui.js` à la racine est **généré**, ne jamais l'éditer à la main.
Source réelle : `panel/hermes-agui/src/`, rebuild avec
`cd panel/hermes-agui && node build.js`. C'est un panneau React +
`@ag-ui/client`, monté hors de l'arbre du DSL `text/x-dc` (pour ne pas être
effacé par ses propres re-renders), consommant le mode `?stream=1` de
`api/agent.js`. Réutilise les globales `window.React`/`window.ReactDOM`
déjà chargées par `support.js` — pas de copie de React embarquée — via des
accesseurs paresseux (`react-shim.js`/`reactdom-shim.js`), nécessaires
parce que le bundle peut s'exécuter avant que `support.js` ait fini de
charger React.

### 3.7 Autres routes

- **`api/gsc-compare.js`** — comparaison Search Console sur une plage de
  dates arbitraire, en appel **live** à l'API Search Console (pas le
  pipeline batch) : la donnée stockée (`searchMonth`) est mensuelle, sans
  résolution jour — projet qui s'interdit toute interpolation. Réutilise
  le compte de service `GSC_SERVICE_ACCOUNT` (même clé que
  `GA4_SERVICE_ACCOUNT` côté GitHub Actions).
- **`api/perf-ticket.js`** — rédige un ticket Jira (titre + corps) depuis
  de vraies mesures PageSpeed, via Claude Haiku. Ne crée rien dans Jira
  (pas d'API configurée), renvoie juste un texte à coller.
- **`api/refresh.js`** — déclenche `refresh.yml` sur GitHub Actions à la
  demande depuis le bouton "Actualiser" du dashboard. Jeton
  `GITHUB_TOKEN` **fin**, portée strictement "Actions: Read and write",
  jamais "Contents". `REF` suit `VERCEL_GIT_COMMIT_REF` (donc `staging` en
  Preview `staging`, `main` en Production).
- **`api/auth.js` / `api/logout.js` / `api/config.js`** — voir §3.4 ;
  `config.js` expose juste `GOOGLE_CLIENT_ID` (pas un secret, mais piloté
  par variable d'env pour ne pas coder en dur un ID de projet Google
  Cloud).

---

## 4. Faire tourner le projet en local

**Aucun build front nécessaire** — un simple serveur de fichiers statiques
suffit. `package.json` racine est **volontairement minimal**
(`{name, private, version}`, rien d'autre) : Vercel ne doit tenter
d'installer/builder *rien* pour ce site statique.

### 4.1 Récupérer de vraies données

L'app n'affiche rien sans un `data/` peuplé (gitignored, pas versionné
ici). Deux options :

```sh
sh scripts/fetch-data.sh     # nécessite DATA_REPO_TOKEN en variable d'env
# ou, sans le token :
gh repo clone dcs-masterclass-ia/psa-site-factory-data data
rm -rf data/.git             # sinon ça devient un sous-repo imbriqué
```

`fetch-data.sh` clone en shallow (`--depth 1`) la branche
`$VERCEL_GIT_COMMIT_REF` du repo data, avec repli sur `main` si cette
branche n'existe pas côté data (ex. une Preview sur une feature branch
quelconque).

### 4.2 Servir l'app

```sh
python3 -m http.server 8199 --directory ..
```
(C'est exactement ce que fait la config Playwright automatiquement — voir
§6.)

### 4.3 Variables d'environnement (fonctions serverless uniquement)

Pas nécessaires pour juste parcourir le dashboard statique contre des
données locales. Nécessaires pour exercer `api/*.js` (ex. via `vercel
dev`) :

| Variable | Utilisée par | Portée requise |
|---|---|---|
| `GOOGLE_CLIENT_ID` | `auth.js`, `config.js` | Client OAuth Web |
| `ALLOWED_DOMAIN` | `auth.js` | ex. `autobiz.com` |
| `AUTH_COOKIE_SECRET` | `_lib/auth.js`, `middleware.js` | secret aléatoire (`openssl rand -hex 32`) |
| `ANTHROPIC_API_KEY` | `_lib/anthropic.js` | clé API Claude |
| `GITHUB_TOKEN` | `refresh.js` | fin, **Actions: Read/write uniquement** sur ce repo |
| `GITHUB_PR_TOKEN` | `_lib/github.js` | fin, **Contents + Pull requests: write** sur ce repo |
| `DATA_REPO_TOKEN` | `fetch-data.sh`, `_lib/store.js` | fin, **Contents: Read and write** sur `psa-site-factory-data` |
| `GSC_SERVICE_ACCOUNT` | `_lib/google.js`, `gsc-compare.js` | JSON complet de la clé de compte de service |
| `KAMIA_STORE_REPO` / `KAMIA_STORE_BRANCH` | `_lib/store.js` | optionnelles, défauts déjà sensés |

**Note secrets** : `GITHUB_TOKEN` (déclenche un workflow) et
`GITHUB_PR_TOKEN` (crée branche + PR) sont volontairement deux jetons
séparés avec des portées différentes — ne jamais les fusionner en un seul
jeton large.

---

## 5. Le pipeline (`pipeline/`, Python)

### 5.1 `build.py` — point d'entrée

Régénère la partie GA4 (séries quotidiennes, totaux mensuels, détection
de trafic automatisé) et **préserve** la partie leads (produite à part par
le back-office — rien n'est écrasé côté leads par `build.py`).

**Écriture incrémentale, site par site** (`_commit_et_pousse()`) — pas un
seul gros commit à la fin. Changement fait suite à deux pertes réelles le
07-08/08/2026 avec l'ancienne écriture en bloc : un push final raté avait
fait perdre ~2h de calcul GA4/GSC/leads pour 52 sites, puis un contrôle
bloquant sur seulement 4 sites avait annulé l'écriture de 48 autres
pourtant publiables. Depuis : un site en échec de contrôle garde les
données de la veille et ne bloque jamais les autres sites du même run.

`data/pipeline.json` est **toujours** écrit (succès comme échec) — c'est
le canal d'alerte du dashboard, un échec muet serait pire qu'un échec
visible.

`DECALAGE_GSC = 3` jours : Search Console publie avec 2-3 jours de retard,
plus long que GA4 — on se limite par prudence à J-3.

### 5.2 `controls.py` — contrôles avant publication

Chaque contrôle est né d'une vraie erreur déjà survenue sur ce projet (les
commentaires du fichier disent laquelle). Deux catégories :

- **Bloquant** : échec ⇒ le site n'est pas écrit, garde les données de la
  veille.
- **Avertissement** : passe, mais remonte dans `data/pipeline.json` et
  s'affiche dans le dashboard.

Seuils actuels : `ECART_DEPOT_MAX=30%`, `NON_ADDITIVITE_MAX=3.5%`,
`TRANSFO_MIN/MAX=[2%, 45%]`, `SESSIONS_PAR_USER_MAX=3.0`,
`TRAFIC_ETRANGER_MAX=40%`.

### 5.3 Autres modules d'extraction

- `ga4.py` / `funnel.py` / `funnel_weekly.py` / `channel.py` — trafic,
  entonnoir, agrégats hebdo, canaux GA4.
- `search_console.py` / `insights.py` — clics/impressions/position,
  génération d'insights texte (OpenAI `gpt-4o-mini`), avec ses propres
  planchers de volume (`SEUIL_GSC`, `PLANCHER_GSC_IMPR`,
  `PLANCHER_JOURS`, `PLANCHER_LEADS`, `SEUIL_DIM_LEADS`,
  `PLANCHER_ENTREES`) et un garde-fou `_mois_incomplets()` contre le biais
  d'un mois partiel.
- `leads_extract.py` / `backfill_leads*.py` / `backfill_rebond.py` —
  extraction et rattrapage des leads back-office.
- `pagespeed.py` — mesures Lighthouse (3 passages par host/stratégie,
  garde la médiane plutôt qu'un essai isolé).
- `v2_report.py` — agrégats avant/après la refonte V2 d'un site
  (`_agrege_jours`, `_agrege_leads`), réutilisés à la fois par
  `build.py` et par `watch.py`.
- `discover.py` / `discover_sites.py` / `metadata.py` — découverte de
  nouvelles propriétés GA4/Search Console accessibles au compte de
  service.

### 5.4 `sites.py` — configuration du périmètre

Liste statique `SITES: list[Site]` (`nom`, `slug`, `propriete` GA4, hôtes
parent/reprise, `verifie: bool`, `acces_api: bool`, `pays`). Règle
absolue héritée du projet : **un nom d'hôte n'est jamais deviné ni
supposé** — toujours relevé réellement dans GA4
(`python3 -m pipeline.ga4 --propriete <id> --hotes`) avant d'être inscrit
ici avec `verifie=True`.

### 5.5 `watch.py` — pré-tri de la veille quotidienne

Voir aussi §7 (workflow). Rien n'écrit dans `data/` — imprime un JSON sur
stdout, lu par `scripts/hermes_watch.js` via une redirection shell.

Un site est retenu si **au moins un** de ces trois signaux, indépendants
les uns des autres, dépasse son seuil :

| Signal | Seuil | Détail |
|---|---|---|
| Trafic/leads | `SEUIL_ECART_PCT=25%` (avec `VOLUME_MIN=20` — sous ce volume, un écart en % est du bruit) | 7 derniers jours vs 7 précédents |
| Régression PageSpeed | `PAGESPEED_SEUIL_PTS=15` pts | mobile OU desktop, entre les deux derniers relevés |
| Dégradation SEO | `SEARCH_SEUIL_POSITION=3.0` positions (avec `SEARCH_PLANCHER_IMPR=50` impressions minimum) | mois vs mois précédent |

`scripts/hermes_watch.js` n'appelle Claude (`askSpecialist()`,
`api/_lib/tools.js` réutilisé directement, **pas** via `/api/agent` — job
planifié sans navigateur/session) que sur les sites retenus. Quand deux
signaux ou plus se déclenchent sur le même site, le prompt lui demande
explicitement de les relier plutôt que de les lister comme des faits
séparés. Résultat écrit dans `data/hermes_watch.json`.

---

## 6. Tests

Une seule suite : **Playwright**, `tests/e2e/smoke.spec.js` — sa propre
`package.json` dans `tests/`, délibérément hors de la racine pour que
Vercel ne tente jamais de builder quoi que ce soit pour elle.

```sh
cd tests
npm ci
npx playwright install --with-deps chromium   # une seule fois
npm test
```

La config Playwright démarre elle-même `python3 -m http.server 8199
--directory ..` — pas de serveur à lancer à la main. Nécessite un `data/`
peuplé (§4.1) : ce sont de vrais fichiers JSON qui sont lus, pas des
fixtures.

**Couverture** : chargement sans erreur JS, vue "tous les sites" par
défaut, chaque onglet de navigation (méga-menu compris — un onglet groupé
doit d'abord ouvrir son groupe avant d'être cliqué), recherche/sélection
de site, changement de période.

**Tourne aussi en CI** (`.github/workflows/e2e-tests.yml`), sur chaque PR
et chaque push sur `main`. **À lancer systématiquement en local avant tout
push sur `main`**, quelle que soit la politique de push direct (§8) — sur
un repo sans étape de déploiement staging par défaut, c'est le seul filet
entre un changement et la prod.

---

## 7. Automatisation (`.github/workflows/`)

| Workflow | Déclenchement | Rôle |
|---|---|---|
| `refresh.yml` | cron `0 22 * * *` (quotidien) + manuel | Lance `pipeline/build.py` sur tout le périmètre, commit/push vers le repo **data**, puis déclenche un redéploiement Vercel |
| `hermes-watch.yml` | cron `45 22 * * *` (juste après `refresh.yml`) + manuel | Pré-tri (`watch.py`) + analyse narrative (`hermes_watch.js`) — voir §5.5 |
| `pagespeed.yml` | **manuel uniquement**, pas de cron | Mesure Lighthouse à la demande (site par site ou tout le périmètre) ; purement additif, n'écrit que la clé `pagespeed`, sans contrôle bloquant `build.py` ; commit/push site par site (un run interrompu laisse quand même publié ce qui est déjà mesuré) |
| `discover-sites.yml` | manuel | Liste les propriétés GA4/Search Console accessibles au compte de service |
| `backfill-leads.yml` / `backfill-leads-2025-debut.yml` / `backfill-rebond.yml` | manuel | Rattrapages ponctuels de données historiques |
| `ga4-check.yml` / `gsc-check.yml` | — | Diagnostics d'accès API |
| `diag-siteid.yml` / `diag-valide.yml` | manuel | Scripts de diagnostic ponctuels (`_diag_*.py`) |
| `e2e-tests.yml` | PR + push sur `main` | Suite Playwright (§6) |
| `metadata.yml` | — | Rafraîchit `pipeline/metadata.py` |

Tous les workflows qui ont besoin de données clonent le repo **data**
séparément (jamais `git submodule`), sur la branche correspondante
(`main`/`staging`) avec repli sur `main`. `pipeline/build.py`'s
`_commit_et_pousse()` pousse **directement vers ce repo data**, jamais
vers ce repo-ci.

---

## 8. Environnements Git et politique de déploiement

**Branches de ce repo** : `main` (défaut, production), `staging`
(preview), plus des branches de travail ponctuelles
(`pipeline-etape1`, `ci/e2e-tests-playwright`).

**Branches du repo data** : `main` et `staging`, en miroir logique des
mêmes noms côté code — chaque déploiement Vercel clone la branche data qui
porte le même nom que la branche code déployée
(`VERCEL_GIT_COMMIT_REF`), avec repli sur `main` si l'équivalent n'existe
pas côté data.

**Politique de push** : direct sur `main`, y compris pour du travail UI —
pas de détour obligatoire par `staging` pour un changement routinier.
`staging` et toute la logique de détection de branche
(`GITHUB_REF_NAME`/`VERCEL_GIT_COMMIT_REF`, checkout du repo data côté
workflows, `REF` dans `api/refresh.js`) doivent rester fonctionnels même
si ce n'est pas le chemin par défaut. **Exception** : un changement à
fort rayon d'impact (refonte visuelle complète affectant tous les
utilisateurs) doit être signalé pour passer d'abord par `staging`, pas
supposé sûr en direct.

**Avant de pousser sur `main`** : `git fetch origin main`, vérifier une
divergence (rare — le pipeline pousse vers le repo data, pas ici — mais
possible si une autre session/CI a déjà poussé), préférer un
fast-forward ; en cas de divergence, inspecter le diff avant de fusionner,
surtout si ça touche `data/` ou du JSON généré.

**Déploiement** : Vercel, build command = `sh scripts/fetch-data.sh`
(clone `data/`, voir §4.1), `outputDirectory: "."` (rien à builder,
fichiers statiques servis tels quels). `vercel.json` fixe aussi
`maxDuration: 300` pour `api/agent.js` (les tours de tool-use de KamIA
peuvent prendre du temps) et un header cache court sur `/data/*`
(`max-age=0, must-revalidate` — toujours resservir la donnée la plus
fraîche plutôt que de risquer un cache Vercel périmé).
