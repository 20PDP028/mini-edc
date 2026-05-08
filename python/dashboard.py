"""
dashboard.py — Phase 5+6: CDM Dashboard with Login, Roles & E-Signature
Save in: Mini_EDC_Project/python/dashboard.py
Run with: python -m streamlit run dashboard.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import os
import sys
from datetime import datetime

st.set_page_config(page_title="Mini EDC | CDM System", page_icon="🏥", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background-color: #0A0E1A; color: #E8EDF5; }
[data-testid="stSidebar"] { background-color: #0D1526; border-right: 1px solid #1E2D4A; }
.kpi-card { background: linear-gradient(135deg,#0D1F3C,#132847); border:1px solid #1E3A5F; border-radius:12px; padding:20px 24px; text-align:center; margin-bottom:8px; }
.kpi-value { font-family:'IBM Plex Mono',monospace; font-size:2.4rem; font-weight:600; line-height:1; margin-bottom:4px; }
.kpi-label { font-size:0.75rem; text-transform:uppercase; letter-spacing:0.12em; color:#7A9CC0; font-weight:600; }
.section-header { font-family:'IBM Plex Mono',monospace; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.2em; color:#4A7AAF; border-bottom:1px solid #1E3A5F; padding-bottom:8px; margin-bottom:16px; margin-top:24px; }
.alert-sae { background:linear-gradient(135deg,#1A0A0A,#2D0F0F); border:1px solid #C62828; border-left:4px solid #C62828; border-radius:8px; padding:14px 18px; margin-bottom:10px; }
.role-badge { display:inline-block; padding:3px 14px; border-radius:20px; font-size:0.75rem; font-weight:700; letter-spacing:0.08em; }
.role-DM { background:#0D47A1; color:#fff; }
.role-MONITOR { background:#1B5E20; color:#fff; }
.role-SITE { background:#E65100; color:#fff; }
.role-ADMIN { background:#4A148C; color:#fff; }
.sig-box { background:#0D1F3C; border:1px solid #1E3A5F; border-left:4px solid #00897B; border-radius:8px; padding:14px 18px; margin-bottom:8px; font-size:0.85rem; }
#MainMenu {visibility:hidden;} footer {visibility:hidden;} header {visibility:hidden;}
</style>
""", unsafe_allow_html=True)

BASE    = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, '..', 'sql', 'cdm_phase3.db')
sys.path.insert(0, BASE)

