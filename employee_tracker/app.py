"""
Smart Employee Work & Salary Tracker
Main Flask application file.

This file contains the Flask app, route definitions, database initialization,
authentication using Flask-Login, and business logic for attendance, work logs,
leave requests, salary calculation, and admin functions.

Every function and route is commented for educational clarity.
"""

from flask import Flask, render_template, request, redirect, url_for, flash, g
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime, date

# --------------------
# Configuration
# --------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'employee.db')

app = Flask(__name__)
# Secret key for session management and flash messages. In production, use a secure value.
app.config['SECRET_KEY'] = 'dev-secret-key-for-demo'

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Attendance and performance bonus configuration constants
# These are configurable constants used in salary calculation.
ATTENDANCE_BONUS = 50   # Amount per attendance day
PERFORMANCE_BONUS = 10  # Amount per task completed

# --------------------
# Database helpers
# --------------------
def get_db():
    """Get a SQLite DB connection, store it on Flask global "g".

    Returns a connection to the SQLite database. If the connection already
    exists on `g`, reuse it.
    """
    db = getattr(g, '_database', None)
    if db is None:
        # Connect to SQLite database; create file if it doesn't exist
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Close DB connection after request finishes."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    """Helper to execute SELECT queries and return results.

    `query` is SQL, `args` is tuple of parameters. If `one` is True,
    return a single row or None.
    """
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    """Helper to execute INSERT/UPDATE/DELETE queries and commit."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    return cur.lastrowid

# --------------------
# Flask-Login User
# --------------------
class User(UserMixin):
    """User object for Flask-Login backed by SQLite.

    We implement a minimal User wrapper that fetches user data from the
    `Employees` table in the SQLite database.
    """
    def __init__(self, id_, employee_id, name, email, role):
        self.id = id_
        self.employee_id = employee_id
        self.name = name
        self.email = email
        self.role = role

    @staticmethod
    def get_by_employee_id(emp_id):
        """Fetch a user by `employee_id` (login identifier).

        Returns a User object or None.
        """
        row = query_db('SELECT * FROM Employees WHERE employee_id = ?', (emp_id,), one=True)
        if row:
            return User(row['id'], row['employee_id'], row['name'], row['email'], row['role'])
        return None

    @staticmethod
    def get_by_id(id_):
        """Fetch a user by internal `id` (for Flask-Login)."""
        row = query_db('SELECT * FROM Employees WHERE id = ?', (id_,), one=True)
        if row:
            return User(row['id'], row['employee_id'], row['name'], row['email'], row['role'])
        return None

