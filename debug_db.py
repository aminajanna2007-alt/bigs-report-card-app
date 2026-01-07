import database
import pandas as pd
import sqlite3

def run():
    conn = database.get_connection()
    
    print("GRADES TABLE:")
    try:
        df_g = pd.read_sql("SELECT * FROM grades", conn)
        print(df_g)
    except Exception as e:
        print(e)
        
    print("\nSTUDENT COUNTS PER GRADE ID:")
    try:
        df_s = pd.read_sql("SELECT grade_id, count(*) as count FROM students GROUP BY grade_id", conn)
        print(df_s)
    except Exception as e:
        print(e)
        
    print("\nUSER ASSIGNMENTS for 'nadasaj':")
    try:
        df_u = pd.read_sql("SELECT ua.grade_id, g.name FROM user_assignments ua JOIN grades g ON ua.grade_id = g.id WHERE username='nadasaj'", conn)
        print(df_u)
    except Exception as e:
        print(e)
        
    conn.close()

if __name__ == "__main__":
    run()
