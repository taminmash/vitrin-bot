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

    conn.commit()

    cur.close()
    conn.close()
