import io, os, csv, hashlib, binascii, streamlit as st
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader

# ---------- Config ----------
FIXED_SUBJECTS = ["ENGLISH","HINDI","ISLAMIC","MATHS","SOCIAL","SCIENCE","IT"]
SKILL_NAMES = ["LEVEL 1 (REMEMBERING)","LEVEL 2 (UNDERSTANDING)","LEVEL 3 (APPLYING)","REGULARITY & PUNCTUALITY","NEATNESS & ORDERLINESS"]
BASE_DIR = os.path.dirname(__file__)
MERIT_CSV = os.path.join(BASE_DIR,"merit.csv")
TEACHERS_CSV = os.path.join(BASE_DIR,"teachers.csv")
HEADER_IMG = os.path.join(BASE_DIR,"top.jpg")
FOOTER_IMG = os.path.join(BASE_DIR,"bottom.jpg")
TOTAL_ROW_COLOR = "#C7B994"

# ---------- Helpers ----------
def title_case_name(name):
    return " ".join([w.capitalize() for w in str(name).split()])

def make_pbkdf2_hash(password, iterations=200000):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
    return f"pbkdf2${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def verify_password(stored, provided):
    try:
        if isinstance(stored, str) and stored.startswith("pbkdf2$"):
            _, iters, salt_hex, stored_hash = stored.split('$')
            salt = binascii.unhexlify(salt_hex)
            dk = hashlib.pbkdf2_hmac('sha256', provided.encode(), salt, int(iters))
            return binascii.hexlify(dk).decode() == stored_hash
        return stored == provided
    except Exception:
        return False

def load_teachers(path):
    if not os.path.exists(path):
        return {}
    with open(path, newline='', encoding='utf-8') as f:
        return {r['username']: {'password': r['password'],'is_admin':r.get('is_admin','').upper()=='TRUE'} for r in csv.DictReader(f)}

def save_teachers(path, teachers):
    with open(path, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["username","password","is_admin"])
        for u,v in teachers.items():
            writer.writerow([u,v["password"],"TRUE" if v.get("is_admin") else "FALSE"])

def load_merit(path):
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            subj = r.get('Subject','').upper()
            try:
                mn = float(r.get('Min',0)); mx = float(r.get('Max',0))
            except:
                mn = 0; mx = 0
            data.setdefault(subj,[]).append((mn,mx,r.get('Grade',''),r.get('Comment','')))
    return data

def grade_comment(merit, subj, score):
    subj = subj.upper()
    if subj in merit:
        for mn,mx,g,c in merit[subj]:
            if mn <= score <= mx:
                return g, c
    if 'ALL' in merit:
        for mn,mx,g,c in merit['ALL']:
            if mn <= score <= mx:
                return g, c
    return "", ""

