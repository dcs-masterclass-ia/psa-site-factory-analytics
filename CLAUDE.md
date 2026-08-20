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
  no framework, no bundler. Reads pre-computed JSON from `data/*.json`.
- **`api/*.js`** (Vercel serverless functions):
  - `auth.js` / `logout.js` — Google Sign-In verification, signs an HMAC
    session cookie (`psf_session`).
  - `config.js` — exposes the OAuth client ID to the client.
  - `agent.js` — "Agent KAM" orchestrator (Claude Sonnet 5, tool-use loop
    over `api/_lib/tools.js`) powering the Hermes/KamIA assistant. Two
    response modes on the same endpoint: default is buffered JSON
    (`{answer, agentsConsultes, charts, history}`, used by the production
    chat in `index.html`, unchanged since before AG-UI work); `?stream=1`
    switches to the real AG-UI protocol (SSE, `RunAgentInput` in →
    `TEXT_MESSAGE_*`/`TOOL_CALL_*`/`RUN_*` events out), consumed only by the
    beta panel below. `ask_agent_dashboard` (auto-edits `index.html` and
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
  - `_lib/` — shared helpers (`anthropic.js`, `auth.js`, `data.js`,
    `github.js`, `google.js`, `tools.js`).
- **`middleware.js`**: Vercel Edge Middleware, the *real* access control.
  Guards `/data/:path*` and the sensitive `/api/*` routes by verifying the
  `psf_session` HMAC cookie — the client-side login screen alone would not
  stop someone from fetching `/data/*.json` directly.
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
`AUTH_COOKIE_SECRET`, `GITHUB_TOKEN`, `OPENAI_API_KEY`/Anthropic key, etc.) —
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
