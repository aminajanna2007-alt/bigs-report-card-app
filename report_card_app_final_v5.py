import io, os, csv, hashlib, binascii, streamlit as st
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader

# ---------- Config ----------
FIXED_SUBJECTS = ["ENGLISH", "HINDI", "ISLAMIC", "MATHS", "SOCIAL", "SCIENCE", "IT"]
SKILL_NAMES = ["LEVEL 1 (REMEMBERING)", "LEVEL 2 (UNDERSTANDING)", "LEVEL 3 (APPLYING)", "REGULARITY & PUNCTUALITY", "NEATNESS & ORDERLINESS"]
BASE_DIR = os.path.dirname(__file__)
MERIT_CSV = os.path.join(BASE_DIR, "merit.csv")
TEACHERS_CSV = os.path.join(BASE_DIR, "teachers.csv")
HEADER_IMG = os.path.join(BASE_DIR, "top.jpg")
FOOTER_IMG = os.path.join(BASE_DIR, "bottom.jpg")
TOTAL_ROW_COLOR = "#C7B994"

# ---------- Helpers ----------
def capitalize_first(text):
    return " ".join([t.capitalize() for t in str(text).split()])

def load_merit_csv(path):
    mapping = {}
    if not os.path.exists(path):
        return mapping
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            subj = r.get('Subject', '').strip().upper()
            try:
                total = int(r.get('Total', '') or 100)
            except:
                total = 100
            try:
                mn = float(r.get('Min', '') or 0)
                mx = float(r.get('Max', '') or 0)
            except:
                mn, mx = 0, 0
            grade = r.get('Grade', '').strip()
            comment = r.get('Comment', '').strip()
            if subj not in mapping:
                mapping[subj] = {'total': total, 'ranges': []}
            mapping[subj]['total'] = total
            mapping[subj]['ranges'].append((mn, mx, grade, comment))
    for subj in mapping:
        mapping[subj]['ranges'].sort(key=lambda x: x[0], reverse=True)
    return mapping

def find_grade_comment(mapping, subject, score):
    subj = subject.upper()
    if subj in mapping:
        for mn, mx, grade, comment in mapping[subj]['ranges']:
            if mn <= score <= mx:
                return grade, comment
    if 'ALL' in mapping:
        for mn, mx, grade, comment in mapping['ALL']['ranges']:
            if mn <= score <= mx:
                return grade, comment
    return "", ""

# Password hashing / verification using PBKDF2
def make_pbkdf2_hash(password, iterations=200000):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f"pbkdf2${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def verify_pbkdf2_hash(stored, password):
    try:
        parts = stored.split('$')
        if parts[0] != 'pbkdf2':
            return False
        iterations = int(parts[1])
        salt = binascii.unhexlify(parts[2])
        dk = binascii.unhexlify(parts[3])
        test = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
        return hashlib.compare_digest(test, dk)
    except Exception:
        return False

def load_teachers(path):
    teachers = {}
    if not os.path.exists(path):
        return teachers
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            username = r.get('username','').strip()
            teachers[username] = {'password': r.get('password',''), 'is_admin': r.get('is_admin','').upper()=='TRUE'}
    return teachers

def save_teachers(path, teachers_dict):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['username','password','is_admin'])
        for u, v in teachers_dict.items():
            writer.writerow([u, v['password'], 'TRUE' if v.get('is_admin') else 'FALSE'])

