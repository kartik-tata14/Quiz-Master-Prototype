# init_db.py
import sqlite3

DB_PATH = "quiz.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # table to hold tests with unique 6 digit codes
    c.execute("""
    CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_code TEXT UNIQUE NOT NULL,
        name TEXT
    )
    """)
    # sample test codes: 6-digit numeric
    sample_codes = [
        ("123456", "Orientation Quiz"),
        ("654321", "Security Awareness"),
        ("111222", "Product Training")
    ]
    for code, name in sample_codes:
        try:
            c.execute("INSERT INTO tests (test_code, name) VALUES (?, ?)", (code, name))
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    print("Database initialized at", DB_PATH)

if __name__ == "__main__":
    init_db()