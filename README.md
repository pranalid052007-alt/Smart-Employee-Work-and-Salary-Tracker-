# Smart Employee Work & Salary Tracker

This is a beginner-friendly Flask web application for tracking employee attendance,
work logs, leaves, and salary computation. The project uses SQLite and is suitable
for a mini-project or viva demonstration.

## Features

- User authentication with `Flask-Login` and password hashing (Werkzeug)
- Employee and admin roles
- Attendance check-in / check-out
- Work log submission
- Leave requests with admin approval
- Salary calculation with configurable bonuses
- Analytics using Chart.js

## Sample Accounts

- Admin: `ADMIN01` / `adminpass`
- Employee: `EMP001` / `employeepass`

## Setup (Windows)

1. Create a virtual environment and activate it:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install requirements:

```powershell
pip install -r requirements.txt
```

3. Run the app:

```powershell
python app.py
```

4. Open http://127.0.0.1:5000 in your browser.

## Notes for Demonstration

- The project initializes the SQLite database on first run and creates sample
  admin and employee accounts. Passwords are hashed using Werkzeug.
- All code is heavily commented to help explain functionality during a viva.
