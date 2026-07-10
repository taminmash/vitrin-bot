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

## Validation

```bash
python -m py_compile bot.py config_v2.py database/db.py handlers/admin.py handlers/home.py handlers/menu.py handlers/post_create.py handlers/profile.py handlers/radar.py handlers/start.py handlers/common.py scripts/seed_radar_items.py
```
