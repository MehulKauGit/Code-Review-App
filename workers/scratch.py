from workers.static import run_ruff, run_bandit, run_semgrep

content = """
import sqlite3

def get_user(username):
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE name = '" + username + "'")
    return cursor.fetchone()
"""

changed_lines = [1, 2, 3, 4, 5, 6, 7, 8]

print("=== RUFF ===")
for f in run_ruff("auth.py", content, changed_lines):
    print(f)

print("=== BANDIT ===")
for f in run_bandit("auth.py", content, changed_lines):
    print(f)

print("=== SEMGREP ===")
for f in run_semgrep("auth.py", content, changed_lines):
    print(f)