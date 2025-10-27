# db_add_total_trainees.py
import sqlite3
DB_PATH = "quiz.db"

def migrate():
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
    migrate()
