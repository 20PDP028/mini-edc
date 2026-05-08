"""
validation.py — Mini EDC Validation Engine
Validates clinical data against predefined rules and flags issues.
"""

import pandas as pd
import re
from datetime import datetime

# ─── Validation Rules ────────────────────────────────────────────────────────
RULES = {
    "Age":        {"min": 1,    "max": 120,   "required": True},
    "Weight_kg":  {"required": True},
    "Gender":     {"allowed": ["Male", "Female"], "required": True},
    "Lab_Hb":     {"min": 8.0,  "max": 18.0,  "required": True},
    "Lab_WBC":    {"min": 4000, "max": 11000,  "required": True},
    "Dose_mg":    {"min": 0,    "required": True},
    "Subject_ID": {"unique": True, "required": True},
}

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_blank(val):
    return val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == ""


def validate_dataset(df: pd.DataFrame) -> list[dict]:
    """
    Run all validation checks on the dataframe.
    Returns a list of issue dicts with keys:
        row, subject_id, field, value, issue, severity
    """
    issues = []

    seen_ids = {}

    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel row number (1-indexed + header)
        sid = str(row.get("Subject_ID", "")).strip()

        # ── Duplicate Subject_ID ─────────────────────────────────────────────
        if sid:
            if sid in seen_ids:
                issues.append({
                    "row": row_num,
                    "subject_id": sid,
                    "field": "Subject_ID",
                    "value": sid,
                    "issue": f"Duplicate Subject_ID (first seen at row {seen_ids[sid]})",
                    "severity": "Critical",
                })
            else:
                seen_ids[sid] = row_num

        # ── Age ──────────────────────────────────────────────────────────────
        age = row.get("Age")
        if _is_blank(age):
            issues.append({"row": row_num, "subject_id": sid, "field": "Age",
                            "value": age, "issue": "Age is missing", "severity": "Critical"})
        else:
            try:
                age = float(age)
                if not (RULES["Age"]["min"] <= age <= RULES["Age"]["max"]):
                    issues.append({"row": row_num, "subject_id": sid, "field": "Age",
                                   "value": age,
                                   "issue": f"Age {age} out of range (1–120)",
                                   "severity": "Critical"})
            except (ValueError, TypeError):
                issues.append({"row": row_num, "subject_id": sid, "field": "Age",
                                "value": age, "issue": "Age is not numeric", "severity": "Critical"})

        # ── Weight ───────────────────────────────────────────────────────────
        weight = row.get("Weight_kg")
        if _is_blank(weight):
            issues.append({"row": row_num, "subject_id": sid, "field": "Weight_kg",
                            "value": weight, "issue": "Weight is missing (required field)",
                            "severity": "Major"})

        # ── Gender ───────────────────────────────────────────────────────────
        gender = str(row.get("Gender", "")).strip()
        if _is_blank(gender):
            issues.append({"row": row_num, "subject_id": sid, "field": "Gender",
                            "value": gender, "issue": "Gender is missing", "severity": "Major"})
        elif gender not in RULES["Gender"]["allowed"]:
            issues.append({"row": row_num, "subject_id": sid, "field": "Gender",
                            "value": gender,
                            "issue": f"Invalid gender value '{gender}' (expected Male/Female)",
                            "severity": "Major"})

        # ── Lab Hb ───────────────────────────────────────────────────────────
        hb = row.get("Lab_Hb")
        if _is_blank(hb):
            issues.append({"row": row_num, "subject_id": sid, "field": "Lab_Hb",
                            "value": hb, "issue": "Lab_Hb is missing", "severity": "Major"})
        else:
            try:
                hb = float(hb)
                if not (RULES["Lab_Hb"]["min"] <= hb <= RULES["Lab_Hb"]["max"]):
                    issues.append({"row": row_num, "subject_id": sid, "field": "Lab_Hb",
                                   "value": hb,
                                   "issue": f"Hb value {hb} g/dL out of range (8–18)",
                                   "severity": "Critical"})
            except (ValueError, TypeError):
                issues.append({"row": row_num, "subject_id": sid, "field": "Lab_Hb",
                                "value": hb, "issue": "Lab_Hb is not numeric", "severity": "Major"})

        # ── Lab WBC ──────────────────────────────────────────────────────────
        wbc = row.get("Lab_WBC")
        if _is_blank(wbc):
            issues.append({"row": row_num, "subject_id": sid, "field": "Lab_WBC",
                            "value": wbc, "issue": "Lab_WBC is missing", "severity": "Major"})
        else:
            try:
                wbc = float(wbc)
                if not (RULES["Lab_WBC"]["min"] <= wbc <= RULES["Lab_WBC"]["max"]):
                    issues.append({"row": row_num, "subject_id": sid, "field": "Lab_WBC",
                                   "value": wbc,
                                   "issue": f"WBC {int(wbc)} cells/μL out of range (4000–11000)",
                                   "severity": "Critical"})
            except (ValueError, TypeError):
                issues.append({"row": row_num, "subject_id": sid, "field": "Lab_WBC",
                                "value": wbc, "issue": "Lab_WBC is not numeric", "severity": "Major"})

        # ── Dose ─────────────────────────────────────────────────────────────
        dose = row.get("Dose_mg")
        if not _is_blank(dose):
            try:
                dose = float(dose)
                if dose < 0:
                    issues.append({"row": row_num, "subject_id": sid, "field": "Dose_mg",
                                   "value": dose,
                                   "issue": f"Dose_mg {dose} is negative (invalid)",
                                   "severity": "Critical"})
            except (ValueError, TypeError):
                pass

        # ── Visit Date ───────────────────────────────────────────────────────
        visit_date = str(row.get("Visit_Date", "")).strip()
        if not _is_blank(visit_date):
            if not DATE_PATTERN.match(visit_date):
                issues.append({"row": row_num, "subject_id": sid, "field": "Visit_Date",
                                "value": visit_date,
                                "issue": f"Invalid date format '{visit_date}' (expected YYYY-MM-DD)",
                                "severity": "Major"})
            else:
                try:
                    datetime.strptime(visit_date, "%Y-%m-%d")
                except ValueError:
                    issues.append({"row": row_num, "subject_id": sid, "field": "Visit_Date",
                                   "value": visit_date,
                                   "issue": f"Impossible date '{visit_date}'",
                                   "severity": "Major"})

        # ── AE Severity present when AE reported ─────────────────────────────
        ae = str(row.get("Adverse_Event", "")).strip()
        ae_sev = str(row.get("AE_Severity", "")).strip()
        if ae and ae.lower() != "none" and _is_blank(ae_sev):
            issues.append({"row": row_num, "subject_id": sid, "field": "AE_Severity",
                            "value": ae_sev,
                            "issue": f"Adverse Event '{ae}' reported but AE_Severity is blank",
                            "severity": "Major"})

    return issues


if __name__ == "__main__":
    df = pd.read_excel(
        "../data/raw_clinical_data.xlsx",
        sheet_name="Clinical_Data",
        dtype={"Subject_ID": str, "Visit_Date": str},
    )
    issues = validate_dataset(df)
    issues_df = pd.DataFrame(issues)
    print(f"\n{'='*60}")
    print(f"  VALIDATION COMPLETE — {len(issues)} issue(s) found")
    print(f"{'='*60}")
    print(issues_df.to_string(index=False))
