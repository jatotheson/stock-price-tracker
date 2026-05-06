# Stock Comparison Webapp Implementation Tracker

This tracker is the working source of truth for building a public stock comparison webapp where thousands of stocks are available to search, select, and compare on one graph.

## Status Legend

| Status | Meaning |
|---|---|
| TODO | Not started |
| NEXT | Ready to work on |
| DOING | In progress |
| BLOCKED | Needs decision, credential, access, or external action |
| DONE | Implemented and verified |

## Phase 0: Decisions And Boundaries

| ID | Status | Task | Owner | Acceptance Criteria |
|---|---|---|---|---|
| 0.1 | TODO | Confirm public data policy for yfinance/Yahoo data | User | We know whether public redistribution is acceptable |
| 0.2 | TODO | Pick initial public universe size | User | Initial rollout target chosen: 10, 100, 500, etc. |
| 0.3 | TODO | Pick custom domain or GitHub Pages default URL | User | Final public URL strategy chosen |
| 0.4 | TODO | Decide AWS auth style for GitHub Actions | Both | Prefer OIDC; fallback is AWS access-key secrets |

## Phase 1: Static App Shell On GitHub Pages

| ID | Status | Task | Owner | Acceptance Criteria |
|---|---|---|---|---|
| 1.1 | TODO | Split generated dashboard into deployable `_site/index.html` shell | Codex | Site can load without embedded stock data |
| 1.2 | TODO | Add GitHub Pages workflow | Codex | Workflow deploys `_site` via GitHub Actions |
| 1.3 | TODO | Configure repo Pages source to GitHub Actions | User | Pages URL serves the app shell |
| 1.4 | TODO | Add README deployment instructions | Codex | Rebuild/deploy process is documented |
| 1.5 | TODO | Add smoke check for deployed shell | Codex | Workflow verifies `index.html` exists before deploy |

## Phase 2: Public Cloud Data Layer

| ID | Status | Task | Owner | Acceptance Criteria |
|---|---|---|---|---|
| 2.1 | TODO | Add Terraform for public chart artifact S3 bucket | Codex | Bucket exists and is private |
| 2.2 | TODO | Add CloudFront distribution | Codex | Public HTTPS endpoint serves S3 artifacts |
| 2.3 | TODO | Add CloudFront Origin Access Control | Codex | S3 is not directly public |
| 2.4 | TODO | Add CORS policy for GitHub Pages origin | Codex | Browser can fetch data from CloudFront |
| 2.5 | TODO | Add cache policy rules | Codex | Versioned files cache long; manifests cache short |
| 2.6 | TODO | Terraform validate/plan/apply | Both | Infra is deployed successfully |

## Phase 3: Data Artifact Format

| ID | Status | Task | Owner | Acceptance Criteria |
|---|---|---|---|---|
| 3.1 | TODO | Define `manifest.json` schema | Codex | Includes version, base paths, available resolutions, update time |
| 3.2 | TODO | Define `symbols.json` schema | Codex | Search can run without loading price data |
| 3.3 | TODO | Define per-symbol `index.json` schema | Codex | App can discover available chunks for one symbol |
| 3.4 | TODO | Define chunk file schema | Codex | Contains compact timestamp/price arrays |
| 3.5 | TODO | Add artifact versioning under `v1/` | Codex | Future breaking format changes are possible |

## Phase 4: Public Data Builder

| ID | Status | Task | Owner | Acceptance Criteria |
|---|---|---|---|---|
| 4.1 | TODO | Create `scripts/build_public_data.py` | Codex | Reads parquet and writes public JSON artifacts |
| 4.2 | TODO | Generate `symbols.json` from stock universe | Codex | Search metadata exists for all enabled symbols |
| 4.3 | TODO | Generate per-symbol monthly chunks | Codex | Example: `symbol=AAPL/resolution=1m/year=2026/month=05.json` |
| 4.4 | TODO | Generate rollups: `5m`, `15m`, `1h`, `1d` | Codex | Larger date ranges do not require minute data |
| 4.5 | TODO | Generate preset files: `1D`, `1W`, `1M`, `3M`, `6M`, `1Y`, `5Y` | Codex | Popular windows load from small prebuilt files |
| 4.6 | TODO | Upload artifacts to public S3 bucket | Codex | CloudFront can serve generated artifacts |
| 4.7 | TODO | Add artifact size guardrails | Codex | Build fails on oversized chunks/manifests |

