"""
db_manager.py — Phase 3 Database Manager
Handles all database operations for the CDM system.
Save in: Mini_EDC_Project/python/db_manager.py
"""

from datetime import datetime

from db_connection import get_conn as _get_conn, is_postgres


def _ph():
    return "%s" if is_postgres() else "?"


def get_conn():
    conn = _get_conn()
    if not is_postgres():
        conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    if is_postgres():
        statements = [
            """CREATE TABLE IF NOT EXISTS subjects (
                usubjid   TEXT PRIMARY KEY,
                siteid    TEXT,
                age       INTEGER,
                gender    TEXT,
                weight_kg DOUBLE PRECISION
            )""",
            """CREATE TABLE IF NOT EXISTS visits (
                visit_id   SERIAL PRIMARY KEY,
                usubjid    TEXT REFERENCES subjects(usubjid),
                visit_date TEXT,
                drug_name  TEXT,
                dose_mg    DOUBLE PRECISION
            )""",
            """CREATE TABLE IF NOT EXISTS adverse_events (
                ae_id       SERIAL PRIMARY KEY,
                usubjid     TEXT REFERENCES subjects(usubjid),
                siteid      TEXT,
                aeterm      TEXT,
                aesev       TEXT,
                aeser       TEXT DEFAULT 'N',
                aestdtc     TEXT,
                report_flag TEXT DEFAULT 'OK'
            )""",
            """CREATE TABLE IF NOT EXISTS queries (
                query_id          TEXT PRIMARY KEY,
                usubjid           TEXT REFERENCES subjects(usubjid),
                siteid            TEXT,
                field_name        TEXT,
                severity          TEXT,
                status            TEXT DEFAULT 'Open',
                issue_description TEXT,
                created_at        TEXT,
                resolved_at       TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS audit_trail (
                audit_id     SERIAL PRIMARY KEY,
                event_time   TEXT,
                action       TEXT,
                table_name   TEXT,
                record_id    TEXT,
                field_name   TEXT,
                old_value    TEXT,
                new_value    TEXT,
                performed_by TEXT
            )""",
        ]
        for sql in statements:
            cur.execute(sql)
        # Views — PostgreSQL syntax
        cur.execute(
            "CREATE OR REPLACE VIEW v_open_queries AS SELECT * FROM queries WHERE status = 'Open'"
        )
        cur.execute(
            "CREATE OR REPLACE VIEW v_sae_pending AS SELECT * FROM adverse_events WHERE report_flag = 'PENDING'"
        )
        cur.execute("""
            CREATE OR REPLACE VIEW v_query_summary AS
            SELECT status, severity, COUNT(*) as count FROM queries GROUP BY status, severity
        """)
    else:
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS subjects (
                usubjid   TEXT PRIMARY KEY,
                siteid    TEXT,
                age       INTEGER,
                gender    TEXT,
                weight_kg REAL
            );
            CREATE TABLE IF NOT EXISTS visits (
                visit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                usubjid    TEXT REFERENCES subjects(usubjid),
                visit_date TEXT,
                drug_name  TEXT,
                dose_mg    REAL
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
                query_id          TEXT PRIMARY KEY,
                usubjid           TEXT REFERENCES subjects(usubjid),
                siteid            TEXT,
                field_name        TEXT,
                severity          TEXT,
                status            TEXT DEFAULT 'Open',
                issue_description TEXT,
                created_at        TEXT,
                resolved_at       TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_trail (
                audit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                event_time   TEXT,
                action       TEXT,
                table_name   TEXT,
                record_id    TEXT,
                field_name   TEXT,
                old_value    TEXT,
                new_value    TEXT,
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
    print("[DB] Initialised")


def load_subjects(df):
    ph = _ph()
    conn = get_conn()
    cur = conn.cursor()
    for _, row in df.iterrows():
        if is_postgres():
            cur.execute(
                f"INSERT INTO subjects (usubjid,siteid,age,gender,weight_kg) VALUES ({ph},{ph},{ph},{ph},{ph}) ON CONFLICT (usubjid) DO NOTHING",
                (
                    str(row.get("Subject_ID", "")),
                    str(row.get("Site_ID", "")),
                    row.get("Age"),
                    row.get("Gender"),
                    row.get("Weight_kg"),
                ),
            )
        else:
            cur.execute(
                f"INSERT OR IGNORE INTO subjects (usubjid,siteid,age,gender,weight_kg) VALUES ({ph},{ph},{ph},{ph},{ph})",
                (
                    str(row.get("Subject_ID", "")),
                    str(row.get("Site_ID", "")),
                    row.get("Age"),
                    row.get("Gender"),
                    row.get("Weight_kg"),
                ),
            )
    conn.commit()
    conn.close()
    print(f"[DB] Loaded {len(df)} subjects")


def load_visits(df):
    ph = _ph()
    conn = get_conn()
    cur = conn.cursor()
    for _, row in df.iterrows():
        cur.execute(
            f"INSERT INTO visits (usubjid,visit_date,drug_name,dose_mg) VALUES ({ph},{ph},{ph},{ph})",
            (
                str(row.get("Subject_ID", "")),
                str(row.get("Visit_Date", "")),
                row.get("Drug_Name"),
                row.get("Dose_mg"),
            ),
        )
    conn.commit()
    conn.close()
    print(f"[DB] Loaded {len(df)} visits")


def load_adverse_events(df):
    ph = _ph()
    conn = get_conn()
    cur = conn.cursor()
    count = 0
    for _, row in df.iterrows():
        ae = row.get("Adverse_Event")
        if ae and str(ae).strip() and str(ae).strip().lower() != "nan":
            sev = str(row.get("AE_Severity", "")).upper()
            flag = "PENDING" if sev == "SEVERE" else "OK"
            cur.execute(
                f"INSERT INTO adverse_events (usubjid,siteid,aeterm,aesev,aeser,aestdtc,report_flag) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})",
                (
                    str(row.get("Subject_ID", "")),
                    str(row.get("Site_ID", "")),
                    str(ae),
                    sev,
                    "Y" if sev == "SEVERE" else "N",
                    str(row.get("Visit_Date", "")),
                    flag,
                ),
            )
            count += 1
    conn.commit()
    conn.close()
    print(f"[DB] Loaded {count} adverse events")


def open_queries(issues):
    ph = _ph()
    conn = get_conn()
    cur = conn.cursor()
    count = 0
    for issue in issues:
        usubjid = str(issue.get("usubjid", "")).strip()
        cur.execute(f"SELECT 1 FROM subjects WHERE usubjid={ph}", (usubjid,))
        exists = cur.fetchone()
        if not exists:
            if is_postgres():
                cur.execute(
                    f"INSERT INTO subjects (usubjid,siteid) VALUES ({ph},{ph}) ON CONFLICT DO NOTHING",
                    (usubjid, issue.get("siteid", "UNKNOWN")),
                )
            else:
                cur.execute(
                    f"INSERT OR IGNORE INTO subjects (usubjid,siteid) VALUES ({ph},{ph})",
                    (usubjid, issue.get("siteid", "UNKNOWN")),
                )

        query_id = issue.get("query_id", f"QRY-{count+1:04d}")
        if is_postgres():
            cur.execute(
                f"INSERT INTO queries (query_id,usubjid,siteid,field_name,severity,status,issue_description,created_at) VALUES ({ph},{ph},{ph},{ph},{ph},'Open',{ph},{ph}) ON CONFLICT (query_id) DO NOTHING",
                (
                    query_id,
                    usubjid,
                    issue.get("siteid", ""),
                    issue.get("field", ""),
                    issue.get("severity", "Minor"),
                    issue.get("issue", ""),
                    datetime.now().isoformat(),
                ),
            )
        else:
            cur.execute(
                f"INSERT OR IGNORE INTO queries (query_id,usubjid,siteid,field_name,severity,status,issue_description,created_at) VALUES ({ph},{ph},{ph},{ph},{ph},'Open',{ph},{ph})",
                (
                    query_id,
                    usubjid,
                    issue.get("siteid", ""),
                    issue.get("field", ""),
                    issue.get("severity", "Minor"),
                    issue.get("issue", ""),
                    datetime.now().isoformat(),
                ),
            )
        cur.execute(
            f"INSERT INTO audit_trail (event_time,action,table_name,record_id,field_name,new_value,performed_by) VALUES ({ph},'QUERY_OPEN','queries',{ph},'status','Open','SYSTEM')",
            (datetime.now().isoformat(), query_id),
        )
        count += 1
    conn.commit()
    conn.close()
    print(f"[DB] Opened {count} queries")


def answer_query(query_id, answer_text, answered_by):
    ph = _ph()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE queries SET status='Answered', resolved_at={ph} WHERE query_id={ph}",
        (datetime.now().isoformat(), query_id),
    )
    cur.execute(
        f"INSERT INTO audit_trail (event_time,action,table_name,record_id,field_name,old_value,new_value,performed_by) VALUES ({ph},'QUERY_ANSWER','queries',{ph},'status','Open',{ph},{ph})",
        (datetime.now().isoformat(), query_id, answer_text, answered_by),
    )
    conn.commit()
    conn.close()
    print(f"[DB] Query {query_id} answered by {answered_by}")


def close_query(query_id, closed_by, reason=""):
    ph = _ph()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE queries SET status='Closed', resolved_at={ph} WHERE query_id={ph}",
        (datetime.now().isoformat(), query_id),
    )
    cur.execute(
        f"INSERT INTO audit_trail (event_time,action,table_name,record_id,field_name,old_value,new_value,performed_by) VALUES ({ph},'QUERY_CLOSE','queries',{ph},'status','Answered',{ph},{ph})",
        (datetime.now().isoformat(), query_id, reason, closed_by),
    )
    conn.commit()
    conn.close()
    print(f"[DB] Query {query_id} closed by {closed_by}")


def query_summary():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) FROM queries GROUP BY status")
    rows = cur.fetchall()
    conn.close()
    print("\n[REPORT] Query Summary:")
    for r in rows:
        r = dict(r)
        print(f"         {list(r.values())}")


def open_queries_report():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT query_id, usubjid, field_name, severity, issue_description FROM v_open_queries LIMIT 10"
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    print(f"\n[REPORT] Open Queries ({len(rows)} shown):")
    for r in rows:
        print(
            f"         {r['query_id']} | {r['usubjid']} | {r['field_name']} | {r['severity']} | {str(r['issue_description'])[:50]}"
        )


def sae_report():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM v_sae_pending")
    rows = cur.fetchall()
    conn.close()
    print(f"\n[REPORT] SAEs Pending Report: {len(rows)}")
    for r in rows:
        print(f"         {dict(r)}")


def audit_report(limit=15):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"SELECT event_time, action, record_id, performed_by FROM audit_trail LIMIT {limit}"
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    print(f"\n[REPORT] Audit Trail (last {limit}):")
    for r in rows:
        print(
            f"         {str(r['event_time'])[:16]} | {r['action']} | {r['record_id']} | {r['performed_by']}"
        )
