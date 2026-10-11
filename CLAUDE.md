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
