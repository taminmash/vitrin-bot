import psycopg2
from psycopg2.extras import RealDictCursor

from config_v2 import DATABASE_URL, POST_STATUS_DELETED, POST_STATUS_PENDING


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            city TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            content TEXT NOT NULL,
            city TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            channel_message_id BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS subcategory TEXT")
    cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS channel_message_id BIGINT")
    cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS city TEXT")
    cur.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS city TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    conn.commit()
    cur.close()
    conn.close()


def get_user(telegram_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def upsert_user(telegram_id, full_name, username, city):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        INSERT INTO users (telegram_id, full_name, username, city, updated_at)
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (telegram_id)
        DO UPDATE SET
            full_name = EXCLUDED.full_name,
            username = EXCLUDED.username,
            city = EXCLUDED.city,
            updated_at = CURRENT_TIMESTAMP
        RETURNING *
        """,
        (telegram_id, full_name, username, city),
    )
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return user


def create_post(telegram_id, category, subcategory, content, city):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        INSERT INTO posts (telegram_id, category, subcategory, content, city, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (telegram_id, category, subcategory, content, city, POST_STATUS_PENDING),
    )
    post = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return post


def get_post(post_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM posts WHERE id = %s", (post_id,))
    post = cur.fetchone()
    cur.close()
    conn.close()
    return post


def update_post_content(post_id, content):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        UPDATE posts
        SET content = %s,
            status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
        """,
        (content, POST_STATUS_PENDING, post_id),
    )
    post = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return post


def update_post_status(post_id, status):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        UPDATE posts
        SET status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
        """,
        (status, post_id),
    )
    post = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return post


def mark_post_published(post_id, channel_message_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        UPDATE posts
        SET status = %s,
            channel_message_id = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
        """,
        ("published", channel_message_id, post_id),
    )
    post = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return post


def delete_post(post_id):
    return update_post_status(post_id, POST_STATUS_DELETED)


def get_latest_user_post(telegram_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT *
        FROM posts
        WHERE telegram_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (telegram_id,),
    )
    post = cur.fetchone()
    cur.close()
    conn.close()
    return post
