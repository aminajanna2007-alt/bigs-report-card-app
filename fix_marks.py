import database
import pandas as pd

def fix_blob_marks():
    conn = database.get_connection()
    try:
        # Check Aliya ID 64
        sid = 64
        # Target Subject IT (23)
        subj_id = 23
        
        print("Checking for duplicate entries (BLOB vs INT)...")
        # 1. Delete STALE integer entry if it exists (Score 33.0)
        # Verify it's the 33.0 one
        dup_check = conn.execute("SELECT id, te_score FROM marks WHERE student_id=? AND subject_id=?", (sid, subj_id)).fetchone()
        if dup_check:
            print(f"Found existing INTEGER entry: ID {dup_check[0]}, Score {dup_check[1]}")
            conn.execute("DELETE FROM marks WHERE id=?", (dup_check[0],))
            print("Deleted existing INTEGER entry.")
            
        # 2. Find BLOB entry and UPDATE it to Integer 23
        # BLOBs can't always be queried easily by value if we don't know exact bytes, but we know it's NOT integer 23.
        # We can query by student_id and exclude known subjects.
        # Or blindly update where typeof is blob?
        # Safe way: Select all marks for student, iterate, check type/value.
        
        all_marks = conn.execute("SELECT id, subject_id, te_score FROM marks WHERE student_id=?", (sid,)).fetchall()
        for row in all_marks:
            mid, s_id, score = row
            if isinstance(s_id, bytes):
                print(f"Found BLOB entry: ID {mid}, Score {score}")
                # Update it
                conn.execute("UPDATE marks SET subject_id=? WHERE id=?", (subj_id, mid))
                print(f"Updated ID {mid} to subject_id {subj_id}")
                
        conn.commit()
        print("Fix applied successfully.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_blob_marks()
