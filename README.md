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

The bot checks membership through the public channel usernames configured in
`config_v2.py`: `@vitrinspain` and `@hayatkhalvatspain`.

Radar channel publishing uses `VITRIN_CHANNEL_ID`; the bot must be an admin in
that Telegram channel. Channel deep links use this format:

```text
https://t.me/<BOT_USERNAME>?start=radar_<item_id>
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
https://www.boe.es/diario_boe/xml.php?id=BOE-S-YYYYMMDD
```

Raw records are stored in the additive `radar_raw_items` table. The table keeps
the source key, official URL, original Spanish title/text, publication dates,
metadata, a deterministic content hash, and a deduplication key. Re-running the
same source updates `last_seen_at` instead of creating duplicates.

Automatic cycle:

```text
BOE fetch -> deduplicate/store raw -> candidate pipeline -> AI summary -> AI classification -> review queue
```

The scheduler prevents overlapping cycles. If a previous cycle is still running,
the next cycle is skipped and logs `Previous fetch cycle still running.` BOE or
pipeline errors are logged and the scheduler retries on the next cycle. Nothing
is published automatically.

Manual one-off ingestion:

```bash
python scripts/run_radar_source.py boe
```

Required environment variable:

- `DATABASE_URL`
- `OPENAI_API_KEY` for AI summary/classification during automatic processing
- `RADAR_FETCH_INTERVAL_MINUTES` optional; defaults to `15`

Known limitations:

- BOE ingestion stores raw Spanish source records before pushing them through
  the existing candidate, AI, classification, and review queue stages.
- It does not mark content as ready or published.
- It does not publish to Telegram automatically.
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
```

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

## Radar AI Summarization

The AI summarization stage is the first optional AI layer after candidate
creation. It reads validated `radar_candidates` with `candidate_status =
pending_ai`, calls OpenAI for a structured JSON response, stores the result in
`radar_ai_results`, and leaves candidate status unchanged. A successful row in
`radar_ai_results` is the completion marker; the unique `candidate_id`
constraint prevents duplicate AI results.

Manual one-off processing:

```bash
python scripts/run_radar_ai.py
python scripts/run_radar_ai.py --limit 25
python scripts/run_radar_ai.py --candidate-id <candidate_uuid>
python scripts/run_radar_ai.py --dry-run
```

Required environment variable for actual processing:

- `OPENAI_API_KEY`

Optional:

- `OPENAI_MODEL` defaults to `gpt-4o-mini`

The prompt version is `radar-summary-v1`. The AI output is limited to:

- `headline`
- `short_summary`
- `why_it_matters`
- `confidence`
- model/prompt/latency metadata

This stage does not publish, translate, classify final categories, detect
audiences or cities, calculate urgency/priority, add tags, run on cron, run
during bot startup, modify Telegram handlers, or write to `radar_items`.

## Radar Admin Review

The admin review stage is the final human review before any future publication
step. It loads candidates that already have successful rows in both
`radar_ai_results` and `radar_ai_classifications`, and have no row yet in
`radar_reviews`.

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

- `OPENAI_API_KEY`

Optional:

- `OPENAI_MODEL` defaults to `gpt-4o-mini`

## Validation

```bash
python -m py_compile bot.py config_v2.py database/db.py handlers/admin.py handlers/home.py handlers/menu.py handlers/post_create.py handlers/profile.py handlers/radar.py handlers/start.py handlers/common.py scripts/seed_radar_items.py scripts/run_radar_source.py scripts/run_radar_pipeline.py scripts/run_radar_ai.py scripts/run_radar_classification.py scripts/run_review_queue.py scripts/run_radar_promotion.py scripts/run_radar_publication.py radar_engine/models.py radar_engine/deduplication.py radar_engine/storage.py radar_engine/source_manager.py radar_engine/scheduler.py radar_engine/taxonomy.py radar_engine/sources/base.py radar_engine/sources/boe.py radar_engine/pipeline/candidate.py radar_engine/pipeline/normalizer.py radar_engine/pipeline/validator.py radar_engine/pipeline/enricher.py radar_engine/pipeline/storage.py radar_engine/pipeline/engine.py radar_engine/ai/prompts.py radar_engine/ai/models.py radar_engine/ai/client.py radar_engine/ai/summarizer.py radar_engine/ai/engine.py radar_engine/ai/storage.py radar_engine/classification/prompts.py radar_engine/classification/models.py radar_engine/classification/classifier.py radar_engine/classification/storage.py radar_engine/classification/engine.py radar_engine/review/models.py radar_engine/review/storage.py radar_engine/review/engine.py radar_engine/review/presentation.py radar_engine/promotion/models.py radar_engine/promotion/mapper.py radar_engine/promotion/storage.py radar_engine/promotion/engine.py radar_engine/publication/models.py radar_engine/publication/storage.py radar_engine/publication/publisher.py radar_engine/publication/engine.py
python -m unittest discover -s tests -v
```
