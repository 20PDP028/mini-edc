"""
validation_phase2.py — Phase 2 CDISC Validation Engine
Validates clinical data against CDISC rules.
Save in: Mini_EDC_Project/python/validation_phase2.py
"""

import pandas as pd
from datetime import datetime


def validate(df):
    """
    Validate clinical dataframe.
    Returns: (issues list, saes list)
    """
    issues = []
    saes = []
    query_counter = [0]

    def add_issue(row, field, severity, issue_text):
        query_counter[0] += 1
        issues.append(
            {
                "query_id": f"QRY-{query_counter[0]:04d}",
                "usubjid": str(row.get("Subject_ID", "")),
                "siteid": str(row.get("Site_ID", "")),
                "field": field,
                "severity": severity,
                "issue": issue_text,
            }
        )

    for idx, row in df.iterrows():
        subj = str(row.get("Subject_ID", f"ROW{idx}"))

        # ── Age ──────────────────────────────────────────────
        age = row.get("Age")
        if pd.isna(age):
            add_issue(row, "Age", "Major", f"Age is missing for {subj}")
        elif not (1 <= float(age) <= 120):
            add_issue(
                row, "Age", "Critical", f"Age {age} out of range (1–120) for {subj}"
            )

        # ── Gender ───────────────────────────────────────────
        gender = str(row.get("Gender", "")).strip()
        if pd.isna(row.get("Gender")) or gender == "":
            add_issue(row, "Gender", "Major", f"Gender missing for {subj}")
        elif gender not in ["Male", "Female", "M", "F", "MALE", "FEMALE"]:
            add_issue(row, "Gender", "Major", f"Invalid Gender '{gender}' for {subj}")

        # ── Weight ───────────────────────────────────────────
        weight = row.get("Weight_kg")
        if pd.isna(weight):
            add_issue(row, "Weight_kg", "Major", f"Weight missing for {subj}")
        elif not (10 <= float(weight) <= 300):
            add_issue(
                row,
                "Weight_kg",
                "Critical",
                f"Weight {weight} kg out of range for {subj}",
            )

        # ── Visit Date ───────────────────────────────────────
        vdate = row.get("Visit_Date")
        if pd.isna(vdate) or str(vdate).strip() == "":
            add_issue(row, "Visit_Date", "Major", f"Visit date missing for {subj}")
        else:
            try:
                datetime.strptime(str(vdate)[:10], "%Y-%m-%d")
            except ValueError:
                add_issue(
                    row,
                    "Visit_Date",
                    "Major",
                    f"Invalid date format '{vdate}' for {subj}",
                )

        # ── Dose ─────────────────────────────────────────────
        dose = row.get("Dose_mg")
        if pd.isna(dose):
            add_issue(row, "Dose_mg", "Minor", f"Dose missing for {subj}")
        elif float(dose) <= 0:
            add_issue(
                row, "Dose_mg", "Critical", f"Dose {dose} mg must be > 0 for {subj}"
            )

        # ── Lab Hb ───────────────────────────────────────────
        hb = row.get("Lab_Hb")
        if not pd.isna(hb):
            if not (5 <= float(hb) <= 20):
                add_issue(
                    row,
                    "Lab_Hb",
                    "Critical",
                    f"Haemoglobin {hb} g/dL out of range (5–20) for {subj}",
                )

        # ── Lab WBC ──────────────────────────────────────────
        wbc = row.get("Lab_WBC")
        if not pd.isna(wbc):
            if not (1000 <= float(wbc) <= 20000):
                add_issue(
                    row,
                    "Lab_WBC",
                    "Major",
                    f"WBC {wbc} out of range (1000–20000) for {subj}",
                )

        # ── SAE Detection ─────────────────────────────────────
        ae = row.get("Adverse_Event")
        sev = str(row.get("AE_Severity", "")).upper()
        if not pd.isna(ae) and str(ae).strip() and sev == "SEVERE":
            saes.append(
                {
                    "usubjid": str(row.get("Subject_ID", "")),
                    "siteid": str(row.get("Site_ID", "")),
                    "aeterm": str(ae),
                    "aesev": sev,
                    "aeser": "Y",
                    "aestdtc": str(row.get("Visit_Date", "")),
                    "report_flag": "PENDING",
                }
            )

    return issues, saes