# ---------- Report creation (aligned tables, title-case names, no big top title) ----------
def create_report_card_bytes(student_name, student_grade, subjects_scores, skills_scores, teacher_comments, prepared_by, output_format="PDF"):
    buffer = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    margin = 15 * mm

    header_h = 55 * mm
    footer_h = 50 * mm

    # header/footer images full width (maximize to top/bottom)
    if os.path.exists(HEADER_IMG):
        try:
            img = ImageReader(HEADER_IMG)
            c.drawImage(img, 0, height - header_h, width=width, height=header_h, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    if os.path.exists(FOOTER_IMG):
        try:
            img = ImageReader(FOOTER_IMG)
            c.drawImage(img, 0, 0, width=width, height=footer_h, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # student info (Name title-case, Grade capitalized first letter)
    top_y = height - header_h - 10 * mm
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, top_y, f"Name: {title_case_name(student_name)}")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(width/2 + margin/2, top_y, f"Grade: {str(student_grade).capitalize()}")

    # load merit mapping
    merit = load_merit(MERIT_CSV)

    # Subjects table
    subj_data = [["SUBJECTS","SCORED","TOTAL","GRADE","COMMENTS"]]
    total_scored = 0
    total_out = 0
    for subj in FIXED_SUBJECTS:
        score = float(subjects_scores.get(subj,0) or 0)
        total = 100
        # if merit stored totals differently, keep default 100
        grade, comment = grade_comment(merit, subj, score)
        subj_data.append([subj, str(int(score)), str(total), grade, comment])
        total_scored += score
        total_out += total
    percentage = (total_scored / total_out * 100) if total_out else 0
    subj_data.append(["TOTAL", str(int(total_scored)), str(int(total_out)), f"{percentage:.1f}%", ""])

    # column widths for subjects (sum used to align skills table)
    subj_col_widths = [55 * mm, 25 * mm, 25 * mm, 25 * mm, 40 * mm]
    subj_table = Table(subj_data, colWidths=subj_col_widths)
    subj_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#dde2df")),
        ('GRID', (0,0), (-1,-1), 0.25, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ])
    subj_style.add('BACKGROUND', (0, len(subj_data)-1), (-1, len(subj_data)-1), colors.HexColor(TOTAL_ROW_COLOR))
    subj_style.add('FONTNAME', (0, len(subj_data)-1), (-1, len(subj_data)-1), 'Helvetica-Bold')
    subj_table.setStyle(subj_style)

    # Skills table - keep 3 columns but match total width & alignment to subjects table
    skill_data = [["SKILLS / WORK HABITS","SCORE","COMMENTS"]]
    for sk in SKILL_NAMES:
        sc = skills_scores.get(sk,1)
        comment = {4:"Outstanding",3:"Accomplished",2:"Progressing",1:"Beginning"}.get(int(sc), "")
        skill_data.append([sk, str(sc), comment])

    # compute total width of subjects table to reuse for skills
    subj_total_width = sum(subj_col_widths)
    # distribute widths proportionally for 3 columns (subject name column should be similar to first column)
    skill_col_widths = [subj_col_widths[0], subj_col_widths[1], subj_col_widths[2] + subj_col_widths[3] + subj_col_widths[4]]
    skill_table = Table(skill_data, colWidths=skill_col_widths)
    skill_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#dde2df")),
        ('GRID', (0,0), (-1,-1), 0.25, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))

    # draw tables with same left margin so they align vertically
    current_y = top_y - 20 * mm
    subj_table.wrapOn(c, width, height)
    subj_h = subj_table._height
    subj_table.drawOn(c, margin, current_y - subj_h)
    current_y = current_y - subj_h - 6 * mm

    skill_table.wrapOn(c, width, height)
    skill_h = skill_table._height
    skill_table.drawOn(c, margin, current_y - skill_h)
    current_y = current_y - skill_h - 8 * mm

    # Comments by teacher (unchanged, above footer)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, current_y, "Comments by Teacher:")
    c.setFont("Helvetica", 10)
    words = teacher_comments.split()
    line = ""
    lines = []
    for w in words:
        test = (line + " " + w).strip()
        if len(test) > 90:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    for i, ln in enumerate(lines[:6]):
        c.drawString(margin, current_y - 12*(i+1), ln)

    # status and prepared on/by
    current_y = current_y - 12*(len(lines)+1) - 6 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, current_y, "Status:")
    c.setFont("Helvetica", 10)
    c.drawString(margin + 50, current_y, "PASSED" if percentage >= 40 else "FAILED")
    c.drawString(margin + 140, current_y, f"Prepared on: {datetime.now().strftime('%d/%m/%Y')}")
    c.drawString(margin + 300, current_y, f"Prepared by: {prepared_by}")

    c.showPage()
    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()

    if output_format.upper() == "JPG":
        try:
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(pdf_bytes, fmt='jpeg', dpi=200)
            img_buf = io.BytesIO()
            images[0].save(img_buf, format='JPEG', quality=95)
            return img_buf.getvalue()
        except Exception:
            return pdf_bytes

    return pdf_bytes

# ---------- Streamlit UI (v7 features retained) ----------
st.set_page_config("Report Card Generator - BIGS Campus School", layout="wide")

# ensure teachers.csv exists with default admin
if not os.path.exists(TEACHERS_CSV):
    with open(TEACHERS_CSV,"w",newline='',encoding="utf-8") as f:
        writer=csv.writer(f); writer.writerow(["username","password","is_admin"])
        writer.writerow(["amina",make_pbkdf2_hash("1234"),"TRUE"])

if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in':False,'username':None,'is_admin':False})

teachers = load_teachers(TEACHERS_CSV)

# Login
if not st.session_state['logged_in']:
    st.title("BIGS Campus School Report Generator")
    st.subheader("Teacher Login")
    uname = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if uname in teachers and verify_password(teachers[uname]['password'], pwd):
            st.session_state.update({'logged_in':True,'username':uname,'is_admin':teachers[uname]['is_admin']})
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()

# Sidebar
user = st.session_state['username']
is_admin = st.session_state['is_admin']

st.sidebar.markdown(f"👤 Logged in as: **{title_case_name(user)} {'(Admin)' if is_admin else '(Teacher)'}**")
if st.sidebar.button("🚪 Logout"):
    st.session_state.update({'logged_in':False,'username':None,'is_admin':False}); st.rerun()

