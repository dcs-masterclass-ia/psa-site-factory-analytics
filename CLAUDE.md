# psa-site-factory-analytics

## What this is

Internal dashboard for Stellantis Site Factory (PSA/DS/Opel/Fiat/Jeep/Alfa
Romeo/Abarth/Lancia/Spoticar "reprise" sites) used by KAMs to track traffic,
leads, funnel, PageSpeed and Search Console performance across ~64
markets/brands, plus "Hermes"/"KamIA", a Claude-powered assistant embedded in
the dashboard that answers questions using the same real data.

Single-page app: `index.html` + `script.js` + `support.js` + `style.css`,
served statically by Vercel with a few serverless functions in `api/`. No
frontend build step — `package.json` at the repo root is intentionally
minimal (see `tests/package.json` comment: Vercel must not try to
install/build anything for this static site).

## Architecture

- **Frontend**: static `index.html`/`script.js`/`support.js`/`style.css`,
  no framework, no bundler (a custom `sc-if`/`sc-for`/`{{ }}` templating DSL
  driven by one big `toState()` method, not React). Reads pre-computed JSON
  from `data/*.json`.
  - **GA4 tab**: beyond the base KPIs, includes a peer-benchmark card (parc
    entier + same-brand only, via the same ranking logic as
    `compare_to_peers`), per-channel×device conversion with deltas vs the
    comparison period and best/worst-channel callouts, a day-of-week
    seasonality module (volume only), a "Conversion" sub-tab (daily
    accueil→estimation curve + 7-day rolling average + previous period +
    V2 switch marker, from `funnelDaily`, GA4-only so limited profiles see it
    too — see "Conversion — one definition everywhere" below), and a trend-break module (z-score
    on rolling weekly sessions/leads, `RUPTURE_VOLUME_MIN`/`RUPTURE_Z_SEUIL`
    guards, same spirit as `pipeline/watch.py`'s thresholds but duplicated
    client-side since this tab makes no server call).
  - **"Avant / après V2" sub-tab** (GA4 view): derived from `funnelDaily`
    like everything else (`pipeline/v2_report.py`
    `avant_apres_depuis_quotidien`, no GA4 request): before = the 28 days
    preceding the site's `v2_date`, after = every day since; volumes shown
    per day (windows differ in length), rates in points; published only with
    ≥ 7 days after and ≥ 21 measured days before; < 300 visitors in a window
    shows a "tendance indicative" notice. `v2_date` (set by hand in
    `data/<slug>.json`, e.g. FR 2026-09-29/30, ES 2026-10-06/07) is the only
    manual input; `v2steps`/`v2` are recomputed for every site that has one
    (hand-entered ones included), and the old weekly `v2Weekly` report (other
    definition: unique users, whole-history baseline) is no longer produced.
    Info bubbles (`.dc-info` / `.dc-tip`, pure CSS) document how each block is
    computed — keep them in sync when a definition changes.
