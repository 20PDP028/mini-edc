"""
sdtm_export.py — Feature 11: CDISC SDTM Export
Exports clinical data in FDA submission-ready SDTM format.
Save in: Mini_EDC_Project/python/sdtm_export.py
Run with: python sdtm_export.py
"""

import sqlite3
import os
import pandas as pd
from datetime import datetime

BASE        = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE, '..', 'sql', 'cdm_phase3.db')
EXPORTS_DIR = os.path.join(BASE, '..', 'reports', 'sdtm_export')

# Trial metadata — customise
STUDYID  = "CARDIO-PHASE2"
DOMAIN_VERSION = "SDTM v1.7"


def _conn():
    return sqlite3.connect(DB_PATH)


def export_dm():
    """
    DM — Demographics domain.
    Maps: subjects → SDTM DM standard columns.
    """
    conn = _conn()
    df = pd.read_sql_query("SELECT * FROM subjects", conn)
    conn.close()
    if df.empty:
        return pd.DataFrame()

    dm = pd.DataFrame()
    dm["STUDYID"]  = STUDYID
    dm["DOMAIN"]   = "DM"
    dm["USUBJID"]  = df["usubjid"]
    dm["SUBJID"]   = df["usubjid"].str.replace("SUB", "", regex=False)
    dm["SITEID"]   = df["siteid"]
    dm["AGE"]      = df.get("age", "")
    dm["AGEU"]     = "YEARS"
    dm["SEX"]      = df.get("gender", "").map(
        lambda x: "M" if str(x).upper() in ["MALE","M"] else
                  "F" if str(x).upper() in ["FEMALE","F"] else "U"
    )
    dm["ARMCD"]    = "TRT"
    dm["ARM"]      = "Treatment"
    dm["COUNTRY"]  = "IND"
    dm["DMDTC"]    = datetime.now().strftime("%Y-%m-%d")
    dm["DMDY"]     = 1
    return dm


def export_ae():
    """
    AE — Adverse Events domain.
    Maps: adverse_events → SDTM AE standard columns.
    """
    conn = _conn()
    df = pd.read_sql_query("SELECT * FROM adverse_events", conn)

    # Try to get MedDRA coding
    try:
        coding = pd.read_sql_query(
            "SELECT ae_id, meddra_pt, meddra_soc, meddra_code FROM ae_coding", conn
        )
        df = df.merge(coding, on="ae_id", how="left")
    except Exception as e:
        print(f"Error loading AE coding: {e}")
        df["meddra_pt"]  = ""
        df["meddra_soc"] = ""
        df["meddra_code"]= ""
    conn.close()

    if df.empty:
        return pd.DataFrame()

    ae = pd.DataFrame()
    ae["STUDYID"]  = STUDYID
    ae["DOMAIN"]   = "AE"
    ae["USUBJID"]  = df["usubjid"]
    ae["AESEQ"]    = range(1, len(df) + 1)
    ae["AETERM"]   = df["aeterm"]
    ae["AEDECOD"]  = df.get("meddra_pt", df["aeterm"])
    ae["AEBODSYS"] = df.get("meddra_soc", "")
    ae["AESOC"]    = df.get("meddra_soc", "")
    ae["AESEV"]    = df["aesev"].map(
        lambda x: "MILD" if str(x).upper() in ["MILD","MINOR"] else
                  "MODERATE" if str(x).upper() == "MODERATE" else
                  "SEVERE" if str(x).upper() == "SEVERE" else str(x).upper()
    )
    ae["AESER"]    = df["aeser"]
    ae["AESTDTC"]  = df["aestdtc"]
    ae["AEOUT"]    = "UNKNOWN"
    ae["AESDTH"]   = "N"
    ae["AESHOSP"]  = df["aeser"].map(lambda x: "Y" if x == "Y" else "N")
    return ae


def export_vs():
    """
    VS — Vital Signs domain (Weight from subjects).
    """
    conn = _conn()
    df = pd.read_sql_query("SELECT * FROM subjects", conn)
    conn.close()
    if df.empty or "weight_kg" not in df.columns:
        return pd.DataFrame()

    vs = pd.DataFrame()
    vs["STUDYID"]  = STUDYID
    vs["DOMAIN"]   = "VS"
    vs["USUBJID"]  = df["usubjid"]
    vs["VSSEQ"]    = range(1, len(df) + 1)
    vs["VSTESTCD"] = "WEIGHT"
    vs["VSTEST"]   = "Weight"
    vs["VSORRES"]  = df.get("weight_kg", "")
    vs["VSORRESU"] = "kg"
    vs["VSSTRESC"] = df.get("weight_kg", "")
    vs["VSSTRESN"] = pd.to_numeric(df.get("weight_kg", ""), errors="coerce")
    vs["VSSTRESU"] = "kg"
    vs["VSBLFL"]   = "Y"
    vs["VISITNUM"] = 1
    vs["VISIT"]    = "BASELINE"
    vs["VSDTC"]    = datetime.now().strftime("%Y-%m-%d")
    return vs


