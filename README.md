# Radar

Philippine scholarship, education-funding and innovation lead research. This is not a passive-income service. Amounts, eligibility, application windows and awards are not verified personal payouts.

## Implemented

- Jurisprudence, Traced: four labeled source directories, local source-specific Google search links, exact-phrase mode, six filterable learning entries, keyboard-expandable source context, research-this-term and clear/reset controls.

- Hono / Cloudflare Pages dashboard with light/dark themes, mobile layouts, search, category/location/application-wording filters, sorting, lead details, source links, copy-link action and CSV export.
- Collector mode: `publish_dashboard.py` fetches four RSS searches in GitHub Actions and uploads authenticated snapshots to D1. Dashboard visits read those snapshots without direct Cloudflare-to-Google fetching.
- Direct mode, when no valid-length sync secret is configured: visits can check eligible feeds, using a three-hour successful-check cache and a 60-second failed-check retry interval. Prior records survive feed failures.
- Mode-aware Refresh guidance, stale-source labels, singular lead wording and distinct unavailable-data versus zero-match states. Failed reloads retain the last response with a warning. Fresh-source counts exclude snapshots over six hours old.
- Original Python CLI and notification monitor retained. Explicit source amounts replace invented estimates; bounded digests preserve complete links and logs withhold credentials. Uncertain notification attempts are held for review; the CLI provides explicit recovery with duplicate risk. Quiet scans can attempt a status message after 24 hours without a gateway attempt.

## Entry points

| Path | Purpose |
| --- | --- |
| `/` | Redirects to dashboard |
| `/static/#discover` | Search and filter collected leads |
| `/static/#sources` | Source health, collection mode and alert-history limits |
| `/static/#guide` | Application-verification guidance |
| `/static/#legal` | Source-linked Philippine legal research and terminology |
| `GET /api/leads` | Public items, source health, stale flags, checking flag and mode |
| `GET /api/health` | D1 schema availability and collectorConfigured flag |
| `POST /api/feeds/:id` | Authenticated RSS upload for dost, ched, dict or local; Bearer token and X-Collected-At epoch milliseconds required |

## User guide

Use Discover to filter leads, review their evidence and visit original sources. Export downloads the current filtered results, including matches beyond the visible page. Sources & health distinguishes fresh, stale, failed and unchecked sources. Counts describe available snapshots, not all possible opportunities.

In collector mode, Refresh reloads the stored snapshot; it does not trigger GitHub Actions. Inspect workflow runs for collection failures. The dashboard does not apply for programs, send payments or trigger notifications.

### Legal research

Enter a topic, case name, docket number or phrase. Typing and preparing links do not submit the query. Opening a search link sends it to Google using `as_sitesearch` and either `as_q` or exact-phrase `as_epq`. Results may be incomplete. Do not enter confidential client or case details. Filter learning entries, expand Source and context, or use Research this term. Clear research resets legal inputs and restores query focus without clearing funding filters.

The directory labels https://elibrary.judiciary.gov.ph/ and https://sc.judiciary.gov.ph/ as official judiciary sources; https://lawphil.net/ and https://www.chanrobles.com/ are nonofficial references. The glossary cites [Lawphil's nonofficial hosting of the 1987 Constitution](https://lawphil.net/consti/cons1987.html) for Article III, Section 1 and Article VIII, Section 1. Ratio decidendi, obiter dictum and dispositive portion cite [Fundamentals of Decision Writing for Judges, Chapter Three](https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/46/63230), an educational handbook, not itself a judicial holding. Excerpts are separate from learning explanations.

The inherited source-check date is 19 September 2026; the handbook publication date is not established. Browser tests verify citation URLs and interface behavior, not external availability or legal authority. No case-specific analysis, subsequent-treatment review or current-controlling-status determination has been completed. This is not legal advice, a case database, a legal-answer engine, a citator or continuous legal verification. Directory and glossary content are static; legal queries are transient browser inputs with no added API or D1 storage.

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

Focused coverage:

```sh
node --test --test-name-pattern='legal|all views' tests/dashboard.test.js
node --test --test-name-pattern='CSV|copy-link' tests/dashboard.test.js
node --test --test-name-pattern='oversized|exact byte limit' tests/importer.test.js
```

The collector suite bundles the actual Hono application using esbuild and runs it inside Miniflare with a separate local D1 database per case. It applies the repository migration, uses a fixture-only token, blocks application outbound fetches and cleans up generated `artifacts/importer-*` directories. Test-only migration/storage inspection and declared-limit routes exist only in the test bundle, not the production source or Vite build. No test reads production secrets or writes production D1.

