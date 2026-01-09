import sqlite3
import os

DB_NAME = "school_data.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Enable foreign keys
    c.execute("PRAGMA foreign_keys = ON;")

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
    
    # Auto-migration for existing tables
    try:
        c.execute("ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'Light'")
    except sqlite3.OperationalError:
        pass # Column likely exists

    # Default Admin (if not exists)
    # We will insert this in the main app startup if needed, but let's ensure table exists first.

    # Grades / Classes (e.g. "10State", "5A")
    c.execute('''CREATE TABLE IF NOT EXISTS grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )''')

    # Subjects
    c.execute('''CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        te_max_marks REAL DEFAULT 100,
        ce_max_marks REAL DEFAULT 0
    )''')
    
    # Grade Scale (e.g. "A1", "B1") - Global or per logic? User asked for "Create Grade Scale".
    # We'll store ranges.
    # Grade Scale (e.g. "A1", "B1")
    # Migration Check: Ensure grade_id exists and constraint is correct
    chk = c.execute("PRAGMA table_info(grade_scales)").fetchall()
    cols = [col[1] for col in chk]
    
    if 'grade_scales' in [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
        if 'grade_id' not in cols:
            # Migration needed
            try:
                c.execute("ALTER TABLE grade_scales RENAME TO grade_scales_old")
                c.execute('''CREATE TABLE grade_scales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grade_label TEXT NOT NULL,
                    min_pct REAL NOT NULL,
                    max_pct REAL NOT NULL,
                    grade_id INTEGER,
                    UNIQUE(grade_label, min_pct, max_pct, grade_id)
                )''')
                c.execute("INSERT INTO grade_scales (id, grade_label, min_pct, max_pct) SELECT id, grade_label, min_pct, max_pct FROM grade_scales_old")
                c.execute("DROP TABLE grade_scales_old")
            except Exception as e:
                pass # Already handled or error
    
    # Ensure creation if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS grade_scales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grade_label TEXT NOT NULL,
        min_pct REAL NOT NULL,
        max_pct REAL NOT NULL,
        grade_id INTEGER,
        UNIQUE(grade_label, min_pct, max_pct, grade_id)
    )''')

    # Skill Scores (1, 2, 3, 4) & Remarks
    c.execute('''CREATE TABLE IF NOT EXISTS skill_scores (
        score INTEGER PRIMARY KEY,
        remark TEXT NOT NULL
    )''')

    # Students
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admission_no TEXT UNIQUE,
        name TEXT NOT NULL,
        grade_id INTEGER,
        parent_signature_path TEXT,
        FOREIGN KEY (grade_id) REFERENCES grades(id) ON DELETE SET NULL
    )''')

    # Enrollments (if we need history, but current requirement implies simple current grade. 
    # For now, student.grade_id is sufficient for current enrollment.)

    # Subject Assignments (Which user teaches which subject for which grade?)
    # "Assign subjects to users", "Assign Grades to users"
    # A user (teacher) can be assigned multiple subjects and multiple grades.
    c.execute('''CREATE TABLE IF NOT EXISTS user_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        grade_id INTEGER,
        subject_id INTEGER,
        FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
        FOREIGN KEY (grade_id) REFERENCES grades(id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
    )''')
    # Use grade_id=NULL if assigned to a subject globally (unlikely) or subject_id=NULL if assigned to a grade (Class Teacher)

    # Marks
    c.execute('''CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        te_score REAL DEFAULT 0,
        ce_score REAL DEFAULT 0,
        remarks TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
        UNIQUE(student_id, subject_id)
    )''')
    
    # Marks
    c.execute('''CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    except sqlite3.OperationalError:
        pass

    # Skills Assessment
    c.execute('''CREATE TABLE IF NOT EXISTS student_skills (
        student_id INTEGER NOT NULL,
        skill_name TEXT NOT NULL,
        score INTEGER,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        PRIMARY KEY (student_id, skill_name)
    )''')
    
    # General Remarks (Class Teacher)
    c.execute('''CREATE TABLE IF NOT EXISTS student_remarks (
        student_id INTEGER PRIMARY KEY,
        remark TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )''')
    
    # Subject-Grade Configuration (Max Marks per Grade)
    c.execute('''CREATE TABLE IF NOT EXISTS subject_grade_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        grade_id INTEGER NOT NULL,
        te_max_marks REAL DEFAULT 100,
        ce_max_marks REAL DEFAULT 0,
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
        FOREIGN KEY (grade_id) REFERENCES grades(id) ON DELETE CASCADE,
        UNIQUE(subject_id, grade_id)
    )''')

    # Background Images
    c.execute('''CREATE TABLE IF NOT EXISTS report_backgrounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL
    )''')
    
    # Background Assignments (One Grade -> One BG, but BG -> Many Grades)
    # Actually, a grade should have only ONE background. So `grades` table could have `background_id`.
    # But user says "next to update image file, add option to assign multiple grades".
    # So `bg_assignments` table is flexible.
    # Constraint: A grade should only be in one assignment? Or we select strict mapping.
    # Let's use a mapping table `grade_backgrounds(grade_id PK, background_id)`.
    c.execute('''CREATE TABLE IF NOT EXISTS grade_backgrounds (
        grade_id INTEGER PRIMARY KEY,
        background_id INTEGER NOT NULL,
        FOREIGN KEY (grade_id) REFERENCES grades(id) ON DELETE CASCADE,
        FOREIGN KEY (background_id) REFERENCES report_backgrounds(id) ON DELETE CASCADE
    )''')

    # Signatures (Global)
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        key TEXT PRIMARY KEY,
        file_path TEXT
    )''')
    
    try:
        c.execute("ALTER TABLE grades ADD COLUMN class_teacher_sign_path TEXT")
    except sqlite3.OperationalError:
        pass
        
    try:
        c.execute("ALTER TABLE students ADD COLUMN parent_signature_path TEXT")
    except sqlite3.OperationalError:
        pass
        
    try:
        c.execute("ALTER TABLE grade_scales ADD COLUMN grade_id INTEGER REFERENCES grades(id)")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
