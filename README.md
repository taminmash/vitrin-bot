# Vitrin Spain Bot

Railway MVP Telegram bot for Vitrin Spain.

## Active Architecture

- Entrypoint: `bot.py`
- Runtime config: `config_v2.py`
- Database layer: `database/db.py`
- Handlers: `handlers/`
- Railway process: `worker: python bot.py`

## Environment Variables

Set these in Railway or your local shell:

- `BOT_TOKEN`
- `DATABASE_URL`
- `BOT_USERNAME` without `@`, for example `VitrinSpainBot`
- `ADMIN_USER_IDS` comma-separated Telegram numeric IDs, for example `8747305714`
- `VITRIN_CHANNEL_ID`
- `HAYAT_CHANNEL_ID`
- `RADAR_FETCH_INTERVAL_MINUTES` optional; defaults to `15`
- `RADAR_AUTO_INGESTION_ENABLED` optional; defaults to enabled. Use `0`,
  `false`, `no`, or `off` to disable automatic Radar ingestion.
- `RADAR_URGENT_AUTO_PUBLISH_ENABLED` optional; defaults to `false`. Accepted
  true values are `1`, `true`, `yes`, and `on`.
- `RADAR_URGENT_AUTO_PUBLISH_MIN_SCORE` optional; defaults to `90` and is
  clamped to `0` through `100`.
- `RADAR_URGENT_AUTO_PUBLISH_MIN_CONFIDENCE` optional; defaults to `0.90` and
  is clamped to `0.0` through `1.0`.
- `RADAR_URGENT_AUTO_PUBLISH_COOLDOWN_MINUTES` optional; defaults to `30` and
  is clamped to `5` through `1440`.
- `RADAR_URGENT_AUTO_PUBLISH_DAILY_SAFETY_LIMIT` optional; defaults to `10`.
  This emergency flood guard applies only to automatic urgent-alert
  publication and never limits manual admin publication.
- `RADAR_ACTIONABILITY_MIN_SCORE` optional; defaults to `60`. Candidates below
  this actionability score are stored as rejected before AI processing.
- `AI_PROVIDER` optional; `gemini` by default. Allowed values: `gemini`,
  `openai`.
- `GEMINI_API_KEY` required when `AI_PROVIDER=gemini`.
- `GEMINI_MODEL` optional; defaults to `gemini-2.5-flash-lite`.
- `OPENAI_API_KEY` required only when `AI_PROVIDER=openai`.
- `OPENAI_MODEL` optional; defaults to `gpt-4o-mini`.
- `RADAR_AI_BATCH_LIMIT` optional for automatic ingestion; defaults to `1`
  when `AI_PROVIDER=gemini` and `10` when `AI_PROVIDER=openai`. It is clamped
  to `1` through `10`.
- `RADAR_AI_REQUEST_DELAY_SECONDS` optional for automatic ingestion; defaults
  to `15` when `AI_PROVIDER=gemini` and `1` when `AI_PROVIDER=openai`. It is
  clamped to `0` through `60`.
- Job connectors are opt-in via `RADAR_SOURCE_INFOJOBS_ENABLED`,
  `RADAR_SOURCE_MADRID_EMPLEO_ENABLED`, `RADAR_SOURCE_TECNOEMPLEO_ENABLED`, and
  `RADAR_SOURCE_DOMESTIKA_JOBS_ENABLED`. InfoJobs also requires
  `INFOJOBS_CLIENT_ID`/`INFOJOBS_CLIENT_SECRET`; Tecnoempleo requires an
  official feed in `TECNOEMPLEO_RSS_URL`.
- InfoJobs search is configured with `RADAR_INFOJOBS_KEYWORDS` (optional),
  `RADAR_INFOJOBS_PROVINCES` (comma-separated; defaults to Madrid, Barcelona,
  Valencia, Alicante, Málaga, Sevilla, Baleares, Las Palmas, and Santa Cruz de
  Tenerife), `RADAR_INFOJOBS_PAGE_SIZE` (default 20, range 10-50), and
  `RADAR_INFOJOBS_MAX_PAGES_PER_CYCLE` (default 2, range 1-10). Credentials are
  sent only through HTTP Basic authentication and are never put in URLs/logs.
