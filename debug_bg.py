import database
import pandas as pd

def run():
    conn = database.get_connection()
    
    print("REPORT BACKGROUNDS:")
    try:
        print(pd.read_sql("SELECT * FROM report_backgrounds", conn))
    except Exception as e:
        print(e)
        
    print("\nGRADE BACKGROUNDS (Raw):")
    try:
        print(pd.read_sql("SELECT * FROM grade_backgrounds", conn))
    except Exception as e:
        print(e)
        
    print("\nJOIN QUERY:")
    try:
        q = """
            SELECT g.name as Grade, b.filename as Background
            FROM grade_backgrounds gb
            JOIN grades g ON gb.grade_id = g.id
            JOIN report_backgrounds b ON gb.background_id = b.id
        """
        print(pd.read_sql(q, conn))
    except Exception as e:
        print(e)

    conn.close()

if __name__ == "__main__":
    run()
