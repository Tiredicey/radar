# Radar

Philippine scholarship, education-funding and innovation lead research. This is not a passive-income service. Amounts, eligibility, application windows and awards are not verified personal payouts.

## Implemented

- Hono / Cloudflare Pages dashboard with light/dark themes, mobile layouts, search, category/location/application-wording filters, sorting, lead details, source links, copy-link action and CSV export.
- Collector mode: `publish_dashboard.py` fetches four RSS searches in GitHub Actions and uploads authenticated snapshots to D1. Dashboard visits read those snapshots without direct Cloudflare-to-Google fetching.
- Direct mode, when no valid-length sync secret is configured: visits can check eligible feeds, using a three-hour successful-check cache and a 60-second failed-check retry interval. Prior records survive feed failures.
- Mode-aware Refresh guidance, stale-source labels, singular lead wording and distinct unavailable-data versus zero-match states. Failed reloads retain the last response with an explicit warning. Fresh-source counts exclude snapshots over six hours old.
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

Use Discover to filter leads, review their evidence and visit original sources. Export downloads the current filtered results. Sources & health distinguishes fresh, stale, failed and unchecked sources. Counts describe available snapshots, not all possible opportunities.

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

The dashboard suite needs Chromium and its system dependencies. It uses isolated fixtures and intercepted browser requests, not production feeds or notifications. Parser-only checks: `node --test tests/core.test.js`. Python checks: `python3 -m unittest -v test_promo_engine`.

## Storage and integration

D1 `cache` stores source ID, normalized JSON payload, checked timestamp, success flag and error. `lease` controls concurrent direct checks. Leads retain publisher, publication and collection dates, source URL, explicit amount evidence and classification signals. API results deduplicate IDs and restrict publication age to 30 days.

The importer checks authorization, source allowlist, the 1.5 MB body limit, XML and collection timestamps. Timestamp-guarded writes prevent older or duplicate snapshots from replacing newer ones. Full importer authorization/persistence regression testing remains pending.

| Configuration | Location | Purpose |
| --- | --- | --- |
| `CALLMEBOT_KEY` | GitHub Actions secret | Existing notification monitor |
| `RADAR_SYNC_TOKEN` | GitHub Actions secret | Upload authorization |
| `SYNC_TOKEN` | Cloudflare Pages production secret | Same shared value, at least 32 characters |
| `RADAR_URL` | Publisher environment | `https://radar-1y6.pages.dev` |

The Python monitor keeps separate SQLite `vouchers.db` history through GitHub Actions cache. The inspected workflow includes restore/save, serialized runs, publishing and a silent baseline if no history file is restored. Cache retention is best-effort. The dashboard cannot confirm a run's restore or notification delivery. `workflow-update.patch` is historical; do not apply it over the current workflow.

Prefer the `CALLMEBOT_KEY` environment variable over command-line secrets. `--auto` can send messages; tests do not invoke it. To stop Messenger notifications, send `stop` to CallMeBot. Rotate exposed keys. Reference: https://www.callmebot.com/blog/free-api-facebook-messenger/

## Verification and release

- Repository: https://github.com/Tiredicey/radar, branch `main`. Recovery baseline: `e940764`.
- Production: https://radar-1y6.pages.dev/static/#discover . Hosting remains the user's Cloudflare Pages and D1 configuration. Workflow and backend files are unchanged by this UI update.
- Current local checks: 18 JavaScript cases passed (6 parser, 12 Chromium dashboard), plus 11 Python methods. Vite build passed. Browser checks cover collection modes, freshness counts, missing/failed/empty data, refresh recovery, singular wording, keyboard search/details and absence of the removed attribution.
- No document overflow was observed at 320, 390, 768 and 1280 CSS pixels across Discover, Sources and Guide in light/dark themes using test fixtures. This is not a claim of universal accessibility or complete visual-regression coverage.
- User-provided historical evidence: dashboard output showed 30 leads and 4/4 source checks; run #10 reported gateway acceptance, a later screenshot showed a received message, run #11 saved a silent baseline and run #13 restored cache without sending a new message. This session does not reverify that history or guarantee future delivery.
- Release uses a normal GitHub push through the existing workflow. Push/build success alone does not prove production serves new assets. No notification tests or direct deployment are included in this change.

## Remaining work

1. Importer authorization, validation and persistence regression suite using isolated D1 data.
2. Broader browser coverage: CSV contents, copy-link behavior, screen-reader, contrast and visual-regression checks.
3. Requested legal-research and GIF-discovery modules after source/API verification; neither is implemented here.
4. Private saved leads/application notes remain unimplemented. The dashboard has no accounts, application submission or payment features.
