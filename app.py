# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import re

DB_PATH = "quiz.db"

app = Flask(__name__)
app.secret_key = "replace-with-a-secure-random-key"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def is_valid_test_code(code):
    # must be exactly 6 digits, numeric only
    return bool(re.fullmatch(r"\d{6}", code))

@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        code = request.form.get("test_code", "").strip()
        # Server-side validation
        if not code:
            error = "Please enter the 6 digit Unique Test ID."
        elif not code.isdigit():
            error = "Unique Test ID must be numeric."
        elif len(code) != 6:
            error = "Unique Test ID must be exactly 6 digits."
        elif not is_valid_test_code(code):
            error = "Invalid Test ID format."
        else:
            # Check DB
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM tests WHERE test_code = ?", (code,))
            row = cur.fetchone()
            conn.close()
            if row:
                # successful login to the exam; replace with proper session flow later
                return redirect(url_for("exam_landing", test_code=code))
            else:
                error = "This Test ID does not exist. Please check with your trainer."
        if error:
            flash(error, "danger")
    return render_template("login.html")

@app.route("/exam/<test_code>")
def exam_landing(test_code):
    # Placeholder page after successful code validation; trainer-specific logic will come later
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM tests WHERE test_code = ?", (test_code,))
    row = cur.fetchone()
    conn.close()
    test_name = row["name"] if row else "Unknown Test"
    return render_template("exam_landing.html", test_code=test_code, test_name=test_name)

if __name__ == "__main__":
    app.run(debug=True)