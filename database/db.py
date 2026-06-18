import os
import psycopg2


DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id BIGINT PRIMARY KEY,
        display_name TEXT,
        city TEXT,
        username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        post_type TEXT,
        category TEXT,
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
    """)
    cur.execute("""
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS subcategory TEXT
    """)
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
):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO posts
        (
            user_id,
            category,
            subcategory,
            city,
            display_name,
            telegram_id,
            content,
            status
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,'pending')
        RETURNING id
        """,
        (
            user_id,
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


def update_post(
    post_id,
    category,
    subcategory,
    city,
    display_name,
    telegram_id,
    content,
):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE posts
        SET
            category = %s,
            subcategory = %s,
            city = %s,
            display_name = %s,
            telegram_id = %s,
            content = %s,
            status = 'pending'
        WHERE id = %s
        """,
        (
            category,
            subcategory,
            city,
            display_name,
            telegram_id,
            content,
            post_id,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


def update_post_content(post_id, content):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE posts
        SET
            content = %s,
            status = 'pending'
        WHERE id = %s
        """,
        (
            content,
            post_id,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_post(post_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id,
            user_id,
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
    return row


def get_pending_edit_post(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id
        FROM posts
        WHERE user_id = %s
        AND status = 'need_edit'
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row[0]
    return None


def update_post_status(post_id, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE posts
        SET status = %s
        WHERE id = %s
        """,
        (
            status,
            post_id,
        ),
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
        (
            message_id,
            post_id,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_user_id_by_post(post_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT user_id
        FROM posts
        WHERE id = %s
        """,
        (post_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row[0]
    return None


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
        (
            user_id,
            display_name,
            city,
            username,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()
