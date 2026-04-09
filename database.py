import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(
        os.getenv("DB_URL"),
        sslmode="require"
    )

# Optional: test connection
def test_connection():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print("Connected to:", cur.fetchone())
    conn.close()


if __name__ == "__main__":
    test_connection()
