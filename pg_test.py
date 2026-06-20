import os
import psycopg2

def test_connection():
    database_url = os.environ.get("DATABASE_URL")

    conn = psycopg2.connect(database_url)

    cur = conn.cursor()
    cur.execute("SELECT version();")

    version = cur.fetchone()

    print("POSTGRES OK")
    print(version)

    cur.close()
    conn.close()


if __name__ == "__main__":
    test_connection()
