-- ============================================================
-- schema_phase3.sql — Phase 3 CDM Database (SQLite)
-- Mini EDC-Based Clinical Data Validation & Query Management
-- ============================================================

PRAGMA foreign_keys = ON;

-- ── 1. SUBJECTS ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subjects (
    usubjid     TEXT PRIMARY KEY,
    siteid      TEXT NOT NULL,
    age         REAL,
    sex         TEXT CHECK(sex IN ('M','F')),
    weightbl    REAL,
    created_at  TEXT DEFAULT (datetime('now')),
    locked      INTEGER DEFAULT 0   -- 1 = data locked (Phase 5 DBL)
);

-- ── 2. VISITS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS visits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usubjid     TEXT NOT NULL REFERENCES subjects(usubjid),
    visitnum    INTEGER,
    visitdt     TEXT,   -- ISO 8601 YYYY-MM-DD
    exdose      REAL,
    lbtest_hb   REAL,
    lbtest_wbc  REAL,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ── 3. ADVERSE EVENTS ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS adverse_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usubjid     TEXT NOT NULL REFERENCES subjects(usubjid),
    aeterm      TEXT,
    aesev       TEXT,   -- MILD / MODERATE / SEVERE
    aeser       TEXT,   -- Y / N
    aestdtc     TEXT,   -- AE start date
    report_flag TEXT DEFAULT 'PENDING',  -- PENDING / REPORTED / CLOSED
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ── 4. QUERIES (Full Lifecycle) ──────────────────────────────
CREATE TABLE IF NOT EXISTS queries (
    query_id    TEXT PRIMARY KEY,           -- QRY-0001 etc.
    usubjid     TEXT NOT NULL REFERENCES subjects(usubjid),
    siteid      TEXT,
    field       TEXT NOT NULL,
    value       TEXT,
    issue       TEXT NOT NULL,
    severity    TEXT CHECK(severity IN ('Critical','Major','Minor')),
    status      TEXT DEFAULT 'Open'
                CHECK(status IN ('Open','Answered','Closed')),
    opened_at   TEXT DEFAULT (datetime('now')),
    answered_at TEXT,
    closed_at   TEXT,
    answer_text TEXT,
    closed_by   TEXT
);

-- ── 5. AUDIT TRAIL (21 CFR Part 11) ─────────────────────────
CREATE TABLE IF NOT EXISTS audit_trail (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time  TEXT DEFAULT (datetime('now')),
    table_name  TEXT NOT NULL,
    record_id   TEXT NOT NULL,
    field       TEXT,
    old_value   TEXT,
    new_value   TEXT,
    action      TEXT CHECK(action IN ('INSERT','UPDATE','DELETE','QUERY_OPEN','QUERY_ANSWER','QUERY_CLOSE','SAE_FLAG')),
    performed_by TEXT DEFAULT 'SYSTEM',
    reason      TEXT
);

-- ── VIEWS ───────────────────────────────────────────────────
CREATE VIEW IF NOT EXISTS v_open_queries AS
    SELECT query_id, usubjid, siteid, field, severity, issue, opened_at
    FROM queries WHERE status = 'Open'
    ORDER BY severity DESC, opened_at ASC;

CREATE VIEW IF NOT EXISTS v_sae_pending AS
    SELECT ae.id, ae.usubjid, s.siteid, ae.aeterm, ae.aesev,
           ae.aestdtc, ae.report_flag
    FROM adverse_events ae
    JOIN subjects s USING(usubjid)
    WHERE ae.aeser = 'Y' AND ae.report_flag = 'PENDING';

CREATE VIEW IF NOT EXISTS v_query_summary AS
    SELECT
        status,
        severity,
        COUNT(*) AS count
    FROM queries
    GROUP BY status, severity
    ORDER BY status, severity;
