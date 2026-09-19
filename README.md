# Radar

Philippine scholarship, education-funding and innovation lead research. This is not a passive-income service. Amounts, eligibility, application windows and awards are not verified personal payouts.

## Implemented

- Hono / Cloudflare Pages dashboard with light/dark themes, mobile layouts, search, category/location/application-wording filters, sorting, lead details, source links, copy-link action and CSV export.
- Collector mode: `publish_dashboard.py` fetches four RSS searches in GitHub Actions and uploads authenticated snapshots to D1. Dashboard visits read those snapshots without direct Cloudflare-to-Google fetching.
- Direct mode, when no valid-length sync secret is configured: visits can check eligible feeds, using a three-hour successful-check cache and a 60-second failed-check retry interval. Prior records survive feed failures.
- Mode-aware Refresh guidance, stale-source labels, singular lead wording and distinct unavailable-data versus zero-match states. Failed reloads retain the last response with a warning. Fresh-source counts exclude snapshots over six hours old.
- Original Python CLI and notification monitor retained. Explicit source amounts replace invented estimates; bounded digests preserve complete links and logs withhold credentials. Uncertain notification attempts are not retried within that alert-history database.

## Entry points

| Path | Purpose |
| --- | --- |
| `/` | Redirects to dashboard |
| `/static/#discover` | Search and filter collected leads |
| `/static/#sources` | Source health, collection mode and alert-history limits |
| `/static/#guide` | Application-verification guidance |
| `GET /api/leads` | Public items, source health, stale flags, checking flag and mode |
| `GET /api/health` | D1 schema availability and collectorConfigured flag |
| `POST /api/feeds/:id` | Authenticated RSS upload for dost, ched, dict or local; Bearer token and X-Collected-At epoch milliseconds required |

## User guide

Use Discover to filter leads, review their evidence and visit original sources. Export downloads the current filtered results, including matches beyond the visible page. Sources & health distinguishes fresh, stale, failed and unchecked sources. Counts describe available snapshots, not all possible opportunities.

In collector mode, Refresh reloads the stored snapshot; it does not trigger GitHub Actions. Inspect workflow runs for collection failures. The dashboard does not apply for programs, send payments or trigger notifications.

## Local development and tests

```sh
npm ci
npm run build
npm run db:local
pm2 start ecosystem.config.cjs
```

Open `http://localhost:3000`. The migration command applies only to local D1, not production. Local state may disappear after sandbox replacement. Without a local `SYNC_TOKEN`, preview uses direct mode. Do not copy production secrets into tests or commit them.

```sh
npx playwright install --with-deps chromium
npm test
```

The dashboard suite needs Chromium, its system dependencies and Python 3. It uses isolated fixtures and intercepted browser requests, not production feeds or notifications. CSV tests read actual browser downloads and decode them with Python's standard-library CSV parser. Clipboard tests use the real Chromium clipboard for success, permission denial and recovery; separate API-absence and deferred-completion cases use test-only stubs.

Individual suites:

```sh
node --test tests/core.test.js
node --test tests/dashboard.test.js
node --test tests/importer.test.js
python3 -m unittest -v test_promo_engine
```

Focused export and clipboard coverage:

```sh
node --test --test-name-pattern='CSV|copy-link' tests/dashboard.test.js
```

The collector suite bundles the actual Hono application using esbuild and runs it inside Miniflare with a separate local D1 database per case. It applies the repository migration, uses a fixture-only token, blocks application outbound fetches and cleans up generated `artifacts/importer-*` directories. Test-only migration/storage inspection routes exist only in the test bundle, not the production source or Vite build. No test reads production secrets or writes production D1.

The explicit esbuild and Miniflare dev dependencies pin the versions already present in the lockfile. They are test tooling, not new production integrations.

## Storage and integration

D1 `cache` stores source ID, normalized JSON payload, checked timestamp, success flag and error. `lease` controls concurrent direct checks. Leads retain publisher, publication and collection dates, source URL, explicit amount evidence and classification signals. API results deduplicate IDs and restrict publication age to 30 days.

The importer checks authorization, source allowlist, the 1.5 MB body limit, XML and collection timestamps. Timestamp-guarded writes prevent older or duplicate snapshots from replacing newer ones.

