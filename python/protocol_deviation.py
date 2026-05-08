"""
protocol_deviation.py — Feature 12: Protocol Deviation Tracker
Log and classify protocol violations by type, severity, and site.
Save in: Mini_EDC_Project/python/protocol_deviation.py
Run with: python protocol_deviation.py
"""

import sqlite3
import os
import pandas as pd
from datetime import datetime

BASE    = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, '..', 'sql', 'cdm_phase3.db')

# ── Deviation Categories ──────────────────────────────────────
DEVIATION_TYPES = {
    "IC":   "Informed Consent",
    "EX":   "Eligibility Criteria",
    "PD":   "Prohibited Drug/Medication",
    "VW":   "Visit Window Violation",
    "DOS":  "Dosing Error",
    "LAB":  "Laboratory Procedure",
    "AE":   "Adverse Event Reporting",
    "SAE":  "SAE Reporting Timeline",
    "DATA": "Data Collection Error",
    "OTH":  "Other",
}

SEVERITY_LEVELS = {
    "Major":   "Directly impacts subject safety or data integrity",
    "Minor":   "No direct impact on safety or data integrity",
    "Medical": "Medical judgement deviation — requires DM review",
}


def init_pd_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS protocol_deviations (
            pd_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            pd_code         TEXT UNIQUE,
            usubjid         TEXT,
            siteid          TEXT,
            deviation_type  TEXT,
            deviation_cat   TEXT,
            severity        TEXT,
            description     TEXT,
            action_taken    TEXT,
            status          TEXT DEFAULT 'Open',
            reported_by     TEXT,
            reported_at     TEXT,
            resolved_at     TEXT,
            capa            TEXT
        )
    """)
    conn.commit()
    conn.close()


def _next_pd_code(conn):
    n = conn.execute("SELECT COUNT(*) FROM protocol_deviations").fetchone()[0]
    return f"PD-{n+1:04d}"


def log_deviation(usubjid, siteid, dev_type, severity, description,
                  action_taken="", reported_by="SITE", capa=""):
    """Log a new protocol deviation."""
    init_pd_table()
    conn = sqlite3.connect(DB_PATH)
    code = _next_pd_code(conn)
    cat  = DEVIATION_TYPES.get(dev_type, "Other")

    conn.execute("""
        INSERT OR IGNORE INTO protocol_deviations
        (pd_code, usubjid, siteid, deviation_type, deviation_cat,
         severity, description, action_taken, reported_by, reported_at, capa)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (code, usubjid, siteid, dev_type, cat,
          severity, description, action_taken,
          reported_by, datetime.now().isoformat(), capa))

    conn.execute("""
        INSERT INTO audit_trail
        (event_time, action, table_name, record_id, field_name, new_value, performed_by)
        VALUES (?,?,?,?,?,?,?)
    """, (datetime.now().isoformat(), "PD_LOGGED", "protocol_deviations",
          code, "status", "Open", reported_by))

    conn.commit()
    conn.close()
    print(f"[PD] Logged {code} — {cat} ({severity})")
    return code


def resolve_deviation(pd_code, resolved_by, capa_description):
    """Mark a deviation as resolved with CAPA."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE protocol_deviations
        SET status='Resolved', resolved_at=?, capa=?
        WHERE pd_code=?
    """, (datetime.now().isoformat(), capa_description, pd_code))
    conn.execute("""
        INSERT INTO audit_trail
        (event_time, action, table_name, record_id, field_name, new_value, performed_by)
        VALUES (?,?,?,?,?,?,?)
    """, (datetime.now().isoformat(), "PD_RESOLVED", "protocol_deviations",
          pd_code, "status", "Resolved", resolved_by))
    conn.commit()
    conn.close()
    print(f"[PD] {pd_code} resolved by {resolved_by}")


def auto_detect_deviations():
    """
    Auto-scan DB for common protocol deviations from existing data.
    Detects: visit window violations, missing consent indicators, dosing errors.
    """
    init_pd_table()
    conn = sqlite3.connect(DB_PATH)
    detected = 0

    # Detect dosing errors from queries
    try:
        dose_issues = conn.execute("""
            SELECT query_id, usubjid, siteid, issue_description
            FROM queries
            WHERE field_name='Dose_mg' AND severity='Critical'
        """).fetchall()

        for qid, subj, site, issue in dose_issues:
            code = _next_pd_code(conn)
            conn.execute("""
                INSERT OR IGNORE INTO protocol_deviations
                (pd_code, usubjid, siteid, deviation_type, deviation_cat,
                 severity, description, reported_by, reported_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (code, subj, site or "UNKNOWN", "DOS", "Dosing Error",
                  "Major", f"Auto-detected: {issue}", "SYSTEM",
                  datetime.now().isoformat()))
            detected += 1
    except Exception as e:
        pass

    # Detect invalid date deviations (visit window violations)
    try:
        date_issues = conn.execute("""
            SELECT query_id, usubjid, siteid, issue_description
            FROM queries
            WHERE field_name='Visit_Date'
        """).fetchall()

        for qid, subj, site, issue in date_issues:
            code = _next_pd_code(conn)
            conn.execute("""
                INSERT OR IGNORE INTO protocol_deviations
                (pd_code, usubjid, siteid, deviation_type, deviation_cat,
                 severity, description, reported_by, reported_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (code, subj, site or "UNKNOWN", "VW", "Visit Window Violation",
                  "Minor", f"Auto-detected: {issue}", "SYSTEM",
                  datetime.now().isoformat()))
            detected += 1
    except Exception as e:
        pass

    conn.commit()
    conn.close()
    print(f"[PD] Auto-detected {detected} protocol deviations")
    return detected


def get_pd_summary():
    """Return summary DataFrame of all deviations."""
    init_pd_table()
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("SELECT * FROM protocol_deviations ORDER BY reported_at DESC", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df


def print_pd_report():
    """Print deviation report to console."""
    df = get_pd_summary()
    print("\n" + "="*65)
    print("  PROTOCOL DEVIATION REPORT")
    print("="*65)

    if df.empty:
        print("  No deviations recorded.")
        print()
        return

    total   = len(df)
    major   = len(df[df["severity"] == "Major"])   if "severity" in df.columns else 0
    minor   = len(df[df["severity"] == "Minor"])   if "severity" in df.columns else 0
    open_pd = len(df[df["status"] == "Open"])      if "status"   in df.columns else 0
    resolved= len(df[df["status"] == "Resolved"])  if "status"   in df.columns else 0

    print(f"  Total Deviations : {total}")
    print(f"  Major            : {major}")
    print(f"  Minor            : {minor}")
    print(f"  Open             : {open_pd}")
    print(f"  Resolved         : {resolved}")

    if "siteid" in df.columns:
        print("\n  By Site:")
        for site, grp in df.groupby("siteid"):
            print(f"  {site:10} | Total: {len(grp)} | Major: {len(grp[grp['severity']=='Major'])}")

    if "deviation_cat" in df.columns:
        print("\n  By Category:")
        for cat, grp in df.groupby("deviation_cat"):
            print(f"  {cat:<35} : {len(grp)}")

    print()


if __name__ == "__main__":
    init_pd_table()

    # Demo: auto-detect from existing data
    auto_detect_deviations()

    # Demo: manually log a deviation
    log_deviation(
        usubjid="SUB005",
        siteid="SITE02",
        dev_type="IC",
        severity="Major",
        description="Informed consent obtained after first study procedure",
        action_taken="Subject re-consented. Protocol amendment submitted.",
        reported_by="MONITOR_01",
        capa="SOP updated to check consent date before any procedure"
    )

    print_pd_report()
