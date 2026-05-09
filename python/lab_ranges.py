"""
lab_ranges.py — Feature 14: Lab Reference Ranges
Dynamic normal ranges by age, gender, and lab test.
Save in: Mini_EDC_Project/python/lab_ranges.py
Run with: python lab_ranges.py
"""

import os
import pandas as pd
from datetime import datetime
from db_connection import get_conn, is_postgres

BASE = os.path.dirname(os.path.abspath(__file__))

# ── Reference Range Dictionary ────────────────────────────────
# Format: test_code: {(gender, age_min, age_max): (low, high, unit, alert_low, alert_high)}
# alert_low/high = panic values requiring immediate action
LAB_RANGES = {
    "HGB": {
        ("M", 18, 64): (13.5, 17.5, "g/dL", 7.0, 20.0),
        ("M", 65, 120): (12.5, 17.0, "g/dL", 7.0, 20.0),
        ("F", 18, 64): (12.0, 16.0, "g/dL", 7.0, 20.0),
        ("F", 65, 120): (11.5, 16.0, "g/dL", 7.0, 20.0),
        ("U", 0, 120): (11.5, 17.5, "g/dL", 7.0, 20.0),
    },
    "WBC": {
        ("M", 18, 120): (4.0, 11.0, "10^3/uL", 2.0, 30.0),
        ("F", 18, 120): (4.0, 11.0, "10^3/uL", 2.0, 30.0),
        ("U", 0, 120): (4.0, 11.0, "10^3/uL", 2.0, 30.0),
    },
    "PLT": {
        ("M", 18, 120): (150, 400, "10^3/uL", 50, 800),
        ("F", 18, 120): (150, 400, "10^3/uL", 50, 800),
        ("U", 0, 120): (150, 400, "10^3/uL", 50, 800),
    },
    "CREAT": {
        ("M", 18, 120): (0.74, 1.35, "mg/dL", 0.4, 10.0),
        ("F", 18, 120): (0.59, 1.04, "mg/dL", 0.4, 10.0),
        ("U", 0, 120): (0.59, 1.35, "mg/dL", 0.4, 10.0),
    },
    "ALT": {
        ("M", 18, 120): (7, 56, "U/L", 1, 500),
        ("F", 18, 120): (7, 45, "U/L", 1, 500),
        ("U", 0, 120): (7, 56, "U/L", 1, 500),
    },
    "AST": {
        ("M", 18, 120): (10, 40, "U/L", 1, 500),
        ("F", 18, 120): (10, 35, "U/L", 1, 500),
        ("U", 0, 120): (10, 40, "U/L", 1, 500),
    },
    "GLUC": {
        ("M", 18, 120): (70, 100, "mg/dL", 40, 500),
        ("F", 18, 120): (70, 100, "mg/dL", 40, 500),
        ("U", 0, 120): (70, 100, "mg/dL", 40, 500),
    },
    "NA": {
        ("M", 18, 120): (136, 145, "mmol/L", 120, 160),
        ("F", 18, 120): (136, 145, "mmol/L", 120, 160),
        ("U", 0, 120): (136, 145, "mmol/L", 120, 160),
    },
    "K": {
        ("M", 18, 120): (3.5, 5.1, "mmol/L", 2.5, 6.5),
        ("F", 18, 120): (3.5, 5.1, "mmol/L", 2.5, 6.5),
        ("U", 0, 120): (3.5, 5.1, "mmol/L", 2.5, 6.5),
    },
}


# Map gender values from DB to M/F/U
def _norm_gender(gender):
    g = str(gender).upper().strip()
    if g in ["M", "MALE"]:
        return "M"
    if g in ["F", "FEMALE"]:
        return "F"
    return "U"


def get_reference_range(test_code: str, gender: str, age: float):
    """
    Get the reference range for a test given gender and age.
    Returns (low, high, unit, alert_low, alert_high) or None
    """
    test_code = test_code.upper()
    if test_code not in LAB_RANGES:
        return None

    gender_norm = _norm_gender(gender)
    ranges = LAB_RANGES[test_code]

    # Try exact gender + age match
    for (g, age_min, age_max), vals in ranges.items():
        if g == gender_norm and age_min <= age <= age_max:
            return vals

    # Fall back to Unknown gender
    for (g, age_min, age_max), vals in ranges.items():
        if g == "U" and age_min <= age <= age_max:
            return vals

    return None


def evaluate_lab_value(test_code: str, value: float, gender: str, age: float):
    """
    Evaluate a lab value against reference range.
    Returns: (status, flag, message)
    status: NORMAL | LOW | HIGH | CRITICALLY_LOW | CRITICALLY_HIGH | UNKNOWN
    """
    ref = get_reference_range(test_code, gender, age)
    if ref is None:
        return "UNKNOWN", "", f"No reference range for {test_code}"

    low, high, unit, alert_low, alert_high = ref

    if value < alert_low:
        return (
            "CRITICALLY_LOW",
            "<<",
            f"{test_code}={value} {unit} CRITICALLY LOW (ref: {low}–{high}, panic <{alert_low})",
        )
    if value > alert_high:
        return (
            "CRITICALLY_HIGH",
            ">>",
            f"{test_code}={value} {unit} CRITICALLY HIGH (ref: {low}–{high}, panic >{alert_high})",
        )
    if value < low:
        return "LOW", "L", f"{test_code}={value} {unit} LOW (ref: {low}–{high})"
    if value > high:
        return "HIGH", "H", f"{test_code}={value} {unit} HIGH (ref: {low}–{high})"
    return "NORMAL", "", f"{test_code}={value} {unit} NORMAL (ref: {low}–{high})"