The test wrapper consumes a clone of each uploaded fixture before invoking the application with the original request. This prevents Miniflare's local HTTP bridge from racing an early rejection against an unfinished upload. It does not change the production importer or return a synthetic rejection. Existing assertions still check HTTP 413 and unchanged D1 records for declared, multibyte and streamed oversized bodies. A separate in-Worker request uses an unreadable stream with zero prefetch to verify that the actual importer rejects oversized Content-Length with HTTP 413 and zero body reads. Buffering is test-only and must not be copied into production; these buffered integration requests do not reproduce production socket timing or backpressure.

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

Prefer the `CALLMEBOT_KEY` environment variable over command-line secrets. `--auto` can send messages. CLI regression tests invoke it with temporary storage and mocked collection/delivery; those tests send no messages. To stop Messenger notifications, send `stop` to CallMeBot. Rotate exposed keys. Reference: https://www.callmebot.com/blog/free-api-facebook-messenger/

## Verification and release

### Legal navigation recovery, 19 September 2026

Recovery began from `9ef049f`. The navigation fix is pushed as `39ff491`; legal browser coverage is pushed as `47258ef`. The body now uses `data-current-view`, distinct from navigation controls' `data-view`; all three legal CSS selectors match. The original duplicate-selector failure was observed before an earlier interruption. At `47258ef`, `npm test` passed all 44 JavaScript cases (6 parser, 23 Chromium dashboard, 15 collector integration) and all 11 Python methods. `npm run build` and `git diff --check` exited successfully. A prior recovery run lacked the Chromium executable and failed; browsers were reinstalled before successful verification.

Four added legal cases cover unique navigation controls, active state, hash changes/reload, hidden funding controls, scholarship-filter preservation, four source labels/URLs, exact-phrase/domain parameters, quote/ampersand/markup-like input without execution, no additional requests during query preparation, six glossary entries, term/description filtering, truthful no-match messaging, keyboard source expansion, citation URLs, research-this-term and clear/reset. The harness serves `legal.js` as JavaScript. No document overflow was observed across all four views, including Legal, at 320, 390, 768 and 1280 CSS pixels in light/dark themes. This does not establish cross-browser, screen-reader or universal accessibility compliance.

Production static verification on 19 September 2026: GitHub's Cloudflare Pages check for `47258ef` reported completed/success. Direct sandbox requests received HTTP 403, but subsequent crawler requests returned HTTP 200 for `/static/`, `/static/app.js`, `/static/style.css` and `/static/legal.js`. The inspected HTML includes the legal module; app code contains `document.body.dataset.currentView=name`, and CSS contains all three `body[data-current-view=legal]` selectors. Only an initial portion of the legal script was returned. Full-file hash equivalence and production browser-interaction success remain unverified. Release uses the existing GitHub-to-Cloudflare integration, not direct deployment. No notifications or production-data test writes were performed.

### Earlier checkpoints and coverage

- Repository: https://github.com/Tiredicey/radar, branch `main`. Dashboard checkpoint: `da48360`. Collector-test checkpoint: `645072d`. CSV/clipboard browser coverage: `ca1eafd`. Collector transport isolation: `079e997`.
- Production: https://radar-1y6.pages.dev/static/#discover . Hosting remains the user's Cloudflare Pages and D1 configuration. The earlier test-only increments changed no application code. The legal navigation increment changes frontend navigation, matching CSS, tests and documentation, not the collector, notification monitor, workflow, dependencies, D1 schema or hosting configuration.
- Historical pre-legal verification: all 40 JavaScript cases passed (6 parser, 19 Chromium dashboard, 15 collector integration), plus all 11 Python methods. Vite build passed.
- Transport diagnosis: the original oversized-body case failed with `write ECONNRESET` in 7 of 8 local runs. A minimal Worker without Hono or D1 returned an immediate 413 for the same 1,500,001-byte upload: the Worker handled all 8 requests, but the client received 3 responses and 5 resets. Consuming a request clone before returning yielded 8 responses and no resets. This isolates a local early-response transport race; it does not identify a specific upstream library defect or establish production behavior.
- After the harness correction, all 8 repeated runs of the three size-boundary cases passed, without retries inside the tests. Two disposable source mutations were detected: raising the limit to 2,000,000 failed the no-read rejection check, and lowering it to 1,499,999 failed exact-limit acceptance. Production source remained unchanged. These observations are bounded local results, not a guarantee against future transport failures.
- Collector checks cover normalized source evidence for all four allowed IDs; missing/wrong/malformed authorization; absent/short configured tokens; unknown IDs; invalid timestamps/XML/entity declarations; declared, streamed and multibyte oversized bodies; early rejection without body reads; exact-size acceptance; duplicate/older/newer and concurrent uploads; persistence across a local runtime restart; fresh/stale collector reads without outbound fetching; and source-isolated empty snapshots. Rejected uploads are checked against the previous stored records. These are local runtime results, not a production security audit.
- Browser checks cover collection modes, freshness counts, unavailable/empty data, refresh recovery, singular wording, keyboard search/details and absence of the removed attribution. No document overflow was observed at 320, 390, 768 and 1280 CSS pixels across Discover, Sources and Guide in light/dark themes using fixtures. This is not a claim of universal accessibility or complete visual-regression coverage.
- Seven added browser cases cover exact filtered CSV membership and newest-first order beyond pagination; Unicode, quotes, commas, LF/CRLF/CR and amount evidence; apostrophe neutralization of tested formula/control prefixes without changing ordinary text; actual clipboard contents for successive selected leads; denied permission with unchanged clipboard and later recovery; missing clipboard API; and waiting for asynchronous completion before success. CSV byte checks do not establish behavior in every spreadsheet application. Clipboard checks do not establish screen-reader announcement or cross-browser support.
- User-provided historical evidence: dashboard output showed 30 leads and 4/4 source checks; run #10 reported gateway acceptance, a later screenshot showed a received message, run #11 saved a silent baseline and run #13 restored cache without sending a new message. This session does not reverify that history or guarantee future delivery.
- Release uses a normal GitHub push through the existing workflow. Push/build success alone does not prove production serves new assets. No notification sends, production-data test writes or direct deployment are included in this test update.

