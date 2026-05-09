"""
main_phase3.py — Phase 3 Runner
Ties together: CDISC validation → DB storage → Query lifecycle → Reports
Save in: Mini_EDC_Project/python/main_phase3.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from db_manager import (
    init_db,
    load_subjects,
    load_visits,
    load_adverse_events,
    open_queries,
    answer_query,
    close_query,
    query_summary,
    open_queries_report,
    sae_report,
    audit_report,
)
from validation_phase2 import validate  # your Phase 2 engine

# ── Config ────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE, "..", "data", "raw_clinical_data.xlsx")
SHEET_NAME = "Clinical_Data"

# ── Step 1: Initialise Database ───────────────────────────────
print("\n" + "=" * 65)
print("  PHASE 3 — CDM + Query Lifecycle")
print("=" * 65)

init_db()

# ── Step 2: Load CDISC Data ───────────────────────────────────
print("\n[STEP 2] Loading clinical data from Excel...")
df = pd.read_excel(
    DATA_FILE,
    sheet_name=SHEET_NAME,
    dtype={"USUBJID": str, "VISITDT": str},
)
print(f"         Loaded {len(df)} rows")

load_subjects(df)
load_visits(df)
load_adverse_events(df)

# ── Step 3: Validate & Open Queries ───────────────────────────
print("\n[STEP 3] Running Phase 2 validation engine...")
issues, saes = validate(df)
print(f"         {len(issues)} issue(s) | {len(saes)} SAE(s) detected")

open_queries(issues)

# ── Step 4: Simulate Query Lifecycle ──────────────────────────
print("\n[STEP 4] Simulating query lifecycle...")

# Site answers QRY-0001
answer_query(
    "QRY-0001", "Subject withdrew consent before weight was recorded", "SITE_001"
)

# DM closes QRY-0001 after review
close_query("QRY-0001", closed_by="DM_JOHN", reason="Explanation accepted")

# Site answers QRY-0002
answer_query(
    "QRY-0002", "Age confirmed as 145 — data entry error, correcting to 45", "SITE_002"
)

# ── Step 5: Reports ───────────────────────────────────────────
print("\n[STEP 5] Generating reports...")

query_summary()
open_queries_report()
sae_report()
audit_report(limit=15)

print("\n" + "=" * 65)
print("  PHASE 3 COMPLETE")
print("=" * 65 + "\n")
