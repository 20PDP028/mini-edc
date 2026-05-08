"""
medical_coding.py — Feature 9: Medical Coding (MedDRA)
Maps AE terms to MedDRA System Organ Class and Preferred Terms.
Save in: Mini_EDC_Project/python/medical_coding.py
Run with: python medical_coding.py
"""

import sqlite3
import os
import pandas as pd
from datetime import datetime

BASE    = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, '..', 'sql', 'cdm_phase3.db')

# ── Built-in MedDRA dictionary (subset) ──────────────────────
# Format: "raw term": ("MedDRA Preferred Term", "System Organ Class", "MedDRA Code")
MEDDRA_DICT = {
    # Cardiac
    "chest pain":           ("Chest pain",                    "Cardiac disorders",                     "10008479"),
    "chest tightness":      ("Chest discomfort",              "Cardiac disorders",                     "10008469"),
    "palpitations":         ("Palpitations",                  "Cardiac disorders",                     "10033557"),
    "arrhythmia":           ("Arrhythmia",                    "Cardiac disorders",                     "10003119"),
    "heart failure":        ("Cardiac failure",               "Cardiac disorders",                     "10007554"),

    # Gastrointestinal
    "nausea":               ("Nausea",                        "Gastrointestinal disorders",             "10028813"),
    "vomiting":             ("Vomiting",                      "Gastrointestinal disorders",             "10047700"),
    "diarrhoea":            ("Diarrhoea",                     "Gastrointestinal disorders",             "10012735"),
    "diarrhea":             ("Diarrhoea",                     "Gastrointestinal disorders",             "10012735"),
    "abdominal pain":       ("Abdominal pain",                "Gastrointestinal disorders",             "10000081"),
    "constipation":         ("Constipation",                  "Gastrointestinal disorders",             "10010774"),

    # Nervous system
    "headache":             ("Headache",                      "Nervous system disorders",               "10019211"),
    "dizziness":            ("Dizziness",                     "Nervous system disorders",               "10013573"),
    "seizure":              ("Seizure",                       "Nervous system disorders",               "10039906"),
    "tremor":               ("Tremor",                        "Nervous system disorders",               "10044562"),
    "syncope":              ("Syncope",                       "Nervous system disorders",               "10042772"),

    # Respiratory
    "dyspnoea":             ("Dyspnoea",                      "Respiratory, thoracic and mediastinal disorders", "10013968"),
    "dyspnea":              ("Dyspnoea",                      "Respiratory, thoracic and mediastinal disorders", "10013968"),
    "cough":                ("Cough",                         "Respiratory, thoracic and mediastinal disorders", "10011224"),
    "pneumonia":            ("Pneumonia",                     "Infections and infestations",            "10035664"),

    # Blood / haematology
    "anaemia":              ("Anaemia",                       "Blood and lymphatic system disorders",   "10002034"),
    "anemia":               ("Anaemia",                       "Blood and lymphatic system disorders",   "10002034"),
    "thrombocytopenia":     ("Thrombocytopenia",              "Blood and lymphatic system disorders",   "10043554"),
    "neutropenia":          ("Neutropenia",                   "Blood and lymphatic system disorders",   "10029354"),

    # Skin
    "rash":                 ("Rash",                          "Skin and subcutaneous tissue disorders", "10037844"),
    "pruritus":             ("Pruritus",                      "Skin and subcutaneous tissue disorders", "10037087"),
    "urticaria":            ("Urticaria",                     "Skin and subcutaneous tissue disorders", "10046735"),

    # Immune
    "anaphylaxis":          ("Anaphylactic reaction",         "Immune system disorders",               "10002198"),
    "allergic reaction":    ("Hypersensitivity",              "Immune system disorders",               "10020751"),

    # Musculoskeletal
    "arthralgia":           ("Arthralgia",                    "Musculoskeletal and connective tissue disorders", "10003239"),
    "myalgia":              ("Myalgia",                       "Musculoskeletal and connective tissue disorders", "10028411"),
    "back pain":            ("Back pain",                     "Musculoskeletal and connective tissue disorders", "10003988"),

    # General
    "fatigue":              ("Fatigue",                       "General disorders and administration site conditions", "10016256"),
    "fever":                ("Pyrexia",                       "General disorders and administration site conditions", "10037660"),
    "pyrexia":              ("Pyrexia",                       "General disorders and administration site conditions", "10037660"),
    "oedema":               ("Oedema peripheral",             "General disorders and administration site conditions", "10030124"),
    "edema":                ("Oedema peripheral",             "General disorders and administration site conditions", "10030124"),
    "pain":                 ("Pain",                          "General disorders and administration site conditions", "10033371"),

    # Hepatic
    "jaundice":             ("Jaundice",                      "Hepatobiliary disorders",               "10023126"),
    "hepatitis":            ("Hepatitis",                     "Hepatobiliary disorders",               "10019717"),

    # Renal
    "renal failure":        ("Acute kidney injury",           "Renal and urinary disorders",           "10069339"),
    "haematuria":           ("Haematuria",                    "Renal and urinary disorders",           "10018867"),
}