## Remaining work

1. Broader browser coverage: screen-reader behavior, contrast, focus navigation, zoom, long text, reduced motion and visual-regression checks.
2. Publisher-side failure/retry tests and injected D1 storage-error coverage. Local importer tests do not establish end-to-end delivery from scheduled GitHub runners or production upload transport behavior.
3. GIF discovery remains unimplemented. Verify server-side permission, endpoint schemas, pagination, content filters, attribution, caching, advertising/tracking requirements and available credentials before implementation. GIPHY's [API requirements](https://developers.giphy.com/docs/api/), inspected 19 September 2026, prohibit proxying API/media requests and require client-side Search/Trending. Some parameter notes mention proxied requests, but do not establish an exception. Do not implement a server-side GIPHY proxy without provider clarification/approval. KLIPY's verified requirements also require prior written approval for server-side requests/proxying; see below. No provider approval or production GIF key is confirmed. Implementation is blocked, not complete.
4. Private saved leads/application notes remain unimplemented. The dashboard has no accounts, application submission or payment features.


### GIF provider evidence, 19 September 2026

KLIPY's [llms.txt](https://docs.klipy.com/llms.txt), linked from its HTML, exposed usable Markdown documentation. These findings concern published requirements, not live credentialed API tests.

- [Integration requirements](https://docs.klipy.com/integration-requirements.md): standard API requests and media loads must originate at the end-user client. Partner servers, proxies and CDNs require prior written approval from `developers@klipy.com`. Preserve media URLs, delivery/tracking data, returned sequence and composition; use a separate KLIPY result section. Media caching requires approval before development or deployment. This blocks Radar's server-side-only credential design without approval; exposing keys in the browser is not an approved workaround.
- [Search contract](https://docs.klipy.com/gifs-api/gifs-search-api.md): documented GET path `api/v1/{app_key}/gifs/search`; parameters include `page` (minimum/default 1), `per_page` (8 to 50, default 24), `q`, `customer_id`, `locale`, `content_filter` (`off`, `low`, `medium`, `high`) and `format_filter` (`gif`, `webp`, `jpg`, `mp4`, `webm`). The response schema includes `result`, nested `data.data`, `current_page`, `per_page`, `has_next`, and items with ID, slug, title, type and rendition URLs/dimensions/sizes. The fetched [Trending Markdown](https://docs.klipy.com/gifs-api/gifs-trending-api.md) was incomplete; its full contract remains unverified.
- [Attribution](https://docs.klipy.com/attribution.md): requires the search placeholder `Search KLIPY`; shared-card watermark and `Powered by KLIPY` are optional. Provider labels remain part of Radar's requested design. Provider attribution is separate from the removed assistant attribution.
- [Network requirements](https://docs.klipy.com/network-requirements.md): lists `api.klipy.com`, `klipy.com`, `static.klipy.com`, `static1.klipy.com` and `static2.klipy.com` over HTTPS. [Quickstart](https://docs.klipy.com/getting-started.md) states testing keys permit 100 API requests/hour and production access requires a Partner Panel request. Radar's production entitlement is unverified.
- [Content filtering](https://docs.klipy.com/content-filtering.md) identifies Partner Dashboard controls; embedded imagery prevented complete inspection of its categories. Integration requirements prohibit independently filtering returned results. Request-level filtering, moderation, ad/tracking obligations and accessible explicit-playback behavior must be reconciled with the approved integration before implementation.

Next gate: obtain written provider approval for Radar's server-side API requests with keys kept in Cloudflare secrets, then verify remaining Trending/filtering/ad contracts and provision credentials outside chat. No GIF UI, backend route, fake results, Discord scraping, user tokens or private-channel integration has been added.
