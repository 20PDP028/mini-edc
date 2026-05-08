-- ============================================================
-- Mini EDC Clinical Data System — SQL Schema
-- ============================================================

-- Drop in reverse dependency order
DROP TABLE IF EXISTS Queries;
DROP TABLE IF EXISTS Adverse_Events;
DROP TABLE IF EXISTS Lab_Results;
DROP TABLE IF EXISTS Visits;
DROP TABLE IF EXISTS Subjects;

-- ─── Subjects ────────────────────────────────────────────────
CREATE TABLE Subjects (
    subject_id   VARCHAR(20)  PRIMARY KEY,
    site_id      VARCHAR(20)  NOT NULL,
    age          INTEGER      CHECK (age BETWEEN 1 AND 120),
    gender       VARCHAR(10)  CHECK (gender IN ('Male', 'Female')),
    weight_kg    DECIMAL(5,1),
    drug_name    VARCHAR(50)  NOT NULL,
    created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- ─── Visits ──────────────────────────────────────────────────
CREATE TABLE Visits (
    visit_id     SERIAL       PRIMARY KEY,
    subject_id   VARCHAR(20)  REFERENCES Subjects(subject_id),
    visit_date   DATE         NOT NULL,
    dose_mg      DECIMAL(6,1) CHECK (dose_mg >= 0)
);

-- ─── Lab Results ─────────────────────────────────────────────
CREATE TABLE Lab_Results (
    lab_id       SERIAL       PRIMARY KEY,
    subject_id   VARCHAR(20)  REFERENCES Subjects(subject_id),
    visit_id     INTEGER      REFERENCES Visits(visit_id),
    lab_hb       DECIMAL(4,1) CHECK (lab_hb BETWEEN 8 AND 18),
    lab_wbc      INTEGER      CHECK (lab_wbc BETWEEN 4000 AND 11000),
    collected_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- ─── Adverse Events ──────────────────────────────────────────
CREATE TABLE Adverse_Events (
    ae_id        SERIAL       PRIMARY KEY,
    subject_id   VARCHAR(20)  REFERENCES Subjects(subject_id),
    visit_id     INTEGER      REFERENCES Visits(visit_id),
    ae_term      VARCHAR(200) NOT NULL,
    ae_severity  VARCHAR(20)  CHECK (ae_severity IN ('Mild', 'Moderate', 'Severe')),
    reported_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- ─── Queries (CDM Query Log) ──────────────────────────────────
CREATE TABLE Queries (
    query_id        VARCHAR(12)  PRIMARY KEY,
    subject_id      VARCHAR(20)  REFERENCES Subjects(subject_id),
    field_name      VARCHAR(50)  NOT NULL,
    invalid_value   TEXT,
    issue_detected  TEXT         NOT NULL,
    severity        VARCHAR(20)  CHECK (severity IN ('Critical', 'Major', 'Minor')),
    query_text      TEXT         NOT NULL,
    status          VARCHAR(20)  DEFAULT 'Open'
                                 CHECK (status IN ('Open', 'Answered', 'Closed', 'Cancelled')),
    generated_date  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    resolved_by     VARCHAR(100),
    resolution_date DATE,
    resolution_note TEXT
);

-- ─── Useful Views ─────────────────────────────────────────────

-- Open queries per site
CREATE VIEW v_open_queries_by_site AS
    SELECT s.site_id,
           COUNT(q.query_id) AS open_queries
    FROM Queries q
    JOIN Subjects s ON q.subject_id = s.subject_id
    WHERE q.status = 'Open'
    GROUP BY s.site_id
    ORDER BY open_queries DESC;

-- Lab results with subject info
CREATE VIEW v_lab_overview AS
    SELECT s.subject_id, s.site_id, s.drug_name,
           v.visit_date,
           lr.lab_hb, lr.lab_wbc
    FROM Lab_Results lr
    JOIN Subjects  s ON lr.subject_id = s.subject_id
    JOIN Visits    v ON lr.visit_id   = v.visit_id;

-- AE summary by severity
CREATE VIEW v_ae_summary AS
    SELECT ae_severity,
           COUNT(*) AS total_events,
           COUNT(DISTINCT subject_id) AS affected_subjects
    FROM Adverse_Events
    GROUP BY ae_severity
    ORDER BY
        CASE ae_severity
            WHEN 'Severe'   THEN 1
            WHEN 'Moderate' THEN 2
            WHEN 'Mild'     THEN 3
        END;
