"""
BIGS Campus School Report Card Generator - v7
Full-feature version with:
- Secure login (PBKDF2)
- Welcome message (capitalized name)
- Admin sidebar (upload images/CSVs, manage users, change password)
- Teacher password change
- PDF/JPG report generator with merit.csv auto grading
"""

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
def capitalize_first(text): return str(text).capitalize()

def make_pbkdf2_hash(password, iterations=200000):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
    return f"pbkdf2${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def verify_password(stored, provided):
    try:
        if stored.startswith("pbkdf2$"):
            _, iters, salt_hex, stored_hash = stored.split('$')
            salt = binascii.unhexlify(salt_hex)
            dk = hashlib.pbkdf2_hmac('sha256', provided.encode(), salt, int(iters))
            return binascii.hexlify(dk).decode() == stored_hash
        return stored == provided
    except Exception:
        return False

def load_teachers(path):
    if not os.path.exists(path): return {}
    with open(path, newline='', encoding='utf-8') as f:
        return {r['username']: {'password': r['password'],'is_admin':r['is_admin'].upper()=='TRUE'} for r in csv.DictReader(f)}

def save_teachers(path, teachers):
    with open(path, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["username","password","is_admin"])
        for u,v in teachers.items():
            writer.writerow([u,v["password"],"TRUE" if v["is_admin"] else "FALSE"])

