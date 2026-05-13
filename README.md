# mini-edc

A mini Electronic Data Capture system I built as a personal project to understand how clinical data management actually works under the hood.

I'm a PharmD student who did a CRC internship and kept wondering — what's happening on the backend when you enter data into an EDC? So I tried to build one from scratch.

---

## What this does

The project is split into 4 phases, each one building on the last.

**Phase A — Validation Engine**
Checks clinical trial data against CDISC SDTM rules. Covers 7 domains (DM, AE, VS, LB, EX, SV, DS) with 40+ edit checks. Things like: is systolic BP actually higher than diastolic, did consent happen before first dose, are SAE flags consistent.

**Phase B — SDTM Generator**
Takes raw data and converts it into CDISC SDTM v1.8 compliant datasets. Also generates a `define.xml` file (CDISC Define-XML 2.0) — the kind you'd attach to an FDA submission.

**Phase C — 21 CFR Part 11 Compliance**
This was the most interesting part to build. Implemented an audit trail where every row is HMAC-chained to the one before it, so you can detect if anyone tampers with the log. Electronic signatures with proper legal manifestation, role-based access, password hashing with PBKDF2 (260k iterations). Basically tried to check off every §11.x requirement I could.

**Phase D — Streamlit Dashboard**
A 7-page web app that ties everything together — run validations, export SDTM datasets, browse the audit trail, manage users, generate compliance reports.

---

## Running it locally

```bash
pip install -r requirements.txt
cd python
streamlit run dashboard_phase_d.py
```

Then open http://localhost:8501

---

## Folder structure

```
mini-edc/
├── python/
│   ├── cdisc_validation_engine.py   # Phase A
│   ├── sdtm_generator.py            # Phase B
│   ├── part11_audit.py              # Phase C
│   └── dashboard_phase_d.py         # Phase D
├── data/                            # Sample trial data
├── reports/
│   ├── sdtm/                        # Generated SDTM outputs
│   ├── phase_a_findings.json
│   ├── part11_audit.db              # SQLite audit database
│   └── audit_trail_export.csv
├── sql/
├── tests/
├── nginx/
└── requirements.txt
```

---

## Demo login

| Username | Password | Role |
|---|---|---|
| dr_sharma | Sharma@Trial2024! | Investigator |
| cdm_raj | CdmRaj@Trial2024! | Data Manager |
| monitor1 | Monitor@Trial2024! | Monitor |
| admin | Admin@Trial2024! | Admin |

---

## Tech used

- Python 3.12
- Streamlit
- SQLite
- Plotly
- PBKDF2-HMAC-SHA256 + HMAC-SHA256
- CDISC SDTM v1.8 / Define-XML 2.0
- Docker (for deployment setup)

---

## Why I built this

During my CRC internship at Premier Research / Mysore Medical College, I was doing CRF entry, SDV, and query management daily but always as an end user. I wanted to understand what's going on behind the forms — how audit trails are actually enforced, what SDTM compliance looks like at the data level, and what 21 CFR Part 11 means in practice beyond just "use e-signatures."

This project is my attempt to figure that out. It's not perfect and it's not a real EDC, but it helped me understand CDM at a level that no textbook really explained.

---

Built by Saravanan B , learning CDM one bug at a time.
