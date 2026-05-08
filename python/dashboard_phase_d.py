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

import os, sys, json, sqlite3, io, zipfile, csv
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── path setup so we can import our Phase A/B/C modules ──────────────────────
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from cdisc_validation_engine import CDISCValidator, SAMPLE_DATA, Severity
from sdtm_generator import SDTMGenerator, DefineXMLGenerator, SDTMConformanceChecker
from part11_audit import (
    UserManager, ESignatureEngine, AuditTrailEngine, ClinicalRecordManager,
    generate_compliance_report, Role, SignatureReason, RecordStatus,
    DB_PATH, init_db,
)

# ── constants ─────────────────────────────────────────────────────────────────
SDTM_OUT = str(HERE.parent / "reports" / "sdtm")
STUDY_ID = "STUDY001"

# ═════════════════════════════════════════════════════════════════════════════
# Page config & theme
# ═════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Mini EDC — Clinical Data System",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── sidebar nav ── */
[data-testid="stSidebar"] { background: #0f1117; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
[data-testid="stSidebar"] .stRadio label { font-size: 14px; padding: 4px 0; }

/* ── metric cards ── */
[data-testid="metric-container"] {
    background: #1a1d27;
    border: 1px solid #2a2d3a;
    border-radius: 10px;
    padding: 16px !important;
}

/* ── severity badges ── */
.badge-critical { background:#4a1515; color:#ff6b6b; padding:2px 10px;
                  border-radius:4px; font-size:12px; font-weight:600; }
.badge-major    { background:#3d2a00; color:#ffa940; padding:2px 10px;
                  border-radius:4px; font-size:12px; font-weight:600; }
.badge-minor    { background:#0d2b4a; color:#69b1ff; padding:2px 10px;
                  border-radius:4px; font-size:12px; font-weight:600; }
.badge-ok       { background:#0d3320; color:#52c41a; padding:2px 10px;
                  border-radius:4px; font-size:12px; font-weight:600; }

/* ── section headers ── */
.section-hdr {
    border-left: 3px solid #5b5fc7;
    padding-left: 10px;
    margin: 1.5rem 0 1rem;
    font-size: 16px; font-weight: 600;
}

/* ── finding row ── */
.finding-row {
    border: 1px solid #2a2d3a;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 6px;
    background: #1a1d27;
}

/* ── signature card ── */
.sig-card {
    border: 1px solid #3a2d6a;
    border-left: 4px solid #5b5fc7;
    border-radius: 8px;
    padding: 12px 16px;
    background: #1a1d27;
    margin-bottom: 10px;
    font-size: 13px;
}

/* ── audit entry ── */
.audit-entry {
    border-bottom: 1px solid #2a2d3a;
    padding: 8px 0;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# Session state defaults
# ═════════════════════════════════════════════════════════════════════════════
def ss(key, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

ss("validation_findings", [])
ss("validation_summary", {})
ss("sdtm_datasets", {})
ss("sdtm_generated", False)
ss("logged_in_user", None)   # dict from authenticate()
ss("page", "🏠 Home")


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════
def get_db():
    return sqlite3.connect(DB_PATH)

def ensure_demo_users():
    """Seed demo users if none exist."""
    um = UserManager(DB_PATH)
    con = get_db()
    n = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    con.close()
    if n == 0:
        try:
            um.create_user("dr_sharma", "Dr. Priya Sharma", Role.INVESTIGATOR,
                           "sharma@site1.com", "Sharma@Trial2024!")
            um.create_user("cdm_raj",   "Raj Kumar",        Role.DATA_MANAGER,
                           "raj@cro.com",     "CdmRaj@Trial2024!")
            um.create_user("monitor1",  "Sarah Chen",       Role.MONITOR,
                           "chen@sponsor.com","Monitor@Trial2024!")
            um.create_user("admin",     "System Admin",     Role.ADMIN,
                           "admin@trial.com", "Admin@Trial2024!")
        except Exception:
            pass

init_db(DB_PATH)
ensure_demo_users()

SEV_ICON  = {"CRITICAL": "🔴", "MAJOR": "🟡", "MINOR": "🔵"}
SEV_COLOR = {"CRITICAL": "#ff4d4f", "MAJOR": "#faad14", "MINOR": "#1890ff"}
ACTION_COLOR = {
    "CREATE": "#52c41a", "UPDATE": "#1890ff", "SIGN": "#722ed1",
    "LOGIN": "#faad14",  "LOGIN_FAIL": "#ff4d4f", "ACCOUNT_LOCK": "#ff4d4f",
    "EXPORT": "#13c2c2", "LOCK": "#eb2f96",
}


# ═════════════════════════════════════════════════════════════════════════════
# Sidebar
# ═════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🧬 Mini EDC")
    st.markdown(f"**Study:** {STUDY_ID}")
    st.markdown("---")

    page = st.radio("Navigation", [
        "🏠 Home",
        "✅ Validation",
        "📦 SDTM Export",
        "🔐 Audit Trail",
        "✍️ E-Signatures",
        "👥 Users",
        "📊 Reports",
    ], label_visibility="collapsed")

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
        "<div style='font-size:11px;color:#666'>"
        "Phase A · Phase B · Phase C<br>"
        "CDISC SDTM v1.8 · 21 CFR Part 11"
        "</div>", unsafe_allow_html=True
    )


# ═════════════════════════════════════════════════════════════════════════════
# ── Login widget (shown in sidebar pages that need auth) ─────────────────────
# ═════════════════════════════════════════════════════════════════════════════
def login_widget():
    with st.expander("🔑 Sign in to continue", expanded=True):
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Sign in", use_container_width=True):
            um = UserManager(DB_PATH)
            result = um.authenticate(username, password,
                                     ip_address="127.0.0.1")
            if result:
                st.session_state.logged_in_user = result
                st.success(f"Welcome, {result['display_name']}!")
                st.rerun()
            else:
                st.error("Invalid credentials or account locked.")
    st.stop()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 1 — HOME
# ═════════════════════════════════════════════════════════════════════════════
if page == "🏠 Home":
    st.title("🧬 Mini EDC — Clinical Data Management System")
    st.caption(f"Study: **{STUDY_ID}** · CDISC SDTM v1.8 · 21 CFR Part 11 Compliant")

    st.markdown('<div class="section-hdr">Study Overview</div>', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Subjects Enrolled", "3", delta="+3")
    col2.metric("Active Sites", "2")
    col3.metric("CRF Records", "13", delta="+13")
    col4.metric("Open Queries", "0")
    col5.metric("SAEs", "1", delta="+1", delta_color="inverse")

    st.markdown('<div class="section-hdr">System Status</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        **Phase A — CDISC Validation**
        - ✅ 40+ validation rules active
        - 🔴 9 critical findings (sample data)
        - 🟡 6 major findings
        - 🔵 2 minor findings
        """)
    with c2:
        st.markdown("""
        **Phase B — SDTM Export**
        - ✅ 5 domains supported (DM/AE/VS/LB/EX)
        - ✅ define.xml (CDISC Define-XML 2.0)
        - ✅ Conformance checker
        - ✅ Study day auto-calculation
        """)
    with c3:
        st.markdown("""
        **Phase C — 21 CFR Part 11**
        - ✅ Immutable audit trail (HMAC-chained)
        - ✅ E-signatures with §11.50 manifest
        - ✅ Password re-entry (§11.200)
        - ✅ Role-based access control
        """)

    st.markdown('<div class="section-hdr">Quick Actions</div>', unsafe_allow_html=True)
    qa1, qa2, qa3, qa4 = st.columns(4)
    with qa1:
        if st.button("▶ Run Validation", use_container_width=True):
            page = "✅ Validation"
            st.rerun()
    with qa2:
        if st.button("📦 Generate SDTM", use_container_width=True):
            page = "📦 SDTM Export"
            st.rerun()
    with qa3:
        if st.button("🔐 View Audit Log", use_container_width=True):
            page = "🔐 Audit Trail"
            st.rerun()
    with qa4:
        if st.button("📊 View Reports", use_container_width=True):
            page = "📊 Reports"
            st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style='font-size:13px; color:#888; text-align:center'>
    Mini EDC · Built with Python · CDISC SDTM v1.8 · 21 CFR Part 11 · SQLite
    </div>
    """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2 — VALIDATION (Phase A)
# ═════════════════════════════════════════════════════════════════════════════
elif page == "✅ Validation":
    st.title("✅ CDISC Validation — Phase A")
    st.caption("40+ rules across 7 domains: DM · AE · VS · LB · EX · SV · DS")

    col_run, col_info = st.columns([2, 3])
    with col_run:
        data_source = st.selectbox("Data source", ["Built-in sample data", "Custom JSON"])
        if data_source == "Custom JSON":
            uploaded = st.file_uploader("Upload study data (JSON)", type="json")
            raw_data = json.load(uploaded) if uploaded else SAMPLE_DATA
        else:
            raw_data = SAMPLE_DATA

        if st.button("🚀 Run Validation", use_container_width=True, type="primary"):
            validator = CDISCValidator()
            findings  = validator.run_all(raw_data)
            summary   = validator.summary()
            st.session_state.validation_findings = findings
            st.session_state.validation_summary  = summary
            st.success(f"Validation complete — {summary['total']} findings detected.")

    if st.session_state.validation_summary:
        s = st.session_state.validation_summary
        st.markdown('<div class="section-hdr">Summary</div>', unsafe_allow_html=True)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Findings",  s["total"])
        m2.metric("🔴 Critical",     s["by_severity"].get("CRITICAL", 0))
        m3.metric("🟡 Major",        s["by_severity"].get("MAJOR",    0))
        m4.metric("🔵 Minor",        s["by_severity"].get("MINOR",    0))
        ready = s.get("submission_ready", False)
        m5.metric("Submission Ready", "✅ Yes" if ready else "❌ No")

        # Charts row
        ch1, ch2 = st.columns(2)
        with ch1:
            domain_df = pd.DataFrame([
                {"Domain": k, "Findings": v}
                for k, v in s["by_domain"].items()
            ])
            fig = px.bar(domain_df, x="Domain", y="Findings",
                         color="Domain",
                         color_discrete_sequence=px.colors.qualitative.Set2,
                         title="Findings by domain")
            fig.update_layout(showlegend=False, height=280,
                              plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                              font_color="#e0e0e0")
            st.plotly_chart(fig, use_container_width=True)

        with ch2:
            sev_df = pd.DataFrame([
                {"Severity": k, "Count": v}
                for k, v in s["by_severity"].items() if v > 0
            ])
            fig2 = px.pie(sev_df, names="Severity", values="Count",
                          color="Severity",
                          color_discrete_map={
                              "CRITICAL": "#ff4d4f",
                              "MAJOR":    "#faad14",
                              "MINOR":    "#1890ff",
                          },
                          title="Severity breakdown",
                          hole=0.55)
            fig2.update_layout(height=280,
                               plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                               font_color="#e0e0e0")
            st.plotly_chart(fig2, use_container_width=True)

        # Findings table
        st.markdown('<div class="section-hdr">Findings Detail</div>',
                    unsafe_allow_html=True)

        fil_sev    = st.multiselect("Filter by severity",
                                    ["CRITICAL", "MAJOR", "MINOR"],
                                    default=["CRITICAL", "MAJOR", "MINOR"])
        fil_domain = st.multiselect("Filter by domain",
                                    list(s["by_domain"].keys()),
                                    default=list(s["by_domain"].keys()))

        findings_filtered = [
            f for f in st.session_state.validation_findings
            if f["severity"] in fil_sev and f["domain"] in fil_domain
        ]

        for f in findings_filtered:
            icon  = SEV_ICON.get(f["severity"], "⚪")
            color = SEV_COLOR.get(f["severity"], "#888")
            st.markdown(
                f'<div class="finding-row">'
                f'<span style="color:{color};font-weight:600">{icon} {f["severity"]}</span>'
                f'&nbsp;&nbsp;<code style="font-size:12px">[{f["rule_id"]}]</code>'
                f'&nbsp;&nbsp;<strong>{f["domain"]}</strong>'
                f'&nbsp;·&nbsp;<code>{f["subject_id"]}</code>'
                f'&nbsp;·&nbsp;<code>{f["variable"]}={f["value"]}</code>'
                f'<br><span style="color:#aaa;font-size:12px">{f["message"]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

        # Download
        findings_csv = pd.DataFrame(findings_filtered).to_csv(index=False)
        st.download_button(
            "⬇ Download findings CSV",
            findings_csv,
            file_name="validation_findings.csv",
            mime="text/csv",
        )


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 3 — SDTM EXPORT (Phase B)
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📦 SDTM Export":
    st.title("📦 SDTM Export — Phase B")
    st.caption("CDISC SDTM v1.8 · define.xml · Conformance check")

    col_gen, col_status = st.columns([1, 2])
    with col_gen:
        study_id_inp = st.text_input("Study ID", value=STUDY_ID)
        domains = st.multiselect("Domains to export",
                                 ["DM", "AE", "VS", "LB", "EX"],
                                 default=["DM", "AE", "VS", "LB", "EX"])
        gen_define = st.checkbox("Generate define.xml", value=True)
        run_conf   = st.checkbox("Run conformance check", value=True)

        if st.button("📦 Generate SDTM", use_container_width=True, type="primary"):
            with st.spinner("Generating SDTM datasets…"):
                gen = SDTMGenerator(study_id_inp, SDTM_OUT)
                datasets = gen.run_all(SAMPLE_DATA)
                st.session_state.sdtm_datasets  = datasets
                st.session_state.sdtm_generated = True
                st.session_state.sdtm_gen_meta  = gen.generated_datasets
                if gen_define:
                    d = DefineXMLGenerator(study_id_inp, gen.generated_datasets)
                    d.generate(os.path.join(SDTM_OUT, "define.xml"))
                if run_conf:
                    checker = SDTMConformanceChecker(datasets)
                    issues  = checker.run_all()
                    summary = checker.summary()
                    st.session_state.sdtm_conf_issues  = issues
                    st.session_state.sdtm_conf_summary = summary
            st.success("SDTM generation complete!")

    if st.session_state.sdtm_generated:
        st.markdown('<div class="section-hdr">Generated Datasets</div>',
                    unsafe_allow_html=True)

        for ds in st.session_state.get("sdtm_gen_meta", []):
            with st.expander(
                f"**{ds['domain']}** — {ds['label']} ({ds['n_records']} records)"
            ):
                df = pd.read_csv(os.path.join(SDTM_OUT, f"{ds['domain'].lower()}.csv"))
                st.dataframe(df, use_container_width=True)
                csv_data = df.to_csv(index=False)
                st.download_button(
                    f"⬇ {ds['domain']}.csv",
                    csv_data,
                    file_name=f"{ds['domain'].lower()}.csv",
                    mime="text/csv",
                    key=f"dl_{ds['domain']}",
                )

        # Conformance results
        if "sdtm_conf_summary" in st.session_state:
            cs = st.session_state.sdtm_conf_summary
            st.markdown('<div class="section-hdr">Conformance Check</div>',
                        unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Issues",  cs["total"])
            c2.metric("Errors",        cs["errors"])
            c3.metric("Warnings",      cs["warnings"])
            c4.metric("Submission OK", "✅ Yes" if cs["submission_ready"] else "❌ No")

            if st.session_state.sdtm_conf_issues:
                for issue in st.session_state.sdtm_conf_issues:
                    icon = "🔴" if issue["severity"] == "ERROR" else "🟡"
                    st.markdown(
                        f'<div class="finding-row">'
                        f'{icon} <strong>{issue["domain"]}</strong> '
                        f'<code>[{issue["check_id"]}]</code> {issue["message"]}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
            else:
                st.success("✅ No conformance issues — datasets are submission-ready.")

        # define.xml download
        define_path = os.path.join(SDTM_OUT, "define.xml")
        if os.path.exists(define_path):
            with open(define_path) as f:
                xml_content = f.read()
            st.download_button(
                "⬇ Download define.xml",
                xml_content,
                file_name="define.xml",
                mime="application/xml",
            )

        # ZIP download of everything
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            for fn in os.listdir(SDTM_OUT):
                zf.write(os.path.join(SDTM_OUT, fn), fn)
        zip_buf.seek(0)
        st.download_button(
            "📦 Download all SDTM files (ZIP)",
            zip_buf,
            file_name=f"{study_id_inp}_SDTM.zip",
            mime="application/zip",
        )


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 4 — AUDIT TRAIL (Phase C)
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🔐 Audit Trail":
    st.title("🔐 Audit Trail — 21 CFR Part 11 §11.10(e)")

    aud = AuditTrailEngine(DB_PATH)

    # Integrity check banner
    integrity = aud.verify_chain_integrity()
    if integrity["integrity_ok"]:
        st.success(
            f"✅ Chain integrity verified — {integrity['total_entries']} entries, "
            f"0 tampered. Checked at {integrity['checked_at'][:19]} UTC."
        )
    else:
        st.error(
            f"⚠️ INTEGRITY FAILURE — {integrity['tampered_count']} tampered entries detected!"
        )

    # Fetch all entries
    con = get_db()
    rows = con.execute(
        "SELECT audit_id, timestamp_utc, username, user_role, action, "
        "domain, record_id, field_name, old_value, new_value, reason "
        "FROM audit_trail ORDER BY timestamp_utc DESC"
    ).fetchall()
    con.close()

    cols = ["audit_id","timestamp","username","role","action",
            "domain","record_id","field","old_value","new_value","reason"]
    df = pd.DataFrame(rows, columns=cols)

    if df.empty:
        st.info("No audit entries yet. Perform some actions to generate entries.")
    else:
        # Filters
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            users = ["All"] + sorted(df["username"].unique().tolist())
            sel_user = st.selectbox("Filter by user", users)
        with fc2:
            actions = ["All"] + sorted(df["action"].unique().tolist())
            sel_action = st.selectbox("Filter by action", actions)
        with fc3:
            domains = ["All"] + sorted(df["domain"].dropna().unique().tolist())
            sel_domain = st.selectbox("Filter by domain", domains)

        filtered = df.copy()
        if sel_user   != "All": filtered = filtered[filtered["username"] == sel_user]
        if sel_action != "All": filtered = filtered[filtered["action"]   == sel_action]
        if sel_domain != "All": filtered = filtered[filtered["domain"]   == sel_domain]

        st.markdown(f"**{len(filtered)}** entries")

        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total entries",  len(df))
        m2.metric("Unique users",   df["username"].nunique())
        m3.metric("Domains touched", df["domain"].nunique())
        m4.metric("Integrity",      "✅ OK" if integrity["integrity_ok"] else "❌ FAIL")

        # Action distribution chart
        action_counts = df["action"].value_counts().reset_index()
        action_counts.columns = ["Action", "Count"]
        fig = px.bar(action_counts, x="Action", y="Count",
                     color="Action",
                     color_discrete_sequence=px.colors.qualitative.Pastel,
                     title="Audit actions distribution")
        fig.update_layout(showlegend=False, height=260,
                          plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                          font_color="#e0e0e0")
        st.plotly_chart(fig, use_container_width=True)

        # Entries table (styled)
        st.markdown('<div class="section-hdr">Audit Entries (newest first)</div>',
                    unsafe_allow_html=True)

        for _, row in filtered.head(50).iterrows():
            action = row["action"]
            color  = ACTION_COLOR.get(action, "#888")
            ts     = str(row["timestamp"])[:19]
            change = ""
            if row["field"] and row["old_value"] != row["new_value"]:
                change = (f'&nbsp;·&nbsp;<code>{row["field"]}</code>: '
                          f'<span style="color:#ff7875">{row["old_value"]}</span>'
                          f' → <span style="color:#95de64">{row["new_value"]}</span>')
            st.markdown(
                f'<div class="audit-entry">'
                f'<span style="color:{color};font-weight:600">{action}</span>'
                f'&nbsp;&nbsp;<span style="color:#888;font-size:12px">{ts} UTC</span>'
                f'&nbsp;&nbsp;<strong>{row["username"]}</strong>'
                f'&nbsp;<span style="color:#888;font-size:11px">({row["role"]})</span>'
                f'{change}'
                f'{"&nbsp;·&nbsp;<em>" + row["reason"] + "</em>" if row["reason"] else ""}'
                f'</div>',
                unsafe_allow_html=True
            )

        # Download full audit trail
        csv_out = df.to_csv(index=False)
        st.download_button(
            "⬇ Export full audit trail (CSV)",
            csv_out,
            file_name="audit_trail_full.csv",
            mime="text/csv",
        )


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 5 — E-SIGNATURES (Phase C)
# ═════════════════════════════════════════════════════════════════════════════
elif page == "✍️ E-Signatures":
    st.title("✍️ Electronic Signatures — 21 CFR Part 11 §11.50")

    if not st.session_state.logged_in_user:
        st.warning("You must be signed in to apply electronic signatures.")
        login_widget()

    user = st.session_state.logged_in_user

    # Show existing signatures
    con = get_db()
    sigs = con.execute(
        "SELECT sig_id, timestamp_utc, display_name, role, domain, "
        "record_id, reason, manifest, sig_hash "
        "FROM esignatures ORDER BY timestamp_utc DESC"
    ).fetchall()
    con.close()

    sig_cols = ["sig_id","timestamp","display_name","role","domain",
                "record_id","reason","manifest","sig_hash"]

    st.markdown('<div class="section-hdr">Applied Signatures</div>',
                unsafe_allow_html=True)

    if not sigs:
        st.info("No signatures yet. Apply one below.")
    else:
        for s in sigs:
            sd = dict(zip(sig_cols, s))
            st.markdown(
                f'<div class="sig-card">'
                f'<strong>{sd["display_name"]}</strong> · {sd["role"]}'
                f'<span style="float:right;color:#888;font-size:11px">'
                f'{str(sd["timestamp"])[:19]} UTC</span><br>'
                f'<span style="color:#888;font-size:12px">'
                f'Reason: <em>{sd["reason"]}</em> · Domain: {sd["domain"]} · '
                f'Record: <code>{sd["record_id"][:30]}</code></span><br>'
                f'<span style="color:#555;font-size:11px;font-family:monospace">'
                f'{sd["manifest"][:180]}…</span>'
                f'</div>',
                unsafe_allow_html=True
            )

    # Apply new signature
    st.markdown('<div class="section-hdr">Apply New Signature</div>',
                unsafe_allow_html=True)

    # Get or create a demo record
    crm = ClinicalRecordManager(DB_PATH)
    con = get_db()
    records = con.execute(
        "SELECT record_id, domain, subject_id, visit FROM clinical_records LIMIT 20"
    ).fetchall()
    con.close()

    if not records:
        # Create a demo record
        demo_data = {"USUBJID": "STUDY001-001-001", "AETERM": "Headache",
                     "AESTDTC": "2024-02-10", "AESEV": "MILD", "AESER": "N"}
        rec_id = crm.create_record(
            "STUDY001-001-001", "AE", "WEEK 4", demo_data,
            user["user_id"], user["username"], user["role"],
            session_id=user["session_id"],
        )
        records = [(rec_id, "AE", "STUDY001-001-001", "WEEK 4")]

    record_opts = {
        f'{r[1]} · {r[2]} · {r[3]}': r[0] for r in records
    }

    sc1, sc2 = st.columns(2)
    with sc1:
        sel_record = st.selectbox("Select record", list(record_opts.keys()))
        sel_reason = st.selectbox("Signature reason",
                                  [r.value for r in SignatureReason])
    with sc2:
        sig_password = st.text_input(
            "Re-enter your password (§11.200(b))",
            type="password",
            help="Password re-entry is required for every e-signature per 21 CFR Part 11 §11.200(b)"
        )

    if st.button("✍️ Apply Signature", type="primary", use_container_width=True):
        if not sig_password:
            st.error("Password is required (§11.200(b))")
        else:
            record_id = record_opts[sel_record]
            rec       = crm.get_record(record_id)
            esig_eng  = ESignatureEngine(DB_PATH)
            try:
                result = esig_eng.sign_record(
                    user_id     = user["user_id"],
                    password    = sig_password,
                    record_id   = record_id,
                    domain      = rec["domain"],
                    reason      = SignatureReason(sel_reason),
                    record_data = rec["data"],
                    session_id  = user.get("session_id", ""),
                    ip_address  = "127.0.0.1",
                )
                st.success(
                    f"✅ Signature applied by **{result['signer']}** at {result['timestamp'][:19]} UTC"
                )
                st.code(result["manifest"], language=None)
                st.rerun()
            except ValueError as e:
                st.error(f"Signature failed: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 6 — USERS
# ═════════════════════════════════════════════════════════════════════════════
elif page == "👥 Users":
    st.title("👥 User Management — §11.10(d) Access Control")

    con = get_db()
    users = con.execute(
        "SELECT username, display_name, role, email, "
        "failed_attempts, locked, last_login, created_at, active "
        "FROM users ORDER BY created_at DESC"
    ).fetchall()
    con.close()

    ucols = ["Username","Display Name","Role","Email",
             "Failed","Locked","Last Login","Created","Active"]
    df_u = pd.DataFrame(users, columns=ucols)

    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total users",   len(df_u))
    m2.metric("Active",        int(df_u["Active"].sum()))
    m3.metric("Locked",        int(df_u["Locked"].sum()))
    m4.metric("Roles",         df_u["Role"].nunique())

    # Role distribution
    role_counts = df_u["Role"].value_counts().reset_index()
    role_counts.columns = ["Role","Count"]
    fig = px.pie(role_counts, names="Role", values="Count",
                 hole=0.5, title="Users by role",
                 color_discrete_sequence=px.colors.qualitative.Set3)
    fig.update_layout(height=250,
                      plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                      font_color="#e0e0e0")
    st.plotly_chart(fig, use_container_width=True)

    # Users table
    st.dataframe(
        df_u.style.apply(
            lambda col: ["background-color:#4a1515" if v else "" for v in col]
            if col.name == "Locked" else [""] * len(col),
            axis=0
        ),
        use_container_width=True,
    )

    # Create new user form
    st.markdown('<div class="section-hdr">Create New User</div>',
                unsafe_allow_html=True)

    with st.form("new_user_form"):
        nc1, nc2 = st.columns(2)
        with nc1:
            new_username = st.text_input("Username")
            new_display  = st.text_input("Display name")
            new_email    = st.text_input("Email")
        with nc2:
            new_role = st.selectbox("Role", [r.value for r in Role])
            new_pw   = st.text_input("Password", type="password",
                                     help="Min 12 chars, upper+lower+digit+special")
            new_pw2  = st.text_input("Confirm password", type="password")

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
                        new_username, new_display,
                        Role(new_role), new_email, new_pw,
                        created_by="admin",
                    )
                    st.success(f"User **{new_username}** created (ID: {uid[:8]}…)")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    # Demo credentials notice
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

    # 21 CFR Part 11 compliance table
    st.markdown('<div class="section-hdr">21 CFR Part 11 Compliance Status</div>',
                unsafe_allow_html=True)

    for req, met in report["requirements_met"].items():
        icon = "✅" if met else "❌"
        color = "#52c41a" if met else "#ff4d4f"
        st.markdown(
            f'<div style="padding:6px 12px;margin:3px 0;border-radius:6px;'
            f'background:#1a1d27;border:1px solid #2a2d3a;font-size:13px">'
            f'<span style="color:{color}">{icon}</span>&nbsp;&nbsp;{req}</div>',
            unsafe_allow_html=True
        )

    st.markdown('<div class="section-hdr">Statistics</div>',
                unsafe_allow_html=True)

    stats = report["statistics"]
    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    mc1.metric("Users",         stats["users"])
    mc2.metric("Sessions",      stats["sessions"])
    mc3.metric("Audit entries", stats["audit_entries"])
    mc4.metric("E-signatures",  stats["e_signatures"])
    mc5.metric("CRF records",   stats["crf_records"])

    # Audit action breakdown
    if report["audit_actions"]:
        st.markdown('<div class="section-hdr">Audit Activity</div>',
                    unsafe_allow_html=True)
        action_df = pd.DataFrame([
            {"Action": k, "Count": v}
            for k, v in report["audit_actions"].items()
        ])
        fig = px.bar(action_df, x="Action", y="Count",
                     color="Action",
                     color_discrete_sequence=px.colors.qualitative.Pastel,
                     title="Audit actions")
        fig.update_layout(showlegend=False, height=300,
                          plot_bgcolor="#0f1117", paper_bgcolor="#0f1117",
                          font_color="#e0e0e0")
        st.plotly_chart(fig, use_container_width=True)

    # Integrity report
    st.markdown('<div class="section-hdr">Chain Integrity Report</div>',
                unsafe_allow_html=True)
    integ = report["integrity"]
    ic1, ic2, ic3 = st.columns(3)
    ic1.metric("Total entries",  integ["total_entries"])
    ic2.metric("Tampered",       integ["tampered_count"])
    ic3.metric("Integrity",      "✅ OK" if integ["integrity_ok"] else "❌ FAIL")

    # Download full JSON report
    st.download_button(
        "⬇ Download full compliance report (JSON)",
        json.dumps(report, indent=2),
        file_name="part11_compliance_report.json",
        mime="application/json",
    )

    # Re-run all validation and show combined summary
    st.markdown('<div class="section-hdr">Live Validation Summary</div>',
                unsafe_allow_html=True)
    if st.button("🔄 Re-run CDISC validation"):
        validator = CDISCValidator()
        findings  = validator.run_all(SAMPLE_DATA)
        summary   = validator.summary()
        st.json(summary)
