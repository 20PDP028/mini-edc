"""
Phase D: Mini EDC — Full Streamlit Dashboard
=============================================
Ties together:
  Phase A  → CDISC Validation Engine
  Phase B  → SDTM Dataset Generator
  Phase C  → 21 CFR Part 11 Audit Trail & E-Signatures

Run:
    streamlit run dashboard_phase_d.py

Pages:
  1. 🏠 Home          — study overview & KPIs
  2. ✅ Validation    — Phase A: run CDISC validation, browse findings
  3. 📦 SDTM Export  — Phase B: generate & download SDTM datasets + define.xml
  4. 🔐 Audit Trail  — Phase C: view immutable audit log, verify chain integrity
  5. ✍️ E-Signatures  — Phase C: apply & verify electronic signatures
  6. 👥 Users        — manage users, roles, sessions
  7. 📊 Reports      — compliance report + charts
"""

import sys
import json
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
from cdisc_validation_engine import CDISCValidator, SAMPLE_DATA
from part11_audit import (
    UserManager,
    generate_compliance_report,
    Role,
    DB_PATH,
    init_db,
)
from db_connection import get_conn as _get_conn

# ── path setup ────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

# ── constants ─────────────────────────────────────────────────────────────────
SDTM_OUT = str(HERE.parent / "reports" / "sdtm")
STUDY_ID = "STUDY001"