# ---------- PDF/JPG Generation ----------
def create_report_card_bytes(student_name, student_grade, subjects_scores, skills_scores, teacher_comments, prepared_by, output_format="PDF"):
    buffer = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    margin = 15 * mm

    # header/footer heights
    header_h = 55 * mm
    footer_h = 50 * mm
    if os.path.exists(HEADER_IMG):
        try:
            header = ImageReader(HEADER_IMG)
            c.drawImage(header, 0, height - header_h, width=width, height=header_h, preserveAspectRatio=True, mask='auto')
        except:
            pass
    if os.path.exists(FOOTER_IMG):
        try:
            footer = ImageReader(FOOTER_IMG)
            c.drawImage(footer, 0, 0, width=width, height=footer_h, preserveAspectRatio=True, mask='auto')
        except:
            pass

    # school banner text
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height - header_h + 10, "BIGS Campus School Report Generator")

    # student info
    top_y = height - header_h - 10 * mm
    c.setFont("Helvetica-Bold", 18)
    c.drawString(15 * mm, top_y, f"Name: {capitalize_first(student_name)}")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(width/2 + 15 * mm/2, top_y, f"Grade: {capitalize_first(student_grade)}")

    # load merit mapping
    merit = load_merit_csv(MERIT_CSV)

    # subjects table
    subj_data = [["SUBJECTS", "SCORED", "TOTAL MARK", "GRADE", "COMMENTS"]]
    total_scored = 0
    total_out = 0
    for subj in FIXED_SUBJECTS:
        score = float(subjects_scores.get(subj, 0) or 0)
        total = int(merit.get(subj, {}).get('total', 100))
        grade, comment = find_grade_comment(merit, subj, score)
        subj_data.append([subj, str(int(score)), str(total), grade, comment])
        total_scored += score
        total_out += total
    percentage = (total_scored / total_out * 100) if total_out else 0
    subj_data.append(["TOTAL", str(int(total_scored)), str(int(total_out)), f"{percentage:.1f}%", ""])

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

    # skills table
    skill_data = [["SKILLS / WORK HABITS", "SCORE", "COMMENTS"]]
    for sk in SKILL_NAMES:
        sc = skills_scores.get(sk, 1)
        comment = {4:"Outstanding",3:"Accomplished",2:"Progressing",1:"Beginning"}.get(int(sc), "")
        skill_data.append([sk, str(sc), comment])

    skill_col_widths = [55 * mm, 25 * mm, 90 * mm]
    skill_table = Table(skill_data, colWidths=skill_col_widths)
    skill_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#dde2df")),
        ('GRID', (0,0), (-1,-1), 0.25, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))

    subj_table.wrapOn(c, width, height)
    skill_table.wrapOn(c, width, height)

    current_y = top_y - 20 * mm
    subj_h = subj_table._height
    subj_table.drawOn(c, 15 * mm, current_y - subj_h)
    current_y = current_y - subj_h - 6 * mm
    skill_h = skill_table._height
    skill_table.drawOn(c, 15 * mm, current_y - skill_h)
    current_y = current_y - skill_h - 8 * mm

    # Comments by teacher above footer
    c.setFont("Helvetica-Bold", 11)
    c.drawString(15 * mm, current_y, "Comments by Teacher:")
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
        c.drawString(15 * mm, current_y - 12*(i+1), ln)

    # status and prepared on
    current_y = current_y - 12*(len(lines)+1) - 6 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(15 * mm, current_y, "Status:")
    c.setFont("Helvetica", 10)
    c.drawString(15 * mm + 50, current_y, "PASSED" if percentage >= 40 else "FAILED")
    c.drawString(15 * mm + 140, current_y, f"Prepared on: {datetime.now().strftime('%d/%m/%Y')}")
    c.drawString(15 * mm + 300, current_y, f"Prepared by: {prepared_by}")

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

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Report Card Generator - BIGS Campus School", layout="wide")
st.title("BIGS Campus School Report Generator")

# session state for login
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['username'] = None
    st.session_state['is_admin'] = False

teachers = load_teachers(TEACHERS_CSV)

# Login form
if not st.session_state['logged_in']:
    st.subheader("Teacher Login")
    uname = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Login"):
            if uname in teachers and verify_pbkdf2_hash(teachers[uname]['password'], pwd):
                st.session_state['logged_in'] = True
                st.session_state['username'] = uname
                st.session_state['is_admin'] = teachers[uname].get('is_admin', False)
                st.experimental_rerun()
            else:
                st.error("Invalid username or password.")
    with col2:
        st.write("")  # placeholder for layout
    st.stop()