- Per-source schedules use `RADAR_SOURCE_<KEY>_INTERVAL_MINUTES` (minimum 5,
  default 60). Shared bounds: `RADAR_JOB_SOURCE_TIMEOUT_SECONDS` (12),
  `RADAR_JOB_SOURCE_RETRIES` (2), and `RADAR_JOB_SOURCE_MAX_ITEMS` (50,
  maximum 200).
- `RADAR_JOB_STALE_REVIEW_DAYS` defaults to 30. A job without a reliable
  deadline becomes "needs validity review" after this age; it is not falsely
  marked expired. `RADAR_EXPIRED_CHANNEL_EDIT_ENABLED` defaults to `false` and
  enables best-effort editing of already-published expired channel messages.

The bot checks membership through the public channel usernames configured in
`config_v2.py`: `@vitrinspain` and `@hayatkhalvatspain`.

Radar channel publishing uses `VITRIN_CHANNEL_ID`; the bot must be an admin in
that Telegram channel. Channel deep links use this format:

```text
https://t.me/<BOT_USERNAME>?start=radar_<item_id>
```

### Radar publishing policy

The automatic scheduler may fetch, normalize, deduplicate, score, summarize,
classify, store, and queue ordinary Radar content, but it never publishes that
content. News, jobs, discounts, events, legal, transport, economy, education,
ordinary weather, city, family, and travel items always require admin review
and manual publication. Manual publication has no daily or category limit.

Only an item classified exactly as `alert` with urgency `urgent` can enter the
automatic publication safety check. Automatic publication remains off by
default. When enabled, the actionability gate and score, classification
confidence, official active source registry trust, current validity, required
content, URL, duplicate/rejection state, cooldown, daily flood guard, renderer,
and configured Telegram target must all pass. At most one urgent alert is
published per scheduler cycle. Any failed check leaves the candidate in the
existing admin review queue; nothing is silently discarded.

Recommended initial Railway values:

```text
RADAR_AUTO_INGESTION_ENABLED=true
RADAR_URGENT_AUTO_PUBLISH_ENABLED=false
RADAR_URGENT_AUTO_PUBLISH_MIN_SCORE=90
RADAR_URGENT_AUTO_PUBLISH_MIN_CONFIDENCE=0.90
RADAR_URGENT_AUTO_PUBLISH_COOLDOWN_MINUTES=30
RADAR_URGENT_AUTO_PUBLISH_DAILY_SAFETY_LIMIT=10
RADAR_SOURCE_INFOJOBS_ENABLED=false
RADAR_SOURCE_MADRID_EMPLEO_ENABLED=false
RADAR_SOURCE_DOMESTIKA_JOBS_ENABLED=false
RADAR_SOURCE_TECNOEMPLEO_ENABLED=false
RADAR_JOB_STALE_REVIEW_DAYS=30
RADAR_EXPIRED_CHANNEL_EDIT_ENABLED=false
```

## Run Locally

```bash
pip install -r requirements.txt
python bot.py
```

## Deployment

The app uses long polling. Railway only needs the worker process from `Procfile`.
Database tables and additive columns are created on startup by `init_db()`.

## MVP Database Migration

`init_db()` keeps the legacy `posts` table for compatibility and adds the MVP
tables:

- `content_objects`
- `drafts`
- `reviews`
- `publications`
- `comments`
- `reactions`
- `reports`
- `admin_logs`
- `radar_items`
- `source_registry`

The migration is additive and uses UUID internal IDs plus human-readable IDs
such as `USR-000001`, `CNT-000001`, `MSG-000001`, and `COM-000001`.

Radar items are reusable content records linked to `content_objects` through
`radar_items.content_id`, so they can later power the dashboard, city pages,
category pages, personalized feeds, and notifications.

Radar content engine fields are additive:

- `content_status`: `draft`, `ready`, `published`, `expired`
- `channel_status`: `not_sent`, `published`, `failed`
- `channel_message_id`, `channel_published_at`, `last_publish_error`
- `ai_summary`, `ai_reason`, `ai_tags`, `ai_priority`
- `original_text`, `original_language`

