import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import Json, RealDictCursor


DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg2.connect(DATABASE_URL)


@contextmanager
def db_cursor(dict_cursor=False):
    conn = get_connection()
    cursor_factory = RealDictCursor if dict_cursor else None
    cur = conn.cursor(cursor_factory=cursor_factory)
    try:
        yield conn, cur
        conn.commit()
    finally:
        cur.close()
        conn.close()


def row_to_dict(row):
    return dict(row) if row else None


def init_db():
    with db_cursor() as (_, cur):
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

        cur.execute("CREATE SEQUENCE IF NOT EXISTS user_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS content_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS message_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS comment_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS draft_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS review_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS publication_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS report_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS reaction_human_seq")
        cur.execute("CREATE SEQUENCE IF NOT EXISTS admin_log_human_seq")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                display_name TEXT,
                city TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS internal_id UUID DEFAULT gen_random_uuid()")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS human_id TEXT")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                post_type TEXT,
                category TEXT,
                subcategory TEXT,
                display_name TEXT,
                city TEXT,
                content TEXT,
                telegram_id TEXT,
                hashtags TEXT,
                status TEXT DEFAULT 'pending',
                channel_message_id BIGINT,
                approved_by BIGINT,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS post_type TEXT")
        cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS subcategory TEXT")
        cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS approved_by BIGINT")
        cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP")
        cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS channel_message_id BIGINT")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS content_objects (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                user_telegram_id BIGINT NOT NULL,
                content_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                category TEXT,
                city TEXT,
                title TEXT,
                description TEXT,
                price TEXT,
                media_file_id TEXT,
                media_type TEXT,
                anonymous_author TEXT,
                published_channel_id BIGINT,
                published_message_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS drafts (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                user_telegram_id BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                current_step TEXT,
                payload JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                admin_telegram_id BIGINT,
                action TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS publications (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                channel_id BIGINT NOT NULL,
                channel_message_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                user_telegram_id BIGINT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                admin_telegram_id BIGINT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reactions (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                user_telegram_id BIGINT NOT NULL,
                reaction TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(content_id, user_telegram_id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                content_id UUID REFERENCES content_objects(internal_id),
                user_telegram_id BIGINT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_logs (
                internal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                human_id TEXT UNIQUE NOT NULL,
                admin_telegram_id BIGINT NOT NULL,
                action TEXT NOT NULL,
                object_id TEXT NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def next_human_id(cur, prefix, sequence_name):
    cur.execute("SELECT nextval(%s)", (sequence_name,))
    return f"{prefix}-{cur.fetchone()[0]:06d}"


def get_or_create_user(tg_user):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute("SELECT * FROM users WHERE id = %s", (tg_user.id,))
        row = cur.fetchone()
        if row:
            human_id = row.get("human_id") or next_human_id(cur, "USR", "user_human_seq")
            cur.execute(
                """
                UPDATE users
                SET human_id = COALESCE(human_id, %s),
                    username = %s,
                    first_name = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
                """,
                (human_id, tg_user.username, tg_user.first_name, tg_user.id),
            )
            return row_to_dict(cur.fetchone())

        human_id = next_human_id(cur, "USR", "user_human_seq")
        display_name = tg_user.full_name or tg_user.first_name or "کاربر"
        cur.execute(
            """
            INSERT INTO users (id, human_id, display_name, username, first_name)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (tg_user.id, human_id, display_name, tg_user.username, tg_user.first_name),
        )
        return row_to_dict(cur.fetchone())


def get_user_profile(user_id):
    with db_cursor() as (_, cur):
        cur.execute("SELECT display_name, city FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if row and row[0] and row[1]:
            return row[0], row[1]
        return None


def save_user_profile(user_id, display_name, city, username=None):
    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO users (id, human_id, display_name, city, username)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET human_id = COALESCE(users.human_id, EXCLUDED.human_id),
                display_name = EXCLUDED.display_name,
                city = EXCLUDED.city,
                username = EXCLUDED.username,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, next_human_id(cur, "USR", "user_human_seq"), display_name, city, username),
        )


def create_content(user_id, content_type):
    with db_cursor(dict_cursor=True) as (_, cur):
        prefix = "MSG" if content_type == "hayat" else "CNT"
        human_id = next_human_id(cur, prefix, "message_human_seq" if content_type == "hayat" else "content_human_seq")
        cur.execute(
            """
            INSERT INTO content_objects (human_id, user_telegram_id, content_type, status)
            VALUES (%s, %s, %s, 'draft')
            RETURNING *
            """,
            (human_id, user_id, content_type),
        )
        content = row_to_dict(cur.fetchone())
        draft_id = next_human_id(cur, "DRF", "draft_human_seq")
        cur.execute(
            """
            INSERT INTO drafts (human_id, content_id, user_telegram_id, status, payload)
            VALUES (%s, %s, %s, 'active', '{}'::jsonb)
            """,
            (draft_id, content["internal_id"], user_id),
        )
        return content


def update_content(human_id, **fields):
    allowed = {
        "status",
        "category",
        "city",
        "title",
        "description",
        "price",
        "media_file_id",
        "media_type",
        "anonymous_author",
        "published_channel_id",
        "published_message_id",
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return get_content(human_id)

    assignments = [f"{key} = %s" for key in updates]
    values = list(updates.values())
    values.append(human_id)

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            f"""
            UPDATE content_objects
            SET {", ".join(assignments)}, updated_at = CURRENT_TIMESTAMP
            WHERE human_id = %s
            RETURNING *
            """,
            values,
        )
        return row_to_dict(cur.fetchone())


def update_draft(content_human_id, status=None, current_step=None, payload=None):
    content = get_content(content_human_id)
    if not content:
        return

    fields = []
    values = []
    if status is not None:
        fields.append("status = %s")
        values.append(status)
    if current_step is not None:
        fields.append("current_step = %s")
        values.append(current_step)
    if payload is not None:
        fields.append("payload = %s")
        values.append(Json(payload))

    if not fields:
        return

    values.append(content["internal_id"])
    with db_cursor() as (_, cur):
        cur.execute(
            f"""
            UPDATE drafts
            SET {", ".join(fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE content_id = %s
            """,
            values,
        )


def get_content(human_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute("SELECT * FROM content_objects WHERE human_id = %s", (human_id,))
        return row_to_dict(cur.fetchone())


def list_user_content(user_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT *
            FROM content_objects
            WHERE user_telegram_id = %s
              AND status <> 'deleted'
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_pending_content():
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT *
            FROM content_objects
            WHERE status = 'pending_review'
            ORDER BY updated_at ASC
            LIMIT 20
            """
        )
        return [dict(row) for row in cur.fetchall()]


def submit_for_review(content_human_id):
    content = update_content(content_human_id, status="pending_review")
    update_draft(content_human_id, status="pending_review")
    with db_cursor(dict_cursor=True) as (_, cur):
        review_id = next_human_id(cur, "REV", "review_human_seq")
        cur.execute(
            """
            INSERT INTO reviews (human_id, content_id, action, status)
            VALUES (%s, %s, 'submit', 'pending')
            RETURNING *
            """,
            (review_id, content["internal_id"]),
        )
        return content, row_to_dict(cur.fetchone())


def resolve_review(content_human_id, admin_id, action, reason=None):
    status_by_action = {
        "approve": "published",
        "need_edit": "needs_edit",
        "reject": "rejected",
        "delete": "deleted",
    }
    content_status = status_by_action[action]
    content = update_content(content_human_id, status=content_status)
    if action == "need_edit":
        update_draft(content_human_id, status="needs_edit")
    elif action in ("reject", "delete"):
        update_draft(content_human_id, status=content_status)

    with db_cursor(dict_cursor=True) as (_, cur):
        review_status = "approved" if action == "approve" else action
        cur.execute(
            """
            UPDATE reviews
            SET admin_telegram_id = %s,
                action = %s,
                status = %s,
                reason = %s,
                resolved_at = CURRENT_TIMESTAMP
            WHERE content_id = %s
              AND status = 'pending'
            """,
            (admin_id, action, review_status, reason, content["internal_id"]),
        )
        log_admin_action(admin_id, action, content_human_id, reason, cur=cur)
        return content


def save_publication(content_human_id, channel_id, message_id):
    content = get_content(content_human_id)
    with db_cursor(dict_cursor=True) as (_, cur):
        human_id = next_human_id(cur, "PUB", "publication_human_seq")
        cur.execute(
            """
            INSERT INTO publications (human_id, content_id, channel_id, channel_message_id)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (human_id, content["internal_id"], channel_id, message_id),
        )
        cur.execute(
            """
            UPDATE content_objects
            SET status = 'published',
                published_channel_id = %s,
                published_message_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE internal_id = %s
            """,
            (channel_id, message_id, content["internal_id"]),
        )
        return row_to_dict(cur.fetchone())


def archive_content(content_human_id, user_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE content_objects
            SET status = 'archived', updated_at = CURRENT_TIMESTAMP
            WHERE human_id = %s
              AND user_telegram_id = %s
              AND status IN ('draft', 'needs_edit')
            RETURNING *
            """,
            (content_human_id, user_id),
        )
        return row_to_dict(cur.fetchone())


def create_comment(content_human_id, user_id, body):
    content = get_content(content_human_id)
    with db_cursor(dict_cursor=True) as (_, cur):
        human_id = next_human_id(cur, "COM", "comment_human_seq")
        cur.execute(
            """
            INSERT INTO comments (human_id, content_id, user_telegram_id, body, status)
            VALUES (%s, %s, %s, %s, 'pending')
            RETURNING *
            """,
            (human_id, content["internal_id"], user_id, body),
        )
        comment = row_to_dict(cur.fetchone())
        comment["content_human_id"] = content_human_id
        return comment


def get_comment(human_id):
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT c.*, co.human_id AS content_human_id
            FROM comments c
            JOIN content_objects co ON co.internal_id = c.content_id
            WHERE c.human_id = %s
            """,
            (human_id,),
        )
        return row_to_dict(cur.fetchone())


def resolve_comment(comment_human_id, admin_id, action, reason=None):
    status = "approved" if action == "approve" else "rejected"
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE comments
            SET status = %s,
                admin_telegram_id = %s,
                reason = %s,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE human_id = %s
            RETURNING *
            """,
            (status, admin_id, reason, comment_human_id),
        )
        comment = row_to_dict(cur.fetchone())
        log_admin_action(admin_id, f"comment_{action}", comment_human_id, reason, cur=cur)
        return comment


def list_approved_comments(content_human_id):
    content = get_content(content_human_id)
    if not content:
        return []
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT *
            FROM comments
            WHERE content_id = %s
              AND status = 'approved'
            ORDER BY created_at ASC
            LIMIT 20
            """,
            (content["internal_id"],),
        )
        return [dict(row) for row in cur.fetchall()]


def save_reaction(content_human_id, user_id, reaction):
    content = get_content(content_human_id)
    with db_cursor(dict_cursor=True) as (_, cur):
        human_id = next_human_id(cur, "RCT", "reaction_human_seq")
        cur.execute(
            """
            INSERT INTO reactions (human_id, content_id, user_telegram_id, reaction)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (content_id, user_telegram_id) DO UPDATE
            SET reaction = EXCLUDED.reaction,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (human_id, content["internal_id"], user_id, reaction),
        )
        return row_to_dict(cur.fetchone())


def create_report(content_human_id, user_id, reason):
    content = get_content(content_human_id)
    with db_cursor(dict_cursor=True) as (_, cur):
        human_id = next_human_id(cur, "RPT", "report_human_seq")
        cur.execute(
            """
            INSERT INTO reports (human_id, content_id, user_telegram_id, reason, status)
            VALUES (%s, %s, %s, %s, 'active')
            RETURNING *
            """,
            (human_id, content["internal_id"], user_id, reason),
        )
        return row_to_dict(cur.fetchone())


def list_active_reports():
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT r.*, co.human_id AS content_human_id, co.content_type, co.title
            FROM reports r
            JOIN content_objects co ON co.internal_id = r.content_id
            WHERE r.status = 'active'
            ORDER BY r.created_at ASC
            LIMIT 20
            """
        )
        return [dict(row) for row in cur.fetchall()]


def log_admin_action(admin_id, action, object_id, reason=None, cur=None):
    if cur is not None:
        human_id = next_human_id(cur, "LOG", "admin_log_human_seq")
        cur.execute(
            """
            INSERT INTO admin_logs (human_id, admin_telegram_id, action, object_id, reason)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (human_id, admin_id, action, object_id, reason),
        )
        return

    with db_cursor() as (_, own_cur):
        log_admin_action(admin_id, action, object_id, reason, cur=own_cur)
