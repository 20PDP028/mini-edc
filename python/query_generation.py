"""
query_generation.py — Automatic CDM Query Generator
Converts validation issues into formal clinical data management queries.
"""

import pandas as pd
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from validation import validate_dataset

QUERY_TEMPLATES = {
    "Duplicate Subject_ID": "Duplicate Subject ID detected. Please confirm this is a unique patient record and correct if necessary.",
    "Age": "Please verify the recorded age. Value appears to be out of acceptable range (1–120 years).",
    "Weight_kg": "Weight_kg is a required field. Please provide the subject's weight at this visit.",
    "Gender": "Gender value is invalid or improperly formatted. Acceptable values are 'Male' or 'Female' only.",
    "Lab_Hb": "Hemoglobin value is outside the expected physiological range (8–18 g/dL). Please verify with source document.",
    "Lab_WBC": "WBC count is outside the expected range (4000–11000 cells/μL). Please verify with laboratory report.",
    "Dose_mg": "Dose recorded is negative, which is not valid. Please confirm the correct dose administered.",
    "Visit_Date": "Visit date is in an incorrect format or represents an impossible date. Expected format: YYYY-MM-DD.",
    "AE_Severity": "An Adverse Event has been recorded but severity grade is missing. Please complete AE_Severity.",
}

STATUS_OPEN = "Open"


def generate_query_text(field: str, issue: str) -> str:
    for key in QUERY_TEMPLATES:
        if key in field or key in issue:
            return QUERY_TEMPLATES[key]
    return f"Data discrepancy detected in field '{field}'. Please verify against source document: {issue}"


def generate_queries(issues: list[dict]) -> pd.DataFrame:
    if not issues:
        return pd.DataFrame()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    records = []

    for i, issue in enumerate(issues, 1):
        query_text = generate_query_text(issue["field"], issue["issue"])
        records.append(
            {
                "Query_ID": f"QRY-{i:04d}",
                "Generated_Date": now,
                "Subject_ID": issue["subject_id"],
                "Row_Number": issue["row"],
                "Field": issue["field"],
                "Invalid_Value": issue["value"],
                "Issue_Detected": issue["issue"],
                "Severity": issue["severity"],
                "Query_Text": query_text,
                "Status": STATUS_OPEN,
                "Resolved_By": "",
                "Resolution_Date": "",
                "Resolution_Note": "",
            }
        )

    return pd.DataFrame(records)


if __name__ == "__main__":
    df = pd.read_excel(
        "../data/raw_clinical_data.xlsx",
        sheet_name="Clinical_Data",
        dtype={"Subject_ID": str, "Visit_Date": str},
    )

    issues = validate_dataset(df)
    query_df = generate_queries(issues)

    output_path = "../data/query_log.csv"
    query_df.to_csv(output_path, index=False)

    print(f"\n{'='*65}")
    print(f"  QUERY GENERATION COMPLETE — {len(query_df)} queries raised")
    print(f"  Saved to: {output_path}")
    print(f"{'='*65}\n")

    summary = query_df.groupby("Severity").size().reset_index(name="Count")
    print("Query Severity Summary:")
    print(summary.to_string(index=False))
    print()
    print(
        query_df[["Query_ID", "Subject_ID", "Field", "Severity", "Status"]].to_string(
            index=False
        )
    )
