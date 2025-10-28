import os
import re
import csv
import io
import math
import json
import random
import sqlite3
from datetime import datetime
import string
from flask import (
    Flask, g, render_template, request, redirect, url_for, flash, session, abort
)

# Configuration
DB_PATH = "quiz.db"
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "replace-with-secure-secret")
TRAINER_PASSWORD = os.environ.get("TRAINER_PASSWORD", "trainer123")  # change in env for production

# ---------------- Database helper (per-request connection, WAL, timeout)
def get_db_connection():
    if "db_conn" not in g:
        # timeout allows SQLite to wait for locks rather than immediate failure
        conn = sqlite3.connect(DB_PATH, timeout=30, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        # improve concurrency for small deployments
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        g.db_conn = conn
    return g.db_conn

@app.teardown_appcontext
def close_db_connection(exception):
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()

# ---------------- Utilities
def is_valid_test_code(code):
    return bool(re.fullmatch(r"[A-Za-z0-9]{6}", code))

def generate_unique_code(conn):
    cur = conn.cursor()
    chars = string.ascii_uppercase + string.digits  # A-Z, 0-9
    for _ in range(2000):
        cand = ''.join(random.choices(chars, k=6))
        cur.execute("SELECT 1 FROM tests WHERE test_code = ?", (cand,))
        if not cur.fetchone():
            return cand
    raise RuntimeError("Unable to generate unique test code")



# ---------------- Routes: Trainee login + exam landing
@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST" and request.form.get("action") == "trainee_login":
        code = request.form.get("test_code", "").strip()
        if not code:
            error = "Please enter the 6 digit Unique Test ID."
        elif not re.fullmatch(r"[A-Za-z0-9]{6}", code):
            error = "Test ID must be exactly 6 alphanumeric characters."
        elif not is_valid_test_code(code):
            error = "Invalid Test ID format."
        else:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM tests WHERE test_code = ?", (code,))
            row = cur.fetchone()
            if row:
                return redirect(url_for("exam_landing", test_code=code))
            else:
                error = "This Test ID does not exist. Please check with your trainer."
        if error:
            flash(error, "danger")
    return render_template("login.html")

@app.route("/exam/<test_code>")
def exam_landing(test_code):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, duration_minutes FROM tests WHERE test_code = ?", (test_code,))
    test = cur.fetchone()
    if not test:
        flash("Test not found.", "danger")
        return redirect(url_for("login"))
    test_id = test["id"]
    cur.execute("SELECT COUNT(1) as cnt FROM questions WHERE test_id = ?", (test_id,))
    qcount_row = cur.fetchone()
    qcount = qcount_row["cnt"] if qcount_row else 0
    has_questions = qcount > 0
    return render_template(
        "exam_landing.html",
        test_code=test_code,
        test_name=test["name"],
        has_questions=has_questions
    )

# ---------------- Trainer auth inline (from login page)
@app.route("/trainer/login", methods=["POST"])
def trainer_login():
    pwd = request.form.get("trainer_password", "")
    if pwd == TRAINER_PASSWORD:
        session["trainer_authenticated"] = True
        flash("Logged in as trainer.", "success")
        return redirect(url_for("trainer_index"))
    else:
        flash("Incorrect trainer password.", "danger")
        return redirect(url_for("login"))

@app.route("/trainer/logout")
def trainer_logout():
    session.pop("trainer_authenticated", None)
    flash("Logged out.", "info")
    return redirect(url_for("login"))

def trainer_login_required():
    if not session.get("trainer_authenticated"):
        return redirect(url_for("login"))
    return None

# ---------------- Trainer Portal: list, create, edit, delete, upload questions
@app.route("/trainer")
def trainer_index():
    redirect_resp = trainer_login_required()
    if redirect_resp:
        return redirect_resp
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, test_code, name, duration_minutes, created_at, updated_at
        FROM tests
        ORDER BY created_at DESC
    """)
    tests = cur.fetchall()
    return render_template("trainer_list.html", tests=tests)

@app.route("/trainer/create", methods=["GET", "POST"])
def trainer_create():
    redirect_resp = trainer_login_required()
    if redirect_resp:
        return redirect_resp
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        duration = request.form.get("duration", "0").strip()
        code_mode = request.form.get("code_mode", "auto")
        manual_code = request.form.get("manual_code", "").strip()
        if not name:
            flash("Test name is required.", "danger")
            return redirect(url_for("trainer_create"))
        try:
            duration_int = int(duration)
            if duration_int < 0:
                raise ValueError
        except ValueError:
            flash("Duration must be a non-negative integer (minutes).", "danger")
            return redirect(url_for("trainer_create"))

        conn = get_db_connection()
        cur = conn.cursor()

        if code_mode == "manual":
            if not manual_code or not is_valid_test_code(manual_code):
                flash("Manual Test Code must be exactly 6 alphanumeric characters (A-Z, 0-9).", "danger")
                return redirect(url_for("trainer_create"))
            code = manual_code
        else:
            try:
                code = generate_unique_code(conn)
            except RuntimeError:
                flash("Unable to generate unique code. Try again.", "danger")
                return redirect(url_for("trainer_create"))

        now = datetime.utcnow().isoformat()
        try:
            cur.execute("""
                INSERT INTO tests (test_code, name, description, duration_minutes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (code, name, description, duration_int, now, now))
            conn.commit()
            flash(f"Test created with code {code}.", "success")
            return redirect(url_for("trainer_index"))
        except sqlite3.IntegrityError:
            flash("Test code already exists. Please try again.", "danger")
        # no explicit conn.close() here: teardown will close per-request connection
    return render_template("trainer_create.html")

@app.route("/trainer/edit/<int:test_id>", methods=["GET", "POST"])
def trainer_edit(test_id):
    redirect_resp = trainer_login_required()
    if redirect_resp:
        return redirect_resp
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tests WHERE id = ?", (test_id,))
    row = cur.fetchone()
    if not row:
        flash("Test not found.", "danger")
        return redirect(url_for("trainer_index"))
    # convert sqlite3.Row to plain dict so templates can use .get() safely
    test = dict(row)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        duration = request.form.get("duration", "0").strip()
        total_trainees = request.form.get("total_trainees", "0").strip()
        try:
            duration_int = int(duration)
            if duration_int < 0:
                raise ValueError
        except ValueError:
            flash("Duration must be a non-negative integer (minutes).", "danger")
            return redirect(url_for("trainer_edit", test_id=test_id))
        try:
            total_trainees_int = int(total_trainees)
            if total_trainees_int < 0:
                raise ValueError
        except ValueError:
            flash("Total trainees must be a non-negative integer.", "danger")
            return redirect(url_for("trainer_edit", test_id=test_id))
        now = datetime.utcnow().isoformat()
        try:
            cur.execute("""
                UPDATE tests
                SET name = ?, description = ?, duration_minutes = ?, total_trainees = ?, updated_at = ?
                WHERE id = ?
            """, (name, description, duration_int, total_trainees_int, now, test_id))
            conn.commit()
            flash("Test updated successfully.", "success")
            return redirect(url_for("trainer_index"))
        except Exception:
            flash("Error updating test.", "danger")
        finally:
            pass
    return render_template("trainer_edit.html", test=test)

@app.route("/trainer/delete/<int:test_id>", methods=["POST"])
def trainer_delete(test_id):
    redirect_resp = trainer_login_required()
    if redirect_resp:
        return redirect_resp
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tests WHERE id = ?", (test_id,))
    conn.commit()
    flash("Test deleted.", "success")
    return redirect(url_for("trainer_index"))

@app.route("/trainer/upload/<int:test_id>", methods=["GET", "POST"])
def trainer_upload(test_id):
    redirect_resp = trainer_login_required()
    if redirect_resp:
        return redirect_resp
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, test_code, name FROM tests WHERE id = ?", (test_id,))
    test = cur.fetchone()
    if not test:
        flash("Test not found.", "danger")
        return redirect(url_for("trainer_index"))
    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file or file.filename == "":
            flash("Please select a CSV file.", "danger")
            return redirect(url_for("trainer_upload", test_id=test_id))
        try:
            content = file.read().decode("utf-8")
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
            if not rows:
                raise ValueError("CSV is empty")
            # skip header row if present
            if rows and rows[0] and rows[0][0].strip().lower() == "question":
                rows = rows[1:]
            inserted = 0
            parsed_rows = []
            for r in rows:
                if len(r) < 6:
                    raise ValueError("Each row must have 6 columns: Question,Option1..4,Correct")
                q_text = r[0].strip()
                opts = [r[1].strip(), r[2].strip(), r[3].strip(), r[4].strip()]
                correct_raw = r[5].strip()
                if not q_text or not all(opts):
                    raise ValueError("Question text and all four options are required")
                if not correct_raw:
                    raise ValueError("Correct column is required")
                parts = [p.strip() for p in correct_raw.replace(",", ";").split(";") if p.strip()]
                for p in parts:
                    if p not in ("1", "2", "3", "4"):
                        raise ValueError(f"Invalid correct index '{p}' for question '{q_text}'")
                correct_norm = ";".join(sorted(set(parts), key=lambda x: int(x)))
                is_multiple = 1 if len(parts) > 1 else 0
                parsed_rows.append((test_id, q_text, opts[0], opts[1], opts[2], opts[3], correct_norm, is_multiple))
                inserted += 1
            # perform batch insert in a short transaction
            if parsed_rows:
                cur.executemany("""
                    INSERT INTO questions (test_id, question_text, option1, option2, option3, option4, correct, is_multiple)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, parsed_rows)
                conn.commit()
            flash(f"Imported {inserted} questions into test {test['test_code']}.", "success")
            return redirect(url_for("trainer_index"))
        except Exception as e:
            flash(f"Error importing CSV: {e}", "danger")
            return redirect(url_for("trainer_upload", test_id=test_id))
    return render_template("trainer_upload.html", test=test)

# View questions for a test
@app.route("/trainer/questions/<int:test_id>")
def trainer_questions(test_id):
    redirect_resp = trainer_login_required()
    if redirect_resp:
        return redirect_resp
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, test_code, name FROM tests WHERE id = ?", (test_id,))
    test = cur.fetchone()
    if not test:
        flash("Test not found.", "danger")
        return redirect(url_for("trainer_index"))
    cur.execute("""
        SELECT id, question_text, option1, option2, option3, option4, correct, is_multiple
        FROM questions
        WHERE test_id = ?
        ORDER BY id ASC
    """, (test_id,))
    questions = cur.fetchall()
    return render_template("trainer_questions.html", test=test, questions=questions)

# Delete a single question (POST)
@app.route("/trainer/question/delete/<int:question_id>", methods=["POST"])
def trainer_question_delete(question_id):
    redirect_resp = trainer_login_required()
    if redirect_resp:
        return redirect_resp
    conn = get_db_connection()
    cur = conn.cursor()
    # find test_id to return back to questions list
    cur.execute("SELECT test_id FROM questions WHERE id = ?", (question_id,))
    row = cur.fetchone()
    if not row:
        flash("Question not found.", "danger")
        return redirect(url_for("trainer_index"))
    test_id = row["test_id"]
    cur.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    conn.commit()
    flash("Question deleted.", "success")
    return redirect(url_for("trainer_questions", test_id=test_id))

@app.route("/trainer/questions/delete_bulk", methods=["POST"])
def trainer_questions_delete_bulk():
    redirect_resp = trainer_login_required()
    if redirect_resp:
        return redirect_resp
    # 'test_id' is used to redirect back; 'selected_q' are question ids from the form
    test_id = request.form.get("test_id")
    selected = request.form.getlist("selected_q")
    if not test_id:
        flash("Missing test reference.", "danger")
        return redirect(url_for("trainer_index"))
    if not selected:
        flash("No questions selected for deletion.", "warning")
        return redirect(url_for("trainer_questions", test_id=test_id))
    # validate ids are integers
    try:
        ids = [int(x) for x in selected]
    except ValueError:
        flash("Invalid question selection.", "danger")
        return redirect(url_for("trainer_questions", test_id=test_id))
    conn = get_db_connection()
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in ids)
    cur.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", tuple(ids))
    conn.commit()
    flash(f"Deleted {cur.rowcount} question(s).", "success")
    return redirect(url_for("trainer_questions", test_id=test_id))


@app.route("/trainer/results/<int:test_id>")
def trainer_results(test_id):
    # trainer auth
    redirect_resp = trainer_login_required()
    if redirect_resp:
        return redirect_resp

    conn = get_db_connection()
    cur = conn.cursor()

    # load test metadata including total_trainees
    cur.execute("SELECT id, test_code, name, total_trainees FROM tests WHERE id = ?", (test_id,))
    test = cur.fetchone()
    if not test:
        flash("Test not found.", "danger")
        return redirect(url_for("trainer_index"))

    # PARTICIPATION
    cur.execute("SELECT COUNT(1) as cnt FROM results WHERE test_id = ?", (test_id,))
    participants_row = cur.fetchone()
    participants = participants_row["cnt"] if participants_row else 0
    total_trainees = test["total_trainees"] or 0
    non_participants = max(total_trainees - participants, 0)

    # QUESTIONWISE ANALYSIS
    # fetch questions for this test
    cur.execute("SELECT id, question_text, correct FROM questions WHERE test_id = ? ORDER BY id ASC", (test_id,))
    qrows = cur.fetchall()
    q_ids = [q["id"] for q in qrows]
    q_texts = [q["question_text"] for q in qrows]
    correct_map = {q["id"]: q["correct"] for q in qrows}

    # initialize counts
    q_total_attempts = {qid: 0 for qid in q_ids}
    q_correct_counts = {qid: 0 for qid in q_ids}
    # fetch all results for this test
    cur.execute("SELECT raw_answers FROM results WHERE test_id = ?", (test_id,))
    result_rows = cur.fetchall()
    for r in result_rows:
        raw = r["raw_answers"]
        try:
            answers = json.loads(raw)
        except Exception:
            answers = {}
        for qid in q_ids:
            s_qid = str(qid)
            ans = answers.get(s_qid, "")
            if ans:
                q_total_attempts[qid] += 1
                # compare answer set to correct set
                correct = correct_map.get(qid, "")
                if correct:
                    # sets of strings like {'1','3'}
                    if set(ans.split(";")) == set(correct.split(";")):
                        q_correct_counts[qid] += 1

    # Build arrays for chart (aligned with q_texts)
    question_labels = q_texts
    correct_counts = [q_correct_counts[qid] for qid in q_ids]
    wrong_counts = [q_total_attempts[qid] - q_correct_counts[qid] for qid in q_ids]

    # RESULT DISTRIBUTION
    # bins: 100%, >=75% and <100, >=50% and <75, <50%
    cur.execute("SELECT score, total FROM results WHERE test_id = ?", (test_id,))
    score_rows = cur.fetchall()
    bins = {"100": 0, "75plus": 0, "50to75": 0, "below50": 0}
    for sr in score_rows:
        score = sr["score"]
        total = sr["total"] or 1
        pct = (score / total) * 100.0
        if math.isclose(pct, 100.0, rel_tol=1e-9):
            bins["100"] += 1
        elif pct >= 75.0:
            bins["75plus"] += 1
        elif pct >= 50.0:
            bins["50to75"] += 1
        else:
            bins["below50"] += 1

    # prepare JSON data for template
    chart_data = {
        "participation": {
            "labels": ["Participants", "Non Participants"],
            "values": [participants, non_participants]
        },
        "question_analysis": {
            "labels": question_labels,
            "correct": correct_counts,
            "wrong": wrong_counts
        },
        "result_dist": {
            "labels": ["100%", ">=75%", "50-75%", "<50%"],
            "values": [bins["100"], bins["75plus"], bins["50to75"], bins["below50"]]
        },
        "test": {"id": test["id"], "code": test["test_code"], "name": test["name"], "total_trainees": total_trainees}
    }

    conn.close()
    return render_template("trainer_results.html", chart_data=json.dumps(chart_data))



# ---------------- Quiz flow for trainees: start, submit, results
@app.route("/quiz/start/<test_code>", methods=["GET"])
def quiz_start(test_code):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, duration_minutes FROM tests WHERE test_code = ?", (test_code,))
    test = cur.fetchone()
    if not test:
        flash("Test not found.", "danger")
        return redirect(url_for("login"))

    test_id = test["id"]
    duration = test["duration_minutes"] or 5  # default to 5 minutes if not set

    # fetch distinct question ids and question rows
    cur.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,))
    id_rows = cur.fetchall()
    question_ids = [r["id"] for r in id_rows]

    if not question_ids:
        flash("No questions available for this test. Contact the trainer.", "danger")
        return redirect(url_for("exam_landing", test_code=test_code))

    # choose up to 5 unique question ids without replacement
    pick_count = min(5, len(question_ids))
    chosen_ids = random.sample(question_ids, k=pick_count)

    # fetch the chosen question rows in a single query preserving order of chosen_ids
    placeholders = ",".join("?" for _ in chosen_ids)
    cur.execute(f"SELECT * FROM questions WHERE id IN ({placeholders})", tuple(chosen_ids))
    rows = {r["id"]: r for r in cur.fetchall()}

    # build quiz_questions in the same order as chosen_ids
    quiz_questions = []
    for qid in chosen_ids:
        q = rows[qid]
        quiz_questions.append({
            "id": q["id"],
            "text": q["question_text"],
            "options": [q["option1"], q["option2"], q["option3"], q["option4"]],
            "is_multiple": bool(q["is_multiple"])
        })

    # store only the chosen ids in session to avoid any accidental re-selection on refresh
    session['current_quiz'] = {
        "test_id": test_id,
        "test_code": test_code,
        "question_ids": chosen_ids,
        "started_at": datetime.utcnow().isoformat(),
        "duration_seconds": duration * 60
    }

    return render_template("quiz.html", test_name=test["name"], duration_seconds=duration * 60, questions=quiz_questions, test_code=test_code)

@app.route("/quiz/submit/<test_code>", methods=["POST"])
def quiz_submit(test_code):
    sq = session.get("current_quiz")
    if not sq or sq.get("test_code") != test_code:
        flash("No active quiz found or quiz expired.", "danger")
        return redirect(url_for("login"))
    test_id = sq["test_id"]
    question_ids = sq["question_ids"]
    conn = get_db_connection()
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in question_ids)
    cur.execute(f"SELECT id, correct FROM questions WHERE id IN ({placeholders})", tuple(question_ids))
    rows = cur.fetchall()
    correct_map = {r["id"]: r["correct"] for r in rows}
    score = 0
    total = len(question_ids)
    raw_answers = {}
    for qid in question_ids:
        field = f"q_{qid}"
        vals = request.form.getlist(field)
        vals_norm = ";".join(sorted(set(vals), key=lambda x: int(x))) if vals else ""
        raw_answers[str(qid)] = vals_norm
        correct_ans = correct_map.get(qid, "")
        if vals_norm and correct_ans:
            if set(vals_norm.split(";")) == set(correct_ans.split(";")):
                score += 1
    now = datetime.utcnow().isoformat()
    cur.execute("""
        INSERT INTO results (test_id, attempted_at, score, total, raw_answers)
        VALUES (?, ?, ?, ?, ?)
    """, (test_id, now, score, total, json.dumps(raw_answers)))
    conn.commit()
    session.pop("current_quiz", None)
    return render_template("quiz_result.html", score=score, total=total, test_code=test_code)

# ---------------- Admin utility: simple DB migration if tables missing
def ensure_schema():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # tests table (if not present)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        description TEXT DEFAULT '',
        duration_minutes INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    # questions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        option1 TEXT NOT NULL,
        option2 TEXT NOT NULL,
        option3 TEXT NOT NULL,
        option4 TEXT NOT NULL,
        correct TEXT NOT NULL,
        is_multiple INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE
    )
    """)
    # results table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        attempted_at TEXT NOT NULL,
        score INTEGER NOT NULL,
        total INTEGER NOT NULL,
        raw_answers TEXT NOT NULL,
        FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE
    )
    """)
    conn.commit()
    conn.close()

# Run schema ensure on startup
ensure_schema()

# ---------------- Run app
if __name__ == "__main__":
    # debug mode for development; remove debug=True in production
    app.run(debug=True)
