"""
analysis.py — Data Cleaning + Clinical Analysis
Produces cleaned_data.csv and summary statistics.
"""

import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from validation import validate_dataset

VALID_GENDERS = {"Male", "Female"}


def clean_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (cleaned_df, removed_df).
    Removes records with critical unfixable errors;
    auto-corrects minor format issues where safe.
    """
    issues = validate_dataset(df)
    bad_rows = set()

    for issue in issues:
        row_num = issue["row"]
        df_idx = row_num - 2  # back to 0-based index

        field = issue["field"]
        sev = issue["severity"]

        # Auto-fix: normalise gender capitalisation
        if field == "Gender" and "Invalid gender" in issue["issue"]:
            raw = str(df.at[df_idx, "Gender"]).strip()
            if raw.lower() in ("male", "m"):
                df.at[df_idx, "Gender"] = "Male"
            elif raw.lower() in ("female", "f"):
                df.at[df_idx, "Gender"] = "Female"
            else:
                bad_rows.add(df_idx)
            continue

        # Flag critical issues for removal
        if sev == "Critical":
            bad_rows.add(df_idx)

    cleaned = df.drop(index=list(bad_rows)).reset_index(drop=True)
    removed = df.loc[list(bad_rows)].reset_index(drop=True)
    return cleaned, removed


def ae_frequency(df: pd.DataFrame) -> pd.DataFrame:
    ae = df[df["Adverse_Event"].notna() & (df["Adverse_Event"].str.lower() != "none")]
    return (
        ae.groupby(["Adverse_Event", "AE_Severity"])
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )


def lab_summary(df: pd.DataFrame) -> pd.DataFrame:
    return df[["Lab_Hb", "Lab_WBC"]].describe().round(2)


def site_summary(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("Site_ID")
        .agg(
            Subjects=("Subject_ID", "count"),
            Avg_Age=("Age", "mean"),
            Avg_Weight=("Weight_kg", "mean"),
            Avg_Hb=("Lab_Hb", "mean"),
        )
        .round(2)
        .reset_index()
    )


if __name__ == "__main__":
    df = pd.read_excel(
        "../data/raw_clinical_data.xlsx",
        sheet_name="Clinical_Data",
        dtype={"Subject_ID": str, "Visit_Date": str},
    )

    cleaned, removed = clean_dataset(df.copy())
    cleaned.to_csv("../data/cleaned_data.csv", index=False)

    print(f"\n{'='*60}")
    print(f"  DATA CLEANING SUMMARY")
    print(f"{'='*60}")
    print(f"  Original records : {len(df)}")
    print(f"  Removed (critical errors): {len(removed)}")
    print(f"  Cleaned records  : {len(cleaned)}")
    print(f"  Saved to         : ../data/cleaned_data.csv\n")

    print("─── AE Frequency ──────────────────────────────────────")
    print(ae_frequency(cleaned).to_string(index=False))

    print("\n─── Lab Summary (cleaned data) ─────────────────────────")
    print(lab_summary(cleaned))

    print("\n─── Site Summary ───────────────────────────────────────")
    print(site_summary(cleaned).to_string(index=False))
