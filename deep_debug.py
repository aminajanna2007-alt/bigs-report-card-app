import database
import pandas as pd

def deep_check():
    conn = database.get_connection()
    try:
        print("--- SUBJECTS CHECK ---")
        subs = pd.read_sql("SELECT * FROM subjects WHERE name = 'IT'", conn)
        print(subs)
        
        if subs.empty:
            print("CRITICAL: Subject 'IT' not found!")
            return
            
        it_id = subs.iloc[0]['id']
        print(f"Using IT Subject ID: {it_id}")

        print("\n--- MARKS CHECK (All IT Marks) ---")
        # Show all marks for IT to see if ANY exist
        it_marks = pd.read_sql("SELECT * FROM marks WHERE subject_id = ?", conn, params=(it_id,))
        print(f"Total IT Marks entries found: {len(it_marks)}")
        print(it_marks.head())
        
        print("\n--- STUDENT 64 SPECIFIC ---")
        sid = 64
        m64 = pd.read_sql("SELECT * FROM marks WHERE student_id = ? AND subject_id = ?", conn, params=(sid, it_id))
        print(f"Marks for Aliya (ID 64) in IT (ID {it_id}):")
        print(m64)
        
        # Check if saved to WRONG subject?
        print("\n--- ALL MARKS FOR ALIYA (ID 64) ---")
        all_m = pd.read_sql("""
            SELECT m.*, s.name as SubName 
            FROM marks m 
            JOIN subjects s ON m.subject_id = s.id 
            WHERE m.student_id = ?
        """, conn, params=(sid,))
        print(all_m)

    finally:
        conn.close()

if __name__ == "__main__":
    deep_check()
