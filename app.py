# app.py
import os
import re
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort

DB_PATH = "quiz.db"
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "replace-with-secure-secret")
TRAINER_PASSWORD = os.environ.get("TRAINER_PASSWORD", "trainer123")  # change in env for production

# --- DB helper
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def is_valid_test_code(code):
    return bool(re.fullmatch(r"\d{6}", code))

# --- Trainee login (unchanged behavior)
@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST" and request.form.get("action") == "trainee_login":
        code = request.form.get("test_code", "").strip()
        if not code:
            error = "Please enter the 6 digit Unique Test ID."
        elif not code.isdigit():
            error = "Unique Test ID must be numeric."
        elif len(code) != 6:
            error = "Unique Test ID must be exactly 6 digits."
        elif not is_valid_test_code(code):
            error = "Invalid Test ID format."
        else:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM tests WHERE test_code = ?", (code,))
            row = cur.fetchone()
            conn.close()
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
    cur.execute("SELECT name FROM tests WHERE test_code = ?", (test_code,))
    row = cur.fetchone()
    conn.close()
    test_name = row["name"] if row else "Unknown Test"
    return render_template("exam_landing.html", test_code=test_code, test_name=test_name)

# --- Trainer auth helpers
def trainer_login_required():
    if not session.get("trainer_authenticated"):
        return redirect(url_for("login"))
    return None

# POST handler for trainer login from the same page
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

# --- Trainer routes (protected)
@app.route("/trainer")
def trainer_index():
    redirect_resp = trainer_login_required()
    if redirect_resp:
        return redirect_resp
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, test_code, name, duration_minutes, created_at, updated_at FROM tests ORDER BY created_at DESC")
    tests = cur.fetchall()
    conn.close()
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
        if code_mode == "manual":
            if not manual_code or not is_valid_test_code(manual_code):
                flash("Manual Test Code must be exactly 6 numeric digits.", "danger")
                return redirect(url_for("trainer_create"))
            code = manual_code
        else:
            import random
            conn = get_db_connection()
            cur = conn.cursor()
            for _ in range(1000):
                cand = f"{random.randint(0,999999):06d}"
                cur.execute("SELECT 1 FROM tests WHERE test_code = ?", (cand,))
                if not cur.fetchone():
                    code = cand
                    break
            else:
                conn.close()
                flash("Unable to generate unique code. Try again.", "danger")
                return redirect(url_for("trainer_create"))
            conn.close()
        now = datetime.utcnow().isoformat()
        conn = get_db_connection()
        cur = conn.cursor()
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
        finally:
            conn.close()
    return render_template("trainer_create.html")

@app.route("/trainer/edit/<int:test_id>", methods=["GET", "POST"])
def trainer_edit(test_id):
    redirect_resp = trainer_login_required()
    if redirect_resp:
        return redirect_resp
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tests WHERE id = ?", (test_id,))
    test = cur.fetchone()
    if not test:
        conn.close()
        flash("Test not found.", "danger")
        return redirect(url_for("trainer_index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        duration = request.form.get("duration", "0").strip()
        try:
            duration_int = int(duration)
            if duration_int < 0:
                raise ValueError
        except ValueError:
            flash("Duration must be a non-negative integer (minutes).", "danger")
            return redirect(url_for("trainer_edit", test_id=test_id))
        now = datetime.utcnow().isoformat()
        try:
            cur.execute("""
                UPDATE tests
                SET name = ?, description = ?, duration_minutes = ?, updated_at = ?
                WHERE id = ?
            """, (name, description, duration_int, now, test_id))
            conn.commit()
            flash("Test updated successfully.", "success")
            return redirect(url_for("trainer_index"))
        finally:
            conn.close()
    conn.close()
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
    conn.close()
    flash("Test deleted.", "success")
    return redirect(url_for("trainer_index"))


if __name__ == "__main__":
    app.run(debug=True)