`source_registry` stores reusable source metadata for future automation. It is
seeded safely at startup with government, discount, jobs, travel, events, and
weather sources such as BOE, SEPE, Carrefour, InfoJobs, Renfe, Eventbrite, and
AEMET. No scrapers are included yet.

## Radar Spain Smoke Test

To load realistic sample data into a local or test database:

```bash
python scripts/seed_radar_items.py
```

The seed is safe to run more than once. It skips existing Radar items with the
same `title` and `type`.

1. Send `/start` and confirm the Today in Vitrin dashboard appears with the
   Radar button.
2. Tap `📡 رادار اسپانیا`.
3. Tap each Radar category button: urgent, discounts, events, jobs, legal,
   travel, family, weather, transport, economy, education, city, and all.
4. Tap `❤️ ذخیره` and `🔔 یادآوری`; both should show the next-version message.
5. Tap `🏠 بازگشت به خانه` to return to the dashboard.

## Admin Radar Workflow

1. Open `/admin` with an admin user.
2. Tap `➕ محتوای جدید رادار`.
3. Send fields in order: title, type/category, city, short summary, why it
   matters, full body, source name, source URL, start date, end date, urgency,
   and audience tags.
4. Review the channel preview. It is intentionally short: one title line,
   maximum three short reason lines, one bot CTA, and source name.
5. Choose `💾 ذخیره پیش‌نویس`, `✅ آماده انتشار`, or `📤 انتشار در کانال`.

When publishing, the bot sends the short channel version to `VITRIN_CHANNEL_ID`
with an inline `🤖 مشاهده جزئیات در ویترین` button. The button opens the full
Radar item inside the bot through the deep link. Already-published and expired
items are blocked from duplicate publishing.

## Radar Publishing Test Steps

1. Ensure `BOT_TOKEN`, `DATABASE_URL`, `BOT_USERNAME`, `ADMIN_USER_IDS`, and
   `VITRIN_CHANNEL_ID` are configured.
2. Run `python bot.py`.
3. Send `/start` and confirm the Today Dashboard still opens.
4. Open Radar Spain and confirm the existing category flow still works.
5. Start Submit Ad, Hayat Khalvat, and Profile flows to confirm existing
   buttons still open.
6. Send `/admin`, create a Radar item, save it as draft, then create another
   and mark it ready.
7. Publish a ready item to the channel.
8. Confirm the channel post is short and has the bot deep-link button.
9. Tap the channel button and confirm the full Radar item opens in the bot.
10. Try publishing the same item again and confirm duplicate publishing is
    blocked.
11. Create an item with an expired `end_date` and confirm it does not appear in
    active Radar lists and is not publishable.
12. Confirm a non-admin cannot access `/admin` or admin Radar callbacks.

## Radar Limitations

- Source registry is metadata only; no scraping or external AI API is active.
- AI fields are ready for future automation, but formatting currently uses a
  deterministic fallback from `ai_reason` or `summary`.
- Save and reminder buttons in the public Radar item view remain placeholders.
- Dashboard/Radar counts use database values when available and keep graceful
  fallback if the database is unavailable.

## Radar Source Engine

The `radar_engine` package includes the automated BOE ingestion foundation.
On bot startup, the Radar scheduler starts automatically and logs
`Radar scheduler started`. By default it runs every 15 minutes; override this
with `RADAR_FETCH_INTERVAL_MINUTES`.

The first experimental connector is `boe`, which reads BOE's official daily
summary XML endpoint:

```text
https://www.boe.es/boe/dias/YYYY/MM/DD/sumario.xml
```

The connector selects dates using `Europe/Madrid` and looks backward through a
bounded window. Configure the window with `BOE_LOOKBACK_DAYS`; it defaults to
`7` and is clamped to the safe range `1` through `30`. Ordinary dates with no
BOE edition, such as some weekends or holidays, are treated as non-fatal and
the connector checks the next older date. Network errors, rate limits, server
errors, malformed XML, or HTML error pages are treated as source failures.

Raw records are stored in the additive `radar_raw_items` table. The table keeps
the source key, official URL, original Spanish title/text, publication dates,
metadata, a deterministic content hash, and a deduplication key. Re-running the
same source updates `last_seen_at` instead of creating duplicates.

