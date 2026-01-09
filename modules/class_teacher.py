import streamlit as st
import pandas as pd
import database
import modules.reports as reports
import os

def app():
    st.header("Class Teacher Dashboard")
    
    # Identify user and assigned grades
    user = st.session_state.user['username']
    
    conn = database.get_connection()
    q = """
    SELECT distinct g.id, g.name 
    FROM user_assignments ua
    JOIN grades g ON ua.grade_id = g.id
    WHERE ua.username = ?
    """
    grades = pd.read_sql(q, conn, params=(user,))
    conn.close()
    
    if grades.empty:
        st.warning("No grades assigned to you.")
        return

    # Select Class/Grade
    sel_grade_name = st.selectbox("Select Class / Grade", grades['name'].tolist())
    grade_id = int(grades[grades['name'] == sel_grade_name]['id'].values[0])

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📝 Marks Entry", "🧠 Skills & Remarks", "📄 Generate Reports"])
    
    # --------------------------------------------------------------------------------
    # TAB 1: MARKS ENTRY (Mirrors Teacher Dashboard)
    # --------------------------------------------------------------------------------
    with tab1:
        st.subheader(f"Enter Subject Marks - {sel_grade_name}")
        
        # Filter options
        # Restricted to Assigned Subjects only as per request
        conn = database.get_connection()
        
        # Fetch only assigned subjects for this grade
        # Marks Entry is allowed for assigned subjects (Role 3)
        q_as = """
        SELECT s.id, s.name 
        FROM user_assignments ua
        JOIN subjects s ON ua.subject_id = s.id
        WHERE ua.username = ? AND ua.grade_id = ?
        ORDER BY s.name
        """
        subjs_df = pd.read_sql(q_as, conn, params=(user, grade_id))
            
        conn.close()
        
        if subjs_df.empty:
            st.warning("No subjects assigned to you for this Class.")
        else:
            sel_subj_name = st.selectbox("Select Subject", subjs_df['name'].tolist())
            
            if sel_subj_name:
                subj_id = subjs_df[subjs_df['name'] == sel_subj_name]['id'].values[0]
                
                # Fetch Max Marks (Grade Specific > Subject Default)
                conn = database.get_connection()
                lim_res = conn.execute("SELECT te_max_marks, ce_max_marks FROM subject_grade_config WHERE subject_id=? AND grade_id=?", (int(subj_id), int(grade_id))).fetchone()
                if lim_res:
                    te_max, ce_max = lim_res
                else:
                    s_def = conn.execute("SELECT te_max_marks, ce_max_marks FROM subjects WHERE id=?", (int(subj_id),)).fetchone()
                    te_max, ce_max = s_def if s_def else (100.0, 0.0)
                
                st.write(f"Entering Marks for **{sel_subj_name}** in **{sel_grade_name}** (Max TE: {te_max}, Max CE: {ce_max})")
                
                # Fetch Students + Marks
                q_st = "SELECT id, name, admission_no FROM students WHERE grade_id=? ORDER BY name"
                students_df = pd.read_sql(q_st, conn, params=(grade_id,))
                
                if not students_df.empty:
                    # Fetch Existing Marks
                    q_m = "SELECT student_id, te_score, ce_score, remarks FROM marks WHERE subject_id=?"
                    marks_df = pd.read_sql(q_m, conn, params=(subj_id,))
                    
                    # Merge
                    merged = pd.merge(students_df, marks_df, left_on='id', right_on='student_id', how='left')
                    
                    # Prepare editor df
                    editor_df = merged[['id', 'name', 'admission_no', 'te_score', 'ce_score', 'remarks']].copy()
                    editor_df.rename(columns={'id': 'student_id', 'remarks': 'Remarks'}, inplace=True)
                    
                    # Data Editor
                    edited_df = st.data_editor(
                        editor_df,
                        key=f"ct_marks_{grade_id}_{subj_id}",
                        disabled=["student_id", "name", "admission_no"],
                        column_config={
                            "te_score": st.column_config.NumberColumn("TE Score", min_value=0.0, max_value=float(te_max), step=0.5, format="%.1f"),
                            "ce_score": st.column_config.NumberColumn("CE Score", min_value=0.0, max_value=float(ce_max), step=0.5, format="%.1f"),
                            "Remarks": st.column_config.TextColumn("Remarks", width="large")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    if st.button("Save Marks", key=f"save_marks_{subj_id}"):
                        conn = database.get_connection()
                        try:
                            # DEBUG: Verify what is being saved
                            # st.write(f"Saving Marks for Subject ID: {subj_id} (Grade: {grade_id})")
                            debug_saved_count = 0
                            
                            for idx, row in edited_df.iterrows():
                                sid = row['student_id']
                                te = row.get('te_score')
                                ce = row.get('ce_score')
                                rem = row.get('Remarks')
                                
                                # Diagnostic print
                                # st.write(f"Processing Student {sid}: TE={te}, CE={ce}, Rem={rem}")
                                
                                val_te = te if pd.notna(te) else None
                                val_ce = ce if pd.notna(ce) else None
                                val_rem = rem if pd.notna(rem) else ""
                                
                                conn.execute("""
                                    INSERT INTO marks (student_id, subject_id, te_score, ce_score, remarks)
                                    VALUES (?, ?, ?, ?, ?)
                                    ON CONFLICT(student_id, subject_id) DO UPDATE SET
                                        te_score=excluded.te_score,
                                        ce_score=excluded.ce_score,
                                        remarks=excluded.remarks
                                """, (sid, subj_id, val_te, val_ce, val_rem))
                                debug_saved_count += 1
                                
                            conn.commit()
                            st.success(f"Marks saved for {sel_subj_name}! ({debug_saved_count} records)")
                            st.cache_data.clear()
                        except Exception as e:
                            st.error(f"Error saving marks: {e}")
                        finally:
                            conn.close()
                else:
                    st.warning("No students in this grade.")
                conn.close()

    # --------------------------------------------------------------------------------
    # TAB 2: SKILLS & REMARKS (Matrix View)
    # --------------------------------------------------------------------------------
    # Determine if Class Teacher for selected grade
    # Role 1 & 2: Skills and Reports -> Only for Class Teacher assigned grades
    conn = database.get_connection()
    is_ct = conn.execute("SELECT 1 FROM user_assignments WHERE username=? AND grade_id=? AND subject_id=-1", (user, grade_id)).fetchone()
    conn.close()

    # --------------------------------------------------------------------------------
    # TAB 2: SKILLS & REMARKS (Matrix View)
    # --------------------------------------------------------------------------------
    with tab2:
        if not is_ct:
             st.info(f"You are not the Class Teacher for {sel_grade_name}. Skills & Remarks are restricted.")
        else:
            st.subheader(f"Skills & Work Habits - {sel_grade_name}")
            
            # User Defined Skills
            skill_cols = ["Remembering", "Understanding", "Applying", "Regularity & Punctuality", "Neatness & Orderliness"]
            
            conn = database.get_connection()
            students = pd.read_sql("SELECT id, name, admission_no FROM students WHERE grade_id=? ORDER BY name", conn, params=(grade_id,))
            
            if students.empty:
                st.info("No students in this class.")
                conn.close()
            else:
                # Fetch Existing Data
                # Skills
                skills_df = pd.read_sql("SELECT student_id, skill_name, score FROM student_skills WHERE student_id IN (SELECT id FROM students WHERE grade_id=?)", conn, params=(grade_id,))
                # Remarks
                rem_df = pd.read_sql("SELECT student_id, remark FROM student_remarks WHERE student_id IN (SELECT id FROM students WHERE grade_id=?)", conn, params=(grade_id,))
                conn.close()
            
            # Build Editor Data
            data = []
            for _, stud in students.iterrows():
                sid = stud['id']
                row = {"Student ID": sid, "Student Name": stud['name']}
                
                # Fill skills
                for sc in skill_cols:
                    match = skills_df[(skills_df['student_id'] == sid) & (skills_df['skill_name'] == sc)]
                    row[sc] = int(match['score'].values[0]) if not match.empty else None
                
                # Fill remark
                rem_match = rem_df[rem_df['student_id'] == sid]
                row["Class Teacher's Remarks"] = rem_match['remark'].values[0] if not rem_match.empty else ""
                
                data.append(row)
            
            df_edit = pd.DataFrame(data)
            
            # Configure Layout
            column_config = {
                "Student ID": st.column_config.NumberColumn(disabled=True),
                "Student Name": st.column_config.TextColumn(disabled=True),
                "Class Teacher's Remarks": st.column_config.TextColumn("Class Teacher's Remarks", width="medium")
            }
            # 1-4 Score Config
            for sc in skill_cols:
                column_config[sc] = st.column_config.NumberColumn(
                    sc, 
                    min_value=1, 
                    max_value=4, 
                    step=1,
                    help="1=Beginning, 2=Progressing, 3=Accomplished, 4=Outstanding"
                )
            
            st.markdown("*Enter scores (1-4).*")
            edited_matrix = st.data_editor(
                df_edit, 
                column_config=column_config, 
                hide_index=True, 
                use_container_width=True, 
                key=f"skills_editor_{grade_id}"
            )
            
            if st.button("Save Skills & Remarks"):
                conn = database.get_connection()
                try:
                    for _, row in edited_matrix.iterrows():
                        sid = row['Student ID']
                        
                        # Save Skills
                        for sc in skill_cols:
                            val = row.get(sc)
                            if pd.notna(val):
                                conn.execute("INSERT OR REPLACE INTO student_skills (student_id, skill_name, score) VALUES (?, ?, ?)", (sid, sc, int(val)))
                        
                        # Save Remark
                        rem = row.get("Class Teacher's Remarks")
                        # Always save remark even if empty string (to clear if deleted) -> merge logic handles non-null
                        conn.execute("INSERT OR REPLACE INTO student_remarks (student_id, remark) VALUES (?, ?)", (sid, rem if rem else ""))
                            
                    conn.commit()
                    st.success("Skills & Remarks saved successfully!")
                except Exception as e:
                    st.error(f"Error saving: {e}")
                finally:
                    conn.close()

    # --------------------------------------------------------------------------------
    # TAB 3: GENERATE REPORTS (Bulk)
    # --------------------------------------------------------------------------------
    with tab3:
        if not is_ct:
             st.info(f"You are not the Class Teacher for {sel_grade_name}. Report generation is restricted.")
        else:
            st.subheader(f"Generate Reports for {sel_grade_name}")
        
        fmt = st.multiselect("Output Format", ["PDF", "JPG"], default=["PDF"])
        
        conn = database.get_connection()
        s_df = pd.read_sql("SELECT id, name, admission_no, parent_signature_path FROM students WHERE grade_id=? ORDER BY name", conn, params=(grade_id,))
        
        # Grade specific assets
        g_info = conn.execute("SELECT class_teacher_sign_path FROM grades WHERE id=?", (grade_id,)).fetchone()
        ct_sign_path = g_info[0] if g_info else None
        
        # Background
        # Fetch background assigned to this grade
        bg_row = conn.execute("""
            SELECT rb.filename 
            FROM grade_backgrounds gb
            JOIN report_backgrounds rb ON gb.background_id = rb.id
            WHERE gb.grade_id = ?
        """, (grade_id,)).fetchone()
        bg_img = bg_row[0] if bg_row and os.path.exists(bg_row[0]) else None

        conn.close()
        
        if s_df.empty:
            st.warning("No students found.")
        else:
            # Bulk Selection
            col_sel1, col_sel2 = st.columns([1, 4])
            with col_sel1:
                select_all = st.checkbox("Select All Students", value=False)
            
            default_sel = s_df['name'].tolist() if select_all else []
            
            sel_students = st.multiselect("Select Students", s_df['name'].tolist(), default=default_sel)
            
            if st.button("Generate Reports", type="primary"):
                if not sel_students or not fmt:
                    st.warning("Please select students and output format.")
                else:
                    target_df = s_df[s_df['name'].isin(sel_students)]
                    
                    with st.spinner("Generating Reports..."):
                        import pdf_generator
                        import zipfile
                        import io
                        
                        conn = database.get_connection()
                        # Global signatures/images
                        p_sign = "principal_sign.png" if os.path.exists("principal_sign.png") else None
                        # We use BG image now, but keep header fallback if needed in adapter? 
                        # Adapter handles fallback to frame if bg_img is None.
                        
                        # Renaming for PDF Generator compatibility (Min/Max/Grade)
                        gs = pd.read_sql("SELECT min_pct as Min, max_pct as Max, grade_label as Grade FROM grade_scales", conn)
                        grade_scales = gs.to_dict('records')
                        
                        zip_buffer = io.BytesIO()
                        has_files = False
                        
                        with zipfile.ZipFile(zip_buffer, "w") as zf:
                            for _, stud in target_df.iterrows():
                                sid = stud['id']
                                sname = stud['name']
                                adm = stud['admission_no'] # used for filename
                                par_sign = stud['parent_signature_path']
                                
                                # Marks (with Max Marks) - Left Join on Configured Subjects (MATCH BY NAME to fix ID Mismatch)
                                q_marks = """
                                    SELECT sub.name as subject, 
                                           m_linked.te_score, m_linked.ce_score, m_linked.remarks,
                                           COALESCE(sc.te_max_marks, 100) as t_max,
                                           COALESCE(sc.ce_max_marks, 0) as c_max
                                    FROM subjects sub
                                    JOIN subject_grade_config sc ON sub.id = sc.subject_id
                                    LEFT JOIN (
                                        SELECT m.te_score, m.ce_score, m.remarks, s_actual.name as subj_name, m.student_id
                                        FROM marks m
                                        JOIN subjects s_actual ON m.subject_id = s_actual.id
                                    ) m_linked ON UPPER(TRIM(sub.name)) = UPPER(TRIM(m_linked.subj_name)) AND m_linked.student_id = ?
                                    WHERE sc.grade_id = ?
                                    ORDER BY sub.name
                                """
                                m_rows = pd.read_sql(q_marks, conn, params=(sid, grade_id)).to_dict('records')
                                
                                marks_data = []
                                for r in m_rows:
                                    # Handle Nulls - Pass None if data is missing so PDF gen can skip calculation
                                    te = r['te_score'] if pd.notna(r['te_score']) else None
                                    ce = r['ce_score'] if pd.notna(r['ce_score']) else None
                                    t_max = r['t_max']
                                    c_max = r['c_max']
                                    rem = r['remarks'] if pd.notna(r['remarks']) else ""
                                    
                                    marks_data.append({
                                        "Subject": r['subject'],
                                        "TE": te,
                                        "CE": ce,
                                        "Full_Marks": t_max + c_max,
                                        "Remarks": rem
                                    })
                                
                                # Skills
                                q_skills = "SELECT skill_name, score FROM student_skills WHERE student_id=?"
                                skills_data = pd.read_sql(q_skills, conn, params=(sid,)).to_dict('records')
                                
                                # Teacher Remark
                                rem_rec = conn.execute("SELECT remark FROM student_remarks WHERE student_id=?", (sid,)).fetchone()
                                remark = rem_rec[0] if rem_rec else ""
                                
                                pdf_bytes = pdf_generator.create_report_card_bytes(
                                    student_name=sname,
                                    student_grade=sel_grade_name,
                                    subjects_scores=marks_data,
                                    skills_scores=skills_data,
                                    teacher_comments=remark,
                                    prepared_by=st.session_state.user['full_name'],
                                    header_img_path=None, # Deprecated
                                    footer_img_path=None, # Deprecated
                                    grade_scales=grade_scales,
                                    principal_sign_path=p_sign,
                                    parent_sign_path=par_sign,
                                    class_teacher_sign_path=ct_sign_path,
                                    background_img_path=bg_img
                                )
                                
                                if pdf_bytes:
                                    clean_name = f"{sname}_{adm}".replace(" ", "_")
                                    if "PDF" in fmt:
                                        zf.writestr(f"{clean_name}.pdf", pdf_bytes)
                                    if "JPG" in fmt:
                                        try:
                                            jpg_bytes = pdf_generator.pdf_to_jpg_bytes(pdf_bytes)
                                            zf.writestr(f"{clean_name}.jpg", jpg_bytes)
                                        except:
                                            pass
                                    has_files = True
                        
                        conn.close()
                        
                        if has_files:
                            st.success(f"Reports Ready for {len(sel_students)} students!")
                            st.download_button(
                                label="Download Reports (ZIP)",
                                data=zip_buffer.getvalue(),
                                file_name=f"Reports_{sel_grade_name}_{pd.Timestamp.now().strftime('%Y%m%d')}.zip",
                                mime="application/zip"
                            )
                        else:
                            st.error("No reports generated (check data).")
