import streamlit as st
import database
import auth
import sqlite3
import pandas as pd

# Modules (we will create these next)
# import modules.admin as admin
# import modules.teacher as teacher

# Page Config
st.set_page_config(page_title="BIGS Report Card", layout="wide")

# CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #4B4B4B;
    }
    .stApp {
        /* Default transition */
        transition: background-color 0.3s;
    }
</style>
""", unsafe_allow_html=True)

# Session State Init
if 'user' not in st.session_state:
    st.session_state.user = None

def apply_theme(theme_name):
    if theme_name == "Dark":
        st.markdown("""
        <style>
            /* Main App Background */
            .stApp {
                background-color: #0E1117;
                color: #FAFAFA;
            }
            
            /* Sidebar Background */
            [data-testid="stSidebar"] {
                background-color: #262730;
            }
            
            /* Header */
            .main-header {
                color: #FAFAFA;
            }
            
            /* Typography */
            h1, h2, h3, h4, h5, h6, span, p, label, .stMarkdown {
                color: #FAFAFA !important;
            }
            
            /* Inputs (Text, Number, Select) */
            div[data-baseweb="input"] {
                background-color: #262730 !important; 
                border: 1px solid #4B4B4B !important;
            }
            div[data-baseweb="input"] > div {
                background-color: #262730 !important; 
                color: #FAFAFA !important;
            }
            input {
                color: #FAFAFA !important;
            }
            
            /* Selectbox */
            div[data-baseweb="select"] > div {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border: 1px solid #4B4B4B !important;
            }
            
            /* Dataframes & Tables */
            [data-testid="stDataFrame"] {
                background-color: #262730;
                border: 1px solid #4B4B4B;
            }
            div[data-testid="stTable"] {
                color: #FAFAFA;
            }
            
            /* Expander */
            .streamlit-expanderHeader {
                background-color: #262730 !important;
                color: #FAFAFA !important;
            }
            
            /* Tabs */
            button[data-baseweb="tab"] {
                color: #FAFAFA !important;
            }
            button[data-baseweb="tab"][aria-selected="true"] {
                background-color: #262730 !important;
            }
        </style>
        """, unsafe_allow_html=True)
    else:
        # Light Mode (Default) - No Overrides
        st.markdown("""
        <style>
            /* Reset to defaults if needed, but empty block allows Streamlit defaults */
            .stApp {
                background-color: #FFFFFF;
                color: #31333F;
            }
        </style>
        """, unsafe_allow_html=True)

def login():
    st.title("BIGS Campus School - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            conn = database.get_connection()
            c = conn.cursor()
            # Fetch theme too
            try:
                c.execute("SELECT username, password_hash, full_name, role, dashboard_page, theme FROM users WHERE username=?", (username,))
            except sqlite3.OperationalError:
                 # Fallback if column not yet queried in this session/connection context (though init_db should handle it)
                 c.execute("SELECT username, password_hash, full_name, role, dashboard_page, 'Light' FROM users WHERE username=?", (username,))
            
            user = c.fetchone()
            conn.close()
            
            if user and auth.verify_password(user[1], password):
                st.session_state.user = {
                    "username": user[0],
                    "full_name": user[2],
                    "role": user[3],
                    "dashboard_page": user[4],
                    "theme": user[5] if len(user) > 5 else "Light",
                    "password_hash": user[1]
                }
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def logout():
    st.session_state.user = None
    st.rerun()

def main():
    # Database Init (run once safely)
    database.init_db()
    
    # Check for default admin
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()[0] == 0:
        pwhash = auth.make_pbkdf2_hash("admin123")
        c.execute("INSERT INTO users (username, password_hash, full_name, role, dashboard_page, theme) VALUES (?, ?, ?, ?, ?, ?)", 
                  ("admin", pwhash, "System Admin", "Admin", "Admin Dashboard", "Light"))
        conn.commit()
    conn.close()

    if not st.session_state.user:
        login()
        return

    # Sidebar
    user = st.session_state.user
    
    # Apply Theme
    current_theme = user.get("theme", "Light")
    apply_theme(current_theme)

    with st.sidebar:
        st.write(f"Logged in as: **{user['full_name']}**")
        st.write(f"Role: **{user['role']}**")
        
        # Theme Selector
        st.markdown("---")
        st.write("🎨 **Appearance**")
        selected_theme = st.selectbox("Theme", ["Light", "Dark"], index=0 if current_theme == "Light" else 1)
        
        if selected_theme != current_theme:
            # Update DB and Session
            conn = database.get_connection()
            conn.execute("UPDATE users SET theme=? WHERE username=?", (selected_theme, user['username']))
            conn.commit()
            conn.close()
            
            st.session_state.user['theme'] = selected_theme
            st.rerun()

        st.markdown("---")
        with st.expander("Change Password"):
            curr_pass_input = st.text_input("Current Password", type="password")
            new_pass_input = st.text_input("New Password", type="password")
            if st.button("Update Password"):
                if auth.verify_password(user.get("password_hash") or "", curr_pass_input):
                    new_ph = auth.make_pbkdf2_hash(new_pass_input)
                    conn = database.get_connection()
                    conn.execute("UPDATE users SET password_hash=? WHERE username=?", (new_ph, user['username']))
                    conn.commit()
                    conn.close()
                    st.success("Password Updated!")
                else:
                    st.error("Incorrect Current Password")

        st.markdown("---")
        if st.button("Logout"):
            logout()
    
    # Routing based on Dashboard Page Preference
    dash_page = user.get('dashboard_page')
    
    # Fallback if dashboard_page is not set or legacy
    if not dash_page:
        dash_page = f"{user['role']} Dashboard"

    if dash_page == "Admin Dashboard":
        import modules.admin as admin_module
        admin_module.app()
    elif dash_page == "Teacher Dashboard":
        import modules.teacher as teacher_module
        teacher_module.app()
    elif dash_page == "Class Teacher Dashboard":
        import modules.class_teacher as ct_module
        ct_module.app()
    elif dash_page == "Principal Dashboard":
        import modules.principal as principal_module
        principal_module.app()
    else:
        st.error(f"Unknown Dashboard: {dash_page}")

if __name__ == "__main__":
    main()
