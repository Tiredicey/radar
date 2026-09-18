# Radar

Philippine scholarship, education-funding and innovation lead research. This is not a passive-income service. Source amounts, eligibility, application windows and awards are not verified personal payouts.

## Implemented

- Hono / Cloudflare Pages dashboard with light and dark themes, mobile layouts, search, category/location/application-wording filters, sorting, lead details, source links, copy-link action and CSV export.
- Cloudflare D1 caches four RSS searches for three hours, retains previous data on source failure and deduplicates lead IDs. Results display source publication and collection dates.
- Python CLI preserves `--init-db`, `--fetch`, `--list`, `--auto` and `--callmebot-key`. Prefer the `CALLMEBOT_KEY` environment variable to command-line secrets.
- Explicit source amounts replace invented institutional estimates. Application wording ranks ahead of funding news; unrelated industrial-funding examples are excluded by tested relevance rules.
- Notification logs show safe result codes without raw API responses or keys. Bounded digests preserve complete links. Only selected records are marked attempted; uncertain attempts are not retried within that database.

## Entry points

| Path | Purpose |
| --- | --- |
| `/` | Redirects to dashboard |
| `/static/#discover` | Search and filter collected leads |
| `/static/#sources` | Source-health details and scheduler limitations |
| `/static/#guide` | Application-verification guidance |
| `/api/leads` | Public JSON: items, source status, checking flag |
| `/api/health` | D1 schema availability |

## Run locally

```sh
npm ci
npm run build
npm run db:local
pm2 start ecosystem.config.cjs
```

Open `http://localhost:3000`. After a sandbox reset, repeat `npm run db:local`; preview data is local and may not survive sandbox replacement. Production requires a real D1 binding and applied migrations. The `local-radar` ID in `wrangler.jsonc` is for local development, not a provisioned production database.

```sh
npm test
python3 promo_engine.py --init-db --fetch --list
```

The second command collects data but does not send messages. `--auto` sends notifications if configured. To stop receiving Messenger notifications, send `stop` to CallMeBot. Rotate any exposed API key.

## Storage and boundaries

The web app stores public feed snapshots and a sync lease in D1 (`cache`, `lease`). It has no accounts, private saved leads, application submission or payment features. Its request-triggered refresh is not an offline scheduler. The legacy Python CLI uses its existing local `vouchers.db`; this is separate from the dashboard cache.

`workflow-update.patch` contains the proposed GitHub Actions cache/concurrency fix. GitHub refused workflow-file updates because the authorized App lacks `workflows` permission. The patch has NOT been applied to the live workflow. Fresh runners can therefore repeat alerts. After granting permission, review and apply the patch; the first cacheless run establishes a silent baseline. Actions cache is best-effort, not durable financial record storage.

## Verification and deployment status

- `npm test`: six JavaScript test cases and eleven Python test methods passed at source revision `984608c`'s unchanged tested logic. Coverage includes evidence parsing, URL safety, stale/invalid feeds, gateway response classifications and relevance examples.
- Vite build and local D1 migration passed. Local HTTP checks returned real lead data and four successful source checks during this session; counts vary with source responses.
- User-provided Actions run #10 logs reported HTTP 200 and gateway acceptance of a four-lead digest. This is not confirmation of Messenger delivery.
- A browser console check exposed a missing-favicon 503. The route was fixed; a subsequent HTTP check returned 200. Full browser interaction, accessibility and visual-regression suites have not completed and are not claimed as passed.
- Repository: https://github.com/Tiredicey/radar . Production deployment has not been performed. Choose Genspark-hosted Cloudflare or your own Cloudflare account before deploying.

## Remaining work

1. Authorize and apply the scheduler workflow patch; verify history survives a later run.
2. Complete browser interaction, keyboard, contrast, mobile-overflow and failure-path testing.
3. Add a protected private saved-lead workspace if wanted; it is not part of the current read-only dashboard.
4. Configure production D1 and deploy through the selected path.

Reference: https://www.callmebot.com/blog/free-api-facebook-messenger/