| Configuration | Location | Purpose |
| --- | --- | --- |
| `CALLMEBOT_KEY` | GitHub Actions secret | Existing notification monitor |
| `RADAR_SYNC_TOKEN` | GitHub Actions secret | Upload authorization |
| `SYNC_TOKEN` | Cloudflare Pages production secret | Same shared value, at least 32 characters |
| `RADAR_URL` | Publisher environment | `https://radar-1y6.pages.dev` |

The Python monitor keeps separate SQLite `vouchers.db` history through GitHub Actions cache. The inspected workflow includes restore/save, serialized runs, publishing and a silent baseline if no history file is restored. Cache retention is best-effort. The dashboard cannot confirm a run's restore or notification delivery. `workflow-update.patch` is historical; do not apply it over the current workflow.

Prefer the `CALLMEBOT_KEY` environment variable over command-line secrets. `--auto` can send messages; tests do not invoke it. To stop Messenger notifications, send `stop` to CallMeBot. Rotate exposed keys. Reference: https://www.callmebot.com/blog/free-api-facebook-messenger/

## Verification and release

- Repository: https://github.com/Tiredicey/radar, branch `main`. Dashboard checkpoint: `da48360`. Collector-test checkpoint: `645072d`. CSV/clipboard browser coverage: `ca1eafd`.
- Production: https://radar-1y6.pages.dev/static/#discover . Hosting remains the user's Cloudflare Pages and D1 configuration. The browser-test increment changes no application code, workflow, dependencies or hosting configuration.
- Latest local verification after sandbox recovery: all 39 JavaScript cases passed (6 parser, 19 Chromium dashboard, 14 collector integration), plus all 11 Python methods. Vite build passed. No application defect was established by the seven added browser cases, so production code remains unchanged.
- Earlier recovery warning: the unchanged collector oversized-body case failed with `TypeError: fetch failed`, caused by `write ECONNRESET`, at `tests/importer.test.js:86`. It failed in a full run and in focused runs in that sandbox. After a subsequent sandbox recovery, the same focused case and the full suite passed without source changes. The transport-reset cause remains undiagnosed; passing the latest run does not establish that this intermittent failure is fixed. Reproduce with `node --test --test-reporter=spec --test-name-pattern='oversized declared' tests/importer.test.js` if it recurs.
- Collector checks cover normalized source evidence for all four allowed IDs; missing/wrong/malformed authorization; absent/short configured tokens; unknown IDs; invalid timestamps/XML/entity declarations; declared, streamed and multibyte oversized bodies; exact-size acceptance; duplicate/older/newer and concurrent uploads; persistence across a local runtime restart; fresh/stale collector reads without outbound fetching; and source-isolated empty snapshots. Rejected uploads are checked against the previous stored records. These are local runtime results, not a production security audit.
- Browser checks cover collection modes, freshness counts, unavailable/empty data, refresh recovery, singular wording, keyboard search/details and absence of the removed attribution. No document overflow was observed at 320, 390, 768 and 1280 CSS pixels across Discover, Sources and Guide in light/dark themes using fixtures. This is not a claim of universal accessibility or complete visual-regression coverage.
- Seven added browser cases cover exact filtered CSV membership and newest-first order beyond pagination; Unicode, quotes, commas, LF/CRLF/CR and amount evidence; apostrophe neutralization of tested formula/control prefixes without changing ordinary text; actual clipboard contents for successive selected leads; denied permission with unchanged clipboard and later recovery; missing clipboard API; and waiting for asynchronous completion before success. CSV byte checks do not establish behavior in every spreadsheet application. Clipboard checks do not establish screen-reader announcement or cross-browser support.
- User-provided historical evidence: dashboard output showed 30 leads and 4/4 source checks; run #10 reported gateway acceptance, a later screenshot showed a received message, run #11 saved a silent baseline and run #13 restored cache without sending a new message. This session does not reverify that history or guarantee future delivery.
- Release uses a normal GitHub push through the existing workflow. Push/build success alone does not prove production serves new assets. No notification sends, production-data test writes or direct deployment are included in this test update.

## Remaining work

1. Broader browser coverage: screen-reader behavior, contrast, focus navigation, zoom, long text, reduced motion and visual-regression checks.
2. Publisher-side failure/retry tests, injected D1 storage-error coverage and diagnosis of the intermittent collector test transport reset. Local importer tests do not establish end-to-end delivery from scheduled GitHub runners.
3. Requested legal-research and GIF-discovery modules after source/API verification; neither is implemented here.
4. Private saved leads/application notes remain unimplemented. The dashboard has no accounts, application submission or payment features.
