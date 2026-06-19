import sqlite3
from werkzeug.security import generate_password_hash
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASE_DIR, 'database', 'employee.db')

if not os.path.exists(DB_PATH):
    print('Database not found at', DB_PATH)
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

updates = [
    ('ADMIN01', 'adminpass'),
    ('EMP001', 'employeepass'),
]

for emp_id, plain in updates:
    new_hash = generate_password_hash(plain, method='pbkdf2:sha256')
    cur.execute('UPDATE Employees SET password = ? WHERE employee_id = ?', (new_hash, emp_id))
    print(f'Updated password for {emp_id}')

conn.commit()
conn.close()
print('Done')
