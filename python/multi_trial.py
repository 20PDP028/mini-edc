"""
multi_trial.py — Feature 15: Multi-Trial Support
Handle multiple clinical studies in one system.
Save in: Mini_EDC_Project/python/multi_trial.py
Run with: python multi_trial.py
"""

import sqlite3
import os
import pandas as pd
from datetime import datetime

BASE    = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, '..', 'sql', 'cdm_phase3.db')


def init_trial_tables():
    """Create multi-trial registry tables."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trials (
            trial_id        TEXT PRIMARY KEY,
            trial_name      TEXT NOT NULL,
            protocol_number TEXT,
            phase           TEXT,
            indication      TEXT,
            sponsor         TEXT,
            status          TEXT DEFAULT 'Active',
            start_date      TEXT,
            end_date        TEXT,
            created_at      TEXT,
            created_by      TEXT
        );

        CREATE TABLE IF NOT EXISTS trial_sites (
            ts_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            trial_id    TEXT REFERENCES trials(trial_id),
            siteid      TEXT,
            site_name   TEXT,
            pi_name     TEXT,
            country     TEXT,
            status      TEXT DEFAULT 'Active',
            activated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS trial_subjects (
            ts_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            trial_id    TEXT REFERENCES trials(trial_id),
            usubjid     TEXT,
            siteid      TEXT,
            enrolled_at TEXT,
            status      TEXT DEFAULT 'Active'
        );
    """)

    # Insert default trial (current project)
    conn.execute("""
        INSERT OR IGNORE INTO trials
        (trial_id, trial_name, protocol_number, phase, indication,
         sponsor, status, start_date, created_at, created_by)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, ("CARDIO-P2", "CARDIO-PHASE2 Trial", "PROTO-CARDIO-002",
          "Phase 2", "Cardiovascular Disease",
          "MiniPharma Ltd", "Active",
          "2024-01-01", datetime.now().isoformat(), "ADMIN"))

    conn.commit()
    conn.close()
    print("[TRIAL] Multi-trial tables initialised")


def create_trial(trial_id, trial_name, protocol, phase,
                 indication, sponsor, start_date, created_by="ADMIN"):
    """Register a new clinical trial."""
    init_trial_tables()
    conn = sqlite3.connect(DB_PATH)

    existing = conn.execute(
        "SELECT 1 FROM trials WHERE trial_id=?", (trial_id,)
    ).fetchone()

    if existing:
        conn.close()
        return False, f"Trial {trial_id} already exists"

    conn.execute("""
        INSERT INTO trials
        (trial_id, trial_name, protocol_number, phase, indication,
         sponsor, status, start_date, created_at, created_by)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (trial_id, trial_name, protocol, phase, indication,
          sponsor, "Active", start_date, datetime.now().isoformat(), created_by))

    conn.execute("""
        INSERT INTO audit_trail
        (event_time, action, table_name, record_id, field_name, new_value, performed_by)
        VALUES (?,?,?,?,?,?,?)
    """, (datetime.now().isoformat(), "TRIAL_CREATED", "trials",
          trial_id, "status", "Active", created_by))

    conn.commit()
    conn.close()
    print(f"[TRIAL] Created: {trial_id} — {trial_name}")
    return True, f"Trial {trial_id} created successfully"