@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback. Receives user id and returns User."""
    return User.get_by_id(user_id)

# --------------------
# Database initialization
# --------------------
def init_db():
    """Initialize the SQLite database with required tables and sample data.

    This function creates the tables if they don't exist and inserts a sample
    admin and employee account for demonstration.
    """
    # Ensure database directory exists
    db_dir = os.path.join(BASE_DIR, 'database')
    os.makedirs(db_dir, exist_ok=True)

    # If DB file doesn't exist, create tables and seed sample data
    first_time = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Create Employees table
    c.execute('''
    CREATE TABLE IF NOT EXISTS Employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT UNIQUE,
        name TEXT,
        email TEXT,
        password TEXT,
        department TEXT,
        role TEXT,
        base_salary REAL
    )
    ''')

    # Create Attendance table
    c.execute('''
    CREATE TABLE IF NOT EXISTS Attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT,
        date TEXT,
        check_in TEXT,
        check_out TEXT,
        total_hours REAL
    )
    ''')

    # Create WorkLogs table
    c.execute('''
    CREATE TABLE IF NOT EXISTS WorkLogs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT,
        date TEXT,
        task_description TEXT,
        tasks_completed INTEGER,
        hours_worked REAL
    )
    ''')

    # Create LeaveRequests table
    c.execute('''
    CREATE TABLE IF NOT EXISTS LeaveRequests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT,
        leave_date TEXT,
        reason TEXT,
        status TEXT
    )
    ''')

    # Create Salary table
    c.execute('''
    CREATE TABLE IF NOT EXISTS Salary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT,
        month TEXT,
        attendance_days INTEGER,
        tasks_completed INTEGER,
        final_salary REAL
    )
    ''')

    conn.commit()

    # Seed sample admin and employee accounts if DB was newly created
    if first_time:
        # Sample admin: employee_id = ADMIN01, password = adminpass
        admin_pw = generate_password_hash('adminpass')
        c.execute('INSERT OR IGNORE INTO Employees (employee_id, name, email, password, department, role, base_salary) VALUES (?, ?, ?, ?, ?, ?, ?)',
                  ('ADMIN01', 'Alice Admin', 'alice.admin@example.com', admin_pw, 'Management', 'Admin', 0.0))

        # Sample employee: employee_id = EMP001, password = employeepass
        emp_pw = generate_password_hash('employeepass')
        c.execute('INSERT OR IGNORE INTO Employees (employee_id, name, email, password, department, role, base_salary) VALUES (?, ?, ?, ?, ?, ?, ?)',
                  ('EMP001', 'Bob Employee', 'bob.employee@example.com', emp_pw, 'Engineering', 'Employee', 2000.0))

        conn.commit()

    conn.close()

# Initialize DB at startup
init_db()

# --------------------
# Utility functions
# --------------------
def calculate_total_hours(check_in_str, check_out_str):
    """Calculate total hours between two ISO timestamp strings.

    Returns total hours as float.
    """
    if not check_in_str or not check_out_str:
        return 0.0
    fmt = '%Y-%m-%d %H:%M:%S'
    try:
        dt_in = datetime.strptime(check_in_str, fmt)
        dt_out = datetime.strptime(check_out_str, fmt)
        diff = dt_out - dt_in
        return round(diff.total_seconds() / 3600.0, 2)
    except Exception:
        return 0.0

def compute_performance_rating(total_tasks):
    """Compute performance rating string from total tasks completed.

    Rules:
      0–10 -> Poor
      11–25 -> Average
      26–40 -> Good
      41+ -> Excellent
    """
    if total_tasks <= 10:
        return 'Poor'
    elif total_tasks <= 25:
        return 'Average'
    elif total_tasks <= 40:
        return 'Good'
    else:
        return 'Excellent'

# --------------------
# Authentication routes
# --------------------
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page route.

    Accepts Employee ID and Password via POST. On successful authentication,
    logs in user using Flask-Login and redirects based on role.
    """
    if request.method == 'POST':
        employee_id = request.form.get('employee_id')
        password = request.form.get('password')

        # Fetch user row from DB
        row = query_db('SELECT * FROM Employees WHERE employee_id = ?', (employee_id,), one=True)
        if row:
            # Verify hashed password
            if check_password_hash(row['password'], password):
                user = User(row['id'], row['employee_id'], row['name'], row['email'], row['role'])
                login_user(user)
                flash('Logged in successfully.', 'success')
                # Redirect admins to admin dashboard, employees to employee dashboard
                if user.role == 'Admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                flash('Invalid credentials. Please try again.', 'danger')
        else:
            flash('User not found. Please check your Employee ID.', 'danger')

    # Render login template for GET and failed POST
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout route. Logs out the current user and redirects to login."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --------------------
# Employee routes
# --------------------
@app.route('/dashboard')
@login_required
def dashboard():
    """Employee dashboard route.

    Displays summary statistics for the current logged-in employee, including
    attendance days, total hours, tasks completed, performance rating, and
    estimated current salary.
    """
    emp_id = current_user.employee_id

    # Total attendance days for employee (count distinct dates)
    rows = query_db('SELECT COUNT(DISTINCT date) AS days FROM Attendance WHERE employee_id = ?', (emp_id,), one=True)
    attendance_days = rows['days'] if rows else 0

    # Sum total hours worked from Attendance table
    rows = query_db('SELECT SUM(total_hours) AS hours FROM Attendance WHERE employee_id = ?', (emp_id,), one=True)
    total_hours = rows['hours'] if rows and rows['hours'] else 0.0

    # Sum tasks completed from WorkLogs
    rows = query_db('SELECT SUM(tasks_completed) AS tasks FROM WorkLogs WHERE employee_id = ?', (emp_id,), one=True)
    tasks_completed = rows['tasks'] if rows and rows['tasks'] else 0

    # Compute performance rating
    performance = compute_performance_rating(tasks_completed)

    # Compute current estimated salary using configured bonuses
    # Base salary fetched from Employees table
    emp_row = query_db('SELECT base_salary, name, department FROM Employees WHERE employee_id = ?', (emp_id,), one=True)
    base_salary = emp_row['base_salary'] if emp_row else 0.0
    department = emp_row['department'] if emp_row else ''

    estimated_salary = base_salary + (attendance_days * ATTENDANCE_BONUS) + (tasks_completed * PERFORMANCE_BONUS)

    return render_template('dashboard.html',
                           name=current_user.name,
                           department=department,
                           attendance_days=attendance_days,
                           total_hours=total_hours,
                           tasks_completed=tasks_completed,
                           performance=performance,
                           estimated_salary=estimated_salary,
                           base_salary=base_salary)