Automatic cycle:

```text
BOE fetch -> deduplicate/store raw -> candidate pipeline -> AI summary -> AI classification -> review queue
```

The scheduler prevents overlapping cycles in two layers:

- an in-process guard logs `Previous fetch cycle still running.`
- a PostgreSQL advisory lock for `radar_scheduler:boe` logs
  `Previous Radar BOE cycle is running in another process.`

The advisory lock uses a dedicated PostgreSQL session and is released in a
`finally` path; no normal row transaction is held open during BOE network calls
or AI processing. BOE or pipeline errors are logged and the scheduler retries on
the next cycle. If BOE fails before fetching any item, downstream candidate, AI,
and classification stages are skipped for that cycle. Nothing is published
automatically.

If a cycle inserts no new raw item, the existing backlog stages may still run:
raw rows already waiting in the database can move through candidate, AI, and
classification processing. The `Queued for review` metric means newly
classification-completed items in that cycle, not the total historical review
queue size.

For Gemini free-tier safety, automatic AI processing is intentionally gradual:
by default one summarization job and one classification job are attempted per
cycle with a 15-second provider-call delay. If Gemini returns a quota/rate-limit
response, the current AI or classification batch stops immediately and the
remaining work stays retryable for the next scheduled cycle.

### Radar job sources

Permitted job feeds normalize into the existing raw-item/candidate pipeline.
Original source identity and URL are retained in provenance. A deterministic
title/employer/location fingerprint merges obvious cross-source duplicates
into the first-seen raw record and appends the additional provenance; records
are never deleted. Existing validation, Actionability Gate, AI,
classification, and admin review remain unchanged.

Empleo Público is enabled by default; the other implemented Job connectors are
opt-in. BOE is temporarily disabled by default but its adapter and historical
data are retained. Enabled sources run during the existing shared Radar cycle,
each with its own interval and failure boundary. A failed connector does not
stop another connector or backlog processing.

| Source | Status | Integration |
| --- | --- | --- |
| InfoJobs | Ready with credentials | Official REST search API |
| Madrid Empleo | Ready | Madrid open-data employment/opposition RSS |
| Tecnoempleo | Ready with feed URL | Official user-configured RSS |
| Domestika Jobs | Ready | Public jobs Atom feed |
| EURES | Blocked | No documented public vacancy retrieval API; partner/PES access required |
| Indeed | Blocked | Job Sync posts ATS jobs; it is not a public vacancy retrieval API |
| LinkedIn Jobs | Blocked | Job APIs require approved partner access; no public search API |
| Barcelona Activa | Blocked | No documented public feed/API; search is a dynamic authenticated app |
| Generalitat/SOC | Blocked | Official listing identified, but no documented stable public vacancy API/feed was verified |
| Empleo Público | Active | Bounded official server-rendered Administracion.gob.es listing; no credentials required |
| 2K Madrid Careers | Active | Public documented Greenhouse Job Board API; Spain vacancies only |
| Keyfactor Spain Careers | Active | Public documented Greenhouse Job Board API; Spain vacancies only |
| Scopely Spain Careers | Active | Public documented Greenhouse Job Board API; Spain vacancies only |

All connectors use public/official API, RSS, Atom, or a stable public listing.
There is no browser automation, CAPTCHA bypass, restricted scraping, or
undocumented endpoint.
The Madrid and Domestika connectors remain disabled until their endpoint can be
smoke-tested from the production network. Tecnoempleo accepts only an
operator-supplied RSS/Atom URL and has no HTML fallback.

### Job date and expiration policy

Source publication/update dates and application deadlines are stored with
their provenance in existing metadata/structured JSON; no schema migration is
required. Date-only deadlines expire at the end of that calendar day in
`Europe/Madrid`, including daylight-saving transitions. A deadline is accepted
only from an explicit source field or deadline-labelled source text. A generic
page publication date is never treated as an application deadline.

The scheduler refreshes at most 200 non-expired jobs per normal cycle, inside
the existing advisory lock. Expired records are retained for history and deep
links continue to display them with an expired notice, but they are rejected
before AI/review eligibility and rechecked immediately before Telegram send.
Stale jobs with unknown deadlines stay stored and reviewable with a warning.
Ordinary jobs are never auto-published.