def load_merit(path):
    data = {}
    if not os.path.exists(path): return data
    with open(path,newline='',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            subj=r.get('Subject','').upper()
            try:
                mn=float(r.get('Min',0)); mx=float(r.get('Max',0))
            except:
                mn=0; mx=0
            data.setdefault(subj,[]).append((mn,mx,r.get('Grade',''),r.get('Comment','')))
    return data

def grade_comment(merit,subj,score):
    subj=subj.upper()
    if subj in merit:
        for mn,mx,g,c in merit[subj]:
            if mn<=score<=mx: return g,c
    if 'ALL' in merit:
        for mn,mx,g,c in merit['ALL']:
            if mn<=score<=mx: return g,c
    return "",""

# ---------- Streamlit setup ----------
st.set_page_config("Report Card Generator - BIGS Campus School", layout="wide")

# ensure teachers.csv exists
if not os.path.exists(TEACHERS_CSV):
    with open(TEACHERS_CSV,"w",newline='',encoding="utf-8") as f:
        writer=csv.writer(f); writer.writerow(["username","password","is_admin"])
        writer.writerow(["amina",make_pbkdf2_hash("1234"),"TRUE"])

if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in':False,'username':None,'is_admin':False})

teachers=load_teachers(TEACHERS_CSV)

# ---------- Login ----------
if not st.session_state['logged_in']:
    st.title("BIGS Campus School Report Generator")
    st.subheader("Teacher Login")
    uname=st.text_input("Username")
    pwd=st.text_input("Password",type="password")
    if st.button("Login"):
        if uname in teachers and verify_password(teachers[uname]['password'],pwd):
            st.session_state.update({'logged_in':True,'username':uname,'is_admin':teachers[uname]['is_admin']})
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()

# ---------- Sidebar ----------
user=st.session_state['username']
is_admin=st.session_state['is_admin']

st.sidebar.markdown(f"👤 Logged in as: **{capitalize_first(user)} {'(Admin)' if is_admin else '(Teacher)'}**")
if st.sidebar.button("🚪 Logout"):
    st.session_state.update({'logged_in':False,'username':None,'is_admin':False})
    st.rerun()

if is_admin:
    with st.sidebar.expander("📸 Upload Image Files", expanded=False):
        top=st.file_uploader("Upload top.jpg",type=["jpg","jpeg"],key="topimg")
        if top:
            open(HEADER_IMG,"wb").write(top.read())
            st.success("✅ top.jpg uploaded successfully.")
        bottom=st.file_uploader("Upload bottom.jpg",type=["jpg","jpeg"],key="bottomimg")
        if bottom:
            open(FOOTER_IMG,"wb").write(bottom.read())
            st.success("✅ bottom.jpg uploaded successfully.")

    with st.sidebar.expander("📊 Upload CSV Files", expanded=False):
        merit=st.file_uploader("Upload merit.csv",type=["csv"],key="meritcsv")
        if merit:
            open(MERIT_CSV,"wb").write(merit.read()); st.success("✅ merit.csv updated.")
        teachers_csv=st.file_uploader("Upload teachers.csv",type=["csv"],key="teachcsv")
        if teachers_csv:
            open(TEACHERS_CSV,"wb").write(teachers_csv.read()); st.success("✅ teachers.csv updated."); st.rerun()

    with st.sidebar.expander("👥 Manage Users", expanded=False):
        newu=st.text_input("Username",key="newu")
        newp=st.text_input("Password",type="password",key="newp")
        adm=st.checkbox("Is Admin",key="newadmin")
        if st.button("Add / Update Teacher",key="addbtn"):
            t=load_teachers(TEACHERS_CSV)
            t[newu]={'password':make_pbkdf2_hash(newp),'is_admin':adm}
            save_teachers(TEACHERS_CSV,t); st.success(f"✅ User '{newu}' added/updated.")

    with st.sidebar.expander("🔑 Change Password", expanded=False):
        oldp=st.text_input("Current Password",type="password",key="oldp")
        newp=st.text_input("New Password",type="password",key="newpadmin")
        if st.button("Update Admin Password",key="chgpwadmin"):
            t=load_teachers(TEACHERS_CSV)
            if user in t and verify_password(t[user]['password'],oldp):
                t[user]['password']=make_pbkdf2_hash(newp); save_teachers(TEACHERS_CSV,t)
                st.success("✅ Password changed successfully."); st.rerun()
            else: st.error("Invalid current password.")

else:
    with st.sidebar.expander("🔑 Change My Password", expanded=False):
        oldp=st.text_input("Current Password",type="password",key="oldpuser")
        newp=st.text_input("New Password",type="password",key="newpuser")
        if st.button("Change My Password",key="chgpwuser"):
            t=load_teachers(TEACHERS_CSV)
            if user in t and verify_password(t[user]['password'],oldp):
                t[user]['password']=make_pbkdf2_hash(newp); save_teachers(TEACHERS_CSV,t)
                st.success("✅ Password changed successfully."); st.rerun()
            else: st.error("Invalid current password.")

# ---------- Welcome message ----------
st.title("🎉 Welcome back, " + capitalize_first(user) + "!")
st.markdown("---")

# ---------- Report Generator ----------
st.subheader("Generate Student Report Card")
with st.form("report_form"):
    c1,c2=st.columns([2,1])
    with c1: name=st.text_input("Student Name")
    with c2: grade=st.text_input("Grade / Class")

    st.markdown("#### Academic Scores")
    merit=load_merit(MERIT_CSV)
    subscores={}
    cols=st.columns(3)
    for i,s in enumerate(FIXED_SUBJECTS):
        with cols[i%3]: subscores[s]=st.number_input(f"{s} - Scored",0,100,0,1)

    st.markdown("#### Skills & Work Habits (1-4)")
    skillscores={}
    cols2=st.columns(3)
    for i,s in enumerate(SKILL_NAMES):
        with cols2[i%3]: skillscores[s]=st.number_input(f"{s} - Score",1,4,1,1)

    comments=st.text_area("Comments by Teacher")
    fmt=st.selectbox("Output Format",["PDF","JPG"])
    submit=st.form_submit_button("Generate Report")

if submit:
    from reportlab.pdfgen import canvas
    buf=io.BytesIO(); width,height=A4; c=canvas.Canvas(buf,pagesize=A4)
    if os.path.exists(HEADER_IMG): c.drawImage(ImageReader(HEADER_IMG),0,height-55*mm,width=width,height=55*mm)
    if os.path.exists(FOOTER_IMG): c.drawImage(ImageReader(FOOTER_IMG),0,0,width=width,height=50*mm)
    c.setFont("Helvetica-Bold",18); c.drawString(15*mm,height-65*mm,f"Name: {name.capitalize()}")
    c.setFont("Helvetica-Bold",14); c.drawString(width/2+15*mm/2,height-65*mm,f"Grade: {grade.capitalize()}")
    subj=[["SUBJECTS","SCORED","TOTAL","GRADE","COMMENTS"]]; total_s=0; total_t=0
    for s in FIXED_SUBJECTS:
        score=subscores.get(s,0); g,cmt=grade_comment(merit,s,score); subj.append([s,str(score),"100",g,cmt]); total_s+=score; total_t+=100
    perc=total_s/total_t*100 if total_t else 0; subj.append(["TOTAL",str(total_s),str(total_t),f"{perc:.1f}%",""])
    t=Table(subj,colWidths=[55*mm,25*mm,25*mm,25*mm,40*mm])
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.25,colors.black),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dde2df')),
                           ('BACKGROUND',(0,len(subj)-1),(-1,len(subj)-1),colors.HexColor(TOTAL_ROW_COLOR)),
                           ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,len(subj)-1),(-1,len(subj)-1),'Helvetica-Bold'),
                           ('ALIGN',(1,1),(-1,-1),'CENTER'),('FONTSIZE',(0,0),(-1,-1),9)]))
    top_y=height-85*mm; t.wrapOn(c,width,height); t.drawOn(c,15*mm,top_y-t._height)
    c.setFont("Helvetica",10); c.drawString(15*mm,top_y-t._height-10*mm,"Status: "+("PASSED" if perc>=40 else "FAILED"))
    c.drawString(15*mm+140,top_y-t._height-10*mm,f"Prepared on: {datetime.now().strftime('%d/%m/%Y')}")
    c.drawString(15*mm+300,top_y-t._height-10*mm,f"Prepared by: {capitalize_first(user)}")
    c.showPage(); c.save(); pdf=buf.getvalue(); buf.close()
    if fmt=="JPG":
        try:
            from pdf2image import convert_from_bytes
            img=convert_from_bytes(pdf,fmt='jpeg')[0]; out=io.BytesIO(); img.save(out,format='JPEG')
            data=out.getvalue(); mime="image/jpeg"; ext="jpg"
        except Exception:
            data=pdf; mime="application/pdf"; ext="pdf"
    else: data=pdf; mime="application/pdf"; ext="pdf"
    st.download_button("⬇️ Download Report",data=data,file_name=f"{name.replace(' ','_')}_ReportCard.{ext}",mime=mime)
