import sqlite3
import os
from flask import g, current_app

def get_db_path():
    """Returns the absolute path to the SQLite database file in the instance directory."""
    if current_app and current_app.config.get('DATABASE'):
        return current_app.config['DATABASE']
    if current_app:
        instance_path = current_app.instance_path
    else:
        # Fallback when running standalone scripts
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        instance_path = os.path.join(base_dir, 'instance')
    
    os.makedirs(instance_path, exist_ok=True)
    return os.path.join(instance_path, 'smart_lab.sqlite3')

def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if 'db' not in g:
        db_path = get_db_path()
        g.db = sqlite3.connect(db_path)
        # Enable column access by name
        g.db.row_factory = sqlite3.Row
        # Enable foreign key constraint checks
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db

def close_db(e=None):
    """Closes the database again at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(app=None):
    """Initializes the database schema using schema.sql."""
    db_path = get_db_path() if app is None else os.path.join(app.instance_path, 'smart_lab.sqlite3')
    if app:
        os.makedirs(app.instance_path, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
    with open(schema_path, 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    """Executes a parameterized query and returns all rows (or one row)."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=(), commit=True):
    """Executes a parameterized INSERT, UPDATE, or DELETE query."""
    db = get_db()
    cur = db.execute(query, args)
    if commit:
        db.commit()
    last_id = cur.lastrowid
    row_count = cur.rowcount
    cur.close()
    return last_id, row_count

def has_unresolved_computer_issues(computer_id):
    """
    Checks if a computer has any open complaints (Pending, In Progress).
    Returns (has_issues: bool, reason: str).
    """
    open_complaints = query_db(
        "SELECT id, title, status FROM complaints WHERE computer_id = ? AND status IN ('Pending', 'In Progress')",
        (computer_id,)
    )
    if open_complaints:
        titles = ", ".join([f"#{c['id']} ({c['title']})" for c in open_complaints])
        return True, f"Computer has {len(open_complaints)} unresolved complaint(s): {titles}"
    return False, ""