# ═════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Mini EDC — Clinical Data System",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
[data-testid="stSidebar"] { background: #0f1117; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
[data-testid="stSidebar"] .stRadio label { font-size: 14px; padding: 4px 0; }
[data-testid="metric-container"] {
    background: #1a1d27; border: 1px solid #2a2d3a;
    border-radius: 10px; padding: 16px !important;
}
.badge-critical { background:#4a1515; color:#ff6b6b; padding:2px 10px; border-radius:4px; font-size:12px; font-weight:600; }
.badge-major    { background:#3d2a00; color:#ffa940; padding:2px 10px; border-radius:4px; font-size:12px; font-weight:600; }
.badge-minor    { background:#0d2b4a; color:#69b1ff; padding:2px 10px; border-radius:4px; font-size:12px; font-weight:600; }
.badge-ok       { background:#0d3320; color:#52c41a; padding:2px 10px; border-radius:4px; font-size:12px; font-weight:600; }
.section-hdr { border-left: 3px solid #5b5fc7; padding-left: 10px; margin: 1.5rem 0 1rem; font-size: 16px; font-weight: 600; }
.finding-row { border: 1px solid #2a2d3a; border-radius: 8px; padding: 10px 14px; margin-bottom: 6px; background: #1a1d27; }
.sig-card { border: 1px solid #3a2d6a; border-left: 4px solid #5b5fc7; border-radius: 8px; padding: 12px 16px; background: #1a1d27; margin-bottom: 10px; font-size: 13px; }
.audit-entry { border-bottom: 1px solid #2a2d3a; padding: 8px 0; font-size: 13px; }
</style>
""",
    unsafe_allow_html=True,
)


# ═════════════════════════════════════════════════════════════════════════════
def ss(key, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


ss("validation_findings", [])
ss("validation_summary", {})
ss("sdtm_datasets", {})
ss("sdtm_generated", False)
ss("logged_in_user", None)
ss("page", "🏠 Home")


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_db():
    return _get_conn()


def ensure_demo_users():
    um = UserManager(DB_PATH)
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    n = cur.fetchone()
    n = list(n.values())[0] if hasattr(n, "keys") else n[0]
    con.close()
    if n == 0:
        try:
            um.create_user(
                "dr_sharma",
                "Dr. Priya Sharma",
                Role.INVESTIGATOR,
                "sharma@site1.com",
                "Sharma@Trial2024!",
            )
            um.create_user(
                "cdm_raj",
                "Raj Kumar",
                Role.DATA_MANAGER,
                "raj@cro.com",
                "CdmRaj@Trial2024!",
            )
            um.create_user(
                "monitor1",
                "Sarah Chen",
                Role.MONITOR,
                "chen@sponsor.com",
                "Monitor@Trial2024!",
            )
            um.create_user(
                "admin",
                "System Admin",
                Role.ADMIN,
                "admin@trial.com",
                "Admin@Trial2024!",
            )
        except Exception:
            pass


init_db(DB_PATH)
ensure_demo_users()

SEV_ICON = {"CRITICAL": "🔴", "MAJOR": "🟡", "MINOR": "🔵"}
SEV_COLOR = {"CRITICAL": "#ff4d4f", "MAJOR": "#faad14", "MINOR": "#1890ff"}
ACTION_COLOR = {
    "CREATE": "#52c41a",
    "UPDATE": "#1890ff",
    "SIGN": "#722ed1",
    "LOGIN": "#faad14",
    "LOGIN_FAIL": "#ff4d4f",
    "ACCOUNT_LOCK": "#ff4d4f",
    "EXPORT": "#13c2c2",
    "LOCK": "#eb2f96",
}

# ═════════════════════════════════════════════════════════════════════════════
# Sidebar
# ═════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🧬 Mini EDC")
    st.markdown(f"**Study:** {STUDY_ID}")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        [
            "🏠 Home",
            "✅ Validation",
            "📦 SDTM Export",
            "🔐 Audit Trail",
            "✍️ E-Signatures",
            "👥 Users",
            "📊 Reports",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    if st.session_state.logged_in_user:
        u = st.session_state.logged_in_user
        st.markdown(f"**{u['display_name']}**  \n`{u['role']}`")
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in_user = None
            st.rerun()
    else:
        st.markdown("*Not signed in*")
    st.markdown("---")
    st.markdown(
        "<div style='font-size:11px;color:#666'>Phase A · Phase B · Phase C<br>CDISC SDTM v1.8 · 21 CFR Part 11</div>",
        unsafe_allow_html=True,
    )

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 6 — USERS
# ═════════════════════════════════════════════════════════════════════════════
if page == "👥 Users":
    st.title("👥 User Management — §11.10(d) Access Control")

    con = get_db()
    cur = con.cursor()
    cur.execute(
        "SELECT username, display_name, role, email, "
        "failed_attempts, locked, last_login, created_at, active "
        "FROM users ORDER BY created_at DESC"
    )
    users = [dict(r) for r in cur.fetchall()]
    con.close()

    ucols = [
        "Username",
        "Display Name",
        "Role",
        "Email",
        "Failed",
        "Locked",
        "Last Login",
        "Created",
        "Active",
    ]
    df_u = pd.DataFrame(users, columns=ucols) if users else pd.DataFrame(columns=ucols)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total users", len(df_u))
    m2.metric("Active", int(df_u["Active"].sum()) if not df_u.empty else 0)
    m3.metric("Locked", int(df_u["Locked"].sum()) if not df_u.empty else 0)
    m4.metric("Roles", df_u["Role"].nunique() if not df_u.empty else 0)

    if not df_u.empty:
        role_counts = df_u["Role"].value_counts().reset_index()
        role_counts.columns = ["Role", "Count"]
        fig = px.pie(
            role_counts,
            names="Role",
            values="Count",
            hole=0.5,
            title="Users by role",
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig.update_layout(
            height=250,
            plot_bgcolor="#0f1117",
            paper_bgcolor="#0f1117",
            font_color="#e0e0e0",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df_u, use_container_width=True)

    st.markdown(
        '<div class="section-hdr">Create New User</div>', unsafe_allow_html=True
    )
    with st.form("new_user_form"):
        nc1, nc2 = st.columns(2)
        with nc1:
            new_username = st.text_input("Username")
            new_display = st.text_input("Display name")
            new_email = st.text_input("Email")
        with nc2:
            new_role = st.selectbox("Role", [r.value for r in Role])
            new_pw = st.text_input(
                "Password",
                type="password",
                help="Min 12 chars, upper+lower+digit+special",
            )
            new_pw2 = st.text_input("Confirm password", type="password")

        submitted = st.form_submit_button("Create User", use_container_width=True)
        if submitted:
            if new_pw != new_pw2:
                st.error("Passwords do not match")
            elif not all([new_username, new_display, new_email, new_pw]):
                st.error("All fields are required")
            else:
                um = UserManager(DB_PATH)
                try:
                    uid = um.create_user(
                        new_username,
                        new_display,
                        Role(new_role),
                        new_email,
                        new_pw,
                        created_by="admin",
                    )
                    st.success(f"User **{new_username}** created (ID: {uid[:8]}…)")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    st.markdown("---")
    st.info(
        "**Demo credentials:**\n\n"
        "- `dr_sharma` / `Sharma@Trial2024!` (Investigator)\n"
        "- `cdm_raj` / `CdmRaj@Trial2024!` (Data Manager)\n"
        "- `monitor1` / `Monitor@Trial2024!` (Monitor)\n"
        "- `admin` / `Admin@Trial2024!` (Admin)"
    )

# ═════════════════════════════════════════════════════════════════════════════
# PAGE 7 — REPORTS
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📊 Reports":
    st.title("📊 Compliance Reports")
    report = generate_compliance_report(DB_PATH)

    st.markdown(
        '<div class="section-hdr">21 CFR Part 11 Compliance Status</div>',
        unsafe_allow_html=True,
    )
    for req, met in report["requirements_met"].items():
        icon = "✅" if met else "❌"
        color = "#52c41a" if met else "#ff4d4f"
        st.markdown(
            f'<div style="padding:6px 12px;margin:3px 0;border-radius:6px;background:#1a1d27;border:1px solid #2a2d3a;font-size:13px">'
            f'<span style="color:{color}">{icon}</span>&nbsp;&nbsp;{req}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-hdr">Statistics</div>', unsafe_allow_html=True)
    stats = report["statistics"]
    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    mc1.metric("Users", stats["users"])
    mc2.metric("Sessions", stats["sessions"])
    mc3.metric("Audit entries", stats["audit_entries"])
    mc4.metric("E-signatures", stats["e_signatures"])
    mc5.metric("CRF records", stats["crf_records"])

    if report["audit_actions"]:
        st.markdown(
            '<div class="section-hdr">Audit Activity</div>', unsafe_allow_html=True
        )
        action_df = pd.DataFrame(
            [{"Action": k, "Count": v} for k, v in report["audit_actions"].items()]
        )
        fig = px.bar(
            action_df,
            x="Action",
            y="Count",
            color="Action",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            title="Audit actions",
        )
        fig.update_layout(
            showlegend=False,
            height=300,
            plot_bgcolor="#0f1117",
            paper_bgcolor="#0f1117",
            font_color="#e0e0e0",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div class="section-hdr">Chain Integrity Report</div>', unsafe_allow_html=True
    )
    integ = report["integrity"]
    ic1, ic2, ic3 = st.columns(3)
    ic1.metric("Total entries", integ["total_entries"])
    ic2.metric("Tampered", integ["tampered_count"])
    ic3.metric("Integrity", "✅ OK" if integ["integrity_ok"] else "❌ FAIL")

    st.download_button(
        "⬇ Download full compliance report (JSON)",
        json.dumps(report, indent=2),
        file_name="part11_compliance_report.json",
        mime="application/json",
    )

    st.markdown(
        '<div class="section-hdr">Live Validation Summary</div>', unsafe_allow_html=True
    )
    if st.button("🔄 Re-run CDISC validation"):
        validator = CDISCValidator()
        findings = validator.run_all(SAMPLE_DATA)
        summary = validator.summary()
        st.json(summary)