@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    """Attendance page route.

    Allows employees to check in and check out. Stores timestamps and computes
    total hours for the day. Displays attendance history.
    """
    emp_id = current_user.employee_id
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today = date.today().isoformat()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'check_in':
            # Insert or update today's attendance record with check_in time
            # We allow multiple check-ins; this simple system records the first check-in
            existing = query_db('SELECT * FROM Attendance WHERE employee_id = ? AND date = ?', (emp_id, today), one=True)
            if existing and existing['check_in']:
                flash('You already checked in today.', 'warning')
            else:
                if existing:
                    execute_db('UPDATE Attendance SET check_in = ? WHERE id = ?', (now, existing['id']))
                else:
                    execute_db('INSERT INTO Attendance (employee_id, date, check_in, check_out, total_hours) VALUES (?, ?, ?, ?, ?)',
                               (emp_id, today, now, None, 0.0))
                flash('Check-in recorded at {}'.format(now), 'success')

        elif action == 'check_out':
            # Record check-out time and compute total_hours
            existing = query_db('SELECT * FROM Attendance WHERE employee_id = ? AND date = ?', (emp_id, today), one=True)
            if not existing or not existing['check_in']:
                flash('You must check in before checking out.', 'danger')
            elif existing['check_out']:
                flash('You already checked out today.', 'warning')
            else:
                # Calculate total hours between check_in and now
                total_h = calculate_total_hours(existing['check_in'], now)
                execute_db('UPDATE Attendance SET check_out = ?, total_hours = ? WHERE id = ?', (now, total_h, existing['id']))
                flash('Check-out recorded at {} (Hours: {})'.format(now, total_h), 'success')

        return redirect(url_for('attendance'))

    # GET: show attendance history (last 30 records)
    records = query_db('SELECT * FROM Attendance WHERE employee_id = ? ORDER BY date DESC LIMIT 30', (emp_id,))
    return render_template('attendance.html', records=records)

@app.route('/worklog', methods=['GET', 'POST'])
@login_required
def worklog():
    """Work log page route.

    Allows employees to submit daily work logs (task description, tasks completed,
    and hours worked) and view previous logs.
    """
    emp_id = current_user.employee_id
    if request.method == 'POST':
        # Gather form data and insert into WorkLogs
        entry_date = request.form.get('date') or date.today().isoformat()
        task_description = request.form.get('task_description')
        tasks_completed = int(request.form.get('tasks_completed') or 0)
        hours_worked = float(request.form.get('hours_worked') or 0.0)

        execute_db('INSERT INTO WorkLogs (employee_id, date, task_description, tasks_completed, hours_worked) VALUES (?, ?, ?, ?, ?)',
                   (emp_id, entry_date, task_description, tasks_completed, hours_worked))
        flash('Work log submitted.', 'success')
        return redirect(url_for('worklog'))

    # GET: show last 30 work logs
    logs = query_db('SELECT * FROM WorkLogs WHERE employee_id = ? ORDER BY date DESC LIMIT 30', (emp_id,))
    return render_template('worklog.html', logs=logs)

@app.route('/salary', methods=['GET'])
@login_required
def salary():
    """Employee salary view route.

    Shows base salary, attendance bonus, performance bonus, and final salary.
    Uses the following formula:
      Final Salary = Base Salary + (Attendance Days × Attendance Bonus) + (Tasks Completed × Performance Bonus)
    """
    emp_id = current_user.employee_id
    # Fetch base salary
    emp_row = query_db('SELECT base_salary FROM Employees WHERE employee_id = ?', (emp_id,), one=True)
    base_salary = emp_row['base_salary'] if emp_row else 0.0

    # Calculate attendance days and tasks completed this month
    month_prefix = date.today().strftime('%Y-%m')
    rows = query_db('SELECT COUNT(DISTINCT date) AS days FROM Attendance WHERE employee_id = ? AND date LIKE ?', (emp_id, month_prefix + '%'), one=True)
    attendance_days = rows['days'] if rows else 0
    rows = query_db('SELECT SUM(tasks_completed) AS tasks FROM WorkLogs WHERE employee_id = ? AND date LIKE ?', (emp_id, month_prefix + '%'), one=True)
    tasks_completed = rows['tasks'] if rows and rows['tasks'] else 0

    attendance_bonus = attendance_days * ATTENDANCE_BONUS
    performance_bonus = tasks_completed * PERFORMANCE_BONUS
    final_salary = base_salary + attendance_bonus + performance_bonus

    return render_template('salary.html', base_salary=base_salary, attendance_days=attendance_days,
                           tasks_completed=tasks_completed, attendance_bonus=attendance_bonus,
                           performance_bonus=performance_bonus, final_salary=final_salary)