Controlled smoke test (fetch and normalize only; no database write, AI,
review, promotion, or publication):

```bash
python scripts/run_radar_jobs.py --smoke
python scripts/run_radar_jobs.py --source madrid_empleo --smoke
python scripts/run_radar_jobs.py --source infojobs --smoke
python scripts/run_radar_jobs.py --source domestika_jobs --smoke
python scripts/run_radar_jobs.py --source empleo_publico --smoke
```

Smoke mode reports fetched, normalized, expired/invalid skipped, failures, and
duration per source. It performs no database write, AI request, review,
promotion, Telegram send, or publication. Output samples are sanitized and do
not include credentials or full source payloads.

Without `--smoke`, the command stores raw records only. It never invokes AI or
publication; subsequent processing uses the existing scheduler pipeline.

Manual one-off ingestion:

```bash
python scripts/run_radar_source.py boe
python scripts/run_radar_source.py boe --lookback-days 7
```

Required environment variable:

- `DATABASE_URL`
- `OPENAI_API_KEY` for AI summary/classification during automatic processing
- `RADAR_FETCH_INTERVAL_MINUTES` optional; defaults to `15`
- `RADAR_AUTO_INGESTION_ENABLED` optional; defaults to enabled
- `RADAR_SOURCE_BOE_ENABLED` optional; defaults to disabled
- `RADAR_SOURCE_EMPLEO_PUBLICO_ENABLED` optional; defaults to enabled
- `RADAR_EMPLEO_PUBLICO_MAX_PAGES_PER_CYCLE` optional; defaults to `2`, clamped between `1` and `10`
- `RADAR_SOURCE_2K_MADRID_ENABLED` optional; defaults to enabled
- `RADAR_SOURCE_KEYFACTOR_SPAIN_ENABLED` optional; defaults to enabled
- `RADAR_SOURCE_SCOPELY_SPAIN_ENABLED` optional; defaults to enabled
- `BOE_LOOKBACK_DAYS` optional; defaults to `7`, clamped between `1` and `30`

Known limitations:

- BOE ingestion stores raw Spanish source records before pushing them through
  the existing candidate, AI, classification, and review queue stages.
- It does not mark content as ready or published.
- It does not publish ordinary content automatically. Verified urgent alerts
  may use the separately gated, disabled-by-default exception documented above.
- BOE upstream XML availability or format changes can affect ingestion.

## Radar Candidate Pipeline

The candidate pipeline is the second isolated Radar source stage:

```text
radar_raw_items -> deterministic normalization -> validation -> factual enrichment -> radar_candidates
```

It is rule-based and does not call AI. It does not translate, summarize,
classify final Radar categories, detect audiences, publish content, run on a
cron, run during bot startup, or write to `radar_items`.

Manual one-off processing:

```bash
python scripts/run_radar_pipeline.py
python scripts/run_radar_pipeline.py --limit 50
python scripts/run_radar_pipeline.py --backfill-actionability --limit 200
```

Each normal scheduler cycle performs a bounded FIFO actionability backfill after
new candidate ingestion and before AI loading. It evaluates at most the scheduler
stage limit (50 by default), only for legacy `pending_ai` candidates that do not
already contain `metadata.actionability_gate`. Passed candidates remain eligible
for AI; rejected candidates remain stored with their gate decision and validation
outcome. The explicit command above performs the same safe, idempotent backfill
without AI, review, promotion, publication, or candidate deletion and reports the
evaluated, passed, rejected, and remaining counts.

The default limit is 100 and the maximum accepted limit is 500. Processing reads
raw rows with `ingestion_status = raw`, creates idempotent candidate rows in
`radar_candidates`, and updates raw processing state only after candidate
handling succeeds.

Candidate statuses in this phase:

- `pending_ai`
- `rejected`
- `failed`

Raw processing statuses used by the pipeline:

- `raw`
- `candidate_created`
- `candidate_rejected`
- `candidate_failed`

## Radar AI Structured Extraction