- **Conversion — one definition everywhere (2026-10-09).** Taux de conversion
  = estimations (users who fired `tradein_request` with step "price
  estimation") ÷ visitors of the funnel's home step, summed over the **exact
  selected days**. Source of truth: `funnelDaily` (`pipeline/funnel_daily.py`,
  6 steps per day, 5 GA4 requests per site over 180 days). The top-of-page
  rate, funnel bars/completion, "Leads GA4" tile, sparklines, park ranking
  and median, and the daily curve all derive from it (`aggregate()` →
  `funnelSteps`/`convDaily`). Fallback to whole weeks/months
  (`funnelWeekly`/`funnelMonth`) only when a site has no daily funnel
  covering the period start, and the UI then says "période approchée".
  Rate deltas are in **points** (`ptDeltaBadge`), never a relative % labelled
  "pt". The channel×device table is a different, labelled metric (converted
  sessions ÷ sessions). Do not add another "conversion" computed from
  sessions or leads BO.
- **Search Console "Pages" — Leads GA4 / Conv.**: `landingMonth[mois].pages`
  (`ga4.landing_conversions_par_page`): sessions and converted sessions by GA4
  `landingPage` (the session's entry page), not by `pagePath` (the event fires
  on the form page, so that was always 0). Landing paths include parent-site
  pages (sessions cross over); the UI only attaches them to pages known to
  Search Console, and never attributes "/" (shared by parent and reprise).
  Format v2 (`{"v":2,"pages":[{page,sessions,conversions,c:{o|p|d|a:[sessions,conv]}}]}`,
  restricted to `build.chemins_landing`): channel groups o=Organic Search,
  p=paid/display, d=Direct, a=other. The Pages card has a channel filter
  (`state.pagesCanal`, default `o`); old-format months only feed "Tous canaux"
  until `backfill-landing.yml` rewrites them. Never name GA4 fields `leads`
  (limited role `stripLeads`).
  History is filled by the manual workflow `backfill-landing.yml`.
- **`api/*.js`** (Vercel serverless functions):
  - `auth.js` / `logout.js` — Google Sign-In verification, signs an HMAC
    session cookie (`psf_session`).
  - `config.js` — exposes the OAuth client ID to the client.
  - `agent.js` — "Agent KAM" orchestrator (Claude Sonnet 5, `thinking:
    {type:"adaptive"}`, tool-use loop over `api/_lib/tools.js` — tools
    include `list_sites`, `ask_agent_analytics/business/ux`, `get_series`,
    `compare_to_peers` (ranks a site against the rest of the fleet, or
    against same-brand peers only — never eyeball a number as "good/bad"
    without it), `show_chart`, `ask_agent_dashboard`) powering the
    Hermes/KamIA assistant. `KAM_MAX_TOKENS` (`maxTokens` passed to
    `callClaudeStream`) is shared between the thinking budget and the final
    answer text — set too low, a multi-tool question can burn the whole
    budget on reasoning and return an empty answer with
    `stop_reason:"max_tokens"` (fixed 2026-09-02, was 4096, now 16000; both
    loops below have a fallback message for this case instead of silently
    returning `""`). Two response modes on the same endpoint: default is
    buffered JSON (`{answer, agentsConsultes, charts, history}`, used by the
    production chat in `index.html`, unchanged since before AG-UI work);
    `?stream=1` switches to the real AG-UI protocol (SSE, `RunAgentInput` in
    → `TEXT_MESSAGE_*`/`TOOL_CALL_*`/`RUN_*` events out), consumed only by
    the beta panel below. `ask_agent_dashboard` (auto-edits `index.html` and
    opens a PR) triggers an AG-UI interrupt in stream mode — the run pauses
    and the client must confirm/cancel via `resume` before it executes;
    the JSON mode still auto-executes it as before (no interrupt support
    there).
  - `hermes-agui.js` (repo root) — **generated**, do not edit by hand.
    React + `@ag-ui/client` panel for Hermes/KamIA ("Hermes β" floating
    button, mounted outside the `text/x-dc` DSL tree so it can't be wiped
    by the DSL's own re-renders). Source in `panel/hermes-agui/src/`,
    rebuild with `cd panel/hermes-agui && node build.js`. Reuses the
    `window.React`/`window.ReactDOM` globals `support.js` already loads
    (no bundled React copy) — see the `react-shim.js`/`reactdom-shim.js`
    lazy accessors, required because the bundle can execute before
    `support.js` has finished loading React.
  - `gsc-compare.js` — on-demand Search Console comparison for arbitrary
    date ranges (live API call; the stored data is monthly resolution only
    — the project's rule is never to interpolate/invent numbers).
  - `perf-ticket.js` — drafts a Jira ticket body from real PageSpeed data
    (does not call Jira, just returns text).
  - `refresh.js` — triggers the `refresh.yml` GitHub Actions workflow
    on demand from the UI, using a fine-grained GitHub token kept
    server-side only.
  - `kamia-conversations.js` — per-user KamIA chat history. Stores one
    JSON file per profile (`kamia/<sha256(email)>.json`) in the private
    **data repo** via the GitHub Contents API (`_lib/store.js`). `GET`
    returns the conversation list (metadata only), `GET ?id=` one full
    conversation, `PUT {upsert:[…],delete:[…]}` merges changes into the
    file. The client (`index.html`) keeps a `localStorage` mirror for
    instant paint / offline resilience and **batches** writes (flush on
    conversation switch, every ~2 min, and on `visibilitychange`/
    `pagehide`) — not one commit per message.
  - `_lib/` — shared helpers (`anthropic.js`, `auth.js`, `data.js`,
    `github.js`, `store.js`, `google.js`, `tools.js`). `store.js` reuses
    `DATA_REPO_TOKEN`, which therefore now needs **Contents: Read and
    write** on `psa-site-factory-data` (it was read-only for
    `fetch-data.sh`). Writes go to `KAMIA_STORE_BRANCH` (default `main`).
    `anthropic.js`'s SSE parser must handle `thinking`/`redacted_thinking`
    content blocks explicitly (distinct `thinking_delta`/`signature_delta`
    events, no `text_delta`) — folding them into the generic "not
    tool_use ⇒ text" branch leaves an empty `{type:"text", text:""}` block
    in the conversation history, which the Messages API then rejects on the
    next turn ("text content blocks must be non-empty"); this broke KamIA
    silently for a while until fixed 2026-09-02. Any future content-block
    type Anthropic adds needs the same explicit handling, not a fallback to
    "text".
- **`middleware.js`**: Vercel Edge Middleware, the *real* access control.
  Guards `/data/:path*` and EVERY `/api/*` route except `auth`, `config`
  and `logout` (protected by default: a new route is closed unless added to
  that public list) by verifying the `psf_session` HMAC cookie — the
  client-side login screen alone would not stop someone from fetching
  `/data/*.json` directly. Sessions last 1 h absolute (`MAX_SESSION_MS` in
  `api/_lib/auth.js`, mirrored in `middleware.js`; `verify` also rejects
  tokens whose `exp` is further than 1 h away, so old long-lived cookies
  die). `index.html` clears the identity cookie and reloads on any 401 or
  when that cookie expires. API handlers must return generic errors via
  `api/_lib/errors.js` `fail()` (detail goes to logs only), and client
  conversation history goes through `api/_lib/history.js` before reaching
  Anthropic.
- **Maintenance mode**: set the Vercel env var `MAINTENANCE=1` (production)
  and redeploy (`vercel redeploy <prod url>`; unset + redeploy to lift). The
  page stays reachable but blurred and inert behind a "Maintenance en cours"
  card (`#maint` in `index.html`, flag read from the public, no-store
  `/api/config`, re-checked every 60 s, auto-reload when lifted), and
  `middleware.js` answers 503 on `/data/*` and every protected `/api/*`
  whatever the profile — the overlay alone is cosmetic.
- **`pipeline/`** (Python): the data pipeline. `build.py` is the entry
  point — extracts GA4 (`ga4.py`, `funnel.py`, `channel.py`), Search
  Console (`search_console.py`, `insights.py`), leads/BO
  (`leads_extract.py`, `backfill_*.py`), PageSpeed (`pagespeed.py`),
  runs blocking controls (`controls.py`) per site, and writes/commits
  each site's JSON **incrementally** — a site is only written/committed if
  its own blocking controls pass; a failing site keeps yesterday's data and
  does not block the other sites in the same run. `data/pipeline.json` is
  always written (success or failure) — it's the dashboard's alert channel,
  a silent failure would be worse than a visible one.
- **Daily proactive watch** (`.github/workflows/hermes-watch.yml`):
  `pipeline/watch.py` does a free statistical pre-filter over every site's
  already-built `data/<slug>.json` (traffic/leads week-over-week delta
  above `SEUIL_ECART_PCT`, a PageSpeed regression, or a Search Console
  position degradation — any one of the three can trigger alone) and prints
  candidates as JSON; only sites it flags get a paid Claude call
  (`scripts/hermes_watch.js`, via `askSpecialist()` in `api/_lib/tools.js`
  — reused directly, not through `/api/agent`, since this is a scheduled
  job with no browser/session) for a narrative write-up, written to
  `data/hermes_watch.json` and surfaced in the dashboard. When two or more
  of the three signal types fire on the same site, `hermes_watch.js` is
  instructed to correlate them explicitly rather than list them as
  unrelated facts.
- **Data storage**: since 2026-08-12, `data/` is **not** part of this repo
  (`/data/` is gitignored here). It lives in a separate private repo,
  `dcs-masterclass-ia/psa-site-factory-data`, so this code repo can be
  public without exposing business data. `scripts/fetch-data.sh` (Vercel
  build command) and every GitHub workflow that needs data check it out
  separately, on the matching branch (`main`/`staging`) with a fallback to
  `main`. `pipeline/build.py`'s `_commit_et_pousse()` commits/pushes
  straight to that data repo (not to this one).

## Local dev

No local server/build needed for manual testing beyond a static file
server — see the Playwright config, which spins up
`python3 -m http.server 8199 --directory ..` automatically. To pull real
data locally (needed for the app to show anything): `sh scripts/fetch-data.sh`
requires a `DATA_REPO_TOKEN` with access to `psa-site-factory-data`; without
it, clone that repo into `data/` manually (e.g. `gh repo clone
dcs-masterclass-ia/psa-site-factory-data data`) and strip its `.git/` so it
doesn't become a nested repo.

Serverless functions (`api/*.js`) need Vercel env vars documented in each
file's header comment (`GOOGLE_CLIENT_ID`, `ALLOWED_DOMAIN`,
`LIMITED_EMAILS` (comma-separated accounts restricted to GA4 / Search Console / PageSpeed: never BO leads, V2 comparison, KamIA or refresh — enforced server-side by `middleware.js` + `api/data.js`/`api/_lib/limited.js`, which strip `leads`, `insights.leads` and `v2*` from the JSON; `index.html` only hides the matching tabs via the `psf_role` cookie), `ALLOWED_EMAILS` (optional allowlist, comma-separated; when set it replaces
the domain check at login AND is re-checked on every request by
`middleware.js`/`verifySessionFromRequest`, so already-issued cookies of
non-listed accounts stop working — keep the addresses in the Vercel env var,
never in this public repo), `AUTH_COOKIE_SECRET`, `GITHUB_TOKEN`, `OPENAI_API_KEY`/Anthropic key, etc.) —
not needed just to browse the static dashboard against local data.

## Testing (run before every push to main)

E2E smoke tests live in `tests/` (deliberately its own `package.json`, kept
out of the repo root so Vercel never tries to build/install anything for
it). They hit the real `index.html` and real `data/*.json` — no mocks.

```
cd tests
npm ci
npx playwright install --with-deps chromium   # first run only
npm test
```

`tests/e2e/smoke.spec.js` covers: page loads with no JS errors, default
"all sites" aggregated view, every nav tab (mega-menu aware) renders
without JS errors, site picker search/selection, period picker. Requires a
populated `data/` directory (see Local dev above) — the tests read real
JSON files, not fixtures.

This same suite runs in CI as `.github/workflows/e2e-tests.yml`, on every
PR and on every push to `main`.

**Always run this locally before pushing to `main`**, regardless of the
direct-to-main policy below — it's the only gate standing between a change
and production for a repo with no staging deploy step in the default flow.

## Push policy

**Default: push straight to `main`.** This includes UI work — no
mandatory staging detour for routine changes. The `staging` branch and the
`GITHUB_REF_NAME`/`VERCEL_GIT_COMMIT_REF` branch-detection plumbing (data
repo checkout ref, `api/refresh.js`'s `REF`, etc.) must be kept working
even though it isn't part of the default flow.

**Exception**: an unusually large, high-blast-radius change — a full
visual overhaul affecting every user (e.g. a past full redesign) — should
be flagged to go through `staging` first rather than assumed safe to push
straight to `main`. Routine feature/bugfix work does not need to ask.

**Before pushing to `main`**: fetch `origin/main` and check for
divergence (the automated `refresh.yml` pipeline pushes to the separate
data repo, not this one, so divergence here is rare, but other sessions/CI
can still have pushed to this repo). Prefer a fast-forward. If diverged,
inspect the diff before merging — do not blindly auto-merge, especially
anything touching `data/` or generated JSON if that ever changes.

## Design fidelity

When given exact reference code/CSS/markup to replicate a UI: copy the
values verbatim (colors, padding, border-radius, flex properties,
font-size, shadows) — don't approximate or "improve" them. Check the outer
composition against the *full* reference screenshot (e.g. one unified
card/surface vs. several floating pieces), not just the fragment handed
over. The one allowed substitution is swapping the app's own real brand
logos/assets in for generic reference placeholders — call that out
explicitly when done.

## Incident : couper l'accès d'un compte (2026-10-10)

Le dashboard ne revérifie pas Google à chaque requête : un compte désactivé
chez Google reste connecté jusqu'à 1 h (durée de la session). Pour couper
tout de suite : (1) désactiver le compte chez Google ; (2) retirer
l'adresse de `ALLOWED_EMAILS` / `LIMITED_EMAILS` dans les variables Vercel
(`vercel env rm …` puis `vercel env add …`), puis `vercel redeploy <url prod>`
— `middleware.js` revérifie ces listes à chaque requête. Si le token du
back-office a fuité : le renouveler côté BO, puis mettre à jour le secret
GitHub `LEADS_EXTRACT_TOKEN`.

## Déploiement : ce qui est public (2026-10-09)

`vercel.json` a `outputDirectory: "public"`, dossier **généré au build** par
`scripts/fetch-data.sh` (liste blanche de fichiers + copie de `data/`, sans
`data/history` ni `data/kamia`). Les sources restent à la racine pour le dev
local et les tests. `middleware.js` et `api/` restent à la racine (Vercel ne
les détecte qu'à cet endroit) mais ne sont plus servis. Tout nouveau fichier
que le navigateur doit charger doit être ajouté à la liste du `cp` dans
`scripts/fetch-data.sh`, sinon il sera 404 en prod.

## Historique profond (2026-10-09)

`python -m pipeline.history leads|ga4|gsc` (workflow `history.yml`) écrit
dans `data/history/<source>/<site>.csv.gz` du repo de données : leads BO
depuis 2020 (agrégés par jour, sans donnée personnelle), GA4 depuis la
création des propriétés (2022), Search Console 16 mois fusionnés avec
l'existant (à relancer de temps en temps pour archiver). Jamais déployé ni
servi par le dashboard. Pas de GSC pour Spoticar, Stellantis &You, Alfa DE,
DS GB (propriété absente du compte de service) ni Citroën PT (403).

## Thème clair / sombre (2026-10-11)

`html[data-theme="dark"]` applique `filter: invert(.92) hue-rotate(180deg) …`
sur toute la page (un seul jeu de styles à maintenir : les couleurs du code
restent celles du mode clair). Ce qui doit garder ses vraies couleurs est
ré-inversé : `[data-keep]` (logos colorés, en-tête du panneau KamIA),
`[data-fab]` (bouton KamIA), les `iframe`, les orbes (`background:#0c1120`).
Un nouvel élément coloré à préserver = lui ajouter `data-keep`. Choix
Automatique / Clair / Sombre dans l'en-tête, mémorisé dans
`localStorage.psf_theme` ; l'amorce dans `<head>` applique le thème avant le
premier rendu et suit `prefers-color-scheme` en direct.

## Espaces STLA / OEM (2026-10-23)
Après la connexion, une page de choix propose **STLA** (les 91 sites Stellantis, comportement inchangé) et **OEM** (constructeurs hors Stellantis, **Ford seulement** pour l'instant) : `montreChoixEspace` / `choisirEspace` / `changeEspace` dans `index.html` (écran créé à la demande, jamais présent dans le DOM tant qu'il n'est pas utile ; dernier choix mémorisé dans `localStorage.psf_espace`, `?espace=oem` le force ; pastille d'espace dans l'en-tête pour revenir au choix ; profil limité = STLA seulement). Logos des cartes : `logo-espace-stla.png` / `logo-espace-ford.png` (à la racine, dans la liste `cp` de `scripts/fetch-data.sh` : la CSP interdit les images de sites tiers). L'espace OEM n'affiche que GA4 (rail sans Search Console / PageSpeed / KamIA / leads, `isOem`), sans carte « Sessions site de la marque » ni classement du parc (un seul site).
**Collecte** : `pipeline/oem.py` (PAS `build.py`, trop couplé au plan de marquage Stellantis : leads BO, `step_name`, contrôles de structure) avec un **compte de service GA4 distinct** (`ga4-autobiz-master@ga4-master-autobiz.iam.gserviceaccount.com`, secret GitHub `GA4_OEM_SERVICE_ACCOUNT`, variable `GA4_OEM_CREDENTIALS` ou `GOOGLE_APPLICATION_CREDENTIALS_OEM`) -> `oem/<slug>.json` + `oem/index.json` du repo de données (workflow `oem.yml`, chaque nuit 03:45 UTC ; sans secret il s'arrête sans échec). Les fichiers reprennent les clés d'un fichier de site Stellantis (`daily`, `funnelDaily`, `canalQuotidien`, `repriseMonth`, `trafficMonth`) pour réutiliser les écrans GA4 ; `normaliseOem` complète le reste (jamais de donnée inventée). Ajouter un constructeur / un site = une ligne dans `SITES_OEM` + l'accès « Lecteur » du compte de service sur la propriété GA4.
**Ford** : propriété 382291926, hôte de production `www.ford-reprise.fr` seul (les hôtes `ppr-`, `test-`, `stg-oem-site-factory.shakazoola…` sont du bruit de recette). Tunnel (plan de marquage propre, pas de `step_name`) : Visiteurs -> Identification du véhicule (`tunnel_identificationVehicule`) -> État du véhicule (`tunnel_etatVehicule`) -> Projet d'achat (`tunnel_projetAchat`) -> Estimation (`page_estimation`) -> Offre (`tunnel_offer`) ; **la dernière étape (Offre) joue le rôle de « Leads GA »** (choix provisoire, à confirmer ; Estimation en est à 1 % près). Aucun lead back-office ni C1ST pour cet espace. Accès : tous les profils complets (le profil limité ne lit pas `/data/*`). Tests : `tests/e2e/oem.spec.js` (`OEM_CAPTURES=<dossier>` pour sortir des captures clair / sombre) ; `playwright.config.js` précharge `psf_espace=stla` pour les specs existantes.

## Filtre par adresse IP (2026-10-22)
Variable Vercel `ALLOWED_IPS` (adresses séparées par des virgules : IPv4 avec ou sans masque `/24`, IPv6 exacte). **Absente ou vide : filtre inactif.** Renseignée : `middleware.js` répond 403 à toute requête d'une autre adresse, page et scripts compris (le matcher couvre désormais toutes les requêtes ; les règles de session `/api` et `/data` restent celles d'avant, voir `estProtege`). L'adresse est la première valeur de `x-forwarded-for`, que Vercel écrase côté serveur. Conséquences à connaître : les liens de décision de ticket reçus dans Teams (`/api/ticket-decision`) sont aussi bloqués hors de ces adresses ; une adresse qui change (box, 4G, télétravail) ferme l'accès jusqu'à mise à jour de la variable + redéploiement (`vercel env`, puis `vercel redeploy`). Test : `node --test tests/api/ip.test.js`.

## Veille de sécurité (2026-10-22)
`api/auth.js` consigne chaque tentative de connexion (réussie ou refusée : motif, compte, adresse, pays, navigateur) dans `securite/connexions.json` du repo de données PRIVÉ (`api/_lib/journal.js`, 2000 lignes max ; ne bloque jamais la connexion ; retiré du déploiement par `scripts/fetch-data.sh`). `.github/workflows/securite-veille.yml` lance `pipeline/securite_veille.py` : toutes les 30 min une carte Teams seulement si anormal (3 échecs depuis une même adresse, compte non autorisé, première connexion d'un compte, adresse ou pays nouveau pour un compte) ; chaque matin un bilan 24 h. Secrets GitHub : `SECURITE_WEBHOOK_URL` (à défaut `ALERTES_WEBHOOK_URL`) ; facultatif `VERCEL_TOKEN` pour ajouter au bilan le nombre de requêtes traitées par le pare-feu Vercel. Le pare-feu (liste blanche d'adresses, limites de débit) bloque AVANT notre code : ses refus ne sont visibles que dans l'onglet Firewall du projet Vercel. Les journaux publics de l'Action ne montrent que des comptages. Tests : `node --test tests/api/*.test.js`, `python3 -m unittest tests.py.test_securite_veille`.

## Tickets (2026-10-11)

Bouton « Ticket » dans l'en-tête : bug de données, optimisation, question,
avec le contexte (onglet, périmètre, période) joint automatiquement.
`api/tickets.js` stocke dans le repo de données PRIVÉ (`tickets/tickets.json`,
jamais dans ce repo public). Profil complet : voit tous les tickets, change le
statut, commente ; profil limité : crée et ne voit que les siens (la route est
dans `LIMITED_API` de `middleware.js`, les droits sont revérifiés dans le
handler). Limites : 10 tickets / personne / jour, 500 au total. Notification
optionnelle : variable Vercel `TICKETS_WEBHOOK_URL` (webhook Teams, carte
adaptative). Pour traiter les tickets : lire `tickets/tickets.json` dans le repo
de données. Tests : `node --test tests/api/tickets.test.js` (API, sans réseau) et
`tests/e2e/tickets.spec.js` (interface, API simulée).

## Onglet Présentations (2026-10-11)

Mode de saisie du véhicule (`construit.entree_vehicule`, global) : part des leads avec plaque (`leads[mois].entry` des fichiers de site) par marque, en points vs période précédente / N-1 ; le taux de complétion par mode de saisie n'existe pas dans nos données (non affiché). Avant / après V2 par marque (`construit.v2_marque`, module trafic_marque) : utilisateurs par étape (`v2steps`), part de l'accueil, complétion de bout en bout ; seulement pour les marques ayant un site V2 dans le périmètre.

Commentaires et actions (étape 7 du questionnaire) : champs `commentaires` ({clé: texte ≤ 240}, clés fixes de `CLES_COMMENTAIRE` dans `api/presentations.js` + `marque:NOM`) et `actionsMarques` ({MARQUE: [≤ 5 lignes]}). Générateur : `construit.commentaire_diapo` affiche le commentaire sous le titre à droite, une seule fois par clé ; les actions saisies remplacent celles de `analyse.apercu_marque` pour la marque.

Classement des marchés (`construit.classement_marches`) : leads New cars (VN, valides) de tous les marchés autobiz sur la période, rang, part, évolution vs N-1, cumul de l'année ; BE + LU regroupés (BELUX), GB + UK regroupés. Générée dans la vue d'ensemble de toute édition.

Projection du mois (`construit.projection_mois`) : générée dans la vue d'ensemble d'une édition **mensuelle** dont le mois n'est pas terminé ; leads New cars du 1er au dernier jour connu des leads BO, ramenés à la durée du mois au rythme moyen constant (indicatif), comparés au même mois N-1 et au mois précédent. Aucune slide si le mois est terminé.

Vue « Leads overview » (équivalent des diapos 14-15 du deck BELUX T3) : `construit.apercu_marques`, générée dans toute présentation à vue d'ensemble, une ligne par marque (tendance vs périodes de comparaison, part New cars, moteurs par canal / trafic, actions suggérées par règles `analyse.apercu_marque`) ; le champ `actionsMarques` du brief ({MARQUE: [texte]}) remplace les actions calculées.

Icône sous Tableau (profil complet seulement). Questionnaire → **brief** (client,
langue, périmètre pays/marques, trimestre, comparaisons QoQ/YoY, modules, points
ouverts, prochaines étapes, contact) + plan de présentation calculé en direct
(nombre de diapositives). `api/presentations.js` stocke les briefs dans le repo de
données privé (`presentations/briefs.json`) ; la route n'est pas dans `LIMITED_API`.
Périodicité : mois / trimestre / semestre / année (`periode = {type, annee, indice}`) ; modèles enregistrables (`presentations/templates.json`, 3 modèles de base côté interface). Génération : bouton « Générer » → `api/presentations.js` (action `generate`, `GITHUB_TOKEN`) déclenche
`.github/workflows/presentation.yml` → `python -m pipeline.deck --briefs … --id …` (python-pptx, graphiques natifs,
gabarit `pipeline/deck/gabarit_autobiz.pptx`) → `presentations/out/<id>.pptx` dans le repo de données, brief en
`generee`/`echec` ; téléchargement par `GET /api/presentations?fichier=<id>`. Les sources d'acquisition sont
regroupées (`GROUPES_SOURCES` dans `pipeline/deck/donnees.py`), la diapo détaille le regroupement. Tests Python :
`python -m unittest tests.py.test_deck`. Règles de calcul : `docs/presentations-definitions.md`. Tests :
`node --test tests/api/presentations.test.js`, `tests/e2e/presentations.spec.js`.

## GA4 — « Analyses détaillées » : organisation par questions (2026-10-11)

Navigation à deux niveaux, du constat vers l'explication (`GA_THEMES` dans `index.html`) :
**Évolution** « Pourquoi ça bouge ? » (Contribution en cascade · Sessions par canal · Années passées · Événements) ·
**Acquisition** « D'où vient le trafic ? » (Sources · Campagnes · Qualité du trafic) ·
**Conversion** « Où et chez qui convertit-on ? » (Par jour · Fuites du tunnel · Canal × device · Avant / après V2) ·
**Audience** « Qui sont les visiteurs ? » (Jour & navigateurs) · **Pilotage** « Où va-t-on ? » (Alertes · Objectifs, ce dernier réservé au profil complet).
Chaque vue suit le même gabarit : en-tête (icône, titre, info-bulle, sous-titre), visuel qui remplit la carte, bandeau « À retenir » calculé
(`ins*`). La carte a une hauteur minimale commune (`tabMinH`) et les graphiques SVG sont mesurés (`measureBoxes`, ids `cb*`) pour la remplir.
Une nouvelle vue = une entrée dans `GA_THEMES` + `GA_LABELS`, un bloc `<sc-if value="{{ isX }}">`, ses variables dans `renderVals` et son bandeau `ins`.
Données ajoutées aux JSON de site (jamais de lead) : `convCanalDevice[].engagees` (sessions engagées), `utmMonth` (top 20 source/médium × campagne par mois),
`funnelSeg` (entonnoir mensuel par appareil et canal), `histMonth` (totaux mensuels GA4 depuis 2022, dérivés de `data/history` par `pipeline/hist_month.py`).
Les campagnes / sessions engagées se rattrapent par 3 mois anciens et par site à chaque rafraîchissement (`rattrapage` dans `pipeline/build.py`).
Le calendrier d'événements (`api/events.js`, `events/events.json`) pose des repères sur les courbes et alimente l'analyse des présentations ;
les objectifs (`api/objectifs.js`, profil complet) comparent le réalisé, l'attendu à date (saisonnalité N-1) et la projection ; les alertes
(`pipeline/alertes.py`, étape de `refresh.yml`, `api/alertes.js`) sont des règles à seuils réglables, sans IA ; Teams seulement si le secret
`ALERTES_WEBHOOK_URL` existe et que « notifier » est actif. Les dossiers de travail du repo de données (presentations, tickets, events, objectifs,
alertes) ne sont jamais servis en statique (`scripts/fetch-data.sh`).

## Search Console — « Analyses détaillées » (2026-10-11)

Même principe que GA4 (`SX_THEMES` dans `index.html`, 2 niveaux, carte de hauteur commune `tabMinH`, bandeau « À retenir » `insSx*`) :
**Visibilité** « Où apparaît-on ? » (Positions · Appareils · Marque / hors marque) · **Requêtes** « Sur quoi est-on trouvé ? » (Top requêtes · Gagnantes & perdantes ·
Opportunités · Cannibalisation) · **Pages** « Quelles pages performent ? » (Top pages · Pages en déclin · Du clic à l'estimation) · **Technique** (Indexation) ·
**Comparer** (deux périodes, appel en direct). Les listes Requêtes / Pages / Comparer d'avant sont les vues « Top requêtes », « Top pages » et « Deux périodes ».
Données : `searchMonth[mois]` reçoit, pour les 6 derniers mois ENTIERS, `devices`, `positions`, `marque`, `gagnants`, `perdants`, `opps`, `cannib`, `pagesDeclin`
(`pipeline/search_console.py` `analyse_mois`, calculé sur la liste complète des requêtes ; rattrapage de 3 mois par passage et par site). Les instantanés (gagnants,
opportunités…) portent sur le dernier mois analysé de la période. Indexation : `pipeline/indexation.py` (API URL Inspection, 10 pages par site, workflow
`indexation.yml` chaque lundi) -> `indexation.json` du repo de données, servi par `api/indexation.js`.

## Présentations — parcours de création par étapes (2026-10-11)

« Nouveau brief » est un parcours à 6 étapes (`prStepsDef` dans `index.html`) : 1 Choisir un modèle · 2 Cadrage (titre, langue, périmètre et période) · 3 Contenu ·
4 Points ouverts · 5 Prochaines étapes · 6 Contact. Les étapes 1 à 3 sont obligatoires et se débloquent dans l'ordre ; 4 à 6 sont facultatives. Le contenu (étape 3)
est verrouillé par défaut sur les modules recommandés du modèle (`reco`) : « Personnaliser » demande une confirmation, « Revenir au contenu recommandé » restaure.
Une seule action principale à la fois : « Continuer » dans l'étape (plein tant que le brief n'est pas prêt), « Générer le PowerPoint » dans le panneau (actif quand 1 à 3
sont terminées) ; « Enregistrer le brouillon » (= brief, onglet « Mes présentations ») et « Enregistrer comme modèle » sont des actions secondaires expliquées. Le client est
toujours Stellantis (plus de champ). Langues : fr, en, it, es, de — libellés, mois et chiffres traduits (`pipeline/deck/textes.py`, `periodes.py`) ; les analyses rédigées
(`analyse.py`) et quelques phrases de `construit.py` restent en français ou en anglais (repli anglais).


## Tickets : capture de livraison
À chaque livraison d'un ticket, joindre une capture ciblée sur la section livrée (l'élément concerné, jamais l'écran entier) : fichier PNG dans `tickets/captures/<id>-livraison.png` du repo de données, référencé par le champ `image` du commentaire de réponse (servi par `GET /api/tickets?capture=<nom>`, visible par l'auteur et les profils complets, affiché dans le suivi et le modal d'alerte).

## Langue du dashboard (FR / EN)
- Le dashboard est écrit en français ; `i18n.js` traduit à l'exécution (sélecteur FR | EN dans l'en-tête, préférence en localStorage `psf_lang`).
- Dictionnaire : `i18n/en/*.json` ({français: anglais}, valeurs variables `{0}`, `{1}`…) et `i18n/mots.json` (mots / locutions : jours, mois…).
  `python scripts/build-i18n.py` génère `i18n-en.js` (à commiter). `python scripts/i18n-extract.py` liste les textes de `index.html` sans traduction (`i18n/todo.json`).
- **Tout nouveau texte visible doit avoir sa traduction** : ajouter la clé (le texte français exact, ou un motif avec `{0}`) dans un nouveau `i18n/en/NN-*.json`, puis relancer le build. Texte assemblé dans le code (`'médiane '+x`) : utiliser `T('médiane')` (défini en tête de `renderVals`) ; jour ambigu (« Mar ») : `T(x,'jour')`.
- Les noms de sites, requêtes Search Console et contenus saisis ne sont jamais traduits (absents du dictionnaire). Nombres convertis automatiquement (« 27 651 » -> « 27,651 », « 7,1 % » -> « 7.1% ») ; dates restent en jj/mm.
- Test : `tests/e2e/langue.spec.js` (bascule, retour FR identique, aucun accent français résiduel sur la vue GA4 principale).

## AAA Data — marché automobile (2026-10-14)
Onglet « AAA Data » (`source:'aaa'`, profil complet) : lit `data/market.json` du repo de données (servi comme les autres JSON).
Mise à jour : `.github/workflows/market.yml` (cron le 2 et le 25 de chaque mois, ou manuel avec `dry_run`) -> `python -m pipeline.market`.
Un agent Claude Code (abonnement via `CLAUDE_CODE_OAUTH_TOKEN`, pas de clé API ; WebFetch limité au domaine de chaque source) lit le dernier communiqué de AAA Data (FR), ACEA (Europe, cumul annuel),
KBA (DE), UNRAE (IT), ANFAC (ES), SMMT (GB) ; chaque relevé est validé (période, plages, domaine de la source, citation, cohérence avec la série)
avant d'être fusionné ; un relevé refusé laisse la série existante intacte. Les visuels des podiums viennent de domaines listés dans la CSP de `vercel.json`.
Tests : `python -m unittest tests.py.test_market`, `tests/e2e/aaa-data.spec.js`.

## Entrée directe sur la reprise — alignement Looker (2026-10-15)
Vue GA4 > Acquisition > « Arrivées directes » (`entreeMonth`, `ga4.entree_directe_par_canal`, rattrapage `pipeline/backfill_entree.py`).
Règle = champ calculé Looker « Site Marque vs Entrée directe » (`ga4.classe_entree`) sur les sessions dont l'hôte est la reprise et
`page_category` = « home page ». Appliquée telle quelle elle donne +5 % : Looker ne compte pas les lignes dont la page de provenance est le site de
reprise lui-même (sauf source non renseignée). Vérifié sur OPEL FR septembre 2026 : 13 243 sessions des deux côtés, canaux à ±1.
Ne pas y ajouter de proxy : toute évolution se valide contre un tableau Looker.

## In Journey — alignement Looker (2026-10-15)
`In Journey` = sessions du site de reprise (nom d'hôte) dont la catégorie de page (`customEvent:page_category`) est « form page » ou « lead page »
(`ga4.in_journey_par_jour/par_mois`, stocké dans `inJourney` : `daily` + `month`, rattrapage `pipeline/backfill_entree.py`). Vérifié contre Looker :
OPEL FR sept. 2026 = 7 025, CITROEN FR = 38 702 (l'évènement `form_step_view` seul donne 6 922 : ne pas l'utiliser). Carte « Parcours comme Looker » du
tunnel GA4 : Sessions → In Journey → Leads GA ; masquée si un site choisi n'a pas la série (jamais de valeur approchée).

## AAA Data — Portugal (lecture directe) et Pologne (2026-10-15)
Portugal : `pipeline/market_pt.py` lit les fichiers publiés par l'ACAP (xlsx « par Marca » : 74 marques, mois + cumul + part ; pdf « par tipo de energia » : mix du mois et du cumul)
sans agent ni modèle (étape « Collecte directe Portugal » de `market.yml`, `PT` exclu de la consigne de l'agent via `market.DETERMINISTES`). Pologne : agent, sur le texte de Samar / PZPM ;
les classements complets de Samar sont des images, donc seuls le top 5 des marques du cumul, les premiers modèles et le total/BEV/part particuliers-entreprises sont publiés.

## Historique leads — modèles (conquête / fidélité, 2026-10-15)
`data/history/leads_modeles/<site>.csv.gz` (`pipeline/history.py: collecte_leads`) : par mois, leads valides ventilés par marque et modèle repris
(`TRADE-IN BRAND` / `TRADE-IN MODEL`), marque et modèle d'achat (`PURCHASE BRAND` / `PURCHASE MODEL`) et projet. Comptages seulement, aucune donnée personnelle.
Alimente les diapos « Conquest vs loyalty » des présentations (fidèles = marque reprise = marque d'achat, autres Stellantis, concurrents).

## Historique leads — envoyés (périmètre C1ST, 2026-10-15)
`data/history/leads_envoyes/<site>.csv.gz` : par jour, leads ventilés par projet d'achat (`PURCHASE PROJECT`, colonne AX), `LEAD SENT` (colonne BB, YES / NO) et statut.
C1ST ne voit que les leads **envoyés** (BB = YES) et **VN** (AX = VN) : c'est ce filtre, appliqué à l'extract BO (statut valide), qui doit redonner les chiffres de C1ST à un faible écart près.

## C1ST dans les présentations (2026-10-15)
Source : `c1st/kpi.json` du repo de données (totaux par marché, mois et marque, **aucune donnée personnelle**), produit par `pipeline/c1st_collecte.py` (workflow `c1st.yml`, **chaque nuit à 02:30 UTC** : le mois en cours + les 3 précédents (`--courant`), car les commandes sont rattachées au lead jusqu'à 90 jours après ; les jeux C1ST se rechargent dans la journée (04:11 / 07:38 / 11:36 UTC le 15/10/2026), on lit donc l'instantané de la veille ; **le mois de `collecte.date` est partiel** : `Donnees.c1st()` / `c1st_nsc()` ne l'utilisent jamais comme un mois complet). Authentification SANS navigateur : Connected App « Converge C1ST lecture » (OAuth JWT bearer, scopes api + wave_api + refresh_token, ensemble d'autorisations « Converge C1ST API » pré-autorisé pour le compte e121630@mpsa.com.prod, certificat valable jusqu'au 14/10/2028 — à renouveler avant), secrets GitHub `C1ST_CLIENT_ID`, `C1ST_USERNAME`, `C1ST_PRIVATE_KEY`, `C1ST_LOGIN_URL` (en place depuis le 16/10/2026) ; sans secrets le workflow s'arrête en « non configuré » sans échec. Le MCP local `psa-c1st` (`~/psa-c1st-mcp`, lecture seule, agrégats) interroge C1ST avec les mêmes identifiants. Tests : `python -m unittest tests.py.test_c1st_collecte`.
Périmètre « leads VN envoyés vus par C1ST » : type 1, activité VN, campagne Autobiz, nature « 47 » (xP) ou « A68 » (xF) ; **non comparable au back-office** (écarts ≤ 3 % en FR/BE/IT xP, plus larges ailleurs — Opel/Alfa FR, Portugal : laissés tels quels, mention de périmètre sur chaque slide).
`Donnees.c1st(periode, marque)` : jamais de total partiel (un mois manquant => None). Slides `c1st_lead_management` et `c1st_conversion` (global) ; BE et LU comptés ensemble (clé « BE »), DE et LU seul absents de C1ST.

**Précautions C1ST (2026-10-15)** : (1) les taux de contact / traitement reflètent les statuts saisis par les concessionnaires dans C1ST, déployés progressivement selon les marchés (FR : ≈ 0 % jusqu'en juin 2026, 41 % depuis août) : jamais d'évolution calculée dessus, libellé « Non traités » ; (2) les commandes sont rattachées au lead jusqu'à 90 jours après : une période terminée depuis moins de 90 jours est « provisoire », aucune évolution n'est calculée (`Ctx.aujourdhui`). Collecte : `c1st/kpi.json`, 5 marchés (FR, BE+LU, ES, PT, IT) ; DE, PL, AT, LU seul, GB absents de C1ST.

**Traductions (it / es / de)** : `pipeline/deck/traductions.py` traduit, à la fin de la génération, les libellés et phrases anglais des diapositives récentes (libellés exacts, phrases à gabarit `{nom}`, morceaux « vs previous period ») et les noms d'étapes du tunnel (données en français → en/it/es/de). Un texte anglais ajouté dans une fonction de diapositive récente sans traduction fait échouer `tests.py.test_deck.Traductions.test_couverture_des_textes_anglais`. Les textes narratifs d'`analyse.py` (module « Analyse ») restent en anglais pour it / es / de.

**C1ST — Spoticar et ventes additionnelles (2026-10-15)** : Spoticar (code SP, leads de rachat, activité VO) est dans `c1st/kpi.json` mais C1ST n'y suit ni contact, ni traitement, ni commandes : affiché « n.d. » et exclu des totaux (`SANS_SUIVI_C1ST`). Slide `c1st_ventes_additionnelles` (commandes NSC période − même période N-1, cumul de l'année) : lit `nsc` dans `c1st/kpi.json` (jeu SUB) ; inactive si `nsc` manque pour un des mois de la période (définition validée, voir ci-dessous).

**C1ST — commandes NSC validées (2026-10-15)** : `c1st/kpi.json` contient `nsc` (jeu « SUB », commandes rattachées au lead entre 1 et 90 jours, par mois de création du lead, pour FR/BE/ES/PT/IT). **Validé à la décimale près** sur les graphiques « NSC Orders » et « % NSC Orders » de M. (Belgique : Peugeot janv. 2025 177 commandes = 15,2 %) : taux de commande = commandes NSC ÷ clients uniques. `Donnees.c1st()` utilise ces commandes NSC (et non plus le jeu dealer) ; slides « Du lead à la commande » et `c1st_ventes_additionnelles` (commandes NSC période − même période N-1 + cumul de l'année) actives. Piège : un graphique C1ST affiche UN pays (le « # Leads Generated » identifiait la Belgique).

## Onglet C1ST (2026-10-16)
Onglet « C1ST » (`source:'c1st'`, réservé aux adresses de `PRESENTATIONS_EMAILS` comme l'onglet Présentations : cookie `psf_feat=pres` côté interface, et `middleware.js` répond 403 sur `/data/c1st/*` aux autres adresses ; entre Leads et AAA Data) : lit `data/c1st/kpi.json` (voir « C1ST dans les présentations »), jamais de donnée personnelle.
Le **périmètre** suit les sites sélectionnés (marque + pays, LU compté dans BE ; sites hors C1ST — autres pays, Leapmotor, Stellantis &You — signalés, non inclus) ; la **période et la comparaison sont celles du calendrier général** (pas de sélecteur propre : il doublonnait), arrondies aux **mois entiers terminés** disponibles — le mois de `collecte.date` est exclu, la comparaison « précédente » = les mêmes nombres de mois juste avant, « N-1 » = −12 mois, « personnalisée » = mois couverts ; aucune comparaison si les longueurs diffèrent. Seul état propre : `c1Vue` (par marque / par marché).
Mêmes définitions que les présentations : suivi (contactés, dans les délais, traités) en % des clients envoyés, conversion (opportunité, devis, commandes NSC) en % des clients uniques, Spoticar « n.d. » et hors totaux. Règles : **aucune évolution sur les taux de suivi** (statuts saisis par les concessionnaires, déploiement progressif) ; commandes NSC et taux de commande **provisoires** tant que la période de fin n'a pas plus de 90 jours (aucune évolution) ; le **mois de `collecte.date` est partiel** (exclu de la période).
Rapprochement back-office ↔ C1ST : leads BO au projet d'achat VN (`leads[mois].project`) face aux leads C1ST, écart > 5 % signalé (périmètres différents : un signal, pas une erreur ; Opel/Alfa FR et Portugal connus). Logo : celui de Salesforce (C1ST est une application CRM Analytics), PNG 160 px en data URI (constante `c1Logo` dans `renderVals`). Tests : `tests/e2e/c1st.spec.js` ; traductions : `i18n/en/99-quater-c1st.json`.

## Présentations — modules d'après les decks de référence (2026-10-16)
Modules `crm` (C1ST, désormais un vrai module : les 3 slides C1ST n'apparaissent plus que s'il est coché), `ytd` (leads mensuels N vs N-1 par marque), `seo` (Search Console : vue d'ensemble + par marque),
`marche` (leads vs immatriculations de `market.json`) et `objectifs` (objectifs saisis dans le dashboard) : `pipeline/deck/construit.py` (`ytd_marque`, `seo_vue`, `seo_marque`, `marche_pays`, `objectifs_vue`),
données `donnees.py` (`gsc_mensuel`, `gsc_requetes`, `marche_mensuel`, `objectifs`), identifiants dans `MODULES` d'`api/presentations.js` et `PR_MODULES` d'`index.html`. Une section dont les données manquent n'est **pas** créée
(avertissement, jamais de sommaire orphelin). 3 modèles de base ajoutés : Revue mensuelle France, Bilan annuel et plan d'action, Reporting trimestriel pays.
Design des diapositives = deck de référence (`nouvelle_ref`, `boite_pointillee`, `drapeau` dans `graphiques.py`, drapeaux générés par `scripts/make-drapeaux.py` dans `pipeline/deck/drapeaux/`) ; titre Calibri gras 28 pt 043882 sur toutes les slides.
Définitions : `docs/presentations-definitions.md`. Piège traductions : une entrée générique de `PHRASES` peut avaler une phrase plus longue (placer la plus spécifique d'abord) ; `tests/py/test_deck.py::SlidesReference` le détecte.

## Format « revue mensuelle France » (2026-10-16)
Brief avec `format: "revue_fr"` (période mensuelle obligatoire, validé par `api/presentations.js`) : `construit()` délègue à `pipeline/deck/revue_fr.py`, qui reproduit le deck de référence
« Stellantis FR — Trade in review » (73 diapositives) avec les données du mois : couverture, « Ongoing actions » (`actionsEnCours` du brief : sujet, détails, date, pilote, statut en lignes), agenda ×5,
résumé exécutif, vue globale, tendance des leads, trafic et leads par groupe xP / xF, projection du mois en cours, conversion des ventes NSC, puis 6 diapositives par marque
(séparateur, trafic, YTD, leads par canal, leads du site principal, conquête et fidélité), annexe CTA (captures reprises du deck d'origine) et contacts.
Code : `revue_commun.py` (socle : `Revue`, `slide_revue`, encadré de commentaires, `graphique_annuel`), `revue_global.py`, `revue_resultats.py`, `revue_marque.py`, `revue_canaux.py`, `revue_conquete.py`.
Éléments statiques (logos de marque, drapeau, bloc Stellantis, captures de l'annexe, manifeste de positions) : **repo de données privé** `presentations/assets/revue_fr/` (jamais dans ce repo public),
produits par `scripts/extract-revue-assets.py "<deck.pptx>" <dossier>` (recadrage du deck d'origine appliqué). Tout est natif (graphiques / tableaux éditables) ; commentaires de droite calculés par règles, en anglais.
Particularités de données : sessions du « site principal » = `trafficMonth` des fichiers de site (≠ chiffre Looker du deck d'origine, définition GA4 différente) ; groupes de support CTA regroupés par `groupe_support`
(codes tronqués à la collecte : « er-menu » = header-menu…) ; la marque « DS » s'écrit « DS AUTOMOBILES » dans les données de reprise ; le tableau « NC lead by purchase project / trade-in model » filtre `projet_achat = VN`
(`Donnees.modeles(..., projet="VN")`). Test local : `python3 -m pipeline.deck --brief <brief.json> --sortie out.pptx --hist <clone du repo de données>/history` (le clone frais donne aussi site JSON, market.json, c1st, assets).
Génération réelle : brief dans `presentations/briefs.json` du repo de données + workflow `presentation.yml` (GA4 disponible : In Journey / Hot leads).

**Correction C1ST — marchés (2026-10-16)** : contrairement à ce qui est écrit plus haut (« DE, PL, AT, GB absents de C1ST »), le jeu `lead` contient bien des leads Autobiz (type 1, activité VN, natures 47 / A68, 2026 au 15/10) pour **DE (15 067, 14 929 envoyés), PL (2 204), AT (429), GB (83)** en plus de FR, IT, ES, BE, PT (LU est compté dans BE, aucun pays « LU »). Mais le **suivi par les concessionnaires y est quasi inexistant** : contactés DE 2,8 %, AT 6 %, GB 43 % (83 leads), PL 31 % ; FR 15 %, IT 42 %, ES 31 %, BE 21 %, PT 38 %. Notre collecte (`PAYS` dans `pipeline/c1st_collecte.py`) ne couvre que FR, BE, ES, PT, IT : ajouter DE, PL, AT, GB est possible (leads, envoyés), avec « n.d. » ou mise en garde sur les taux de suivi.

## Format « revue trimestrielle pays » (2026-10-16)
Brief avec `format: "revue_trim"` (période **trimestrielle** obligatoire, validé par `api/presentations.js` ; modèle de base « Reporting trimestriel pays » de l'onglet Présentations, contenu fixe) : `construit()` délègue à `pipeline/deck/revue_trim.py`,
qui reproduit le deck de référence « Stellantis Reporting Q3 2026 BE » (76 diapositives) pour tous pays (FR/BE+LU/ES/PT/IT/DE/PL/AT/GB) et toutes les marques cochées, en anglais. Même socle que la revue mensuelle (`revue_commun.py`, `revue_fr.py` : agenda, contacts ; `Revue.trim`,
`court()` et `mois_label()` gèrent le trimestre) ; les modules par marque `revue_marque.trafic`, `revue_canaux.canaux`, `revue_conquete.conquete` sont partagés (titres « Traffic DEEP DIVE » / « LEAD DEEP DIVE » en trimestre, comparaisons QoQ / YoY).
Ordre : couverture, agenda, Global overview, leads par marque (Q vs YoY, Q vs QoQ ; commentaires calculés par règles), par mois (3 ans), NC par mois (global puis xP / xF / autres par 4 marques), projets d'achat xP / xF, trafic et leads, vue d'ensemble par marque
(tendance, moteurs, actions de `analyse.apercu_marque`, `actionsMarques` du brief prioritaire), **Sales performance (C1ST)** : lead management xP / xF, leads VN xP / xF, ventes additionnelles ; deep dive par marque (trafic, canaux, conquête sauf Spoticar / Stellantis &You) ; Open points (`pointsOuverts`), Next steps (`prochainesEtapes`), Q/A, contacts.
Les captures Tableau / C1ST du deck d'origine sont refaites en graphiques et tableaux **natifs** avec les vraies données : C1ST via `d.c1st()` / `d.c1st_nsc()` (mois entier seulement, jamais de proxy, Spoticar exclu, % de commandes = commandes NSC ÷ leads sur les diapos « leads VN », ÷ clients uniques sur « lead management »),
mois sans aucun statut de suivi saisi = non tracé (pas un 0 % réel). « Leads by status » du dashboard C1ST n'existe pas dans nos données : remplacé par les étapes de suivi du trimestre. Une section sans données n'est **pas** créée (avertissement ; sans C1ST complet sur le trimestre pour tous les marchés du périmètre, ni « Sales performance » ni son entrée d'agenda).
Pas d'annexe CTA ni de diapositives de contenu propre à BE (Trade-in POP IN, migration, BMS, RUN topics). Logos / drapeau de couverture / bloc Stellantis : mêmes éléments statiques que la revue FR (`presentations/assets/revue_fr/` du repo de données privé). Tests : `python3 -m unittest tests.py.test_revue_trim`, `node --test tests/api/presentations.test.js`.
Test local : `python3 -m pipeline.deck --brief <brief.json> --sortie out.pptx --hist <clone du repo de données>/history` avec `format:"revue_trim"`, `periode:{type:"trimestre",annee:2026,indice:3}`.

**C1ST — Meetdeal (2026-10-16)** : la campagne « Meetdeal » / « MEETDEAL » (`CampaignIDUSER__c`, France seulement, ~33 400 leads VN depuis janvier 2025, surtout des devis via « 320.Sites Partenaires ») n'est PAS exclue en 2025 pour les marques xP : la règle par source 315/515/311/511 la compte (1 833 leads sur janvier-août 2025 sur 63 156), ce qui redonne à l'unité le tableau « NC Sales Conversion » de référence (63 158). L'exclure ferait −2,9 %. Décision de M. : on garde (alignement sur le deck). En 2026 la règle par campagne Autobiz l'exclut déjà. À revoir seulement si l'équipe confirme que le deck 2025 compte à tort ces leads.

**C1ST — règle de périmètre actuelle (2026-10-16)** : aucun filtre de nature pour les marques standard ; 2026 = campagne AUTOBIZ / Autobiz ; avant 2026, xP = source 315 / 515 / 311 / 511, xF = campagne Autobiz. Commandes NSC cumulées (janvier au mois) collectées à part (`nsc_cumul`, commandes uniques sur la période). Leads par statut : `Status_ProcessLogic` (`statuts` dans `c1st/kpi.json`).

## Code d'accès mensuel C1ST (2026-10-18)
En plus de la session Google et de `PRESENTATIONS_EMAILS`, `/data/c1st/*` exige le cookie `psf_c1st` (`middleware.js`, 403 `c1st_code` sinon) ; l'onglet C1ST affiche la saisie du code. Code **dérivé** (`api/_lib/c1st-acces.js` : HMAC(secret, mois de Paris, révision) → `XXXXX-XXXXX`), il change tout seul le 1er du mois, rien à stocker. Poser le cookie : `POST /api/c1st-acces {code}` (**3 codes faux = adresse suspendue de tout le dashboard** : `c1st/bans.json` du repo de données privé, refus de connexion dans `api/auth.js` et de toute requête dans `middleware.js` (cache 15 s, panne GitHub = dernière valeur connue) ; compteur remis à zéro par un bon code ou après 24 h ; les adresses de `C1ST_ADMIN_EMAILS` ne sont jamais suspendues et réactivent une adresse d'un clic depuis l'encart « Accès C1ST » ; cookie HttpOnly lié à l'adresse + mois + révision, jusqu'à fin de mois). Lire le code du mois : `GET /api/c1st-acces?code=1` pour les adresses de la variable Vercel `C1ST_ADMIN_EMAILS` (jamais dans le repo). **Coupure d'urgence** : bouton « Révoquer tous les accès » de l'onglet C1ST (adresses de `C1ST_ADMIN_EMAILS`, avec confirmation) : nouveau compteur dans `c1st/revision.json` du repo de données privé (lu avec 15 s de cache par les fonctions et le middleware ; illisible = accès refusé) -> nouveau code, tous les cookies invalidés ; la variable `C1ST_CODE_REV` joue le même rôle à la main. Secret : `C1ST_CODE_SECRET`, à défaut `AUTH_COOKIE_SECRET`. Tests : `node --test tests/api/c1st-acces.test.js`, `tests/e2e/c1st.spec.js`.
Verrouillage automatique (2026-10-18) : cookie `psf_c1st` = `t0.ts.hmac` (t0 = saisie du code, ts = dernière activité), valide 5 min après `ts` et 4 h après `t0` (middleware + `api/_lib/c1st-acces.js`, mêmes bornes). Le client (`c1Surveille` dans `index.html`) renouvelle par `PATCH /api/c1st-acces` toutes les minutes tant qu'il y a de l'activité (souris, clavier, défilement) ; après 5 min sans activité il efface `_c1st` / `_c1reseau`, supprime le cookie (`DELETE`) et réaffiche la saisie du code. Bouton « Verrouiller » (plein, à droite du titre C1ST ; bascule immédiate avant l'appel réseau) ; la durée du verrouillage n'est volontairement pas affichée.

## Funnel par mode de saisie du véhicule (2026-10-18)
Vue GA4 « Tunnel de conversion » : pastilles Tous les parcours / Immatriculation / Marque-modèle (`state.funMode`, `agg.funnelEntree`) ; la jauge « Conversion funnel » et son évolution en points suivent le mode (la « Conversion globale », leads GA ÷ sessions, reste tous parcours). Signal GA4 : `virtualpage_url` des évènements du formulaire, `/form/plate/<étape>` (plaque) ou `/form/brand/<étape>` (marque / modèle) ; l'évènement `tradein_request` « price estimation » porte la même URL (OPEL FR sept. 2026 : 3 448 + 141 = 3 589 estimations contre 3 581 au tunnel général ; part marque / modèle 4,3 % contre 4,4 % des leads « Marque / modèle » du back-office). `pipeline/funnel_entree.py` : 2 requêtes GA4 par site pour toute la fenêtre (`build.py`) -> `funnelEntree[AAAA-MM] = {immat:[5], marque_modele:[5]}` (Version, Kilométrage, Coordonnées, Point de vente, Estimation ; visiteurs uniques du mois, mois entiers qui chevauchent la période). L'accueil est commun aux deux parcours : les barres des deux modes partent de « Version ». « Tous » = tunnel général (step_name). Tests : `tests/py/test_funnel_entree.py`, `tests/e2e/funnel-entree.spec.js`.

## Présentations : cloisonnement et dossiers (2026-10-18)
`api/presentations.js` : chacun ne voit, ne modifie, ne génère, ne télécharge et ne supprime que SES présentations (`auteur`) ; les administrateurs (`C1ST_ADMIN_EMAILS`, même liste que l'onglet C1ST) voient et gèrent tout (réponse GET : `admin: true`). Un brief d'un autre = 404 (pas 403 : on n'en révèle pas l'existence), y compris le téléchargement `?fichier=`. Les modèles enregistrés restent communs. « Mes présentations » : dossiers pliables pays > année > période (mois, T1-T4, S1-S2, année complète) ; l'administrateur a un niveau utilisateur en plus et des pastilles de filtre par utilisateur. BE + LU = « BELUX », plusieurs autres pays = « Multi-pays ». Colonne « Plan de la présentation » de même hauteur que celle des étapes. Tests : `tests/api/presentations.test.js`, `tests/e2e/presentations.spec.js`.

## KamIA : vrai agent dans le panneau (2026-10-18)
Le panneau KamIA d'`index.html` (bouton flottant) était une MAQUETTE depuis la restauration du 13/09/2026 (commit 4238e50) : trois conversations factices et une réponse type avec des chiffres figés. Il appelle maintenant le vrai agent : `POST /api/agent` (JSON bufferisé : question, historique renvoyé par l'API, périmètre ≤ 8 sites, vue + période affichées) ; la réponse affiche le texte, les agents consultés (`agentsConsultes`) et les graphiques `show_chart` (`kamChart`). Historique par profil : `GET/PUT /api/kamia-conversations` (liste au premier affichage, conversation chargée au clic, enregistrée après chaque réponse). Pas de repli inventé : une erreur serveur s'affiche telle quelle. Ancienne maquette : `git show 4238e50:index.html`. Clé : `ANTHROPIC_API_KEY` (Vercel) ; l'abonnement Claude ne peut pas servir à une application web multi-utilisateurs (voir la discussion du 18/10). Tests : `tests/e2e/kamia.spec.js`.

**KamIA — chiffres vérifiés (2026-10-18)** : `api/_lib/grounding.js` contrôle chaque nombre de la réponse (hors dates, années, petits comptages) : il doit figurer dans les données lues ou les résultats d'outils de CETTE question, ou se déduire de deux chiffres calculés (somme, différence, rapport, évolution en %). Sinon un seul rappel à l'agent (« recalcule avec les outils ou retire »), puis, s'il persiste, un avertissement honnête dans la réponse (`verifie:false`). `get_series` renvoie une `synthese` calculée par le serveur (total, moyenne, extrêmes, total par mois) : l'agent ne somme jamais lui-même (cas du 18/10 : 1 777 au lieu de 1 908). Pastille « Chiffres vérifiés » dans le panneau. Ne pas mettre de backticks dans le prompt de `api/agent.js` (littéral de gabarit) : `tests/api/agent-charge.test.js` détecte un fichier qui ne se charge plus. Tests : `tests/api/{grounding,agent-controle,tools-synthese}.test.js`.

## Captures d'image des modules (2026-10-18)
`capture.js` (+ `html-to-image.js` MIT et `capture-fonts.js` Poppins OFL, tous trois dans la liste `cp` de `scripts/fetch-data.sh`) : (1) au survol d'un module (carte blanche à bord arrondi, détectée par style CALCULÉ : le texte de l'attribut `style` varie selon le navigateur) une pastille « Copier / PNG » copie l'image dans le presse-papiers (`ClipboardItem` avec promesse, repli en téléchargement) ou la télécharge ; (2) bouton d'export de la vue (en-tête, visible quand les captures sont activées) = mode capture (menu et en-tête masqués par `html.psf-capture`, `Échap` pour sortir) avec « Tout exporter (ZIP) » (une image par module, ZIP sans compression écrit à la main) et « Vue entière (PNG) ». L'image est toujours en thème clair (bascule brève de `data-theme` pendant le rendu), en x2, avec un pied de page : onglet, périmètre, période, comparaison, personne (partie avant @ de l'e-mail) et date. Les logos hébergés ailleurs ne sont pas embarqués (CSP `connect-src 'self'`) : remplacés par un vide. Contexte fourni par `window.psfCaptureCtx` (défini dans `renderVals`). C1ST : seuls les modules affichés (donc déverrouillés) sont capturables. Tests : `tests/e2e/capture.spec.js`.

## Insights du tableau de bord GA4 (2026-10-18)
La carte à droite du tunnel (ex-« KamIA », qui affichait trois règles simples sous un faux « Analyse IA · il y a 4 min ») est une carte « Insights » : `insights.js` (fonction pure, FR/EN, testée par `tests/api/insights.test.js`, dans la liste `cp` de `scripts/fetch-data.sh`) calcule des constats classés par impact en leads, jamais rédigés par un modèle : décomposition de la variation des leads (effet trafic + effet conversion, exacte), conversion à contre-courant, canal moteur, étape du tunnel qui se dégrade vs la période précédente, écart entre appareils, segment canal × appareil à développer, parcours marque / modèle, position vs médiane du parc, rupture de la semaine. Les gains « potentiels » sont des ordres de grandeur prudents (moitié de l'écart, +20 % de volume). Trois insights au plus ; rien d'affiché de significatif = message « Rien d'anormal ». Chaque insight a « Voir le détail » (vue d'analyse liée) et « Creuser avec KamIA » (ouvre le panneau et envoie le constat à l'agent). Calcul dans `renderVals` (`insBrut`, `insRows`) à partir de `agg` / `cmp`. Tests : `tests/e2e/insights.spec.js`.