# Logged in area
st.markdown(f"**Logged in as: {st.session_state['username']} {'(Admin)' if st.session_state['is_admin'] else '(Teacher)'}**")
col_logout = st.button("Logout")
if col_logout:
    st.session_state['logged_in'] = False
    st.session_state['username'] = None
    st.session_state['is_admin'] = False
    st.experimental_rerun()

# Admin-only add/update teacher in sidebar
if st.session_state.get('is_admin'):
    st.sidebar.header("Admin: Add / Update Teacher")
    new_user = st.sidebar.text_input("Username")
    new_pass = st.sidebar.text_input("Password", type="password")
    is_admin_chk = st.sidebar.checkbox("Is Admin", value=False)
    if st.sidebar.button("Add / Update Teacher"):
        t = load_teachers(TEACHERS_CSV)
        h = make_pbkdf2_hash(new_pass)
        t[new_user] = {'password': h, 'is_admin': is_admin_chk}
        save_teachers(TEACHERS_CSV, t)
        st.sidebar.success(f"Added/Updated user: {new_user}")

st.markdown("---")
st.markdown("### Enter Report Details")

with st.form("entry_form"):
    # name and grade on same line
    c1, c2 = st.columns([2,1])
    with c1:
        name = st.text_input("Student Name", value="")
    with c2:
        grade = st.text_input("Grade / Class", value="")

    st.markdown("#### Academic Scores (enter scored marks only)")
    merit_map = load_merit_csv(MERIT_CSV)
    subjects_scores = {}
    cols = st.columns(3)
    for i, subj in enumerate(FIXED_SUBJECTS):
        total_for_subj = merit_map.get(subj, {}).get('total', 100)
        with cols[i % 3]:
            scored = st.number_input(f"{subj} - Scored", min_value=0, max_value=total_for_subj, value=0, step=1)
            subjects_scores[subj] = scored

    st.markdown("#### Skills & Work Habits Scores (1-4)")
    skills_scores = {}
    cols2 = st.columns(3)
    for i, sk in enumerate(SKILL_NAMES):
        with cols2[i % 3]:
            sc = st.number_input(f"{sk} - Score (1-4)", min_value=1, max_value=4, value=1, step=1)
            skills_scores[sk] = sc

    teacher_comments = st.text_area("Comments by Teacher", value="")
    output_format = st.selectbox("Output Format", ["PDF", "JPG"], index=0)
    submit = st.form_submit_button("Generate Report")

if submit:
    prepared_by = st.session_state.get('username') or ""
    result = create_report_card_bytes(name, grade, subjects_scores, skills_scores, teacher_comments, prepared_by, output_format)
    ext = "pdf" if output_format=="PDF" else "jpg"
    mime = "application/pdf" if output_format=="PDF" else "image/jpeg"
    filename = f"{name.replace(' ', '_')}_ReportCard.{ext}"
    st.success("Report generated successfully.")
    st.download_button("⬇️ Download Report", data=result, file_name=filename, mime=mime)

# Offer sample merit.csv download if missing
if not os.path.exists(MERIT_CSV):
    st.info("Sample merit.csv is available for download. Place a correct merit.csv in the same folder as the app to enable dynamic grading.")
    sample = "Subject,Total,Min,Max,Grade,Comment\n"
    for s in FIXED_SUBJECTS:
        sample += f"{s},100,91,100,A1,Outstanding\n"
        sample += f"{s},100,81,90,A2,Excellent\n"
        sample += f"{s},100,71,80,B1,Very Good\n"
        sample += f"{s},100,61,70,B2,Good\n"
        sample += f"{s},100,51,60,C1,Fair\n"
        sample += f"{s},100,41,50,C2,Average\n"
        sample += f"{s},100,33,40,D,Needs Improvement\n"
        sample += f"{s},100,21,32,E1,Unsatisfactory\n"
        sample += f"{s},100,0,20,E2,Unsatisfactory\n"
    st.download_button("⬇️ Download sample merit.csv", data=sample, file_name="merit.csv", mime="text/csv")