The AI summarization stage is the first optional AI layer after candidate
creation. It reads validated `radar_candidates` with `candidate_status =
pending_ai`, calls the configured AI provider for a structured JSON response,
stores the result in `radar_ai_results`, and leaves candidate status unchanged.
A successful row in
`radar_ai_results` is the completion marker; the unique `candidate_id`
constraint prevents duplicate AI results.

For Job candidates, `visa_sponsorship` uses `YES`, `NO`, or `UNKNOWN`.
`YES` alone is not sufficient for review. The AI must also return a short
verbatim `visa_sponsorship_evidence` excerpt copied from the original candidate
title or body. A deterministic normalization step requires a meaningful
multi-word explicit English/Spanish support statement, matches it against title
or body independently, rejects explicit sponsorship/work-permit denials before
positive matching, and stores the result in structured JSON. Negation is scoped
to the relevant support language, so an unrelated statement such as a role not
being remote does not by itself invalidate explicit sponsorship evidence.
Relocation, English-friendly work, an international company, suitability for
foreigners, applying from abroad, and probable sponsorship do not qualify.

Gemini is the default provider because it supports API-key authentication and
structured JSON output. The default model is Google's stable Flash-Lite model
`gemini-2.5-flash-lite`, suitable for high-frequency lightweight
classification/extraction work. Set `AI_PROVIDER=openai` to use the
OpenAI-compatible provider explicitly; there is no silent fallback between
providers.
Gemini requests use the official `generateContent` REST endpoint with
`generationConfig.responseMimeType=application/json` and
`generationConfig.responseJsonSchema` when a schema is supplied.

Manual one-off processing:

```bash
python scripts/run_radar_ai.py
python scripts/run_radar_ai.py --limit 25
python scripts/run_radar_ai.py --candidate-id <candidate_uuid>
python scripts/run_radar_ai.py --dry-run
python scripts/run_radar_ai.py --check-provider
python scripts/run_radar_ai.py --provider-smoke-test
```

Required environment variable for actual processing:

- `GEMINI_API_KEY` when `AI_PROVIDER=gemini`
- `OPENAI_API_KEY` when `AI_PROVIDER=openai`

Optional:

- `AI_PROVIDER` defaults to `gemini`
- `GEMINI_MODEL` defaults to `gemini-2.5-flash-lite`
- `OPENAI_MODEL` defaults to `gpt-4o-mini`

The prompt version is `radar-structured-v4`. AI extracts the job category,
title, employer, city/region, salary, contract and hours, deadline,
requirements, language and experience levels, visa sponsorship, relocation,
outside-Spain application support, why the item matters, and source URL.
Unavailable fields, including `why_it_matters`, are stored as `null`; the three mobility fields use only
`YES`, `NO`, or `UNKNOWN`. The structured payload is stored in
`radar_ai_results.structured_data` while the existing headline/summary fields
remain populated for backward compatibility with classification and legacy
review flows.

For BOE candidates, this same AI call also stores the complete Persian
translation as `radar_ai_results.structured_data.full_text_fa`. The original
Spanish candidate body remains unchanged and is copied to `radar_items.body`
and `original_text` during promotion. BOE admin/user full-detail views render
the stored Persian field, show a clear Persian "translation not ready" message
when it is missing, and split long translations into ordered Telegram-safe
messages with navigation buttons only on the final message. Opening a detail
view never triggers a new AI request.

Job review and admin preview use a compact structured card and omit unavailable
fields. Legacy pending items without structured data remain reviewable through
a fallback based on their existing AI result, classification, and source. On
promotion, structured data is copied into `radar_items.structured_data`. The
job detail page includes the Vitrin application-help notice; channel posts
explicitly do not include that notice.

This stage does not publish, classify final categories, calculate
urgency/priority, add sources, or write to `radar_items`.

## Radar Admin Review

The admin review stage is the final human review before any future publication
step. It loads candidates that already have successful rows in both
`radar_ai_results` and `radar_ai_classifications`, and have no row yet in
`radar_reviews`.

Non-Job review eligibility is unchanged. Review treats classification, AI
structured category, source category, and candidate content-type metadata as
independent Job signals so a classification error cannot bypass the gate. A Job enters this queue only when
`visa_sponsorship = YES`, evidence is present, and deterministic source matching
succeeded. The evidence excerpt is shown to the admin before a decision. Missing
or unknown mobility values are displayed as `➖ اعلام نشده`, which remains
distinct from the explicit negative `❌ ندارد`. Only verified qualifying Jobs
may display `🔥 فرصت ویزا اسپانسرشیپی`.