@app.route('/leave', methods=['GET', 'POST'])
@login_required
def leave():
    """Leave request page for employees.

    Employees can request leave; requests are stored with status 'Pending'.
    Admin actions are on a separate admin route to approve/reject.
    """
    emp_id = current_user.employee_id
    if request.method == 'POST':
        leave_date = request.form.get('leave_date')
        reason = request.form.get('reason')
        # Insert leave request with 'Pending' status
        execute_db('INSERT INTO LeaveRequests (employee_id, leave_date, reason, status) VALUES (?, ?, ?, ?)',
                   (emp_id, leave_date, reason, 'Pending'))
        flash('Leave request submitted.', 'success')
        return redirect(url_for('leave'))

    # GET: show user's leave requests
    requests_ = query_db('SELECT * FROM LeaveRequests WHERE employee_id = ? ORDER BY id DESC LIMIT 50', (emp_id,))
    return render_template('leave.html', requests=requests_)

# --------------------
# Admin routes
# --------------------
def admin_required(func):
    """Simple decorator to restrict routes to admin users.

    Checks `current_user.role` and redirects if not admin.
    """
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard route.

    Displays summary counts of employees, attendance records, work logs, and leave requests.
    """
    # Total employees
    rows = query_db('SELECT COUNT(*) AS cnt FROM Employees', (), one=True)
    total_employees = rows['cnt'] if rows else 0

    # Total attendance records
    rows = query_db('SELECT COUNT(*) AS cnt FROM Attendance', (), one=True)
    total_attendance = rows['cnt'] if rows else 0

    # Total work logs
    rows = query_db('SELECT COUNT(*) AS cnt FROM WorkLogs', (), one=True)
    total_worklogs = rows['cnt'] if rows else 0

    # Total leave requests
    rows = query_db('SELECT COUNT(*) AS cnt FROM LeaveRequests', (), one=True)
    total_leaves = rows['cnt'] if rows else 0

    return render_template('admin_dashboard.html', total_employees=total_employees,
                           total_attendance=total_attendance, total_worklogs=total_worklogs,
                           total_leaves=total_leaves)

@app.route('/employees')
@login_required
@admin_required
def employee_management():
    """Employee management page for admins.

    Shows a table of employees and provides links for add/edit/delete via forms.
    """
    employees = query_db('SELECT * FROM Employees ORDER BY id DESC')
    return render_template('employee_management.html', employees=employees)

@app.route('/employees/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_employee():
    """Admin route to add a new employee.

    Creates a new Employees row with hashed password.
    """
    if request.method == 'POST':
        employee_id = request.form.get('employee_id')
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        department = request.form.get('department')
        role = request.form.get('role')
        base_salary = float(request.form.get('base_salary') or 0.0)

        hashed = generate_password_hash(password)
        try:
            execute_db('INSERT INTO Employees (employee_id, name, email, password, department, role, base_salary) VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (employee_id, name, email, hashed, department, role, base_salary))
            flash('Employee added successfully.', 'success')
        except Exception as e:
            flash('Error adding employee: {}'.format(e), 'danger')
        return redirect(url_for('employee_management'))

    return render_template('add_employee.html')

@app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_employee(id):
    """Admin route to edit an existing employee by internal id."""
    row = query_db('SELECT * FROM Employees WHERE id = ?', (id,), one=True)
    if not row:
        flash('Employee not found.', 'danger')
        return redirect(url_for('employee_management'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        department = request.form.get('department')
        role = request.form.get('role')
        base_salary = float(request.form.get('base_salary') or 0.0)
        execute_db('UPDATE Employees SET name = ?, email = ?, department = ?, role = ?, base_salary = ? WHERE id = ?',
                   (name, email, department, role, base_salary, id))
        flash('Employee updated.', 'success')
        return redirect(url_for('employee_management'))

    return render_template('edit_employee.html', employee=row)

@app.route('/employees/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_employee(id):
    """Admin route to delete an employee by id."""
    execute_db('DELETE FROM Employees WHERE id = ?', (id,))
    flash('Employee deleted.', 'info')
    return redirect(url_for('employee_management'))

@app.route('/admin/leaves')
@login_required
@admin_required
def admin_leaves():
    """Admin view for leave requests where admin can approve or reject."""
    requests_ = query_db('SELECT * FROM LeaveRequests ORDER BY id DESC')
    return render_template('admin_leaves.html', requests=requests_)

@app.route('/admin/leaves/<int:id>/action', methods=['POST'])
@login_required
@admin_required
def leave_action(id):
    """Admin action route to approve or reject a leave request."""
    action = request.form.get('action')
    if action == 'approve':
        execute_db('UPDATE LeaveRequests SET status = ? WHERE id = ?', ('Approved', id))
        flash('Leave approved.', 'success')
    elif action == 'reject':
        execute_db('UPDATE LeaveRequests SET status = ? WHERE id = ?', ('Rejected', id))
        flash('Leave rejected.', 'warning')
    return redirect(url_for('admin_leaves'))

@app.route('/salary_report')
@login_required
@admin_required
def salary_report():
    """Admin salary report page.

    Aggregates attendance, work logs, and computes salary for each employee for
    the current month. Provides simple search via query param `q`.
    """
    q = request.args.get('q', '')
    month_prefix = date.today().strftime('%Y-%m')

    # Base query to fetch employees
    if q:
        employees = query_db('SELECT * FROM Employees WHERE name LIKE ? OR employee_id LIKE ? ORDER BY id DESC', ('%'+q+'%', '%'+q+'%'))
    else:
        employees = query_db('SELECT * FROM Employees ORDER BY id DESC')

    report = []
    # For each employee compute attendance days and tasks completed in current month
    for emp in employees:
        emp_id = emp['employee_id']
        rows = query_db('SELECT COUNT(DISTINCT date) AS days FROM Attendance WHERE employee_id = ? AND date LIKE ?', (emp_id, month_prefix + '%'), one=True)
        attendance_days = rows['days'] if rows else 0
        rows = query_db('SELECT SUM(tasks_completed) AS tasks FROM WorkLogs WHERE employee_id = ? AND date LIKE ?', (emp_id, month_prefix + '%'), one=True)
        tasks_completed = rows['tasks'] if rows and rows['tasks'] else 0
        final_salary = emp['base_salary'] + (attendance_days * ATTENDANCE_BONUS) + (tasks_completed * PERFORMANCE_BONUS)
        # Build report entry
        report.append({'employee': emp, 'attendance_days': attendance_days, 'tasks_completed': tasks_completed, 'final_salary': final_salary})

    return render_template('salary_report.html', report=report, query=q)

@app.route('/analytics')
@login_required
@admin_required
def analytics():
    """Analytics page route.

    Prepares datasets for Chart.js charts: attendance overview, tasks completed,
    department-wise counts, and top performers.
    """
    # Attendance overview: count attendance per day (last 30 days)
    rows = query_db('SELECT date, COUNT(*) AS cnt FROM Attendance GROUP BY date ORDER BY date DESC LIMIT 30')
    attendance_labels = [r['date'] for r in rows][::-1]
    attendance_data = [r['cnt'] for r in rows][::-1]

    # Tasks completed per day (last 30 days)
    rows = query_db('SELECT date, SUM(tasks_completed) AS tasks FROM WorkLogs GROUP BY date ORDER BY date DESC LIMIT 30')
    tasks_labels = [r['date'] for r in rows][::-1]
    tasks_data = [r['tasks'] if r['tasks'] else 0 for r in rows][::-1]

    # Department-wise employee count
    rows = query_db('SELECT department, COUNT(*) AS cnt FROM Employees GROUP BY department')
    dept_labels = [r['department'] for r in rows]
    dept_data = [r['cnt'] for r in rows]

    # Top performers (by total tasks completed)
    rows = query_db('SELECT employee_id, SUM(tasks_completed) AS tasks FROM WorkLogs GROUP BY employee_id ORDER BY tasks DESC LIMIT 5')
    top_labels = []
    top_data = []
    for r in rows:
        emp_row = query_db('SELECT name FROM Employees WHERE employee_id = ?', (r['employee_id'],), one=True)
        top_labels.append(emp_row['name'] if emp_row else r['employee_id'])
        top_data.append(r['tasks'] if r['tasks'] else 0)

    return render_template('analytics.html',
                           attendance_labels=attendance_labels, attendance_data=attendance_data,
                           tasks_labels=tasks_labels, tasks_data=tasks_data,
                           dept_labels=dept_labels, dept_data=dept_data,
                           top_labels=top_labels, top_data=top_data)

# --------------------
# Run app
# --------------------
if __name__ == '__main__':
    # Run Flask development server
    app.run(debug=True)