def add_site(trial_id, siteid, site_name, pi_name, country="IND"):
    """Add a site to a trial."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR IGNORE INTO trial_sites
        (trial_id, siteid, site_name, pi_name, country, activated_at)
        VALUES (?,?,?,?,?,?)
    """, (trial_id, siteid, site_name, pi_name, country, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print(f"[TRIAL] Site {siteid} added to {trial_id}")


def enrol_subject(trial_id, usubjid, siteid):
    """Enrol a subject into a specific trial."""
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute(
        "SELECT 1 FROM trial_subjects WHERE trial_id=? AND usubjid=?",
        (trial_id, usubjid)
    ).fetchone()

    if existing:
        conn.close()
        return False, f"{usubjid} already enrolled in {trial_id}"

    conn.execute("""
        INSERT INTO trial_subjects (trial_id, usubjid, siteid, enrolled_at)
        VALUES (?,?,?,?)
    """, (trial_id, usubjid, siteid, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True, f"{usubjid} enrolled in {trial_id}"


def get_trial_dashboard():
    """Return summary metrics for all trials."""
    init_trial_tables()
    conn = sqlite3.connect(DB_PATH)
    try:
        trials = pd.read_sql_query("SELECT * FROM trials ORDER BY start_date DESC", conn)
        subjects_per_trial = pd.read_sql_query("""
            SELECT trial_id, COUNT(*) as enrolled
            FROM trial_subjects GROUP BY trial_id
        """, conn)
        sites_per_trial = pd.read_sql_query("""
            SELECT trial_id, COUNT(*) as sites
            FROM trial_sites GROUP BY trial_id
        """, conn)
    except:
        trials = pd.DataFrame()
        subjects_per_trial = pd.DataFrame()
        sites_per_trial = pd.DataFrame()
    conn.close()

    if not trials.empty:
        if not subjects_per_trial.empty:
            trials = trials.merge(subjects_per_trial, on="trial_id", how="left")
        if not sites_per_trial.empty:
            trials = trials.merge(sites_per_trial, on="trial_id", how="left")
        trials["enrolled"] = trials.get("enrolled", 0).fillna(0).astype(int)
        trials["sites"]    = trials.get("sites",    0).fillna(0).astype(int)

    return trials


def enrol_existing_subjects():
    """Enrol all existing subjects into the default trial."""
    conn = sqlite3.connect(DB_PATH)
    subjects = conn.execute("SELECT usubjid, siteid FROM subjects").fetchall()
    conn.close()

    enrolled = 0
    for usubjid, siteid in subjects:
        ok, _ = enrol_subject("CARDIO-P2", usubjid, siteid or "SITE01")
        if ok:
            enrolled += 1
    print(f"[TRIAL] Enrolled {enrolled} existing subjects into CARDIO-P2")
    return enrolled


def print_trial_report():
    """Print multi-trial summary."""
    df = get_trial_dashboard()

    print("\n" + "="*75)
    print("  MULTI-TRIAL REGISTRY")
    print("="*75)

    if df.empty:
        print("  No trials registered.")
        return

    for _, row in df.iterrows():
        status_icon = "🟢" if row.get("status") == "Active" else "🔴"
        print(f"\n  {status_icon} {row.get('trial_id',''):<15} {row.get('trial_name','')}")
        print(f"     Protocol  : {row.get('protocol_number','')}")
        print(f"     Phase     : {row.get('phase','')}")
        print(f"     Indication: {row.get('indication','')}")
        print(f"     Sponsor   : {row.get('sponsor','')}")
        print(f"     Start Date: {row.get('start_date','')}")
        print(f"     Sites     : {row.get('sites', 0)}")
        print(f"     Subjects  : {row.get('enrolled', 0)}")
        print(f"     Status    : {row.get('status','')}")

    print()


if __name__ == "__main__":
    init_trial_tables()

    # Demo: create a second trial
    create_trial(
        trial_id="ONCO-P3",
        trial_name="ONCO Phase 3 — Lung Cancer Study",
        protocol="PROTO-ONCO-007",
        phase="Phase 3",
        indication="Non-Small Cell Lung Cancer",
        sponsor="MiniPharma Ltd",
        start_date="2024-06-01",
        created_by="ADMIN"
    )

    # Add sites to second trial
    add_site("ONCO-P3", "SITE01", "City Cancer Centre",    "Dr. Meera Rao",   "IND")
    add_site("ONCO-P3", "SITE04", "Regional Cancer Inst.", "Dr. Ajay Kumar",  "IND")
    add_site("ONCO-P3", "SITE05", "National Cancer Hosp.", "Dr. Sarah Chen",  "SGP")

    # Enrol existing subjects into default trial
    enrol_existing_subjects()

    print_trial_report()
