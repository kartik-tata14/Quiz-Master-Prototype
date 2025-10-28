
# Quiz Platform — Trainer and Trainee App

A lightweight Flask-based quiz platform for trainers and trainees. Trainers create tests, upload questions, manage trainees, and view results dashboards with charts. Trainees join a test with a 6-character alphanumeric Test Code, verify their registered Employee ID, take the quiz, and have attempts recorded.

## Key features
- Trainer flows: create tests (auto-generate or manual 6-character alphanumeric Test Codes), upload question CSV, manage trainees, view results with per-question analysis and per-attempt rows.

- Trainee flows: enter Test Code, enter registered Employee ID, take quiz, single-attempt protections and clean scoring.

- Analytics: participation counts, result distribution, question-wise correct/wrong counts, per-attempt list showing Employee ID, Trainee Name, Score and timestamp.

- Frontend: Bootstrap and Chart.js for responsive UI and charts.

## Quick Start

- Clone the Repo

```bash
    git clone <your-repo-url>
    cd <repo-directory>
```

- Create and activate a virtual environment:
```bash
	python -m venv venv
	venv\Scripts\activate
```

- Install flask
```bash
	pip install flask
```

- Initialize the Database: 
```bash
	python init_db.py
```

- Run the flask app: 
```bash
	python app.py
```

- Open the development server: http://127.0.0.1:5000
## Important routes and usage

### Trainer:
- /trainer — Trainer dashboard (requires trainer login key)
- /trainer/create — Create new test (auto or manual 6-character Test Code)
- /trainer/results/<test_id> — Results and attempts list for a test
- /trainer/trainees — List and add trainees

### Trainee:
- / or login landing — Enter Test Code
- /exam/<test_code> — Enter Employee ID, then proceed to quiz
- /quiz/<test_code> — Quiz start
- /quiz/<test_code>/submit — Submit answers (POST only)

#### Notes:
##### Test Code format: exactly 6 alphanumeric characters (A–Z, 0–9).
##### Employee ID format: alphanumeric; must exist in the trainees table to proceed.

### Database schema (core tables)
- tests: id, test_code, name, description, duration_minutes, total_trainees, created_at, updated_at

- questions: id, test_id, question_text, option1, option2, option3, option4, correct, is_multiple

- trainees: id, emp_id, name, created_at

- results: id, test_id, attempted_at, score, total, raw_answers, trainee_id, trainee_emp_id, trainee_name