Approval does not publish. Approval, promotion to a ready Radar item, and
explicit channel publication remain separate actions. This phase does not add
Opportunity Score thresholds or 60/80 publication rules.

Review decisions are stored independently in `radar_reviews` with one row per
candidate. Allowed statuses are `pending`, `approved`, `rejected`, and
`needs_edit`. A successful review row is the review decision marker.

Manual queue report:

```bash
python scripts/run_review_queue.py
python scripts/run_review_queue.py --limit 50
python scripts/run_review_queue.py --candidate-id <candidate_uuid>
```

This stage does not publish, does not write to `radar_items`, does not modify
`radar_ai_results`, does not modify `radar_ai_classifications`, and does not
change candidate statuses.

## Radar Approved Promotion

The approved promotion stage is a manual bridge from admin review into the
existing Radar publishing workflow. It requires an approved row in
`radar_reviews`, successful AI summary/classification rows, and no existing row
in `radar_promotions`.

Promotion maps the reviewed candidate into the existing `radar_items` schema
with `content_status = ready` and `channel_status = not_sent`. The completion
marker is the independent `radar_promotions` row, which links the candidate,
review, and generated Radar item. Approval and promotion remain separate admin
actions.

Manual one-off processing:

```bash
python scripts/run_radar_promotion.py
python scripts/run_radar_promotion.py --limit 50
python scripts/run_radar_promotion.py --candidate-id <candidate_uuid>
python scripts/run_radar_promotion.py --dry-run
```

This stage does not publish, does not send Telegram channel posts, does not run
on cron, does not run on bot startup, does not modify AI/classification outputs,
does not change review decisions, and does not change candidate status.

## Radar Publication Engine

The publication stage is an explicit, human-triggered send step for promoted
Radar items that are already in `radar_items` with `content_status = ready`,
`channel_status = not_sent`, `is_published = false`, and no Telegram channel
message ID. It reuses the existing channel renderer and inline deep-link button,
then records a successful send in the additive `radar_publications` audit table.

Before any Telegram send, the engine creates a durable row in the additive
`radar_publication_attempts` table. Only one active `sending` attempt is allowed
per Radar item, so concurrent admin clicks or runner processes cannot both send
the same item. Active duplicate attempts return `publication_in_progress`
without calling Telegram.

Duplicate publication is blocked by both the `radar_items` channel message
fields and the unique successful `radar_publications` row. If Telegram returns
an ambiguous timeout after a send attempt, the attempt is marked `ambiguous` and
the item is not marked as a normal failed send. After Telegram success, the
message identifiers are first stored on the attempt as `sent_unpersisted`; only
then does the final `radar_publications` persistence run. If final persistence
fails, use reconciliation after checking the channel manually.

Attempt statuses:

- `sending`
- `sent_unpersisted`
- `completed`
- `failed`
- `ambiguous`

Stale `sending` attempts expire after a conservative window into `ambiguous`.
They are not automatically reclaimed because the worker may have sent the
Telegram message before crashing. `ambiguous` and `sent_unpersisted` attempts
remain non-reclaimable until an admin/operator either reconciles a known channel
message or explicitly confirms that no Telegram message was sent.

Manual one-off commands:

```bash
python scripts/run_radar_publication.py --help
python scripts/run_radar_publication.py --radar-item-id <radar_item_uuid>
python scripts/run_radar_publication.py --publish-ready --confirm-publish --limit 5
python scripts/run_radar_publication.py --publish-ready --dry-run
python scripts/run_radar_publication.py --reconcile --radar-item-id <radar_item_uuid> --telegram-message-id <message_id> --channel-id <channel_id>
python scripts/run_radar_publication.py --release-attempt --radar-item-id <radar_item_uuid> --confirm-not-sent
```

`--release-attempt` never sends Telegram. It is only for manually verified
"not sent" outcomes and rejects `sent_unpersisted` attempts and already
published items.

Required environment variables for real publication:

- `BOT_TOKEN`
- `DATABASE_URL`
- `VITRIN_CHANNEL_ID`

Optional config:

- `CHANNEL_VITRIN_USERNAME` or a public `@channel` value can be configured in
  `config_v2.py` for building public post URLs.

This stage does not run on cron or startup, does not publish automatically after
promotion, does not modify AI/classification/review rows, and does not write to
`radar_items` until a Telegram send succeeds or a definite send failure is
recorded.

## Radar AI Classification

The classification stage runs after successful AI summarization. It reads
`radar_candidates` with `candidate_status = pending_ai` that already have a row
in `radar_ai_results`, classifies them with controlled Radar vocabularies, and
stores the result in `radar_ai_classifications`.

A successful row in `radar_ai_classifications` is the completion marker. The
unique `candidate_id` constraint prevents duplicate classification. This stage
does not update `radar_candidates.candidate_status`, does not modify
`radar_ai_results`, does not publish, does not run on cron/startup, and does not
write to `radar_items`.

Produced fields:

- `primary_category`
- `category_tags`
- `audience_tags`
- `cities`
- `geographic_scope`
- `urgency`
- `priority_score`
- `confidence`
- model/prompt/latency metadata

Manual one-off processing:

```bash
python scripts/run_radar_classification.py
python scripts/run_radar_classification.py --limit 50
python scripts/run_radar_classification.py --candidate-id <candidate_uuid>
python scripts/run_radar_classification.py --dry-run
```

Required environment variable for actual processing:

- `GEMINI_API_KEY` when `AI_PROVIDER=gemini`
- `OPENAI_API_KEY` when `AI_PROVIDER=openai`

Optional:

- `AI_PROVIDER` defaults to `gemini`
- `GEMINI_MODEL` defaults to `gemini-2.5-flash-lite`
- `OPENAI_MODEL` defaults to `gpt-4o-mini`

## Validation

```bash
python -m py_compile bot.py config_v2.py database/db.py handlers/admin.py handlers/home.py handlers/menu.py handlers/post_create.py handlers/profile.py handlers/radar.py handlers/start.py handlers/common.py scripts/seed_radar_items.py scripts/run_radar_source.py scripts/run_radar_pipeline.py scripts/run_radar_ai.py scripts/run_radar_classification.py scripts/run_review_queue.py scripts/run_radar_promotion.py scripts/run_radar_publication.py radar_engine/models.py radar_engine/deduplication.py radar_engine/storage.py radar_engine/source_manager.py radar_engine/scheduler.py radar_engine/taxonomy.py radar_engine/sources/base.py radar_engine/sources/boe.py radar_engine/pipeline/candidate.py radar_engine/pipeline/normalizer.py radar_engine/pipeline/validator.py radar_engine/pipeline/enricher.py radar_engine/pipeline/storage.py radar_engine/pipeline/engine.py radar_engine/ai/prompts.py radar_engine/ai/models.py radar_engine/ai/client.py radar_engine/ai/summarizer.py radar_engine/ai/engine.py radar_engine/ai/storage.py radar_engine/ai/providers/__init__.py radar_engine/ai/providers/base.py radar_engine/ai/providers/gemini.py radar_engine/ai/providers/openai.py radar_engine/classification/prompts.py radar_engine/classification/models.py radar_engine/classification/classifier.py radar_engine/classification/storage.py radar_engine/classification/engine.py radar_engine/review/models.py radar_engine/review/storage.py radar_engine/review/engine.py radar_engine/review/presentation.py radar_engine/promotion/models.py radar_engine/promotion/mapper.py radar_engine/promotion/storage.py radar_engine/promotion/engine.py radar_engine/publication/models.py radar_engine/publication/storage.py radar_engine/publication/publisher.py radar_engine/publication/engine.py
python -m unittest discover -s tests -v
```

## Project Knowledge and Development Rules

The repository maintains its project knowledge in version-controlled documentation. [`AGENTS.md`](AGENTS.md) contains mandatory instructions for Codex and contributors.

- [Project context](PROJECT_CONTEXT.md)
- [Architecture](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Known issues](KNOWN_ISSUES.md)
- [Decisions](DECISIONS.md)
