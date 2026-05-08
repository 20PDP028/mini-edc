"""
db_manager.py — Phase 3 Database Manager
Handles all SQLite operations for the CDM system.
Save in: Mini_EDC_Project/python/db_manager.py
"""

import sqlite3
import os
from datetime import datetime

BASE    = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, '..', 'sql', 'cdm_phase3.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS subjects (
            usubjid     TEXT PRIMARY KEY,
            siteid      TEXT,
            age         INTEGER,
            gender      TEXT,
            weight_kg   REAL
        );

        CREATE TABLE IF NOT EXISTS visits (
            visit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            usubjid     TEXT REFERENCES subjects(usubjid),
            visit_date  TEXT,
            drug_name   TEXT,
            dose_mg     REAL
        );

        CREATE TABLE IF NOT EXISTS adverse_events (
            ae_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            usubjid     TEXT REFERENCES subjects(usubjid),
            siteid      TEXT,
            aeterm      TEXT,
            aesev       TEXT,
            aeser       TEXT DEFAULT 'N',
            aestdtc     TEXT,
            report_flag TEXT DEFAULT 'OK'
        );

        CREATE TABLE IF NOT EXISTS queries (
            query_id    TEXT PRIMARY KEY,
            usubjid     TEXT REFERENCES subjects(usubjid),
            siteid      TEXT,
            field_name  TEXT,
            severity    TEXT,
            status      TEXT DEFAULT 'Open',
            issue_description TEXT,
            created_at  TEXT,
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_trail (
            audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time  TEXT,
            action      TEXT,
            table_name  TEXT,
            record_id   TEXT,
            field_name  TEXT,
            old_value   TEXT,
            new_value   TEXT,
            performed_by TEXT
        );

        CREATE VIEW IF NOT EXISTS v_open_queries AS
            SELECT * FROM queries WHERE status = 'Open';

        CREATE VIEW IF NOT EXISTS v_sae_pending AS
            SELECT * FROM adverse_events WHERE report_flag = 'PENDING';

        CREATE VIEW IF NOT EXISTS v_query_summary AS
            SELECT status, severity, COUNT(*) as count
            FROM queries GROUP BY status, severity;
    """)
    conn.commit()
    conn.close()
    print(f"[DB] Initialised → {DB_PATH}")


def load_subjects(df):
    conn = get_conn()
    for _, row in df.iterrows():
        conn.execute("""
            INSERT OR IGNORE INTO subjects (usubjid, siteid, age, gender, weight_kg)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(row.get("Subject_ID", "")),
            str(row.get("Site_ID", "")),
            row.get("Age"),
            row.get("Gender"),
            row.get("Weight_kg"),
        ))
    conn.commit()
    conn.close()
    print(f"[DB] Loaded {len(df)} subjects")


def load_visits(df):
    conn = get_conn()
    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO visits (usubjid, visit_date, drug_name, dose_mg)
            VALUES (?, ?, ?, ?)
        """, (
            str(row.get("Subject_ID", "")),
            str(row.get("Visit_Date", "")),
            row.get("Drug_Name"),
            row.get("Dose_mg"),
        ))
    conn.commit()
    conn.close()
    print(f"[DB] Loaded {len(df)} visits")


def load_adverse_events(df):
    conn = get_conn()
    count = 0
    for _, row in df.iterrows():
        ae = row.get("Adverse_Event")
        if ae and str(ae).strip() and str(ae).strip().lower() != "nan":
            sev = str(row.get("AE_Severity", "")).upper()
            flag = "PENDING" if sev == "SEVERE" else "OK"
            conn.execute("""
                INSERT INTO adverse_events (usubjid, siteid, aeterm, aesev, aeser, aestdtc, report_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row.get("Subject_ID", "")),
                str(row.get("Site_ID", "")),
                str(ae),
                sev,
                "Y" if sev == "SEVERE" else "N",
                str(row.get("Visit_Date", "")),
                flag,
            ))
            count += 1
    conn.commit()
    conn.close()
    print(f"[DB] Loaded {count} adverse events")


