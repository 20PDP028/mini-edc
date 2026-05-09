"""
data_entry.py — Patient Data Entry Form
Add to Mini EDC dashboard as a new page: "📝 Data Entry"
Site Staff only — enters Demographics, Vitals, Labs, Visit/Medication data
"""

import streamlit as st
import os
from datetime import datetime, date

from db_connection import get_conn, is_postgres


# ── DB Setup ──────────────────────────────────────────────────────────────────
def init_data_entry_tables():
    conn = get_conn()
    cur  = conn.cursor()

    if is_postgres():
        cur.execute("""
            CREATE TABLE IF NOT EXISTS demographics (
                id          SERIAL PRIMARY KEY,
                usubjid     TEXT NOT NULL,
                siteid      TEXT NOT NULL,
                age         INTEGER,
                sex         TEXT,
                race        TEXT,
                weight_kg   REAL,
                height_cm   REAL,
                dob         TEXT,
                entered_by  TEXT,
                entered_at  TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vitals (
                id           SERIAL PRIMARY KEY,
                usubjid      TEXT NOT NULL,
                visit        TEXT NOT NULL,
                visit_date   TEXT,
                bp_systolic  INTEGER,
                bp_diastolic INTEGER,
                heart_rate   INTEGER,
                temperature  REAL,
                spo2         REAL,
                resp_rate    INTEGER,
                entered_by   TEXT,
                entered_at   TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lab_results (
                id          SERIAL PRIMARY KEY,
                usubjid     TEXT NOT NULL,
                visit       TEXT NOT NULL,
                visit_date  TEXT,
                test_name   TEXT,
                result      REAL,
                unit        TEXT,
                normal_low  REAL,
                normal_high REAL,
                flag        TEXT,
                entered_by  TEXT,
                entered_at  TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS visit_medications (
                id          SERIAL PRIMARY KEY,
                usubjid     TEXT NOT NULL,
                visit       TEXT NOT NULL,
                visit_date  TEXT,
                drug_name   TEXT,
                dose        REAL,
                dose_unit   TEXT,
                route       TEXT,
                frequency   TEXT,
                start_date  TEXT,
                end_date    TEXT,
                compliance  TEXT,
                notes       TEXT,
                entered_by  TEXT,
                entered_at  TEXT
            )
        """)
    else:
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS demographics (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                usubjid     TEXT NOT NULL,
                siteid      TEXT NOT NULL,
                age         INTEGER,
                sex         TEXT,
                race        TEXT,
                weight_kg   REAL,
                height_cm   REAL,
                dob         TEXT,
                entered_by  TEXT,
                entered_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS vitals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                usubjid     TEXT NOT NULL,
                visit       TEXT NOT NULL,
                visit_date  TEXT,
                bp_systolic INTEGER,
                bp_diastolic INTEGER,
                heart_rate  INTEGER,
                temperature REAL,
                spo2        REAL,
                resp_rate   INTEGER,
                entered_by  TEXT,
                entered_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS lab_results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                usubjid     TEXT NOT NULL,
                visit       TEXT NOT NULL,
                visit_date  TEXT,
                test_name   TEXT,
                result      REAL,
                unit        TEXT,
                normal_low  REAL,
                normal_high REAL,
                flag        TEXT,
                entered_by  TEXT,
                entered_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS visit_medications (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                usubjid      TEXT NOT NULL,
                visit        TEXT NOT NULL,
                visit_date   TEXT,
                drug_name    TEXT,
                dose         REAL,
                dose_unit    TEXT,
                route        TEXT,
                frequency    TEXT,
                start_date   TEXT,
                end_date     TEXT,
                compliance   TEXT,
                notes        TEXT,
                entered_by   TEXT,
                entered_at   TEXT
            );
        """)

    conn.commit()
    conn.close()


def get_subjects(siteid):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        ph   = "%s" if is_postgres() else "?"
        cur.execute(f"SELECT usubjid FROM subjects WHERE siteid = {ph} ORDER BY usubjid", (siteid,))
        rows = [r[0] for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def save_record(table, data):
    conn = get_conn()
    cur  = conn.cursor()
    ph   = "%s" if is_postgres() else "?"
    cols = ", ".join(data.keys())
    plch = ", ".join([ph] * len(data))
    cur.execute(f"INSERT INTO {table} ({cols}) VALUES ({plch})", list(data.values()))
    conn.commit()
    conn.close()


def log_audit(action, detail, username):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        ph   = "%s" if is_postgres() else "?"
        cur.execute(
            f"INSERT INTO audit_trail (action, detail, username, timestamp) VALUES ({ph},{ph},{ph},{ph})",
            (action, detail, username, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def flag_lab(value, low, high):
    if value is None or low is None or high is None:
        return "NORMAL"
    if value < low:
        return "LOW"
    if value > high:
        return "HIGH"
    return "NORMAL"


# ── Main Entry Point ──────────────────────────────────────────────────────────
def render_data_entry(user):
    """Call this function from dashboard.py when page == '📝 Data Entry'"""

    init_data_entry_tables()

    username = user.get("username", "unknown")
    siteid   = user.get("siteid", "SITE01")

    st.markdown(
        "<h1 style='font-family:IBM Plex Mono,monospace;font-size:1.6rem;color:#E8EDF5;'>"
        "📝 Patient Data Entry</h1>"
        "<div style='color:#4A7AAF;font-size:0.8rem;margin-bottom:24px;'>"
        "Enter clinical trial data for your site subjects</div>",
        unsafe_allow_html=True,
    )

    subjects = get_subjects(siteid)
    if not subjects:
        st.warning("No subjects found for your site. Please add subjects first.")
        subject_id = st.text_input("Subject ID (manual entry)", placeholder="e.g. SUBJ-001")
    else:
        subject_id = st.selectbox("Select Subject", subjects)

    visit_options = ["Screening", "Visit 1", "Visit 2", "Visit 3", "Visit 4", "Follow-up", "End of Study"]
    visit         = st.selectbox("Visit", visit_options)
    visit_date    = st.date_input("Visit Date", value=date.today())

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "👤 Demographics",
        "❤️ Vital Signs",
        "🧪 Lab Results",
        "💊 Medications",
    ])

    # ── Tab 1: Demographics ───────────────────────────────────────────────────
    with tab1:
        st.markdown("##### Subject Demographics")
        st.caption("Enter once at screening. Update only if values change.")

        col1, col2 = st.columns(2)
        with col1:
            age        = st.number_input("Age (years)", min_value=0, max_value=120, step=1)
            sex        = st.selectbox("Sex", ["", "Male", "Female", "Other", "Unknown"])
            race       = st.selectbox("Race", ["", "Asian", "Black", "White", "Hispanic", "Other", "Unknown"])
        with col2:
            weight_kg  = st.number_input("Weight (kg)", min_value=0.0, max_value=500.0, step=0.1, format="%.1f")
            height_cm  = st.number_input("Height (cm)", min_value=0.0, max_value=300.0, step=0.1, format="%.1f")
            dob        = st.date_input("Date of Birth", value=None)

        if weight_kg > 0 and height_cm > 0:
            bmi = weight_kg / ((height_cm / 100) ** 2)
            st.info(f"BMI: **{bmi:.1f}** kg/m²")

        if st.button("💾 Save Demographics", type="primary"):
            if not subject_id:
                st.error("Please select a subject.")
            else:
                save_record("demographics", {
                    "usubjid":    subject_id,
                    "siteid":     siteid,
                    "age":        age if age > 0 else None,
                    "sex":        sex or None,
                    "race":       race or None,
                    "weight_kg":  weight_kg if weight_kg > 0 else None,
                    "height_cm":  height_cm if height_cm > 0 else None,
                    "dob":        dob.isoformat() if dob else None,
                    "entered_by": username,
                    "entered_at": datetime.now().isoformat(),
                })
                log_audit("DATA_ENTRY", f"Demographics saved for {subject_id}", username)
                st.success(f"✅ Demographics saved for {subject_id}")

    # ── Tab 2: Vital Signs ────────────────────────────────────────────────────
    with tab2:
        st.markdown("##### Vital Signs")

        col1, col2, col3 = st.columns(3)
        with col1:
            bp_sys  = st.number_input("BP Systolic (mmHg)",  min_value=0, max_value=300, step=1)
            bp_dia  = st.number_input("BP Diastolic (mmHg)", min_value=0, max_value=200, step=1)
        with col2:
            hr      = st.number_input("Heart Rate (bpm)",    min_value=0, max_value=300, step=1)
            rr      = st.number_input("Resp Rate (/min)",    min_value=0, max_value=100, step=1)
        with col3:
            temp    = st.number_input("Temperature (°C)",    min_value=30.0, max_value=45.0, step=0.1, format="%.1f")
            spo2    = st.number_input("SpO₂ (%)",            min_value=0.0,  max_value=100.0, step=0.1, format="%.1f")

        # Auto-flag abnormals
        flags = []
        if bp_sys  > 0 and (bp_sys  > 140 or bp_sys  < 90):  flags.append(f"BP Systolic {bp_sys} mmHg")
        if bp_dia  > 0 and (bp_dia  > 90  or bp_dia  < 60):  flags.append(f"BP Diastolic {bp_dia} mmHg")
        if hr      > 0 and (hr      > 100 or hr      < 60):  flags.append(f"HR {hr} bpm")
        if temp    > 30 and (temp   > 37.5 or temp   < 36.0): flags.append(f"Temp {temp}°C")
        if spo2    > 0  and spo2    < 95:                     flags.append(f"SpO₂ {spo2}%")

        if flags:
            st.warning("⚠️ Abnormal values detected: " + " | ".join(flags))

        if st.button("💾 Save Vitals", type="primary"):
            if not subject_id:
                st.error("Please select a subject.")
            else:
                save_record("vitals", {
                    "usubjid":      subject_id,
                    "visit":        visit,
                    "visit_date":   visit_date.isoformat(),
                    "bp_systolic":  bp_sys  if bp_sys  > 0 else None,
                    "bp_diastolic": bp_dia  if bp_dia  > 0 else None,
                    "heart_rate":   hr      if hr      > 0 else None,
                    "temperature":  temp    if temp    > 30 else None,
                    "spo2":         spo2    if spo2    > 0 else None,
                    "resp_rate":    rr      if rr      > 0 else None,
                    "entered_by":   username,
                    "entered_at":   datetime.now().isoformat(),
                })
                log_audit("DATA_ENTRY", f"Vitals saved for {subject_id} at {visit}", username)
                st.success(f"✅ Vitals saved for {subject_id} — {visit}")

    # ── Tab 3: Lab Results ────────────────────────────────────────────────────
    with tab3:
        st.markdown("##### Laboratory Results")

        LAB_TESTS = {
            "Haemoglobin":    {"unit": "g/dL",   "low": 12.0, "high": 17.5},
            "WBC":            {"unit": "×10³/μL", "low": 4.0,  "high": 11.0},
            "Platelets":      {"unit": "×10³/μL", "low": 150,  "high": 400},
            "Creatinine":     {"unit": "mg/dL",   "low": 0.6,  "high": 1.2},
            "ALT":            {"unit": "U/L",     "low": 7,    "high": 56},
            "AST":            {"unit": "U/L",     "low": 10,   "high": 40},
            "Blood Glucose":  {"unit": "mg/dL",   "low": 70,   "high": 100},
            "HbA1c":          {"unit": "%",       "low": 4.0,  "high": 5.6},
            "Total Bilirubin":{"unit": "mg/dL",   "low": 0.1,  "high": 1.2},
            "Sodium":         {"unit": "mEq/L",   "low": 136,  "high": 145},
            "Potassium":      {"unit": "mEq/L",   "low": 3.5,  "high": 5.0},
        }

        test_name = st.selectbox("Test Name", list(LAB_TESTS.keys()))
        ref       = LAB_TESTS[test_name]

        col1, col2 = st.columns(2)
        with col1:
            result = st.number_input(
                f"Result ({ref['unit']})",
                min_value=0.0, step=0.01, format="%.2f"
            )
        with col2:
            st.markdown(f"**Normal Range:** {ref['low']} – {ref['high']} {ref['unit']}")
            if result > 0:
                flag = flag_lab(result, ref["low"], ref["high"])
                color = {"NORMAL": "🟢", "HIGH": "🔴", "LOW": "🟡"}[flag]
                st.markdown(f"**Flag:** {color} {flag}")

        if st.button("💾 Save Lab Result", type="primary"):
            if not subject_id:
                st.error("Please select a subject.")
            elif result <= 0:
                st.error("Please enter a valid result.")
            else:
                flag = flag_lab(result, ref["low"], ref["high"])
                save_record("lab_results", {
                    "usubjid":    subject_id,
                    "visit":      visit,
                    "visit_date": visit_date.isoformat(),
                    "test_name":  test_name,
                    "result":     result,
                    "unit":       ref["unit"],
                    "normal_low": ref["low"],
                    "normal_high":ref["high"],
                    "flag":       flag,
                    "entered_by": username,
                    "entered_at": datetime.now().isoformat(),
                })
                log_audit("DATA_ENTRY", f"Lab {test_name}={result} saved for {subject_id}", username)
                if flag != "NORMAL":
                    st.warning(f"⚠️ {flag} result saved — consider raising a query.")
                else:
                    st.success(f"✅ {test_name} result saved for {subject_id}")

    # ── Tab 4: Medications ────────────────────────────────────────────────────
    with tab4:
        st.markdown("##### Visit Medications / Study Drug")

        col1, col2 = st.columns(2)
        with col1:
            drug_name  = st.text_input("Drug / Study Drug Name", placeholder="e.g. Metformin")
            dose       = st.number_input("Dose", min_value=0.0, step=0.5, format="%.1f")
            dose_unit  = st.selectbox("Dose Unit", ["mg", "mcg", "g", "mL", "IU", "units"])
            route      = st.selectbox("Route", ["Oral", "IV", "IM", "SC", "Topical", "Inhaled", "Other"])
        with col2:
            frequency  = st.selectbox("Frequency", ["Once daily", "Twice daily", "Three times daily", "Weekly", "As needed", "Other"])
            start_date = st.date_input("Start Date", value=visit_date)
            end_date   = st.date_input("End Date",   value=None)
            compliance = st.selectbox("Compliance", ["Full", "Partial", "Non-compliant", "Unknown"])

        notes = st.text_area("Notes", placeholder="Any relevant observations about medication administration...")

        if st.button("💾 Save Medication", type="primary"):
            if not subject_id:
                st.error("Please select a subject.")
            elif not drug_name:
                st.error("Please enter a drug name.")
            else:
                save_record("visit_medications", {
                    "usubjid":    subject_id,
                    "visit":      visit,
                    "visit_date": visit_date.isoformat(),
                    "drug_name":  drug_name,
                    "dose":       dose if dose > 0 else None,
                    "dose_unit":  dose_unit,
                    "route":      route,
                    "frequency":  frequency,
                    "start_date": start_date.isoformat(),
                    "end_date":   end_date.isoformat() if end_date else None,
                    "compliance": compliance,
                    "notes":      notes or None,
                    "entered_by": username,
                    "entered_at": datetime.now().isoformat(),
                })
                log_audit("DATA_ENTRY", f"Medication {drug_name} saved for {subject_id}", username)
                if compliance != "Full":
                    st.warning(f"⚠️ Compliance recorded as '{compliance}' — consider raising a query.")
                else:
                    st.success(f"✅ Medication {drug_name} saved for {subject_id}")
