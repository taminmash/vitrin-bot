import os

import psycopg2
from psycopg2.extras import RealDictCursor


DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

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

    conn.commit()
    cur.close()
    conn.close()


def save_post(
    user_id,
    category,
    subcategory,
    city,
    display_name,
    telegram_id,
    content,
    post_type="vitrin",
):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO posts (
            user_id,
            post_type,
            category,
            subcategory,
            city,
            display_name,
            telegram_id,
            content,
            status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        RETURNING id
        """,
        (
            user_id,
            post_type,
            category,
            subcategory,
            city,
            display_name,
            telegram_id,
            content,
        ),
    )
    post_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return post_id


def get_post(post_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT
            id,
            user_id,
            post_type,
            category,
            subcategory,
            city,
            display_name,
            telegram_id,
            content,
            status,
            channel_message_id
        FROM posts
        WHERE id = %s
        """,
        (post_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def update_post_status(post_id, status, approved_by=None):
    conn = get_connection()
    cur = conn.cursor()

    if status == "approved":
        cur.execute(
            """
            UPDATE posts
            SET status = %s, approved_by = %s, approved_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (status, approved_by, post_id),
        )
    else:
        cur.execute(
            """
            UPDATE posts
            SET status = %s
            WHERE id = %s
            """,
            (status, post_id),
        )

    conn.commit()
    cur.close()
    conn.close()


def save_channel_message(post_id, message_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE posts
        SET channel_message_id = %s
        WHERE id = %s
        """,
        (message_id, post_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def soft_delete_post_by_owner(post_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE posts
        SET status = 'deleted_by_user'
        WHERE id = %s
        AND user_id = %s
        RETURNING id
        """,
        (post_id, user_id),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return bool(row)


def mark_pending_post_for_resubmission(post_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE posts
        SET status = 'resubmit_requested'
        WHERE id = %s
        AND user_id = %s
        AND status = 'pending'
        RETURNING id
        """,
        (post_id, user_id),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return bool(row)


def get_user_profile(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT display_name, city
        FROM users
        WHERE id = %s
        """,
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row and row[0] and row[1]:
        return row[0], row[1]
    return None


def save_user_profile(user_id, display_name, city, username=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users (id, display_name, city, username)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET
            display_name = EXCLUDED.display_name,
            city = EXCLUDED.city,
            username = EXCLUDED.username
        """,
        (user_id, display_name, city, username),
    )
    conn.commit()
    cur.close()
    conn.close()