def init_lab_flags_table():
    conn = get_conn()
    if is_postgres():
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lab_flags (
                flag_id     SERIAL PRIMARY KEY,
                usubjid     TEXT,
                siteid      TEXT,
                test_code   TEXT,
                value       REAL,
                unit        TEXT,
                ref_low     REAL,
                ref_high    REAL,
                status      TEXT,
                flag        TEXT,
                message     TEXT,
                flagged_at  TEXT
            )
        """)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lab_flags (
                flag_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                usubjid     TEXT,
                siteid      TEXT,
                test_code   TEXT,
                value       REAL,
                unit        TEXT,
                ref_low     REAL,
                ref_high    REAL,
                status      TEXT,
                flag        TEXT,
                message     TEXT,
                flagged_at  TEXT
            )
        """)
    conn.commit()
    conn.close()


def evaluate_all_subjects():
    """
    Read all subjects + their labs from raw Excel and evaluate.
    Returns DataFrame of flagged results.
    """
    init_lab_flags_table()
    raw_path = os.path.join(BASE, "..", "data", "raw_clinical_data.xlsx")
    if not os.path.exists(raw_path):
        print("[LAB] raw_clinical_data.xlsx not found")
        return pd.DataFrame()

    df = pd.read_excel(raw_path, sheet_name="Clinical_Data")
    conn = get_conn()
    ph = "%s" if is_postgres() else "?"

    results = []
    for _, row in df.iterrows():
        usubjid = str(row.get("Subject_ID", ""))
        siteid = str(row.get("Site_ID", ""))
        gender = str(row.get("Gender", "U"))
        age = float(row.get("Age", 30)) if not pd.isna(row.get("Age")) else 30.0

        lab_tests = [
            ("HGB", row.get("Lab_Hb")),
            (
                "WBC",
                (
                    row.get("Lab_WBC") / 1000
                    if not pd.isna(row.get("Lab_WBC", float("nan")))
                    else None
                ),
            ),
        ]

        for test_code, value in lab_tests:
            if value is None or pd.isna(value):
                continue
            value = float(value)
            status, flag, message = evaluate_lab_value(test_code, value, gender, age)
            ref = get_reference_range(test_code, gender, age)

            conn.execute(
                f"""
                INSERT INTO lab_flags
                (usubjid, siteid, test_code, value, unit,
                 ref_low, ref_high, status, flag, message, flagged_at)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
            """,
                (
                    usubjid,
                    siteid,
                    test_code,
                    value,
                    ref[2] if ref else "",
                    ref[0] if ref else None,
                    ref[1] if ref else None,
                    status,
                    flag,
                    message,
                    datetime.now().isoformat(),
                ),
            )

            results.append(
                {
                    "Subject": usubjid,
                    "Site": siteid,
                    "Test": test_code,
                    "Value": value,
                    "Flag": flag,
                    "Status": status,
                    "Message": message,
                }
            )

    conn.commit()
    conn.close()
    return pd.DataFrame(results)


def print_lab_report():
    """Print lab flags report."""
    df = evaluate_all_subjects()

    print("\n" + "=" * 65)
    print("  LAB REFERENCE RANGE EVALUATION")
    print("=" * 65)

    if df.empty:
        print("  No lab data found.")
        return

    total = len(df)
    normal = len(df[df["Status"] == "NORMAL"])
    abnormal = total - normal
    crit = len(df[df["Status"].str.startswith("CRITICALLY")])

    print(f"  Total Lab Values  : {total}")
    print(f"  Normal            : {normal}")
    print(f"  Abnormal          : {abnormal}")
    print(f"  Critical          : {crit}")

    if crit > 0:
        print("\n  ⚠️  CRITICAL VALUES:")
        crit_df = df[df["Status"].str.startswith("CRITICALLY")]
        for _, row in crit_df.iterrows():
            print(
                f"  🚨 {row['Subject']} | {row['Test']} = {row['Value']} | {row['Message']}"
            )

    print("\n  All Flagged Results:")
    flagged = df[df["Status"] != "NORMAL"]
    if flagged.empty:
        print("  ✅ All lab values within normal range.")
    else:
        for _, row in flagged.iterrows():
            icon = "🚨" if "CRIT" in row["Status"] else "⚠️"
            print(
                f"  {icon} {row['Subject']:8} | {row['Test']:6} | {row['Value']:6} | {row['Message']}"
            )
    print()


def print_reference_table():
    """Print all reference ranges in a formatted table."""
    print("\n" + "=" * 75)
    print("  LAB REFERENCE RANGE TABLE")
    print("=" * 75)
    print(
        f"  {'Test':<8} {'Gender':<8} {'Age Range':<12} {'Low':>8} {'High':>8} {'Unit':<12} {'Panic Low':>10} {'Panic High':>10}"
    )
    print("  " + "-" * 71)
    for test, ranges in LAB_RANGES.items():
        for (gender, age_min, age_max), (lo, hi, unit, al, ah) in ranges.items():
            print(
                f"  {test:<8} {gender:<8} {age_min:>3}–{age_max:<7} {lo:>8} {hi:>8} {unit:<12} {al:>10} {ah:>10}"
            )
    print()


if __name__ == "__main__":
    print_reference_table()
    print_lab_report()
