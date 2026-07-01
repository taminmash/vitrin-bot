# Vitrin Spain Bot

Railway MVP Telegram bot for Vitrin Spain.

## Active Architecture

- Entrypoint: `bot.py`
- Runtime config: `config_v2.py`
- Database layer: `database/db.py`
- Handlers: `handlers/`
- Railway process: `worker: python bot.py`

## Environment Variables

Set these in Railway:

- `BOT_TOKEN`
- `DATABASE_URL`
- `ADMIN_USER_IDS` comma-separated Telegram numeric IDs, for example `8747305714`
- `VITRIN_CHANNEL_ID`
- `HAYAT_CHANNEL_ID`

The bot checks membership through the public channel usernames configured in
`config_v2.py`: `@vitrinspain` and `@hayatkhalvatspain`.

Radar Spain uses the same `BOT_TOKEN` and `DATABASE_URL`; no extra environment
variables are required for the placeholder/demo UX.

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

The migration is additive and uses UUID internal IDs plus human-readable IDs
such as `USR-000001`, `CNT-000001`, `MSG-000001`, and `COM-000001`.
Radar items are reusable content records linked to `content_objects` through
`radar_items.content_id`, so they can later power the dashboard, city pages,
category pages, personalized feeds, and notifications.

## Radar Spain Smoke Test

To load realistic sample data into a local or test database:

```bash
python scripts/seed_radar_items.py
```

The seed is safe to run more than once. It skips existing Radar items with the
same `title` and `type`.

1. Send `/start` and confirm the "Today in Vitrin" dashboard appears with the
   Radar button.
2. Tap `📡 رادار اسپانیا`.
3. Tap each Radar category button: urgent, discounts, events, jobs, legal,
   travel, family, weather, transport, economy, education, city, and all.
4. Tap `❤️ ذخیره` and `🔔 یادآوری`; both should show the next-version message.
5. Tap `🏠 بازگشت به خانه` to return to the dashboard.

## Validation

```bash
python -m py_compile bot.py config_v2.py database/db.py handlers/admin.py handlers/home.py handlers/menu.py handlers/post_create.py handlers/profile.py handlers/radar.py handlers/start.py handlers/common.py
```
