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

def add_trainees():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trainees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()
    print("Trainees table ensured.")

def add_total_trainees():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Add column if not exists (SQLite doesn't support IF NOT EXISTS for ALTER, so check pragma)
    cols = [r[1] for r in c.execute("PRAGMA table_info(tests)").fetchall()]
    if "total_trainees" not in cols:
        c.execute("ALTER TABLE tests ADD COLUMN total_trainees INTEGER DEFAULT 0")
        print("Added total_trainees column.")
    else:
        print("Column total_trainees already exists.")
    conn.commit()
    conn.close()



if __name__ == "__main__":
    init_db()
    migrate()
    add_trainees()
    add_total_trainees()

    #add_results_trainee
    conn=sqlite3.connect(DB_PATH)
    cur=conn.cursor()
    # Only add columns if not exists
    cols = [r[1] for r in cur.execute("PRAGMA table_info(results)").fetchall()]
    if "trainee_id" not in cols:
        cur.execute("ALTER TABLE results ADD COLUMN trainee_id INTEGER")
    if "trainee_emp_id" not in cols:
        cur.execute("ALTER TABLE results ADD COLUMN trainee_emp_id TEXT")
    conn.commit()
    conn.close()
    print("results table updated (if columns were missing).")

    #add_results_trainee_cols
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(results)").fetchall()]
    if "trainee_id" not in cols:
        cur.execute("ALTER TABLE results ADD COLUMN trainee_id INTEGER")
    if "trainee_emp_id" not in cols:
        cur.execute("ALTER TABLE results ADD COLUMN trainee_emp_id TEXT")
    if "trainee_name" not in cols:
        cur.execute("ALTER TABLE results ADD COLUMN trainee_name TEXT")
    conn.commit()
    conn.close()
    print("Ensured trainee columns exist in results table.")