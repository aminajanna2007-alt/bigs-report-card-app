import psycopg2
import os
import streamlit as st
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", os.environ.get("DB_URL", "")))


class PgCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, *args, **kwargs):
        self._cursor.execute(query, *args, **kwargs)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()
        
    def __getattr__(self, name):
         return getattr(self._cursor, name)

class PgConnectionWrapper:
    def __init__(self, dsn):
        self.conn = psycopg2.connect(dsn)

    def cursor(self):
        return PgCursorWrapper(self.conn.cursor())

    def execute(self, query, *args, **kwargs):
        cur = self.cursor()
        cur.execute(query, *args, **kwargs)
        return cur

    def commit(self):
        self.conn.commit()
        
    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()
        
    # Some pandas operations or external libraries might need the raw connection
    @property
    def raw(self):
        return self.conn

def get_connection():
    return PgConnectionWrapper(DB_URL)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL,
        dashboard_page TEXT,
        is_active INTEGER DEFAULT 1,
        theme TEXT DEFAULT 'Light'
    )''')
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'Light'")
    except psycopg2.Error:
        conn.rollback()

    c.execute('''CREATE TABLE IF NOT EXISTS grades (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS subjects (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        te_max_marks REAL DEFAULT 100,
        ce_max_marks REAL DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS grade_scales (
        id SERIAL PRIMARY KEY,
        grade_label TEXT NOT NULL,
        min_pct REAL NOT NULL,
        max_pct REAL NOT NULL,
        grade_id INTEGER REFERENCES grades(id),
        UNIQUE(grade_label, min_pct, max_pct)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS skill_scores (
        score INTEGER PRIMARY KEY,
        remark TEXT NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id SERIAL PRIMARY KEY,
        admission_no TEXT UNIQUE,
        name TEXT NOT NULL,
        grade_id INTEGER,
        parent_signature_path TEXT,
        FOREIGN KEY (grade_id) REFERENCES grades(id) ON DELETE SET NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_assignments (
        id SERIAL PRIMARY KEY,
        username TEXT NOT NULL,
        grade_id INTEGER,
        subject_id INTEGER,
        FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
        FOREIGN KEY (grade_id) REFERENCES grades(id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS marks (
        id SERIAL PRIMARY KEY,
        student_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        te_score REAL DEFAULT 0,
        ce_score REAL DEFAULT 0,
        remarks TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
        UNIQUE(student_id, subject_id)
    )''')
    
    try:
        c.execute("ALTER TABLE marks ADD COLUMN remarks TEXT")
    except psycopg2.Error:
        conn.rollback()

    c.execute('''CREATE TABLE IF NOT EXISTS student_skills (
        student_id INTEGER NOT NULL,
        skill_name TEXT NOT NULL,
        score INTEGER,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        PRIMARY KEY (student_id, skill_name)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS student_remarks (
        student_id INTEGER PRIMARY KEY,
        remark TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS subject_grade_config (
        id SERIAL PRIMARY KEY,
        subject_id INTEGER NOT NULL,
        grade_id INTEGER NOT NULL,
        te_max_marks REAL DEFAULT 100,
        ce_max_marks REAL DEFAULT 0,
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
        FOREIGN KEY (grade_id) REFERENCES grades(id) ON DELETE CASCADE,
        UNIQUE(subject_id, grade_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS report_backgrounds (
        id SERIAL PRIMARY KEY,
        filename TEXT NOT NULL
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS grade_backgrounds (
        grade_id INTEGER PRIMARY KEY,
        background_id INTEGER NOT NULL,
        FOREIGN KEY (grade_id) REFERENCES grades(id) ON DELETE CASCADE,
        FOREIGN KEY (background_id) REFERENCES report_backgrounds(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        key TEXT PRIMARY KEY,
        file_path TEXT
    )''')
    
    try:
        c.execute("ALTER TABLE grades ADD COLUMN class_teacher_sign_path TEXT")
    except psycopg2.Error:
        conn.rollback()
        
    try:
        c.execute("ALTER TABLE students ADD COLUMN parent_signature_path TEXT")
    except psycopg2.Error:
        conn.rollback()
        
    try:
        c.execute("ALTER TABLE grade_scales ADD COLUMN grade_id INTEGER REFERENCES grades(id)")
    except psycopg2.Error:
        conn.rollback()

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
