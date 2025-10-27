# db_migrations.py
import sqlite3
DB_PATH = "quiz.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # questions table
    c.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        option1 TEXT NOT NULL,
        option2 TEXT NOT NULL,
        option3 TEXT NOT NULL,
        option4 TEXT NOT NULL,
        correct TEXT NOT NULL, -- semicolon separated indices e.g. "2" or "1;3"
        is_multiple INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE
    )
    """)
    # results table to store trainee attempts
    c.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        attempted_at TEXT NOT NULL,
        score INTEGER NOT NULL,
        total INTEGER NOT NULL,
        raw_answers TEXT NOT NULL, -- JSON or simple encoding of answers
        FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE
    )
    """)
    conn.commit()
    conn.close()
    print("Migration complete")

if __name__ == "__main__":
    migrate()