if is_admin:
    with st.sidebar.expander("📸 Upload Image Files", expanded=False):
        top = st.file_uploader("Upload top.jpg", type=["jpg","jpeg"], key="topimg")
        if top:
            open(HEADER_IMG,"wb").write(top.read()); st.success("✅ top.jpg uploaded successfully.")
        bottom = st.file_uploader("Upload bottom.jpg", type=["jpg","jpeg"], key="bottomimg")
        if bottom:
            open(FOOTER_IMG,"wb").write(bottom.read()); st.success("✅ bottom.jpg uploaded successfully.")

    with st.sidebar.expander("📊 Upload CSV Files", expanded=False):
        merit = st.file_uploader("Upload merit.csv", type=["csv"], key="meritcsv")
        if merit:
            open(MERIT_CSV,"wb").write(merit.read()); st.success("✅ merit.csv updated.")
        teachers_csv = st.file_uploader("Upload teachers.csv", type=["csv"], key="teachcsv")
        if teachers_csv:
            open(TEACHERS_CSV,"wb").write(teachers_csv.read()); st.success("✅ teachers.csv updated."); st.rerun()

    with st.sidebar.expander("👥 Manage Users", expanded=False):
        newu = st.text_input("Username", key="newu")
        newp = st.text_input("Password", type="password", key="newp")
        adm = st.checkbox("Is Admin", key="newadmin")
        if st.button("Add / Update Teacher", key="addbtn"):
            t = load_teachers(TEACHERS_CSV)
            if newu:
                t[newu] = {'password': make_pbkdf2_hash(newp), 'is_admin': adm}
                save_teachers(TEACHERS_CSV, t); st.success(f"✅ User '{newu}' added/updated.")
            else:
                st.error("Enter a username.")

    with st.sidebar.expander("🔑 Change Password", expanded=False):
        oldp = st.text_input("Current Password", type="password", key="oldp")
        newp = st.text_input("New Password", type="password", key="newpadmin")
        if st.button("Update Admin Password", key="chgpwadmin"):
            t = load_teachers(TEACHERS_CSV)
            if user in t and verify_password(t[user]['password'], oldp):
                t[user]['password'] = make_pbkdf2_hash(newp); save_teachers(TEACHERS_CSV, t)
                st.success("✅ Password changed successfully."); st.rerun()
            else:
                st.error("Invalid current password.")

else:
    with st.sidebar.expander("🔑 Change My Password", expanded=False):
        oldp = st.text_input("Current Password", type="password", key="oldpuser")
        newp = st.text_input("New Password", type="password", key="newpuser")
        if st.button("Change My Password", key="chgpwuser"):
            t = load_teachers(TEACHERS_CSV)
            if user in t and verify_password(t[user]['password'], oldp):
                t[user]['password'] = make_pbkdf2_hash(newp); save_teachers(TEACHERS_CSV, t)
                st.success("✅ Password changed successfully."); st.rerun()
            else:
                st.error("Invalid current password.")

# Welcome message
st.title("🎉 Welcome back, " + title_case_name(user) + "!")
st.markdown("---")

# Report generator UI
st.subheader("Generate Student Report Card")
with st.form("report_form"):
    c1, c2 = st.columns([2,1])
    with c1:
        name = st.text_input("Student Name", value="")
    with c2:
        grade = st.text_input("Grade / Class", value="")

    st.markdown("#### Academic Scores")
    merit = load_merit(MERIT_CSV)
    subjects_scores = {}
    cols = st.columns(3)
    for i, subj in enumerate(FIXED_SUBJECTS):
        with cols[i % 3]:
            total_for_subj = 100
            scored = st.number_input(f"{subj} - Scored", min_value=0, max_value=total_for_subj, value=0, step=1)
            subjects_scores[subj] = scored

    st.markdown("#### Skills & Work Habits (1-4)")
    skills_scores = {}
    cols2 = st.columns(3)
    for i, sk in enumerate(SKILL_NAMES):
        with cols2[i % 3]:
            sc = st.number_input(f"{sk} - Score", min_value=1, max_value=4, value=1, step=1)
            skills_scores[sk] = sc

    teacher_comments = st.text_area("Comments by Teacher", value="")
    output_format = st.selectbox("Output Format", ["PDF", "JPG"], index=0)
    submit = st.form_submit_button("Generate Report")

if submit:
    prepared_by = title_case_name(user)
    pdf_bytes = create_report_card_bytes(name, grade, subjects_scores, skills_scores, teacher_comments, prepared_by, output_format)
    ext = "pdf" if output_format == "PDF" else "jpg"
    mime = "application/pdf" if output_format == "PDF" else "image/jpeg"
    filename = f"{name.replace(' ','_')}_ReportCard.{ext}"
    st.success("Report generated successfully.")
    st.download_button("⬇️ Download Report", data=pdf_bytes, file_name=filename, mime=mime)
