import os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    print("DATABASE_URL =", DATABASE_URL)
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    post_id BIGINT,
    user_id BIGINT,
    nickname TEXT,
    comment_text TEXT
)
    """)

    conn.commit()
    cur.close()
    conn.close()


def add_comment(post_id, user_id, nickname, comment_text):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO comments
        (post_id, user_id, nickname, comment_text)
        VALUES (%s, %s, %s, %s)
        """,
        (post_id, user_id, nickname, comment_text)
    )

    conn.commit()
    cur.close()
    conn.close()


def get_comment_count(post_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM comments WHERE post_id = %s",
        (post_id,)
    )

    count = cur.fetchone()[0]

    cur.close()
    conn.close()

    return count


def get_comments(post_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT comment_text FROM comments WHERE post_id = %s ORDER BY id ASC",
        (post_id,)
    )

    comments = cur.fetchall()

    cur.close()
    conn.close()

    return comments
