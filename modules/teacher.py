import streamlit as st
import pandas as pd
import database

def app():
    st.header("Teacher Dashboard")
    
    if 'user' not in st.session_state or not st.session_state.user:
        st.error("Please login.")
        return
        
    username = st.session_state.user['username']
    
    # FETCH ASSIGNMENTS
    conn = database.get_connection()
    # Get assigned grades and subjects
    # A teacher can enter marks for (Grade, Subject) pairs assigned to them.
    # Or if Class Teacher, maybe all subjects?
    # Req: "Marks entry permission of all or selected students, by selected grades (for teacher role)"
    # We implemented `user_assignments` table.
    
    q = """
    SELECT g.name as grade, s.name as subject, g.id as grade_id, s.id as subject_id
    FROM user_assignments ua
    JOIN grades g ON ua.grade_id = g.id
    JOIN subjects s ON ua.subject_id = s.id
    WHERE ua.username = ?
    """
    assigns = pd.read_sql(q, conn, params=(username,))
    
    if assigns.empty:
        st.info("No classes or subjects assigned to you. Please contact Admin.")
        conn.close()
        return

    # Select Grade
    grades_list = assigns['grade'].unique().tolist()
    sel_grade = st.selectbox("Select Class / Grade", grades_list)
    
    # Select Subject (filtered by grade)
    subjs_list = assigns[assigns['grade'] == sel_grade]['subject'].unique().tolist()
    sel_subj = st.selectbox("Select Subject", subjs_list)
    
    # Get IDs
    gid = assigns[assigns['grade'] == sel_grade]['grade_id'].values[0]
    sid = assigns[(assigns['grade'] == sel_grade) & (assigns['subject'] == sel_subj)]['subject_id'].values[0]
    
    # LOAD STUDENTS & MARKS
    # We want a table: Student Name, Admission No, TE Score, CE Score
    # We need to Left Join students with marks for this subject.
    
    # Fetch max marks for validation
    # Fetch max marks (Grade Specific > Global)
    lim_res = conn.execute("SELECT te_max_marks, ce_max_marks FROM subject_grade_config WHERE subject_id=? AND grade_id=?", (int(sid), int(gid))).fetchone()
    if lim_res:
        te_max, ce_max = lim_res
    else:
        subj_info = conn.execute("SELECT te_max_marks, ce_max_marks FROM subjects WHERE id=?", (int(sid),)).fetchone()
        te_max, ce_max = subj_info if subj_info else (100, 0)
    
    st.markdown(f"**Entering Marks for {sel_subj} in {sel_grade}** (Max TE: {te_max}, Max CE: {ce_max})")
    
    q_st = """
    SELECT s.id as student_id, s.name, s.admission_no, m.te_score, m.ce_score, m.remarks
    FROM students s
    LEFT JOIN marks m ON s.id = m.student_id AND m.subject_id = ?
    WHERE s.grade_id = ?
    ORDER BY s.name
    """
    df = pd.read_sql(q_st, conn, params=(int(sid), int(gid)))
    
    # Data Editor
    edited_df = st.data_editor(
        df,
        column_config={
            "student_id": st.column_config.NumberColumn(disabled=True),
            "name": st.column_config.TextColumn(disabled=True),
            "admission_no": st.column_config.TextColumn(disabled=True),
            "te_score": st.column_config.NumberColumn("TE Score", min_value=0, max_value=te_max, step=1, default=0),
            "ce_score": st.column_config.NumberColumn("CE Score", min_value=0, max_value=ce_max, step=1, default=0),
            "remarks": st.column_config.TextColumn("Remarks", width="medium")
        },
        hide_index=True,
        key="marks_editor"
    )
    
    if st.button("Save Marks"):
        c = conn.cursor()
        count = 0
        for _, row in edited_df.iterrows():
            stid = row['student_id']
            te = row.get('te_score', 0)
            ce = row.get('ce_score', 0)
            rem = row.get('remarks', "")
            
            # Fill NaNs
            if pd.isna(te): te = 0
            if pd.isna(ce): ce = 0
            if pd.isna(rem): rem = ""
            
            try:
                c.execute("""
                INSERT INTO marks (student_id, subject_id, te_score, ce_score, remarks)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(student_id, subject_id) DO UPDATE SET
                te_score=excluded.te_score,
                ce_score=excluded.ce_score,
                remarks=excluded.remarks
                """, (stid, int(sid), te, ce, rem))
                count += 1
            except Exception as e:
                st.error(f"Error saving for {row['name']}: {e}")
        
        conn.commit()
        st.success(f"Saved marks for {count} students.")
    
    conn.close()
