# Mini EDC — Clinical Data Management System

A production-grade mini Electronic Data Capture (EDC) system built in Python,
covering CDISC SDTM v1.8 and 21 CFR Part 11 compliance.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the dashboard (from the python/ folder)
cd python
streamlit run dashboard_phase_d.py
```

Open http://localhost:8501 in your browser.

---

## Project Structure

```
Mini_EDC_Project/
├── python/
│   ├── cdisc_validation_engine.py   # Phase A — 40+ CDISC rules
│   ├── sdtm_generator.py            # Phase B — SDTM datasets + define.xml
│   ├── part11_audit.py              # Phase C — 21 CFR Part 11 audit + e-sigs
│   └── dashboard_phase_d.py        # Phase D — Streamlit dashboard (this file)
├── reports/
│   ├── sdtm/                        # Generated SDTM CSV files + define.xml
│   ├── phase_a_findings.json        # Last validation run
│   ├── part11_audit.db              # SQLite audit/signature database
│   └── audit_trail_export.csv      # Exported audit trail
└── requirements.txt
```

---

## What Each Phase Does

### Phase A — CDISC Validation Engine
File: `cdisc_validation_engine.py`

40+ edit checks across 7 CDISC SDTM domains:

| Domain | Rules | Examples |
|--------|-------|---------|
| DM     | 12    | USUBJID uniqueness, SEX/RACE/ETHNIC CT, consent before first dose |
| AE     | 12    | Date ordering, SAE criteria, FATAL→AESDTH cross-check |
| VS     | 8     | Systolic > diastolic, plausibility ranges, unit validation |
| LB     | 6     | ALT/AST > 3×ULN hepatotoxicity flag, normal range indicator |
| EX     | 6     | Dose before consent, negative dose, date ordering |
| SV     | 4     | Visit window compliance (e.g. Week 4 = study day 26–30) |
| DS     | 4     | DSDECOD CT, DSTERM required for protocol deviations |

### Phase B — SDTM Generator
File: `sdtm_generator.py`

- Generates CDISC SDTM v1.8 compliant datasets (DM, AE, VS, LB, EX)
- Calculates study days, baseline flags, derived numeric results
- Creates `define.xml` (CDISC Define-XML 2.0) for FDA submission
- Dataset-level conformance checker

### Phase C — 21 CFR Part 11
File: `part11_audit.py`

| Requirement | Implementation |
|-------------|---------------|
| §11.10(e) Audit trail | HMAC-chained, immutable, timestamped SQLite |
| §11.10(d) Access control | Role-based (Investigator/DM/Monitor/Admin/Sponsor) |
| §11.50 Signature manifest | Full legal statement per signature |
| §11.70 Record binding | SHA-256 hash ties signature to exact record state |
| §11.100 Non-repudiation | User ID + role recorded on every action |
| §11.200 Password re-entry | Required for every e-signature |
| §11.300 Password controls | PBKDF2 (260k iterations), strength rules, last-5 reuse block |
| Tamper detection | HMAC on every audit row; chain hash links to previous entry |
| Immutability | DB triggers prevent UPDATE/DELETE on audit_trail table |

### Phase D — Streamlit Dashboard
File: `dashboard_phase_d.py`

7-page web application:

1. **Home** — Study KPIs and system status
2. **Validation** — Run Phase A, filter findings, download CSV
3. **SDTM Export** — Generate datasets, view data, download ZIP
4. **Audit Trail** — Browse immutable log, verify chain integrity
5. **E-Signatures** — Apply and verify §11.50 signatures
6. **Users** — Role-based user management
7. **Reports** — Full 21 CFR Part 11 compliance report

---

## Demo Credentials

| Username   | Password             | Role         |
|------------|----------------------|--------------|
| dr_sharma  | Sharma@Trial2024!    | Investigator |
| cdm_raj    | CdmRaj@Trial2024!    | Data Manager |
| monitor1   | Monitor@Trial2024!   | Monitor      |
| admin      | Admin@Trial2024!     | Admin        |

---

## CV / Portfolio Description

> Built a Clinical Data Management (CDM) prototype in Python demonstrating
> CDISC SDTM v1.8 validation (40+ edit checks across 7 domains), FDA-submittable
> dataset generation with define.xml, 21 CFR Part 11 compliant audit trail
> (HMAC-chained, tamper-evident), electronic signatures with §11.50 manifestation
> and §11.70 record binding, role-based access control, and a full Streamlit
> web dashboard — built from scratch without commercial EDC tooling.

---

## Tech Stack

- Python 3.12
- Streamlit (dashboard)
- Plotly (charts)
- SQLite (audit database)
- PBKDF2-HMAC-SHA256 (password hashing)
- HMAC-SHA256 (audit chain integrity)
- CDISC SDTM v1.8 / Define-XML 2.0
