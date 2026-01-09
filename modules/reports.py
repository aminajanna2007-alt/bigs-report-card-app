import streamlit as st
import pandas as pd
import database
import pdf_generator
import os

def app():
    st.header("Report Generation Dashboard")
    
    if 'user' not in st.session_state:
        return
    
    user = st.session_state.user
    role = user['role']
    username = user['username']
    
    conn = database.get_connection()
    
    # DETERMINE ACCESSIBLE GRADES
    # Principal -> All Grades
    # Class Teacher -> Assigned Grades (we assumed "Assign Grades" means this)
    # Teacher -> Probably shouldn't generate official reports, but maybe draft? 
    # Req: "Generate reports... (for class teacher / principal)"
    
    if role == "Principal" or role == "Admin":
        grades_df = pd.read_sql("SELECT id, name FROM grades", conn)
    else:
        # Class Teacher
        # Get assigned grades
        q = """
        SELECT DISTINCT g.id, g.name 
        FROM user_assignments ua
        JOIN grades g ON ua.grade_id = g.id
        WHERE ua.username = ?
        """
        grades_df = pd.read_sql(q, conn, params=(username,))
    
    if grades_df.empty:
        st.warning("No grades assigned to you for report generation.")
        conn.close()
        return
        
    # SELECT GRADE
    grade_Ids = grades_df['id'].tolist()
    grade_Names = grades_df['name'].tolist()
    
    sel_grade_name = st.selectbox("Select Grade", grade_Names)
    sel_grade_id = grades_df[grades_df['name'] == sel_grade_name]['id'].values[0]
    
    # SELECT STUDENTS
    # "Generate reports of all or selected students"
    st_df = pd.read_sql("SELECT id, name, admission_no FROM students WHERE grade_id=? ORDER BY name", conn, params=(sel_grade_id,))
    
    all_students = st.checkbox("Select All Students", value=True)
    if all_students:
        sel_students = st_df['id'].tolist()
    else:
        selected_rows = st.multiselect("Select Students", st_df['name'].tolist())
        sel_students = st_df[st_df['name'].isin(selected_rows)]['id'].tolist()
        
    if st.button("Generate Reports"):
        if not sel_students:
            st.error("No students selected.")
        else:
            # PREPARE DATA
            # 1. Subject Scores
            # 2. Grade Scales
            # 3. Config (Signatures)
            
            # Fetch Grade Scales
            gs_df = pd.read_sql("SELECT min_pct, max_pct, grade_label, grade_label as comment FROM grade_scales ORDER BY min_pct DESC", conn) # using label as comment placeholder or empty
            # Refine grade scale list of dicts
            grade_scales = []
            for _, r in gs_df.iterrows():
                grade_scales.append({
                    'Min': r['min_pct'],
                    'Max': r['max_pct'],
                    'Grade': r['grade_label'],
                    'comment': "" 
                })
            
            # Signatures
            header_path = "top.jpg" if os.path.exists("top.jpg") else None
            footer_path = "bottom.jpg" if os.path.exists("bottom.jpg") else None
            
            count = 0
            
            # Progress bar
            progress_bar = st.progress(0)
            
            # ZIP preparation
            import zipfile
            zip_buffer = io.BytesIO() if len(sel_students) > 1 else None
            single_pdf = None
            single_name = ""
            
            with zipfile.ZipFile(zip_buffer, "w") if zip_buffer else io.BytesIO() as zf: # Dummy context for single
                for idx, sid in enumerate(sel_students):
                    # Student Info
                    s_info = st_df[st_df['id'] == sid].iloc[0]
                    s_name = s_info['name']
                    
                    # Fetch Marks
                    # Fetch Marks (Left Join on Configured Subjects - MATCH BY NAME to handle ID Drift)
                    # Use subject_grade_config as the definitive list of subjects for this grade
                    q_m = """
                    SELECT sub.name as subject, 
                           m_linked.te_score, m_linked.ce_score, m_linked.remarks,
                           COALESCE(sc.te_max_marks, 100) as te_max, 
                           COALESCE(sc.ce_max_marks, 0) as ce_max
                    FROM subjects sub
                    JOIN subject_grade_config sc ON sub.id = sc.subject_id
                    LEFT JOIN (
                        SELECT m.te_score, m.ce_score, m.remarks, s_actual.name as subj_name, m.student_id
                        FROM marks m
                        JOIN subjects s_actual ON m.subject_id = s_actual.id
                    ) m_linked ON sub.name = m_linked.subj_name AND m_linked.student_id = ?
                    WHERE sc.grade_id = ?
                    ORDER BY sub.name
                    """
                    # We need grade_id for the query. sel_grade_id is available.
                    marks_data = pd.read_sql(q_m, conn, params=(sid, sel_grade_id))
                    
                    subjects_scores = []
                    for _, row in marks_data.iterrows():
                        # Handle Nulls - Pass None if data is missing so PDF gen can skip calculation
                        te = row['te_score'] if pd.notna(row['te_score']) else None
                        ce = row['ce_score'] if pd.notna(row['ce_score']) else None
                        t_max = row['te_max']
                        c_max = row['ce_max']
                        rem = row['remarks'] if pd.notna(row['remarks']) else ""
                        
                        subjects_scores.append({
                            'Subject': row['subject'], # PDF Gen expects Subject
                            'TE': te,
                            'CE': ce,
                            'Full_Marks': t_max + c_max,
                            'Remarks': rem
                        })
                    
                    # Skills (Dummy for now as logic not fully detailed, or fetch from student_skills)
                    skills_scores = [
                        {'skill': 'Regularity', 'score': 4, 'remark': 'Outstanding'},
                        {'skill': 'Neatness', 'score': 3, 'remark': 'Good'}
                    ]
                    
                    teacher_comments = "Good progress." # Placeholder or from DB if we added it
                    
                    pdf_data = pdf_generator.create_report_card_bytes(
                        s_name,
                        sel_grade_name,
                        subjects_scores,
                        skills_scores,
                        teacher_comments,
                        prepared_by=user['full_name'],
                        header_img_path=header_path,
                        footer_img_path=footer_path,
                        grade_scales=grade_scales
                    )
                    
                    fname = f"{s_name.replace(' ', '_')}.pdf"
                    if zip_buffer:
                        zf.writestr(fname, pdf_data)
                    else:
                        single_pdf = pdf_data
                        single_name = fname
                    
                    count += 1
                    progress_bar.progress(count / len(sel_students))
            
            st.success(f"Generated {count} reports.")
            
            import io
            if zip_buffer:
                st.download_button("Download All (ZIP)", zip_buffer.getvalue(), "reports.zip", "application/zip")
            elif single_pdf:
                st.download_button(f"Download {single_name}", single_pdf, single_name, "application/pdf")
            
    conn.close()
