import streamlit as st
import pandas as pd
import database
import modules.reports as reports
import os

def app():
    st.header("Principal Dashboard")
    st.markdown("### School-Wide Reports")
    
    # Principal Dashboard Logic
    
    # 1. Configuration / Scope Selection
    st.info("Generate Reports for the School")
    
    scope = st.radio("Select Scope", ["Single Grade / Specific Students", "All Grades (Bulk)"], horizontal=True)
    fmt = st.multiselect("Output Format", ["PDF", "JPG"], default=["PDF"])
    
    target_students = [] # List of dicts {id, name, admission_no, grade_id, grade_name, parent_sign}
    
    conn = database.get_connection()
    
    if scope == "Single Grade / Specific Students":
        grades = pd.read_sql("SELECT id, name FROM grades", conn)
        sel_grade_name = st.selectbox("Select Grade", grades['name'].tolist())
        
        if sel_grade_name:
            gid = grades[grades['name'] == sel_grade_name]['id'].values[0]
            # Fetch students
            q_s = "SELECT id, name, admission_no, grade_id, parent_signature_path FROM students WHERE grade_id=? ORDER BY name"
            students_df = pd.read_sql(q_s, conn, params=(gid,))
            
            sel_students = st.multiselect("Select Students (Leave empty for All in Grade)", students_df['name'].tolist(), default=students_df['name'].tolist())
            
            if sel_students:
                 # Filter
                 filtered = students_df[students_df['name'].isin(sel_students)]
                 # Add grade name
                 filtered['grade_name'] = sel_grade_name
                 target_students = filtered.to_dict('records')
            else:
                 students_df['grade_name'] = sel_grade_name
                 target_students = students_df.to_dict('records')

    else:
        # All Grades
        st.warning("This will generate reports for ALL students in the school.")
        if st.checkbox("Confirm Bulk Generation"):
            q_all = """
            SELECT s.id, s.name, s.admission_no, s.grade_id, s.parent_signature_path, g.name as grade_name
            FROM students s
            JOIN grades g ON s.grade_id = g.id
            ORDER BY g.name, s.name
            """
            target_students = pd.read_sql(q_all, conn).to_dict('records')
    
    # Fetch Global Data once
    p_sign = "principal_sign.png" if os.path.exists("principal_sign.png") else None
    top_img = "top.jpg" if os.path.exists("top.jpg") else None
    bottom_img = "bottom.jpg" if os.path.exists("bottom.jpg") else None
    
    gs = pd.read_sql("SELECT * FROM grade_scales", conn)
    grade_scales = gs.to_dict('records')
    
    # Fetch all grade signatures to a dict {grade_id: path}
    g_sigs = pd.read_sql("SELECT id, class_teacher_sign_path FROM grades", conn)
    ct_sigs_map = dict(zip(g_sigs['id'], g_sigs['class_teacher_sign_path']))
    
    conn.close()
    
    if st.button("Generate Reports", type="primary"):
        if not target_students:
            st.error("No students selected.")
            return
            
        if not fmt:
            st.error("Select output format.")
            return

        import pdf_generator
        import zipfile
        import io
        
        zip_buffer = io.BytesIO()
        has_files = False
        
        t_bar = st.progress(0)
        n = len(target_students)
        
        conn = database.get_connection() # Open new conn for loop queries
        
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for i, stud in enumerate(target_students):
                sid = stud['id']
                sname = stud['name']
                adm = stud['admission_no']
                gname = stud['grade_name']
                gid = stud['grade_id']
                par_sign = stud['parent_signature_path']
                ct_sign = ct_sigs_map.get(gid)
                
                # Marks
                q_marks = """
                    SELECT sub.name, m.te_score, m.ce_score, sub.te_max_marks, sub.ce_max_marks, m.remarks
                    FROM marks m
                    JOIN subjects sub ON m.subject_id = sub.id
                    WHERE m.student_id = ?
                """
                marks_data = pd.read_sql(q_marks, conn, params=(sid,)).to_dict('records')
                
                # Skills
                q_skills = "SELECT skill_name, score FROM student_skills WHERE student_id=?"
                skills_data = pd.read_sql(q_skills, conn, params=(sid,)).to_dict('records')
                
                # Remarks
                rem_rec = conn.execute("SELECT remark FROM student_remarks WHERE student_id=?", (sid,)).fetchone()
                remark = rem_rec[0] if rem_rec else ""
                
                pdf_bytes = pdf_generator.create_report_card_bytes(
                    student_name=sname,
                    student_grade=gname,
                    subjects_scores=marks_data,
                    skills_scores=skills_data,
                    teacher_comments=remark,
                    prepared_by="Principal",
                    header_img_path=top_img,
                    footer_img_path=bottom_img,
                    grade_scales=grade_scales,
                    principal_sign_path=p_sign,
                    parent_sign_path=par_sign,
                    class_teacher_sign_path=ct_sign
                )
                
                if pdf_bytes:
                    clean_name = f"{gname}/{sname}_{adm}".replace(" ", "_")
                    # Use hierarchy in zip?
                    # report_data/grade_x/reports...
                    # simple filename: Grade_Name.pdf
                    fname_base = f"{gname}_{sname}".replace(" ", "_")
                    
                    if "PDF" in fmt:
                        zf.writestr(f"{fname_base}.pdf", pdf_bytes)
                    if "JPG" in fmt:
                        try:
                            jpg_bytes = pdf_generator.pdf_to_jpg_bytes(pdf_bytes)
                            zf.writestr(f"{fname_base}.jpg", jpg_bytes)
                        except:
                            pass
                    has_files = True
                
                t_bar.progress((i + 1) / n)
        
        conn.close()
        
        if has_files:
            st.success("Reports Generated!")
            st.download_button("Download ZIP", zip_buffer.getvalue(), file_name="School_Reports.zip", mime="application/zip")
        else:
            st.error("No reports generated.")