def open_queries(issues):
    conn = get_conn()
    count = 0
    for issue in issues:
        usubjid = str(issue.get("usubjid", "")).strip()
        # Ensure subject exists
        exists = conn.execute("SELECT 1 FROM subjects WHERE usubjid=?", (usubjid,)).fetchone()
        if not exists:
            conn.execute("INSERT OR IGNORE INTO subjects (usubjid, siteid) VALUES (?, ?)",
                         (usubjid, issue.get("siteid", "UNKNOWN")))

        query_id = issue.get("query_id", f"QRY-{count+1:04d}")
        conn.execute("""
            INSERT OR IGNORE INTO queries
            (query_id, usubjid, siteid, field_name, severity, status, issue_description, created_at)
            VALUES (?, ?, ?, ?, ?, 'Open', ?, ?)
        """, (
            query_id,
            usubjid,
            issue.get("siteid", ""),
            issue.get("field", ""),
            issue.get("severity", "Minor"),
            issue.get("issue", ""),
            datetime.now().isoformat(),
        ))
        conn.execute("""
            INSERT INTO audit_trail (event_time, action, table_name, record_id, field_name, new_value, performed_by)
            VALUES (?, 'QUERY_OPEN', 'queries', ?, 'status', 'Open', 'SYSTEM')
        """, (datetime.now().isoformat(), query_id))
        count += 1
    conn.commit()
    conn.close()
    print(f"[DB] Opened {count} queries")


def answer_query(query_id, answer_text, answered_by):
    conn = get_conn()
    conn.execute("UPDATE queries SET status='Answered', resolved_at=? WHERE query_id=?",
                 (datetime.now().isoformat(), query_id))
    conn.execute("""
        INSERT INTO audit_trail (event_time, action, table_name, record_id, field_name, old_value, new_value, performed_by)
        VALUES (?, 'QUERY_ANSWER', 'queries', ?, 'status', 'Open', ?, ?)
    """, (datetime.now().isoformat(), query_id, answer_text, answered_by))
    conn.commit()
    conn.close()
    print(f"[DB] Query {query_id} answered by {answered_by}")


def close_query(query_id, closed_by, reason=""):
    conn = get_conn()
    conn.execute("UPDATE queries SET status='Closed', resolved_at=? WHERE query_id=?",
                 (datetime.now().isoformat(), query_id))
    conn.execute("""
        INSERT INTO audit_trail (event_time, action, table_name, record_id, field_name, old_value, new_value, performed_by)
        VALUES (?, 'QUERY_CLOSE', 'queries', ?, 'status', 'Answered', ?, ?)
    """, (datetime.now().isoformat(), query_id, reason, closed_by))
    conn.commit()
    conn.close()
    print(f"[DB] Query {query_id} closed by {closed_by}")


def query_summary():
    conn = get_conn()
    rows = conn.execute("SELECT status, COUNT(*) FROM queries GROUP BY status").fetchall()
    conn.close()
    print("\n[REPORT] Query Summary:")
    for r in rows:
        print(f"         {r[0]}: {r[1]}")


def open_queries_report():
    conn = get_conn()
    rows = conn.execute("SELECT query_id, usubjid, field_name, severity, issue_description FROM v_open_queries LIMIT 10").fetchall()
    conn.close()
    print(f"\n[REPORT] Open Queries ({len(rows)} shown):")
    for r in rows:
        print(f"         {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4][:50]}")


def sae_report():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM v_sae_pending").fetchall()
    conn.close()
    print(f"\n[REPORT] SAEs Pending Report: {len(rows)}")
    for r in rows:
        print(f"         {r}")


def audit_report(limit=15):
    conn = get_conn()
    rows = conn.execute(f"SELECT event_time, action, record_id, performed_by FROM audit_trail LIMIT {limit}").fetchall()
    conn.close()
    print(f"\n[REPORT] Audit Trail (last {limit}):")
    for r in rows:
        print(f"         {r[0][:16]} | {r[1]} | {r[2]} | {r[3]}")