try:
    from auth_manager import init_auth_tables, login, esign, get_signatures, get_all_users, PERMISSIONS
    if os.path.exists(DB_PATH):
        init_auth_tables()
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# ══════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.markdown("<div style='text-align:center;padding:40px 0 10px 0;'><div style='font-family:IBM Plex Mono,monospace;font-size:2rem;color:#4A9EDB;font-weight:600;'>🏥 Mini EDC</div><div style='color:#4A7AAF;font-size:0.85rem;letter-spacing:0.15em;text-transform:uppercase;margin-top:6px;'>Clinical Data Management System</div></div>", unsafe_allow_html=True)

    _, col_c, _ = st.columns([1, 1.2, 1])
    with col_c:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        uid = st.text_input("User ID", placeholder="e.g. DM_JOHN")
        pwd = st.text_input("Password", type="password", placeholder="Enter password")
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if st.button("🔐  Sign In", use_container_width=True, type="primary"):
            demo_users = {
                "DM_JOHN":    {"user_id":"DM_JOHN",    "full_name":"John Smith",   "role":"DM",      "permissions":["view_dashboard","view_queries","view_saes","view_audit","close_query","answer_query","generate_pdf","view_signatures"]},
                "MONITOR_01": {"user_id":"MONITOR_01", "full_name":"Sarah Jones",  "role":"MONITOR", "permissions":["view_dashboard","view_queries","view_saes","view_audit","generate_pdf","view_signatures"]},
                "SITE_001":   {"user_id":"SITE_001",   "full_name":"Site Staff A", "role":"SITE",    "permissions":["view_dashboard","view_queries","answer_query"]},
                "ADMIN":      {"user_id":"ADMIN",      "full_name":"System Admin",  "role":"ADMIN",   "permissions":["view_dashboard","view_queries","view_saes","view_audit","close_query","answer_query","generate_pdf","view_signatures","manage_users"]},
            }
            demo_pwd = {"DM_JOHN":"dm123","MONITOR_01":"monitor123","SITE_001":"site123","ADMIN":"admin123"}

            if AUTH_AVAILABLE and os.path.exists(DB_PATH):
                ok, user_data, token = login(uid.strip(), pwd)
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.user = user_data
                    st.rerun()
                else:
                    st.error(user_data.get("error", "Invalid credentials"))
            elif uid in demo_users and demo_pwd.get(uid) == pwd:
                st.session_state.logged_in = True
                st.session_state.user = demo_users[uid]
                st.rerun()
            else:
                st.error("Invalid credentials")

        st.markdown("""<div style='margin-top:20px;padding:14px;background:#0D1F3C;border-radius:8px;border:1px solid #1E3A5F;font-size:0.78rem;color:#4A7AAF;'>
        <b style='color:#7A9CC0;'>Default Accounts</b><br><br>
        🔵 <b>DM_JOHN</b> / dm123 — Data Manager<br>
        🟢 <b>MONITOR_01</b> / monitor123 — Monitor<br>
        🟠 <b>SITE_001</b> / site123 — Site Staff<br>
        🟣 <b>ADMIN</b> / admin123 — Administrator
        </div>""", unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════
# AUTHENTICATED
# ══════════════════════════════════════════════════════════════
user = st.session_state.user

def can(perm):
    return perm in user.get("permissions", [])

with st.sidebar:
    role = user["role"]
    st.markdown(f"""<div style='padding:12px 0 4px 0;'>
        <div style='font-family:IBM Plex Mono,monospace;font-size:1rem;color:#4A9EDB;font-weight:600;'>🏥 Mini EDC</div>
        <div style='font-size:0.65rem;color:#4A7AAF;text-transform:uppercase;letter-spacing:0.1em;'>Clinical Data Management</div></div>
        <div style='margin:10px 0;padding:10px 12px;background:#0D1F3C;border-radius:8px;border:1px solid #1E3A5F;'>
        <div style='font-size:0.85rem;font-weight:600;color:#E8EDF5;'>{user["full_name"]}</div>
        <div style='margin-top:4px;'><span class='role-badge role-{role}'>{role}</span></div>
        <div style='font-size:0.7rem;color:#4A7AAF;margin-top:6px;'>{user["user_id"]}</div></div>""", unsafe_allow_html=True)

    st.markdown("---")
    pages = []
    if can("view_dashboard"):
        pages.append("📊 Dashboard")
    if can("view_queries"):
        pages.append("🔍 Query Management")
    if can("view_saes"):
        pages.append("⚠️ SAE Monitor")
    if can("view_audit"):
        pages.append("📋 Audit Trail")
    if can("view_signatures"):
        pages.append("✍️ E-Signatures")
    if can("generate_pdf"):
        pages.append("📄 Generate PDF")
    if can("manage_users"):
         pages.append("👥 User Management")
    page = st.radio("Navigation", pages, label_visibility="collapsed")

    st.markdown("---")
    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()
    st.success("✅ DB connected") if os.path.exists(DB_PATH) else st.warning("⚠️ Demo mode")

def load_df(table):
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        conn.close() 
        return df
    except Exception as e: 
        st.error(f"Error loading data from {table}: {e}")
        return pd.DataFrame()

df_queries  = load_df("queries")
df_saes     = load_df("adverse_events")
df_audit    = load_df("audit_trail")
df_subjects = load_df("subjects")

# ── Dashboard ─────────────────────────────────────────────────
if page == "📊 Dashboard":
    st.markdown(f"<h1 style='font-family:IBM Plex Mono,monospace;font-size:1.6rem;color:#E8EDF5;'>CDM Dashboard</h1><div style='color:#4A7AAF;font-size:0.8rem;margin-bottom:24px;'>Welcome back, {user['full_name']} · {datetime.now().strftime('%d %b %Y %H:%M')}</div>", unsafe_allow_html=True)

    if "status" in df_queries.columns:
        open_q = len(df_queries[df_queries["status"] == "Open"])
        ans_q = len(df_queries[df_queries["status"] == "Answered"])
        cls_q = len(df_queries[df_queries["status"] == "Closed"])
    else:
        open_q = 0
        ans_q = 0
        cls_q = 0

    if "report_flag" in df_saes.columns:
        pending_sae = len(df_saes[df_saes["report_flag"] == "PENDING"])
    else:
        pending_sae = 0

    for col, val, label, color in zip(st.columns(6),
        [len(df_queries), open_q, ans_q, cls_q, len(df_saes), len(df_subjects)],
        ["Total Queries","Open","Answered","Closed","SAEs","Subjects"],
        ["#4A9EDB","#C62828","#E65100","#00897B","#6A1B9A","#1565C0"]):
        col.markdown(f"<div class='kpi-card'><div class='kpi-value' style='color:{color};'>{val}</div><div class='kpi-label'>{label}</div></div>", unsafe_allow_html=True)

    cl, cr = st.columns(2)
    with cl:
        st.markdown("<div class='section-header'>Query Status</div>", unsafe_allow_html=True)
        if not df_queries.empty and "status" in df_queries.columns:
            st.bar_chart(df_queries["status"].value_counts(), color="#4A9EDB", height=200)
    with cr:
        st.markdown("<div class='section-header'>Severity</div>", unsafe_allow_html=True)
        if not df_queries.empty and "severity" in df_queries.columns:
            st.bar_chart(df_queries["severity"].value_counts(), color="#C62828", height=200)

    if pending_sae > 0:
        st.markdown("<div class='section-header'>⚠️ SAE Alerts</div>", unsafe_allow_html=True)
        for _, r in df_saes[df_saes["report_flag"]=="PENDING"].iterrows():
            st.markdown(f"<div class='alert-sae'>🚨 <b>SAE PENDING</b> | Subject: <b>{r.get('usubjid','')}</b> | Site: {r.get('siteid','')} | Event: <b>{r.get('aeterm','')}</b> | Severity: {r.get('aesev','')} | Date: {r.get('aestdtc','')}</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-header'>Recent Open Queries</div>", unsafe_allow_html=True)
    open_df = df_queries[df_queries["status"]=="Open"] if "status" in df_queries.columns else df_queries
    if not open_df.empty:
        cols = [c for c in ["query_id","usubjid","siteid","field_name","severity","issue_description"] if c in open_df.columns]
        st.dataframe(open_df[cols].head(5), use_container_width=True, hide_index=True)

# ── Query Management ──────────────────────────────────────────
elif page == "🔍 Query Management":
    st.markdown("<h1 style='font-family:IBM Plex Mono,monospace;font-size:1.6rem;color:#E8EDF5;'>Query Management</h1>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    sf = c1.selectbox("Status",   ["All"]+list(df_queries["status"].unique())   if "status"   in df_queries.columns else ["All"])
    sv = c2.selectbox("Severity", ["All"]+list(df_queries["severity"].unique()) if "severity" in df_queries.columns else ["All"])
    ss = c3.selectbox("Site",     ["All"]+list(df_queries["siteid"].unique())   if "siteid"   in df_queries.columns else ["All"])

    filt = df_queries.copy()
    if sf!="All" and "status"   in filt.columns:
        filt = filt[filt["status"]  ==sf]
    if sv!="All" and "severity" in filt.columns:
        filt = filt[filt["severity"]==sv]
    if ss!="All" and "siteid"   in filt.columns:
        filt = filt[filt["siteid"]  ==ss]
    st.dataframe(filt, use_container_width=True, hide_index=True, height=300)

    if can("answer_query") or can("close_query"):
        st.markdown("<div class='section-header'>Update Query Status</div>", unsafe_allow_html=True)
        ca,cb,cc = st.columns(3)
        sel_q = ca.selectbox("Query", df_queries["query_id"].tolist() if "query_id" in df_queries.columns else [])
        statuses = (["Answered"] if can("answer_query") else []) + (["Closed"] if can("close_query") else [])
        new_status = cb.selectbox("New Status", statuses)
        by_user = cc.text_input("Your ID", value=user["user_id"])

        if new_status == "Closed":
            st.info("✍️ Closing requires your E-Signature (21 CFR Part 11)")
            sig_pwd = st.text_input("Password to sign", type="password")
            sig_meaning = st.text_input("Signature Meaning", value="I certify this query has been reviewed and resolved")

        if st.button("✅ Update Query", type="primary"):
            if os.path.exists(DB_PATH):
                conn2 = sqlite3.connect(DB_PATH)
                conn2.execute("UPDATE queries SET status=?,resolved_at=? WHERE query_id=?",
                              (new_status, datetime.now().isoformat(), sel_q))
                conn2.execute("INSERT INTO audit_trail (event_time,action,table_name,record_id,field_name,new_value,performed_by) VALUES (?,?,?,?,?,?,?)",
                              (datetime.now().isoformat(), f"QUERY_{new_status.upper()}", "queries", sel_q, "status", new_status, by_user))
                conn2.commit()
                conn2.close()
                if new_status == "Closed" and AUTH_AVAILABLE:
                    ok, msg = esign(user["user_id"], sig_pwd, "QUERY_CLOSE", sel_q, sig_meaning)
                    st.success(msg) if ok else st.error(msg)
                else:
                    st.success(f"✅ {sel_q} → {new_status}")
                st.rerun()
            else:
                st.warning("Demo mode")

# ── SAE Monitor ───────────────────────────────────────────────
elif page == "⚠️ SAE Monitor":
    st.markdown("<h1 style='font-family:IBM Plex Mono,monospace;font-size:1.6rem;color:#E8EDF5;'>SAE Monitor</h1>", unsafe_allow_html=True)
    pending = df_saes[df_saes["report_flag"]=="PENDING"] if "report_flag" in df_saes.columns else pd.DataFrame()
    c1,c2 = st.columns(2)
    c1.metric("Total SAEs", len(df_saes))
    c2.metric("🚨 Pending Report", len(pending))
    if not pending.empty: 
        st.error(f"🚨 {len(pending)} SAE(s) require 24-hour expedited reporting!")
    st.dataframe(df_saes, use_container_width=True, hide_index=True)

# ── Audit Trail ───────────────────────────────────────────────
elif page == "📋 Audit Trail":
    st.markdown("<h1 style='font-family:IBM Plex Mono,monospace;font-size:1.6rem;color:#E8EDF5;'>21 CFR Part 11 — Audit Trail</h1>", unsafe_allow_html=True)
    st.metric("Total Audit Events", len(df_audit))
    search = st.text_input("🔍 Search", placeholder="Filter by action, user, record...")
    disp = df_audit.copy()
    if search:
        mask = disp.astype(str).apply(lambda c: c.str.contains(search, case=False)).any(axis=1)
        disp = disp[mask]
    st.dataframe(disp, use_container_width=True, hide_index=True, height=500)

# ── E-Signatures ──────────────────────────────────────────────
elif page == "✍️ E-Signatures":
    st.markdown("<h1 style='font-family:IBM Plex Mono,monospace;font-size:1.6rem;color:#E8EDF5;'>Electronic Signatures — 21 CFR Part 11</h1>", unsafe_allow_html=True)
    st.markdown("<div style='color:#4A7AAF;font-size:0.82rem;margin-bottom:20px;'>All signatures are cryptographically verified and immutable.</div>", unsafe_allow_html=True)

    if can("close_query"):
        st.markdown("<div class='section-header'>Create E-Signature</div>", unsafe_allow_html=True)
        ca,cb = st.columns(2)
        with ca:
            sig_action = st.selectbox("Action", ["QUERY_CLOSE","DATA_LOCK","REPORT_APPROVAL","SAE_REVIEW"])
            sig_record = st.text_input("Record ID", placeholder="e.g. QRY-0001")
        with cb:
            sig_meaning = st.text_input("Meaning", value="I approve this record as accurate and complete")
            sig_pwd2    = st.text_input("Your Password", type="password")
        if st.button("✍️ Apply E-Signature", type="primary"):
            if AUTH_AVAILABLE and os.path.exists(DB_PATH):
                ok, msg = esign(user["user_id"], sig_pwd2, sig_action, sig_record, sig_meaning)
                st.success(msg) if ok else st.error(msg)
            else:
                st.warning("Demo mode — connect DB first")

    st.markdown("<div class='section-header'>Signature Log</div>", unsafe_allow_html=True)
    if AUTH_AVAILABLE and os.path.exists(DB_PATH):
        sigs = get_signatures()
        if sigs:
            for s in sigs:
                st.markdown(f"<div class='sig-box'>✍️ <b>{s[2]}</b> <span style='color:#4A7AAF;'>({s[3]})</span> · <b>{s[4]}</b> on <code>{s[5]}</code> · <i>\"{s[6]}\"</i><br><span style='color:#4A7AAF;font-size:0.75rem;'>Signed: {s[7]} · Password verified: {'✅' if s[8] else '❌'}</span></div>", unsafe_allow_html=True)
        else:
            st.info("No signatures yet.")
    else:
        st.info("Connect database to view signatures.")

# ── Generate PDF ──────────────────────────────────────────────
elif page == "📄 Generate PDF":
    st.markdown("<h1 style='font-family:IBM Plex Mono,monospace;font-size:1.6rem;color:#E8EDF5;'>Generate PDF Report</h1>", unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        trial_name   = st.text_input("Trial Name",      value="CARDIO-PHASE2 Trial")
        protocol     = st.text_input("Protocol Number", value="PROTO-CARDIO-002")
    with c2:
        generated_by = st.text_input("Generated By",    value=f"{user['full_name']} ({user['role']})")
        out_name     = st.text_input("Output Filename", value="cdm_audit_report.pdf")

    if st.button("📄 Generate PDF", type="primary"):
        try:
            from pdf_report import generate_pdf
            out_path = os.path.join(BASE, '..', 'reports', out_name)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            generate_pdf(out_path, trial_name,
                         df_queries.rename(columns={"field_name":"field","issue_description":"issue"}).to_dict(orient="records"),
                         df_saes.to_dict(orient="records"),
                         df_audit.rename(columns={"field_name":"field"}).to_dict(orient="records"),
                         generated_by, protocol)
            with open(out_path,"rb") as f:
                st.download_button("⬇️ Download PDF", data=f, file_name=out_name, mime="application/pdf")
            st.success(f"✅ Saved: {os.path.abspath(out_path)}")
        except Exception as e:
            st.error(f"Error: {e}")

# ── User Management ───────────────────────────────────────────
elif page == "👥 User Management":
    st.markdown("<h1 style='font-family:IBM Plex Mono,monospace;font-size:1.6rem;color:#E8EDF5;'>User Management</h1>", unsafe_allow_html=True)
    if AUTH_AVAILABLE and os.path.exists(DB_PATH):
        rows = get_all_users()
        st.dataframe(pd.DataFrame(rows, columns=["User ID","Full Name","Role","Active","Last Login"]),
                     use_container_width=True, hide_index=True)
    st.markdown("<div class='section-header'>Role Permissions</div>", unsafe_allow_html=True)
    if AUTH_AVAILABLE:
        for r, perms in PERMISSIONS.items():
            with st.expander(f"{r}"):
                st.write(" · ".join(perms))
