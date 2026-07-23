# Architecture

## Runtime Entrypoint

`bot.py` validates `BOT_TOKEN`, calls `database.db.init_db()`, constructs the Telegram application, registers handlers, starts the Radar scheduler through application lifecycle hooks, and runs long polling. Railway runs this entrypoint through `Procfile`.

## Telegram Handler Architecture

Handlers are organized by user surface in `handlers/`: start/home/menu/profile, post creation, Radar, admin operations, and language lessons. `bot.py` registers command, callback-query, and message handlers with explicit callback prefixes (for example `radar:`, `admin_radar:`, `lesson:`). Callback formats are compatibility-sensitive.

## Database Layer

`database/db.py` owns PostgreSQL connections and `init_db()`. Startup schema work is additive and retains legacy tables. Radar uses raw items, candidates, AI results, classifications, reviews, promotions, publications, publication attempts, reactions, and the source registry alongside reusable `radar_items`/content records.

## Radar Scheduler

`RadarBOEIngestionScheduler` runs from bot startup unless `RADAR_AUTO_INGESTION_ENABLED` disables it. It prevents overlap with both an in-process guard and a PostgreSQL advisory lock, then performs expiration refresh, ingestion, candidate processing, actionability backfill, AI work, classification, urgent-alert checks, and review notifications. Failures are logged and isolated so a later cycle can retry eligible work.

## Source Manager

`SourceManager` registers sources, fetches records, normalizes each record, and stores raw items. A source failure is collected in an `IngestionReport`; it does not crash unrelated source or later-cycle work.

## Source Adapters

`radar_engine/sources/boe.py` consumes BOE’s official daily-summary XML. `radar_engine/sources/jobs.py` contains opt-in adapters for InfoJobs, Madrid Empleo, Domestika Jobs, and an operator-configured Tecnoempleo RSS/Atom feed. `source_config.py` documents blocked integrations and deliberately excludes HTML scraping, browser automation, CAPTCHA bypass, and undocumented endpoints.

## Raw Item Storage

Normalized source records are persisted in `radar_raw_items` through `radar_engine/storage.py`. Deterministic hashes/deduplication keys avoid duplicate raw rows while retaining provenance and updating last-seen data. Job-source matching can append provenance rather than delete records.

## Candidate Pipeline

`RadarCandidatePipeline` loads raw rows in `raw` state, normalizes, enriches, validates, evaluates actionability, and creates or rejects `radar_candidates`. It marks raw processing state only after candidate handling. **Known-bug marker:** production reported that job raw rows were inserted while later candidate metrics were zero; repository code does not establish the cause. See `KNOWN_ISSUES.md` KIB-001.

## Actionability Gate

The deterministic Actionability Gate scores practical impact and rejects expired, low-impact, or below-threshold candidates before AI/review eligibility. Its result is stored in candidate metadata; actionability backfill evaluates eligible legacy pending candidates idempotently.

## AI Summary and Classification

`RadarAIEngine` loads pending candidates and persists structured summary/extraction results in `radar_ai_results`. `RadarClassificationEngine` then writes controlled-vocabulary results to `radar_ai_classifications`. Gemini is the default provider; OpenAI is explicit configuration. Both stages are bounded and retryable; provider quota/rate-limit handling stops the current batch rather than discarding remaining work.

For BOE candidates, the same AI summary call also produces `structured_data.full_text_fa`, a complete Persian translation of the original Spanish body. Pending-review BOE candidates whose existing AI result predates this field are eligible for an idempotent AI refresh. Promotion copies structured data forward while preserving the Spanish candidate body and `original_text`. BOE review/detail renderers use only the stored Persian field, fall back explicitly when it is missing, and split long Telegram output with navigation controls on the final message.

## Structured Job Extraction

The summary prompt extracts job-specific fields (such as title, employer, location, deadline, requirements, and mobility-related fields) into structured JSON. Visa sponsorship also requires a short verbatim `visa_sponsorship_evidence` excerpt. After extraction, a deterministic helper normalizes whitespace/case and records verification only when a `YES` excerpt is found directly in the original candidate title/body. Promotion copies structured data additively into `radar_items.structured_data`; no dedicated schema or parallel Job pipeline is used.

## Review Queue

The review engine loads candidates with successful summary and classification records and no review decision. Non-Job behavior is unchanged. A Job is eligible only when sponsorship is `YES`, evidence is present, and deterministic source matching succeeded; mobility or audience signals never substitute for this requirement. The same predicate is used by list, candidate-specific, and pending-count queries. Admin Review displays the source evidence and stores independent `pending`, `approved`, `rejected`, or `needs_edit` decisions in `radar_reviews`. Admin callbacks remain bounded and compatibility-sensitive.

## Admin Notifications

The scheduler’s `RadarReviewNotifier` batches pending-review notifications and retries partial notification delivery. A failure to notify an admin is logged without undoing the queued item.

## Approval Lifecycle

Approval does not publish. `RadarPromotionEngine` is the manual bridge: it accepts approved, unpromoted candidates and creates ready `radar_items` plus an independent `radar_promotions` record.

## Publishing Lifecycle

Explicit admin publication or `run_radar_publication.py` sends only ready, unsent Radar items. The publication engine claims a durable attempt, calls the Telegram publisher, persists success/failure/ambiguous state, and blocks duplicates. **Known-bug marker:** an approved item was production-reported to yield a generic Telegram error in the ready-for-publication queue; root cause is not established. See KIB-002.

## Error Isolation and Retries

Source normalization/storage errors are per item; connector failures are per source; scheduler stage errors are logged into reports. Advisory locking prevents overlapping scheduler cycles. AI quota/errors leave later candidates retryable. Publication treats ambiguous sends conservatively and requires reconciliation rather than unsafe automatic retry.

## Deduplication

Raw storage uses deterministic keys/content hashes. Job normalization uses title/employer/location fingerprints for obvious cross-source matches. Candidate, AI, classification, review, promotion, and publication tables each use their own completion markers/unique constraints to make retries idempotent.

## Backward Compatibility

Schema initialization and Radar extensions are additive. Legacy `posts` remain supported, legacy pending review data has fallbacks, and existing callback prefixes are registered explicitly. Changes must preserve these contracts or provide compatible migration behavior.

## Radar pipeline

```text
fetch
→ normalize
→ raw storage
→ candidate creation [KIB-001: production-reported progression gap; cause unconfirmed]
→ actionability
→ AI summary
→ AI classification
→ review queue
→ admin approval
→ ready for publication
→ channel publication [KIB-002: production-reported generic Telegram error; cause unconfirmed]
```