## Phase 5: Frontend Lazy Loading

| ID | Status | Task | Owner | Acceptance Criteria |
|---|---|---|---|---|
| 5.1 | TODO | Replace embedded `STOCK_DATA` with async data client | Codex | Initial page loads only manifest and symbols |
| 5.2 | TODO | Implement symbol search from `symbols.json` | Codex | Thousands of symbols searchable without chart data |
| 5.3 | TODO | Implement selected-symbol chunk loading | Codex | Selecting a stock fetches only needed data |
| 5.4 | TODO | Implement free-form date range loading | Codex | User can choose arbitrary start/end dates |
| 5.5 | TODO | Implement preset buttons | Codex | `1D`, `1W`, `1M`, etc. load fast path data |
| 5.6 | TODO | Add in-memory cache for loaded chunks | Codex | Re-selecting same range avoids repeat fetches |
| 5.7 | TODO | Add loading/error/empty states | Codex | UI handles slow or missing data gracefully |

## Phase 6: Ingestion Scale-Up

| ID | Status | Task | Owner | Acceptance Criteria |
|---|---|---|---|---|
| 6.1 | TODO | Expand stock universe config model | Codex | Supports thousands of enabled symbols |
| 6.2 | TODO | Add stock universe validation | Codex | Duplicates/invalid rows fail clearly |
| 6.3 | TODO | Refactor worker to fetch symbols in chunks | Codex | 5,000 symbols do not run as one request |
| 6.4 | TODO | Add retry/backoff per chunk | Codex | Partial failures do not kill the entire run |
| 6.5 | TODO | Write raw parquet partitioned by symbol/date | Codex | Raw data supports efficient artifact builds |
| 6.6 | TODO | Add ingestion summary metrics | Codex | Logs report expected, returned, failed symbols |

## Phase 7: Automation

| ID | Status | Task | Owner | Acceptance Criteria |
|---|---|---|---|---|
| 7.1 | TODO | Keep daily ECS ingestion schedule | Codex | Raw data still lands after market close |
| 7.2 | TODO | Add scheduled public artifact build | Codex | Public data refreshes after raw ingest |
| 7.3 | TODO | Add manual rebuild workflow | Codex | Backfills can regenerate public artifacts |
| 7.4 | TODO | Add deploy ordering checks | Codex | Site shell does not point at missing data version |

## Phase 8: Verification And Rollout

| ID | Status | Task | Owner | Acceptance Criteria |
|---|---|---|---|---|
| 8.1 | TODO | Test with 10 symbols | Codex | Current behavior preserved |
| 8.2 | TODO | Test with 100 symbols | Codex | Search and chart remain responsive |
| 8.3 | TODO | Test with 500 symbols | Codex | Build/upload time acceptable |
| 8.4 | TODO | Test with 1,000 symbols | Codex | CDN/data costs and load times acceptable |
| 8.5 | TODO | Test with 5,000+ symbols | Codex | No full-dataset download; app remains usable |
| 8.6 | TODO | Document operating costs and limits | Codex | README states expected monthly AWS/GitHub usage |

## Recommended Implementation Order

1. Complete Phase 0 decisions that affect architecture or credentials.
2. Complete Phase 1 and Phase 2 to establish the app-shell/data-host split.
3. Complete Phase 3 through Phase 5 to make the frontend cloud-data aware.
4. Complete Phase 6 only after the webapp can consume large data efficiently.
5. Complete Phase 7 to automate refreshes.
6. Complete Phase 8 in stages before enabling the full stock universe.

## Notes

- GitHub Pages should host only the static app shell.
- S3 and CloudFront should host public chart data artifacts.
- The browser should fetch only selected symbols, selected date ranges, and selected resolutions.
- Popular time-window presets should first be implemented as precomputed S3 artifacts behind CloudFront.
- A separate database should be added only if static artifacts cannot satisfy dynamic query needs later.