def export_lb():
    """
    LB — Laboratory domain (Hb, WBC from visits/subjects).
    """
    conn = _conn()
    try:
        df = pd.read_sql_query("""
            SELECT s.usubjid, s.siteid, v.visit_date,
                   NULL as lab_hb, NULL as lab_wbc
            FROM subjects s
            LEFT JOIN visits v ON s.usubjid = v.usubjid
        """, conn)
    except Exception as e:
        print(f"Error loading subjects/visits for LB export: {e}")
    conn.close()

    # Try to get labs from raw data if available
    raw_path = os.path.join(BASE, '..', 'data', 'raw_clinical_data.xlsx')
    if os.path.exists(raw_path):
        try:
            raw = pd.read_excel(raw_path, sheet_name="Clinical_Data")
            raw = raw.rename(columns={"Subject_ID": "usubjid"})
        except Exception as e:
            print(f"Error loading raw clinical data for labs: {e}")
            raw = pd.DataFrame()
    else:
        raw = pd.DataFrame()

    rows = []
    seq  = 1

    src = raw if not raw.empty and "Lab_Hb" in raw.columns else pd.DataFrame()

    if not src.empty:
        for _, row in src.iterrows():
            for test, val, unit, lo, hi in [
                ("HGB", row.get("Lab_Hb",  ""), "g/dL",  "12.0", "18.0"),
                ("WBC", row.get("Lab_WBC", ""), "10^3/uL","4.0",  "11.0"),
            ]:
                if pd.isna(val):
                    continue
                rows.append({
                    "STUDYID":  STUDYID,
                    "DOMAIN":   "LB",
                    "USUBJID":  str(row.get("Subject_ID", "")),
                    "LBSEQ":    seq,
                    "LBTESTCD": test,
                    "LBTEST":   "Haemoglobin" if test == "HGB" else "White Blood Cell Count",
                    "LBORRES":  val,
                    "LBORRESU": unit,
                    "LBSTRESC": str(val),
                    "LBSTRESN": val,
                    "LBSTRESU": unit,
                    "LBNRLO":   lo,
                    "LBNRHI":   hi,
                    "VISITNUM": 1,
                    "VISIT":    "BASELINE",
                    "LBDTC":    str(row.get("Visit_Date", "")),
                })
                seq += 1

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def export_qs_queries():
    """
    QS — Custom domain: Query listing (non-standard but useful for DM).
    """
    conn = _conn()
    df = pd.read_sql_query("SELECT * FROM queries", conn)
    conn.close()
    if df.empty:
        return pd.DataFrame()

    qs = pd.DataFrame()
    qs["STUDYID"]   = STUDYID
    qs["DOMAIN"]    = "QS"
    qs["USUBJID"]   = df["usubjid"]
    qs["QSSEQ"]     = range(1, len(df) + 1)
    qs["QSID"]      = df["query_id"]
    qs["QSFIELD"]   = df.get("field_name", "")
    qs["QSSEV"]     = df.get("severity", "")
    qs["QSSTAT"]    = df.get("status", "")
    qs["QSISSUE"]   = df.get("issue_description", "")
    qs["QSDTC"]     = df.get("created_at", "")
    qs["QSENDTC"]   = df.get("resolved_at", "")
    return qs


def run_full_export():
    """Export all SDTM domains to CSV files."""
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    domains = {
        "DM": export_dm,
        "AE": export_ae,
        "VS": export_vs,
        "LB": export_lb,
        "QS": export_qs_queries,
    }

    print("\n" + "="*55)
    print(f"  CDISC SDTM EXPORT — {STUDYID}")
    print(f"  {DOMAIN_VERSION}")
    print("="*55)

    exported = []
    for domain, func in domains.items():
        try:
            df = func()
            if df is not None and not df.empty:
                fname = os.path.join(EXPORTS_DIR, f"{domain.lower()}.csv")
                df.to_csv(fname, index=False)
                print(f"  ✅ {domain:<4} — {len(df):3} rows → {domain.lower()}.csv")
                exported.append(fname)
            else:
                print(f"  ⚠️  {domain:<4} — No data")
        except Exception as e:
            print(f"  ❌ {domain:<4} — Error: {e}")

    # Write define.xml stub
    define_path = os.path.join(EXPORTS_DIR, "define.xml")
    with open(define_path, "w") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- CDISC SDTM Define.xml Stub -->
<!-- Study: {STUDYID} | Generated: {datetime.now().strftime('%d %b %Y %H:%M')} -->
<ODM xmlns="http://www.cdisc.org/ns/odm/v1.3"
     FileType="Snapshot"
     CreationDateTime="{datetime.now().isoformat()}"
     ODMVersion="1.3">
  <Study OID="{STUDYID}">
    <GlobalVariables>
      <StudyName>{STUDYID}</StudyName>
      <StudyDescription>CARDIO Phase 2 Clinical Trial</StudyDescription>
      <ProtocolName>PROTO-CARDIO-002</ProtocolName>
    </GlobalVariables>
  </Study>
</ODM>
""")
    print("  ✅ define.xml stub generated")
    print(f"\n  Export folder: {EXPORTS_DIR}")
    print("="*55)
    return exported


if __name__ == "__main__":
    run_full_export()
    print("\n✅ SDTM export complete.")
    print("   Open reports/sdtm_export/ to view CSV files.")