def init_coding_table():
    """Create ae_coding table if not exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ae_coding (
            coding_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            ae_id       INTEGER,
            usubjid     TEXT,
            raw_term    TEXT,
            meddra_pt   TEXT,
            meddra_soc  TEXT,
            meddra_code TEXT,
            match_type  TEXT,
            coded_at    TEXT,
            coded_by    TEXT DEFAULT 'AUTO'
        )
    """)
    conn.commit()
    conn.close()


def fuzzy_match(term: str) -> tuple:
    """
    Try to match a raw AE term to MedDRA dictionary.
    Returns (preferred_term, soc, code, match_type)
    """
    term_lower = term.strip().lower()

    # Exact match
    if term_lower in MEDDRA_DICT:
        pt, soc, code = MEDDRA_DICT[term_lower]
        return pt, soc, code, "Exact"

    # Partial / contains match
    for key, (pt, soc, code) in MEDDRA_DICT.items():
        if key in term_lower or term_lower in key:
            return pt, soc, code, "Partial"

    # Word-level match
    words = term_lower.split()
    for key, (pt, soc, code) in MEDDRA_DICT.items():
        key_words = key.split()
        if any(w in key_words for w in words if len(w) > 3):
            return pt, soc, code, "Fuzzy"

    return "UNCODED", "UNCODED", "00000000", "No Match"


def code_all_adverse_events():
    """
    Read all AEs from DB and auto-code them to MedDRA.
    Returns DataFrame of coding results.
    """
    init_coding_table()
    conn = sqlite3.connect(DB_PATH)

    aes = conn.execute(
        "SELECT ae_id, usubjid, aeterm FROM adverse_events"
    ).fetchall()

    results = []
    coded = 0
    uncoded = 0

    for ae_id, usubjid, aeterm in aes:
        if not aeterm or str(aeterm).strip().lower() == "nan":
            continue

        pt, soc, code, match_type = fuzzy_match(str(aeterm))

        # Insert/replace coding
        conn.execute("""
            INSERT OR REPLACE INTO ae_coding
            (ae_id, usubjid, raw_term, meddra_pt, meddra_soc, meddra_code, match_type, coded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ae_id, usubjid, aeterm, pt, soc, code, match_type, datetime.now().isoformat()))

        results.append({
            "AE ID":       ae_id,
            "Subject":     usubjid,
            "Raw Term":    aeterm,
            "MedDRA PT":   pt,
            "SOC":         soc,
            "Code":        code,
            "Match Type":  match_type,
        })

        if match_type != "No Match":
            coded += 1
        else:
            uncoded += 1

    conn.commit()
    conn.close()
    return pd.DataFrame(results), coded, uncoded


def get_soc_summary():
    """Returns count of AEs per System Organ Class."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("""
            SELECT meddra_soc as SOC, COUNT(*) as Count
            FROM ae_coding
            WHERE meddra_soc != 'UNCODED'
            GROUP BY meddra_soc
            ORDER BY Count DESC
        """, conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df


def print_coding_report():
    """Print MedDRA coding summary to console."""
    df, coded, uncoded = code_all_adverse_events()
    total = coded + uncoded

    print("\n" + "="*65)
    print("  MEDICAL CODING REPORT — MedDRA")
    print("="*65)
    print(f"  Total AEs Processed : {total}")
    print(f"  Successfully Coded  : {coded}  ({round(coded/total*100,1) if total else 0}%)")
    print(f"  Uncoded (Review)    : {uncoded}")

    if not df.empty:
        print("\n  Coding Results:")
        print(f"  {'Raw Term':<20} {'MedDRA PT':<30} {'Match':<10}")
        print("  " + "-"*60)
        for _, row in df.iterrows():
            status = "✅" if row["Match Type"] != "No Match" else "❌"
            print(f"  {status} {row['Raw Term']:<18} {row['MedDRA PT']:<30} {row['Match Type']}")

    soc_df = get_soc_summary()
    if not soc_df.empty:
        print("\n  AEs by System Organ Class:")
        for _, row in soc_df.iterrows():
            print(f"  {'█' * row['Count']:<15} {row['Count']:2}  {row['SOC']}")
    print()


if __name__ == "__main__":
    print_coding_report()
