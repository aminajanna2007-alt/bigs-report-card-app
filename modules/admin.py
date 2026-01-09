import streamlit as st
import pandas as pd
import database
import auth
import sqlite3
import os

def app():
    st.header("Admin Dashboard")
    
    tabs = st.tabs(["👥 Users", "🏫 Academic Setup", "🎓 Students", "📝 Assignments", "⚙️ Configuration"])
    
    # --------------------------------------------------------------------------------
    # TAB 1: USER MANAGEMENT
    # --------------------------------------------------------------------------------
    # --------------------------------------------------------------------------------
    # TAB 1: USER MANAGEMENT
    # --------------------------------------------------------------------------------
    with tabs[0]:
        st.subheader("User Management")
        
        c1, c2 = st.columns([1, 2])
        
        # Helper to fetch grades for CT assignment
        conn = database.get_connection()
        grades_list = pd.read_sql("SELECT id, name FROM grades", conn)
        conn.close()
        
        with c1:
            st.markdown("### Create New User")
            u_fname = st.text_input("First Name")
            u_lname = st.text_input("Last Name")
            u_role = st.selectbox("Role", ["Admin", "Principal", "Class Teacher", "Teacher"])
            
            # CT Grade Selection Logic
            ct_grades = []
            if u_role == "Class Teacher":
                ct_grades = st.multiselect("Assign Grades", grades_list['name'].tolist())
            
            u_dash = st.selectbox("Dashboard Page", ["Admin Dashboard", "Principal Dashboard", "Class Teacher Dashboard", "Teacher Dashboard"], 
                                  index=["Admin Dashboard", "Principal Dashboard", "Class Teacher Dashboard", "Teacher Dashboard"].index(f"{u_role} Dashboard") if f"{u_role} Dashboard" in ["Admin Dashboard", "Principal Dashboard", "Class Teacher Dashboard", "Teacher Dashboard"] else 0)
            
            if st.button("Create User"):
                if not u_fname or not u_lname:
                    st.error("Name fields are required.")
                else:
                    gen_user = auth.generate_username(u_fname, u_lname)
                    gen_pass = auth.generate_password(u_fname, u_lname)
                    phash = auth.make_pbkdf2_hash(gen_pass)
                    full_name = f"{u_fname} {u_lname}".strip()
                    
                    conn = database.get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO users (username, password_hash, full_name, role, dashboard_page, theme) VALUES (?, ?, ?, ?, ?, ?)",
                                  (gen_user, phash, full_name, u_role, u_dash, 'Light'))
                        
                        # Handle CT Assignment
                        if u_role == "Class Teacher" and ct_grades:
                            gids = grades_list[grades_list['name'].isin(ct_grades)]['id'].tolist()
                            for gid in gids:
                                try:
                                    c.execute("INSERT INTO user_assignments (username, grade_id, subject_id) VALUES (?, ?, ?)", (gen_user, int(gid), -1))
                                except:
                                    pass
                        
                        conn.commit()
                        st.success(f"User Created!\nUsername: **{gen_user}**\nPassword: **{gen_pass}**")
                    except sqlite3.IntegrityError:
                        st.error(f"User '{gen_user}' already exists.")
                    conn.close()

            st.markdown("---")
            st.markdown("### Bulk Upload Users")
            upl_file = st.file_uploader("Upload CSV (First Name, Last Name, Role)", type=["csv"])
            if upl_file:
                if st.button("Process Bulk Upload"):
                    df = pd.read_csv(upl_file)
                    conn = database.get_connection()
                    c = conn.cursor()
                    created = []
                    for _, row in df.iterrows():
                        fname = str(row.get("First Name", "")).strip()
                        lname = str(row.get("Last Name", "")).strip()
                        role = str(row.get("Role", "Teacher")).strip()
                        if fname:
                            u = auth.generate_username(fname, lname)
                            p = auth.generate_password(fname, lname)
                            ph = auth.make_pbkdf2_hash(p)
                            try:
                                c.execute("INSERT INTO users (username, password_hash, full_name, role, dashboard_page) VALUES (?, ?, ?, ?, ?)",
                                          (u, ph, f"{fname} {lname}", role, f"{role} Dashboard"))
                                created.append((u, p))
                            except:
                                pass
                    conn.commit()
                    conn.close()
                    st.success(f"Processed {len(created)} users.")
                    if created:
                            st.write("Created Users:", pd.DataFrame(created, columns=["Username", "Password"]))

        with c2:
            st.markdown("### Existing Users")
            conn = database.get_connection()
            users_df = pd.read_sql("SELECT username, full_name, role, dashboard_page FROM users", conn)
            
            # Additional: Display Class Teacher Assignments Table
            st.markdown("#### Class Teacher Assignments Summary")
            q_ct = """
            SELECT ua.username, u.full_name, GROUP_CONCAT(g.name, ', ') as assigned_grades
            FROM user_assignments ua
            JOIN users u ON ua.username = u.username
            JOIN grades g ON ua.grade_id = g.id
            WHERE u.role = 'Class Teacher' AND ua.subject_id = -1
            GROUP BY ua.username
            """
            ct_summary = pd.read_sql(q_ct, conn)
            if not ct_summary.empty:
                st.dataframe(ct_summary, hide_index=True)
            else:
                st.info("No Class Teachers assigned yet.")

            conn.close()
            st.dataframe(users_df, use_container_width=True)
            
            st.markdown("#### Edit User Details")
            sel_u = st.selectbox("Select User to Edit", users_df['username'].tolist(), index=None)
            if sel_u:
                conn = database.get_connection()
                curr = conn.execute("SELECT full_name, role, dashboard_page FROM users WHERE username=?", (sel_u,)).fetchone()
                
                # Fetch existing CT assignments
                curr_ct_grades = []
                if curr and curr[1] == "Class Teacher":
                    q_g = """
                    SELECT g.name 
                    FROM user_assignments ua
                    JOIN grades g ON ua.grade_id = g.id
                    WHERE ua.username = ? AND ua.subject_id = -1
                    """
                    curr_ct_grades = [r[0] for r in conn.execute(q_g, (sel_u,)).fetchall()]
                
                conn.close()
                
                if curr:
                    curr_name, curr_role, curr_dash = curr
                    parts = curr_name.split(" ", 1)
                    c_fname = parts[0]
                    c_lname = parts[1] if len(parts) > 1 else ""
                    
                    with st.form("edit_user_form"):
                        c_a, c_b = st.columns(2)
                        new_fname = c_a.text_input("First Name", value=c_fname)
                        new_lname = c_b.text_input("Last Name", value=c_lname)
                        new_username = st.text_input("Username", value=sel_u)
                        new_pass = st.text_input("New Password (leave blank)", type="password")
                        
                        role_opts = ["Admin", "Principal", "Class Teacher", "Teacher"]
                        new_role = st.selectbox("Role", role_opts, index=role_opts.index(curr_role) if curr_role in role_opts else 3)
                        
                        # Multi-Select for Grades
                        new_ct_grades = []
                        if new_role == "Class Teacher":
                             new_ct_grades = st.multiselect("Assign Grades (Class Teacher)", grades_list['name'].tolist(), default=curr_ct_grades)

                        dash_opts = ["Admin Dashboard", "Principal Dashboard", "Class Teacher Dashboard", "Teacher Dashboard"]
                        new_dash = st.selectbox("Dashboard Page", dash_opts, index=dash_opts.index(curr_dash) if curr_dash in dash_opts else 3)
                        
                        d1, d2 = st.columns(2)
                        
                        if d1.form_submit_button("Update User"):
                            conn = database.get_connection()
                            new_fullname = f"{new_fname} {new_lname}".strip()
                            
                            try:
                                # 1. Update basic info
                                if new_pass:
                                    ph = auth.make_pbkdf2_hash(new_pass)
                                    conn.execute("UPDATE users SET full_name=?, role=?, dashboard_page=?, password_hash=? WHERE username=?", (new_fullname, new_role, new_dash, ph, sel_u))
                                else:
                                    conn.execute("UPDATE users SET full_name=?, role=?, dashboard_page=? WHERE username=?", (new_fullname, new_role, new_dash, sel_u))
                                
                                # 2. Update Username
                                if new_username != sel_u:
                                    conn.execute("UPDATE users SET username=? WHERE username=?", (new_username, sel_u))
                                    conn.execute("UPDATE user_assignments SET username=? WHERE username=?", (new_username, sel_u))
                                    sel_u = new_username # Update for next steps
                                
                                # 3. Handle CT Assignment (Sync)
                                if new_role == "Class Teacher":
                                    # Get IDs involved
                                    # Current IDs in DB (reload to be safe or use what we had if username unchanged)
                                    # Safest is to querying DB for current status of target user
                                    curr_ids = [r[0] for r in conn.execute("SELECT grade_id FROM user_assignments WHERE username=? AND subject_id=-1", (sel_u,)).fetchall()]
                                    
                                    new_ids = []
                                    if new_ct_grades:
                                        new_ids = grades_list[grades_list['name'].isin(new_ct_grades)]['id'].tolist()
                                    
                                    # Determine Add/Remove
                                    to_add = set(new_ids) - set(curr_ids)
                                    to_remove = set(curr_ids) - set(new_ids)
                                    
                                    for mid in to_remove:
                                        conn.execute("DELETE FROM user_assignments WHERE username=? AND grade_id=? AND subject_id=-1", (sel_u, mid))
                                        
                                    for Aid in to_add:
                                        conn.execute("INSERT INTO user_assignments (username, grade_id, subject_id) VALUES (?, ?, ?)", (sel_u, Aid, -1))
                                
                                conn.commit()
                                st.success("Updated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Update failed: {e}")
                            conn.close()
                            
                        if d2.form_submit_button("DELETE USER", type="primary"):
                            conn = database.get_connection()
                            conn.execute("DELETE FROM users WHERE username=?", (sel_u,))
                            conn.commit()
                            conn.close()
                            st.warning(f"Deleted {sel_u}")
                            st.rerun()

    # --------------------------------------------------------------------------------
    # TAB 2: ACADEMIC SETUP
    # --------------------------------------------------------------------------------
    # --------------------------------------------------------------------------------
    # TAB 2: ACADEMIC SETUP
    # --------------------------------------------------------------------------------
    with tabs[1]:
        c1, c2 = st.columns(2)
        
        # 1. SUBJECTS (Global Names)
        with c1:
            st.subheader("Subjects (Global)")
            with st.form("add_subj"):
                s_name = st.text_input("Subject Name (e.g. MATHS)")
                if st.form_submit_button("Add Subject"):
                    if s_name:
                        conn = database.get_connection()
                        try:
                            # Default max marks to 100/0 if not using config, but config is preferred
                            conn.execute("INSERT INTO subjects (name, te_max_marks, ce_max_marks) VALUES (?, ?, ?)", (s_name.upper(), 100, 0))
                            conn.commit()
                            st.success(f"Added {s_name}")
                        except:
                            st.error("Error/Duplicate")
                        conn.close()
            
            conn = database.get_connection()
            subjs = pd.read_sql("SELECT id, name FROM subjects ORDER BY name", conn)
            st.dataframe(subjs, hide_index=True)
            
            # Delete
            del_s_ids = st.multiselect("Select Subjects to Delete", subjs['name'].tolist())
            if st.button("Delete Subjects", type="primary"):
                if del_s_ids:
                    ids_to_del = subjs[subjs['name'].isin(del_s_ids)]['id'].tolist()
                    placeholders = ','.join('?' for _ in ids_to_del)
                    conn.execute(f"DELETE FROM subjects WHERE id IN ({placeholders})", tuple(ids_to_del))
                    conn.commit()
                    st.success("Deleted Subjects")
                    st.rerun()
            conn.close()

        # 2. GRADES
        with c2:
            st.subheader("Grades / Classes")
            g_name = st.text_input("New Grade Name (e.g. 10State)")
            if st.button("Add Grade"):
                if g_name:
                    conn = database.get_connection()
                    try:
                        conn.execute("INSERT INTO grades (name) VALUES (?)", (g_name,))
                        conn.commit()
                        st.success(f"Added {g_name}")
                    except:
                        st.error("Error/Duplicate")
                    conn.close()
            
            conn = database.get_connection()
            grades = pd.read_sql("SELECT * FROM grades", conn)
            st.dataframe(grades, hide_index=True)
            
            # Delete
            del_g_ids = st.multiselect("Select Grades to Delete", grades['name'].tolist())
            if st.button("Delete Grades", type="primary"):
                if del_g_ids:
                    ids_to_del = grades[grades['name'].isin(del_g_ids)]['id'].tolist()
                    placeholders = ','.join('?' for _ in ids_to_del)
                    conn.execute(f"DELETE FROM grades WHERE id IN ({placeholders})", tuple(ids_to_del))
                    conn.commit()
                    st.success("Deleted Grades")
                    st.rerun()
            conn.close()
            
        st.markdown("---")
        
        # 3. SUBJECT LIMITS PER GRADE
        st.subheader("Subject Limits per Grade")
        st.write("Define TE/CE Max Marks for a Subject in a specific Grade.")
        
        conn = database.get_connection()
        s_df = pd.read_sql("SELECT id, name FROM subjects ORDER BY name", conn)
        g_df = pd.read_sql("SELECT id, name FROM grades ORDER BY name", conn)
        conn.close()
        
        with st.form("subj_grade_config"):
            c_sg1, c_sg2, c_sg3, c_sg4 = st.columns(4)
            sel_s = c_sg1.selectbox("Subject", s_df['name'].tolist() if not s_df.empty else [])
            sel_g = c_sg2.selectbox("Grade", g_df['name'].tolist() if not g_df.empty else [])
            te_m = c_sg3.number_input("TE Max", value=100.0)
            ce_m = c_sg4.number_input("CE Max", value=0.0)
            
            if st.form_submit_button("Set Limits"):
                if sel_s and sel_g:
                    sid = s_df[s_df['name']==sel_s]['id'].values[0]
                    gid = g_df[g_df['name']==sel_g]['id'].values[0]
                    conn = database.get_connection()
                    try:
                        conn.execute("INSERT OR REPLACE INTO subject_grade_config (subject_id, grade_id, te_max_marks, ce_max_marks) VALUES (?, ?, ?, ?)", (int(sid), int(gid), te_m, ce_m))
                        conn.commit()
                        st.success(f"Updated {sel_s} in {sel_g}")
                    except Exception as e:
                        st.error(f"Error: {e}")
                    conn.close()
        
        # Display Configs
        conn = database.get_connection()
        q_conf = """
            SELECT s.name as Subject, g.name as Grade, c.te_max_marks, c.ce_max_marks 
            FROM subject_grade_config c 
            JOIN subjects s ON c.subject_id=s.id 
            JOIN grades g ON c.grade_id=g.id
            ORDER BY g.name, s.name
        """
        conf_df = pd.read_sql(q_conf, conn)
        st.dataframe(conf_df, hide_index=True)
        
        # Delete Subject Limits
        if not conf_df.empty:
            st.markdown("#### Delete Subject Limit")
            # Create a unique list for selection
            # We need IDs to delete. Since we don't display composite ID, we fetch full list for mapping.
            q_full = """
                SELECT c.subject_id, c.grade_id, s.name as Subject, g.name as Grade 
                FROM subject_grade_config c 
                JOIN subjects s ON c.subject_id=s.id 
                JOIN grades g ON c.grade_id=g.id
            """
            full_conf = pd.read_sql(q_full, conn)
            full_conf['label'] = full_conf['Subject'] + " - " + full_conf['Grade']
            
            sel_del_lim = st.selectbox("Select Limit to Delete", full_conf['label'].tolist(), index=None)
            if st.button("Delete Selected Limit"):
                if sel_del_lim:
                    to_del_row = full_conf[full_conf['label'] == sel_del_lim].iloc[0]
                    dsid = int(to_del_row['subject_id'])
                    dgid = int(to_del_row['grade_id'])
                    conn.execute("DELETE FROM subject_grade_config WHERE subject_id=? AND grade_id=?", (dsid, dgid))
                    conn.commit()
                    st.success("Deleted!")
                    st.rerun()

        conn.close()

        st.markdown("---")
        st.subheader("Grade Scales (Per Grade)")
        
        conn = database.get_connection()
        gs_df = pd.read_sql("SELECT gs.grade_label, gs.min_pct, gs.max_pct, g.name as Grade FROM grade_scales gs LEFT JOIN grades g ON gs.grade_id=g.id ORDER BY g.name, gs.min_pct DESC", conn)
        conn.close()
        
        with st.form("grade_scale"):
            c1, c2, c3, c4 = st.columns(4)
            gl = c1.text_input("Label (e.g. A1)")
            mn = c2.number_input("Min %", 0.0, 100.0, 91.0)
            mx = c3.number_input("Max %", 0.0, 100.0, 100.0)
            # Grade Select (Optional? User said 'include grade selection', implies it varies)
            # Grade Select (Optional - Global if empty or selected)
            # Providing option for using same grade label for multiple grades
            gr_for_scale = c4.multiselect("Grades (Select multiple)", ["Global"] + g_df['name'].tolist() if not g_df.empty else ["Global"], default=["Global"])
            
            if st.form_submit_button("Add Grade Scale Rule"):
                conn = database.get_connection()
                try:
                    count = 0
                    if not gr_for_scale:
                         # Default to Global if nothing selected? Or Warn?
                         # Assume Global
                         targets = [None]
                    else:
                         targets = []
                         if "Global" in gr_for_scale:
                             targets.append(None)
                         
                         # Add others
                         extras = [x for x in gr_for_scale if x != "Global"]
                         if extras:
                             # Get IDs
                             g_map = dict(zip(g_df['name'], g_df['id']))
                             for e in extras:
                                 if e in g_map:
                                     targets.append(g_map[e])
                    
                    for gid_val in targets:
                        try:
                            conn.execute("INSERT INTO grade_scales (grade_label, min_pct, max_pct, grade_id) VALUES (?, ?, ?, ?)", (gl, mn, mx, gid_val))
                            count += 1
                        except Exception as e:
                            # Likely unique constraint for this specific combo
                            pass
                            
                    conn.commit()
                    st.success(f"Added Rule for {count} targets")
                except Exception as e:
                    st.error(f"Error: {e}")
                conn.close()
        
        st.dataframe(gs_df, hide_index=True, use_container_width=True)
        
        # Delete for Grade Scale
        if not gs_df.empty:
             st.markdown("#### Delete Grade Scale Rule")
             # Need IDs to delete accurately
             conn = database.get_connection()
             # Re-fetch with ID
             gs_full = pd.read_sql("SELECT id, grade_label, min_pct, max_pct FROM grade_scales", conn)
             conn.close()
             
             if not gs_full.empty:
                 gs_full['disp'] = gs_full.apply(lambda x: f"{x['grade_label']} ({x['min_pct']}-{x['max_pct']}%)", axis=1)
                 sel_del_GS = st.selectbox("Select Rule to Delete", gs_full['disp'].tolist(), index=None)
                 
                 if st.button("Delete Selected Rule"):
                     if sel_del_GS:
                         del_id = int(gs_full[gs_full['disp'] == sel_del_GS]['id'].values[0])
                         conn = database.get_connection()
                         conn.execute("DELETE FROM grade_scales WHERE id=?", (del_id,))
                         conn.commit()
                         conn.close()
                         st.success("Deleted Rule")
                         st.rerun()

    # --------------------------------------------------------------------------------
    # TAB 3: STUDENTS
    # --------------------------------------------------------------------------------
    # --------------------------------------------------------------------------------
    # TAB 3: STUDENTS
    # --------------------------------------------------------------------------------
    with tabs[2]:
        st.subheader("Student Management")
        
        # Helper Data
        conn = database.get_connection()
        g_opts = pd.read_sql("SELECT id, name FROM grades", conn)
        conn.close()
        
        c_add, c_edit = st.columns(2)
        
        with c_add:
            with st.expander("Add Single Student"):
                st_name = st.text_input("Student Name")
                st_adm = st.text_input("Admission No")
                g_sel = st.selectbox("Select Grade", g_opts['name'].tolist() if not g_opts.empty else [], key="add_st_grade")
                
                if st.button("Add Student"):
                    if st_name and g_sel:
                        gid = g_opts[g_opts['name']==g_sel]['id'].values[0]
                        conn = database.get_connection()
                        try:
                            conn.execute("INSERT INTO students (name, admission_no, grade_id) VALUES (?, ?, ?)", (st_name, st_adm, int(gid)))
                            conn.commit()
                            st.success(f"Student {st_name} added to {g_sel}")
                        except:
                            st.error("Error (Duplicate Adm No?)")
                        conn.close()
        
        with c_edit:
             with st.expander("Edit Student Details"):
                 conn = database.get_connection()
                 all_st = pd.read_sql("SELECT id, name, admission_no FROM students ORDER BY name", conn)
                 conn.close()
                 
                 if not all_st.empty:
                     # Searchable selectbox
                     st_display = all_st.apply(lambda x: f"{x['name']} ({x['admission_no']})", axis=1).tolist()
                     sel_st_edit = st.selectbox("Select Student to Edit", st_display)
                     
                     if sel_st_edit:
                         # Extract original name for lookup or just use index?
                         # Better to look up by ID if we mapped it, but here we can just find row
                         sel_idx = st_display.index(sel_st_edit)
                         sid_edit = all_st.iloc[sel_idx]['id']
                         
                         conn = database.get_connection()
                         curr_st = conn.execute("SELECT name, admission_no, grade_id FROM students WHERE id=?", (sid_edit,)).fetchone()
                         conn.close()
                         
                         if curr_st:
                             curr_nm, curr_ad, curr_gid = curr_st
                             
                             new_nm = st.text_input("New Name", value=curr_nm)
                             new_ad = st.text_input("New Adm No", value=curr_ad)
                             
                             # Grade Index
                             curr_gname = g_opts[g_opts['id']==curr_gid]['name'].values[0] if curr_gid in g_opts['id'].values else None
                             new_g = st.selectbox("New Grade", g_opts['name'].tolist(), index=g_opts['name'].tolist().index(curr_gname) if curr_gname in g_opts['name'].tolist() else 0, key="edit_st_grade")
                             
                             if st.button("Update Student Details"):
                                 gid_new = g_opts[g_opts['name']==new_g]['id'].values[0]
                                 conn = database.get_connection()
                                 conn.execute("UPDATE students SET name=?, admission_no=?, grade_id=? WHERE id=?", (new_nm, new_ad, gid_new, sid_edit))
                                 conn.commit()
                                 conn.close()
                                 st.success("Updated!")
                                 st.rerun()

        st.markdown("### Bulk Import Students")
        csv_st = st.file_uploader("Upload Students CSV (Name, Admission No, Grade Name)", type=["csv"])
        if csv_st:
            if st.button("Import Students"):
                df = pd.read_csv(csv_st)
                conn = database.get_connection()
                g_map = dict(conn.execute("SELECT name, id FROM grades").fetchall())
                
                added = 0
                for _, r in df.iterrows():
                    nm = str(r.get("Name", "")).strip()
                    adm = str(r.get("Admission No", "")).strip()
                    gn = str(r.get("Grade Name", "")).strip()
                    
                    gid = g_map.get(gn)
                    if nm and gid:
                        try:
                            conn.execute("INSERT INTO students (name, admission_no, grade_id) VALUES (?, ?, ?)", (nm, adm, gid))
                            added += 1
                        except:
                            pass
                conn.commit()
                conn.close()
                st.success(f"Imported {added} students.")

        st.markdown("---")
        
        # Main Data View
        conn = database.get_connection()
        st_df = pd.read_sql("SELECT s.id, s.name, s.admission_no, g.name as Grade FROM students s LEFT JOIN grades g ON s.grade_id = g.id ORDER BY g.name, s.name", conn)
        conn.close()
        
        c1, c2 = st.columns([3, 1])
        with c1:
            st.dataframe(st_df, use_container_width=True)
        with c2:
            st.markdown("#### Delete")
            to_del_ids = st.multiselect("Select IDs to Delete", st_df['id'].tolist())
            if st.button("Delete Selected", type="primary"):
                if to_del_ids:
                    conn = database.get_connection()
                    placeholders = ','.join('?' for _ in to_del_ids)
                    conn.execute(f"DELETE FROM students WHERE id IN ({placeholders})", tuple(to_del_ids))
                    conn.commit()
                    conn.close()
                    st.success("Deleted!")
                    st.rerun()
                    
        st.markdown("---")
        with st.expander("Admin: Edit Student Marks"):
             st.info("Directly edit marks for any student/subject.")
             # Selectors
             conn = database.get_connection()
             g_sel_m = st.selectbox("Select Grade", g_opts['name'].tolist(), key="admin_marks_g")
             if g_sel_m:
                 gid_m = g_opts[g_opts['name']==g_sel_m]['id'].values[0]
                 sts = pd.read_sql("SELECT id, name FROM students WHERE grade_id=?", conn, params=(gid_m,))
                 
                 st_sel_m = st.selectbox("Select Student", sts['name'].tolist() if not sts.empty else [], key="admin_marks_s")
                 if st_sel_m:
                     sid_m = sts[sts['name']==st_sel_m]['id'].values[0]
                     
                     subjs = pd.read_sql("SELECT id, name FROM subjects ORDER BY name", conn)
                     sub_sel_m = st.selectbox("Select Subject", subjs['name'].tolist(), key="admin_marks_sub")
                     
                     if sub_sel_m:
                         sub_id_m = subjs[subjs['name']==sub_sel_m]['id'].values[0]
                         
                         # Fetch current
                         curr_marks = conn.execute("SELECT te_score, ce_score, remarks FROM marks WHERE student_id=? AND subject_id=?", (sid_m, sub_id_m)).fetchone()
                         te_curr, ce_curr, rem_curr = curr_marks if curr_marks else (0.0, 0.0, "")
                         
                         c_m1, c_m2, c_m3 = st.columns(3)
                         te_new = c_m1.number_input("TE Score", value=te_curr)
                         ce_new = c_m2.number_input("CE Score", value=ce_curr)
                         rem_new = c_m3.text_input("Remarks", value=rem_curr)
                         
                         if st.button("Update Marks (Admin)"):
                             try:
                                 conn.execute("""
                                    INSERT INTO marks (student_id, subject_id, te_score, ce_score, remarks)
                                    VALUES (?, ?, ?, ?, ?)
                                    ON CONFLICT(student_id, subject_id) DO UPDATE SET
                                    te_score=excluded.te_score,
                                    ce_score=excluded.ce_score,
                                    remarks=excluded.remarks
                                 """, (sid_m, sub_id_m, te_new, ce_new, rem_new))
                                 conn.commit()
                                 st.success("Marks Updated")
                             except Exception as e:
                                 st.error(str(e))
             conn.close()

    # --------------------------------------------------------------------------------
    # TAB 4: ASSIGNMENTS
    # --------------------------------------------------------------------------------
    with tabs[3]:
        st.subheader("Teacher Assignments")
        
        conn = database.get_connection()
        users_t = pd.read_sql("SELECT username, full_name FROM users", conn) 
        grades_t = pd.read_sql("SELECT id, name FROM grades", conn)
        subjs_t = pd.read_sql("SELECT id, name FROM subjects", conn)
        conn.close()
        
        if users_t.empty or grades_t.empty or subjs_t.empty:
            st.warning("Ensure Users, Grades, and Subjects exist first.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### Assign Subject to User & Grade")
                sel_u_assign = st.selectbox("Select User", users_t['username'].tolist(), key="user_assign")
                st.write("Assign Grades (Allow access to these grades)")
                sel_g_assign = st.multiselect("Select Grades", grades_t['name'].tolist())
                sel_s_assign = st.multiselect("Select Subjects", subjs_t['name'].tolist())
                
                if st.button("Assign (Cartesian Product)"):
                    conn = database.get_connection()
                    c = conn.cursor()
                    count = 0 
                    g_ids = grades_t[grades_t['name'].isin(sel_g_assign)]['id'].tolist()
                    s_ids = subjs_t[subjs_t['name'].isin(sel_s_assign)]['id'].tolist()
                    
                    for gid in g_ids:
                        for sid in s_ids:
                            exists = c.execute("SELECT 1 FROM user_assignments WHERE username=? AND grade_id=? AND subject_id=?", (sel_u_assign, gid, sid)).fetchone()
                            if not exists:
                                c.execute("INSERT INTO user_assignments (username, grade_id, subject_id) VALUES (?, ?, ?)", (sel_u_assign, gid, sid))
                                count += 1
                    conn.commit()
                    conn.close()
                    st.success(f"Created {count} assignments.")

            with c2:
                st.markdown("#### Current Assignments")
                conn = database.get_connection()
                q = """
                SELECT ua.id, ua.username, g.name as Grade, s.name as Subject 
                FROM user_assignments ua
                JOIN grades g ON ua.grade_id = g.id
                JOIN subjects s ON ua.subject_id = s.id
                WHERE ua.username = ?
                """
                if sel_u_assign:
                    data = pd.read_sql(q, conn, params=(sel_u_assign,))
                    st.dataframe(data, hide_index=True)
                    to_del = st.selectbox("Select ID to Remove", data['id'].tolist() if not data.empty else [])
                    if to_del:
                        if st.button("Remove Assignment"):
                            conn.execute("DELETE FROM user_assignments WHERE id=?", (to_del,))
                            conn.commit()
                            st.rerun()
                conn.close()

    # --------------------------------------------------------------------------------
    # TAB 5: CONFIGURATION
    # --------------------------------------------------------------------------------
    with tabs[4]:
        st.subheader("Global Configuration")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Signatures")
            # Principals
            st.write("**Principal Signature**")
            p_sign = st.file_uploader("Upload Principal Signature", type=["png", "jpg", "jpeg"], key="p_sign")
            if p_sign:
                with open("principal_sign.png", "wb") as f:
                    f.write(p_sign.getbuffer())
                st.success("Principal Signature Saved")
            
            st.markdown("---")
            st.markdown("**Class Teacher Signatures**")
            conn = database.get_connection()
            grades_df = pd.read_sql("SELECT id, name, class_teacher_sign_path FROM grades", conn)
            # Fetch assignments if we want to show?
            conn.close()
            
            sel_g_sig = st.selectbox("Select Grade for Signature", grades_df['name'].tolist())
            ct_sig = st.file_uploader("Upload CT Signature", type=["png", "jpg"], key="ct_sig")
            
            if ct_sig and sel_g_sig:
                if st.button("Save CT Signature"):
                    ext = ct_sig.name.split('.')[-1]
                    fname = f"ct_sign_{sel_g_sig}.{ext}"
                    with open(fname, "wb") as f:
                        f.write(ct_sig.getbuffer())
                    
                    conn = database.get_connection()
                    conn.execute("UPDATE grades SET class_teacher_sign_path=? WHERE name=?", (fname, sel_g_sig))
                    conn.commit()
                    conn.close()
                    st.success(f"Saved for {sel_g_sig}")
            
            st.markdown("---")
            st.markdown("**Parent Signatures**")
            st.info("File name must be `{Admission_No}.png` (e.g. B5A1.png)")
            par_sig = st.file_uploader("Upload Parent Signature", type=["png", "jpg"], key="par_sig")
            st_for_sig = st.text_input("Enter Student Adm No (or Name) to link")
            
            if par_sig and st_for_sig:
                if st.button("Save Parent Signature"):
                    ext = par_sig.name.split('.')[-1]
                    fname = f"parent_sign_{st_for_sig}.{ext}"
                    with open(fname, "wb") as f:
                        f.write(par_sig.getbuffer())
                    
                    conn = database.get_connection()
                    c = conn.cursor()
                    found = c.execute("SELECT id FROM students WHERE admission_no=?", (st_for_sig,)).fetchone()
                    if not found:
                        found = c.execute("SELECT id FROM students WHERE name=?", (st_for_sig,)).fetchone()
                    
                    if found:
                        c.execute("UPDATE students SET parent_signature_path=? WHERE id=?", (fname, found[0]))
                        conn.commit()
                        st.success("Linked!")
                    else:
                        st.error("Student not found")
                    conn.close()

        with c2:
            st.markdown("### Report Backgrounds")
            # 1. Upload Background
            bg_file = st.file_uploader("Upload A4 Background (JPG/PNG)", type=["jpg", "png", "jpeg"], key="bg_up")
            bg_name = st.text_input("Background Name (e.g. Primary_Theme)")
            
            if st.button("Save Background"):
                if bg_file and bg_name:
                    fname = f"bg_{bg_name.replace(' ', '_')}.{bg_file.name.split('.')[-1]}"
                    with open(fname, "wb") as f:
                        f.write(bg_file.getbuffer())
                    
                    conn = database.get_connection()
                    conn.execute("INSERT INTO report_backgrounds (filename) VALUES (?)", (fname,))
                    conn.commit()
                    conn.close()
                    st.success("Background Uploaded")
            
            st.markdown("#### Assign Grade to Background")
            conn = database.get_connection()
            bgs = pd.read_sql("SELECT id, filename FROM report_backgrounds", conn)
            grades = pd.read_sql("SELECT id, name FROM grades", conn)
            conn.close()
            
            if not bgs.empty:
                sel_bg = st.selectbox("Select Background", bgs['filename'].tolist())
                sel_grades_bg = st.multiselect("Assign to Grades", grades['name'].tolist())
                
                if st.button("Assign Background"):
                    bg_id = int(bgs[bgs['filename']==sel_bg]['id'].values[0])
                    g_ids = grades[grades['name'].isin(sel_grades_bg)]['id'].tolist()
                    
                    conn = database.get_connection()
                    for gid in g_ids:
                        conn.execute("INSERT OR REPLACE INTO grade_backgrounds (grade_id, background_id) VALUES (?, ?)", (int(gid), bg_id))
                    conn.commit()
                    conn.close()
                    st.success("Assigned!")
            
            # Show assignments
            conn = database.get_connection()
            q_bg = """
                SELECT g.name as Grade, b.filename as Background
                FROM grade_backgrounds gb
                JOIN grades g ON gb.grade_id=g.id
                JOIN report_backgrounds b ON gb.background_id=b.id
                ORDER BY g.name
            """
            bg_assigns = pd.read_sql(q_bg, conn)
            conn.close()
            st.dataframe(bg_assigns, hide_index=True)
