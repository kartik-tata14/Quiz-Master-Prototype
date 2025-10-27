# init_db.py
import sqlite3
from datetime import datetime

DB_PATH = "quiz.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        duration_minutes INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    sample_codes = [
        ("123456", "Orientation Quiz", "A quick intro quiz", 10),
        ("654321", "Security Awareness", "Phishing & security basics", 20),
        ("111222", "Product Training", "Product feature recall", 15)
    ]
    now = datetime.utcnow().isoformat()
    for code, name, desc, dur in sample_codes:
        try:
            c.execute("""
            INSERT INTO tests (test_code, name, description, duration_minutes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (code, name, desc, dur, now, now))
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    print("Database initialized/updated at", DB_PATH)

if __name__ == "__main__":
    init_db()
