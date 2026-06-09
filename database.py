import sqlite3

DB_NAME = "comments.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        comment_text TEXT
    )
    """)

    conn.commit()
    conn.close()


def add_comment(post_id, comment_text):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO comments (post_id, comment_text) VALUES (?, ?)",
        (post_id, comment_text)
    )

    conn.commit()
    conn.close()


def get_comment_count(post_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM comments WHERE post_id = ?",
        (post_id,)
    )

    count = cur.fetchone()[0]

    conn.close()

    return count
