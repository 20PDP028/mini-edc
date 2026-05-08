"""
Phase B: SDTM Dataset Generator
- Generates real CDISC SDTM v1.8 compliant datasets
- Produces SAS Transport (XPT) compatible CSV + metadata
- Creates define.xml (CDISC Define-XML 2.0) for FDA submission
- Includes dataset-level conformance checks
"""

import json
import csv
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import Optional
from io import StringIO


# ─── SDTM Domain Metadata ─────────────────────────────────────────────────────

SDTM_DOMAINS = {
    "DM": {
        "label": "Demographics",
        "class": "Special Purpose",
        "variables": [
            ("STUDYID",  "Char", "Study Identifier",              True),
            ("DOMAIN",   "Char", "Domain Abbreviation",           True),
            ("USUBJID",  "Char", "Unique Subject Identifier",     True),
            ("SUBJID",   "Char", "Subject Identifier for Study",  True),
            ("RFSTDTC",  "Char", "Subject Reference Start Date",  True),
            ("RFENDTC",  "Char", "Subject Reference End Date",    False),
            ("RFXSTDTC", "Char", "Date/Time of First Study Treatment", False),
            ("RFICDTC",  "Char", "Date/Time of Informed Consent", False),
            ("SITEID",   "Char", "Study Site Identifier",         True),
            ("BRTHDTC",  "Char", "Date/Time of Birth",            False),
            ("AGE",      "Num",  "Age",                           False),
            ("AGEU",     "Char", "Age Units",                     False),
            ("SEX",      "Char", "Sex",                           True),
            ("RACE",     "Char", "Race",                          False),
            ("ETHNIC",   "Char", "Ethnicity",                     False),
            ("COUNTRY",  "Char", "Country",                       True),
            ("ARM",      "Char", "Description of Planned Arm",    False),
            ("ARMCD",    "Char", "Planned Arm Code",              False),
            ("ACTARM",   "Char", "Description of Actual Arm",     False),
            ("DTHDTC",   "Char", "Date/Time of Death",            False),
            ("DTHFL",    "Char", "Subject Death Flag",            False),
        ]
    },
    "AE": {
        "label": "Adverse Events",
        "class": "Events",
        "variables": [
            ("STUDYID",  "Char", "Study Identifier",              True),
            ("DOMAIN",   "Char", "Domain Abbreviation",           True),
            ("USUBJID",  "Char", "Unique Subject Identifier",     True),
            ("AESEQ",    "Num",  "Sequence Number",               True),
            ("AEGRPID",  "Char", "Group ID",                      False),
            ("AETERM",   "Char", "Reported Term for AE",          True),
            ("AELLT",    "Char", "Lowest Level Term",             False),
            ("AELLTCD",  "Num",  "Lowest Level Term Code",        False),
            ("AEDECOD",  "Char", "Dictionary-Derived Term",       False),
            ("AEPTCD",   "Num",  "Preferred Term Code",           False),
            ("AEHLT",    "Char", "High Level Term",               False),
            ("AEHLTCD",  "Num",  "High Level Term Code",          False),
            ("AEHLGT",   "Char", "High Level Group Term",         False),
            ("AEHLGTCD", "Num",  "High Level Group Term Code",    False),
            ("AEBODSYS",  "Char", "Body System or Organ Class",   False),
            ("AEBDSYCD",  "Num",  "Body System Code",             False),
            ("AESOC",    "Char", "Primary System Organ Class",    False),
            ("AESOCCD",  "Num",  "Primary SOC Code",              False),
            ("AESTDTC",  "Char", "Start Date/Time of AE",         True),
            ("AEENDTC",  "Char", "End Date/Time of AE",           False),
            ("AESTDY",   "Num",  "Study Day of Start of AE",      False),
            ("AEENDY",   "Num",  "Study Day of End of AE",        False),
            ("AEDUR",    "Char", "Duration of AE",                False),
            ("AEENRF",   "Char", "End Relative to Ref Period",    False),
            ("AESEV",    "Char", "Severity/Intensity",            True),
            ("AESER",    "Char", "Serious Event",                 True),
            ("AEACN",    "Char", "Action Taken with Study Treatment", False),
            ("AEREL",    "Char", "Causality",                     False),
            ("AEOUT",    "Char", "Outcome of AE",                 False),
            ("AESCAN",   "Char", "Involves Cancer",               False),
            ("AESCONG",  "Char", "Congenital Anomaly/Birth Defect", False),
            ("AESDTH",   "Char", "Results in Death",              False),
            ("AESHOSP",  "Char", "Requires/Prolongs Hospitalization", False),
            ("AESDISAB", "Char", "Persist/Sig Disability/Incapacity", False),
            ("AESLIFE",  "Char", "Life Threatening",              False),
            ("AESMIE",   "Char", "Other Medically Important Event", False),
            ("AETOXGR",  "Char", "Standard Toxicity Grade",       False),
            ("VISIT",    "Char", "Visit Name",                    False),
            ("VISITNUM", "Num",  "Visit Number",                  False),
            ("EPOCH",    "Char", "Epoch",                         False),
        ]
    },
    "VS": {
        "label": "Vital Signs",
        "class": "Findings",
        "variables": [
            ("STUDYID",  "Char", "Study Identifier",              True),
            ("DOMAIN",   "Char", "Domain Abbreviation",           True),
            ("USUBJID",  "Char", "Unique Subject Identifier",     True),
            ("VSSEQ",    "Num",  "Sequence Number",               True),
            ("VSTESTCD", "Char", "Vital Signs Test Short Name",   True),
            ("VSTEST",   "Char", "Vital Signs Test Name",         True),
            ("VSPOS",    "Char", "Vital Signs Position of Subject", False),
            ("VSORRES",  "Char", "Result or Finding in Original Units", True),
            ("VSORRESU", "Char", "Original Units",                True),
            ("VSSTRESC", "Char", "Character Result/Finding in Std Format", False),
            ("VSSTRESN", "Num",  "Numeric Result/Finding in Standard Units", False),
            ("VSSTRESU", "Char", "Standard Units",                False),
            ("VSNRIND",  "Char", "Reference Range Indicator",     False),
            ("VSBLFL",   "Char", "Baseline Flag",                 False),
            ("VSDRVFL",  "Char", "Derived Flag",                  False),
            ("VISITNUM", "Num",  "Visit Number",                  False),
            ("VISIT",    "Char", "Visit Name",                    False),
            ("VSDTC",    "Char", "Date/Time of Measurements",     True),
            ("VSDY",     "Num",  "Study Day of Vital Signs",      False),
        ]
    },
    "LB": {
        "label": "Laboratory Test Results",
        "class": "Findings",
        "variables": [
            ("STUDYID",  "Char", "Study Identifier",              True),
            ("DOMAIN",   "Char", "Domain Abbreviation",           True),
            ("USUBJID",  "Char", "Unique Subject Identifier",     True),
            ("LBSEQ",    "Num",  "Sequence Number",               True),
            ("LBTESTCD", "Char", "Lab Test or Examination Short Name", True),
            ("LBTEST",   "Char", "Lab Test or Examination Name",  True),
            ("LBCAT",    "Char", "Category for Lab Test",         False),
            ("LBORRES",  "Char", "Result or Finding in Original Units", True),
            ("LBORRESU", "Char", "Original Units",                False),
            ("LBSTRESC", "Char", "Character Result in Standard Format", False),
            ("LBSTRESN", "Num",  "Numeric Result in Standard Units", False),
            ("LBSTRESU", "Char", "Standard Units",                False),
            ("LBNRLO",   "Num",  "Reference Range Lower Limit",   False),
            ("LBNRHI",   "Num",  "Reference Range Upper Limit",   False),
            ("LBNRIND",  "Char", "Reference Range Indicator",     False),
            ("LBBLFL",   "Char", "Baseline Flag",                 False),
            ("VISITNUM", "Num",  "Visit Number",                  False),
            ("VISIT",    "Char", "Visit Name",                    False),
            ("LBDTC",    "Char", "Date/Time of Specimen Collection", True),
            ("LBDY",     "Num",  "Study Day of Lab Test",         False),
        ]
    },
    "EX": {
        "label": "Exposure",
        "class": "Interventions",
        "variables": [
            ("STUDYID",  "Char", "Study Identifier",              True),
            ("DOMAIN",   "Char", "Domain Abbreviation",           True),
            ("USUBJID",  "Char", "Unique Subject Identifier",     True),
            ("EXSEQ",    "Num",  "Sequence Number",               True),
            ("EXTRT",    "Char", "Name of Treatment",             True),
            ("EXDOSE",   "Num",  "Dose",                          True),
            ("EXDOSU",   "Char", "Dose Units",                    True),
            ("EXDOSFRM", "Char", "Dose Form",                     False),
            ("EXDOSFRQ", "Char", "Dosing Frequency per Interval", True),
            ("EXROUTE",  "Char", "Route of Administration",       False),
            ("EXSTDTC",  "Char", "Start Date/Time of Treatment",  True),
            ("EXENDTC",  "Char", "End Date/Time of Treatment",    True),
            ("EXSTDY",   "Num",  "Study Day of Start of Treatment", False),
            ("EXENDY",   "Num",  "Study Day of End of Treatment",  False),
            ("VISIT",    "Char", "Visit Name",                    False),
            ("VISITNUM", "Num",  "Visit Number",                  False),
            ("EPOCH",    "Char", "Epoch",                         False),
        ]
    },
}

VS_TEST_NAMES = {
    "SYSBP":  "Systolic Blood Pressure",
    "DIABP":  "Diastolic Blood Pressure",
    "PULSE":  "Pulse Rate",
    "TEMP":   "Temperature",
    "WEIGHT": "Weight",
    "HEIGHT": "Height",
    "BMI":    "Body Mass Index",
    "RESP":   "Respiratory Rate",
    "OXYSAT": "Oxygen Saturation",
}

LB_TEST_NAMES = {
    "ALT":      "Alanine Aminotransferase",
    "AST":      "Aspartate Aminotransferase",
    "BILI":     "Bilirubin",
    "CREAT":    "Creatinine",
    "GGT":      "Gamma Glutamyl Transferase",
    "HGB":      "Hemoglobin",
    "WBC":      "White Blood Cell Count",
    "PLT":      "Platelet Count",
    "SODIUM":   "Sodium",
    "POTASSIUM":"Potassium",
    "GLUCOSE":  "Glucose",
    "ALBUMIN":  "Albumin",
    "ALKPH":    "Alkaline Phosphatase",
    "BUN":      "Blood Urea Nitrogen",
    "CHOL":     "Cholesterol",
    "TRIG":     "Triglycerides",
}

VISIT_NUMBERS = {
    "SCREENING": 1, "BASELINE": 2, "WEEK 1": 3, "WEEK 2": 4,
    "WEEK 4": 5, "WEEK 8": 6, "WEEK 12": 7,
    "END OF TREATMENT": 8, "FOLLOW-UP": 9,
}


# ─── SDTM Generator ───────────────────────────────────────────────────────────

class SDTMGenerator:
    """
    Transforms raw EDC data into SDTM v1.8 compliant datasets.
    """

    def __init__(self, study_id: str, output_dir: str):
        self.study_id   = study_id
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.generated_datasets: list[dict] = []

    @staticmethod
    def _study_day(ref_start: str, event_date: str) -> Optional[int]:
        """Calculate SDTM study day (Day 1 = reference start date)."""
        if not ref_start or not event_date:
            return None
        try:
            ref  = datetime.strptime(ref_start[:10], "%Y-%m-%d").date()
            evt  = datetime.strptime(event_date[:10], "%Y-%m-%d").date()
            delta = (evt - ref).days
            return delta + 1 if delta >= 0 else delta
        except ValueError:
            return None

    @staticmethod
    def _iso_duration(start: str, end: str) -> Optional[str]:
        """Return ISO 8601 duration string P#DT format."""
        try:
            s = datetime.strptime(start[:10], "%Y-%m-%d").date()
            e = datetime.strptime(end[:10], "%Y-%m-%d").date()
            days = (e - s).days
            return f"P{days}D"
        except (ValueError, TypeError):
            return None

    def _write_csv(self, domain: str, rows: list[dict]) -> str:
        """Write dataset as CSV with SDTM column order."""
        if not rows:
            return ""
        variables = SDTM_DOMAINS.get(domain, {}).get("variables", [])
        col_order  = [v[0] for v in variables]
        # Include any extra columns not in metadata (shouldn't happen, but safe)
        all_keys   = col_order + [k for k in rows[0].keys() if k not in col_order]

        filepath = os.path.join(self.output_dir, f"{domain.lower()}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        self.generated_datasets.append({
            "domain":    domain,
            "label":     SDTM_DOMAINS.get(domain, {}).get("label", domain),
            "class":     SDTM_DOMAINS.get(domain, {}).get("class", ""),
            "filepath":  filepath,
            "n_records": len(rows),
            "variables": variables,
        })
        return filepath

    # ── DM ────────────────────────────────────────────────────────────────────

    def generate_dm(self, raw_dm: list[dict]) -> list[dict]:
        rows = []
        for rec in raw_dm:
            sid = rec.get("USUBJID", "")
            arm = rec.get("ARM", "")
            armcd = "TRT-A" if "TREATMENT A" in arm.upper() else \
                    "PBO"   if "PLACEBO"     in arm.upper() else "UNK"
            rows.append({
                "STUDYID":  self.study_id,
                "DOMAIN":   "DM",
                "USUBJID":  sid,
                "SUBJID":   sid.split("-")[-1] if "-" in sid else sid,
                "RFSTDTC":  rec.get("RFSTDTC", ""),
                "RFENDTC":  rec.get("RFENDTC", ""),
                "RFXSTDTC": rec.get("RFSTDTC", ""),   # first treatment = ref start
                "RFICDTC":  rec.get("RFICDTC", ""),
                "SITEID":   rec.get("SITEID", ""),
                "BRTHDTC":  rec.get("BRTHDTC", ""),
                "AGE":      rec.get("AGE", ""),
                "AGEU":     "YEARS",
                "SEX":      rec.get("SEX", ""),
                "RACE":     rec.get("RACE", ""),
                "ETHNIC":   rec.get("ETHNIC", ""),
                "COUNTRY":  rec.get("COUNTRY", ""),
                "ARM":      arm,
                "ARMCD":    armcd,
                "ACTARM":   arm,
                "DTHFL":    "",
                "DTHDTC":   "",
            })
        self._write_csv("DM", rows)
        return rows

    # ── AE ────────────────────────────────────────────────────────────────────

    def generate_ae(self, raw_ae: list[dict], dm_rows: list[dict]) -> list[dict]:
        dm_map = {r["USUBJID"]: r for r in dm_rows}
        rows   = []
        for rec in raw_ae:
            sid     = rec.get("USUBJID", "")
            dm      = dm_map.get(sid, {})
            ref_strt = dm.get("RFSTDTC", "")
            ae_start = rec.get("AESTDTC", "")
            ae_end   = rec.get("AEENDTC", "")
            visit    = rec.get("VISIT", "")
            rows.append({
                "STUDYID":  self.study_id,
                "DOMAIN":   "AE",
                "USUBJID":  sid,
                "AESEQ":    rec.get("AESEQ", ""),
                "AEGRPID":  "",
                "AETERM":   rec.get("AETERM", ""),
                "AELLT":    rec.get("AELLT", ""),
                "AELLTCD":  rec.get("AELLTCD", ""),
                "AEDECOD":  rec.get("AEDECOD", rec.get("AETERM", "")),
                "AEPTCD":   rec.get("AEPTCD", ""),
                "AEHLT":    rec.get("AEHLT", ""),
                "AEHLTCD":  rec.get("AEHLTCD", ""),
                "AEHLGT":   rec.get("AEHLGT", ""),
                "AEHLGTCD": rec.get("AEHLGTCD", ""),
                "AEBODSYS": rec.get("AEBODSYS", ""),
                "AEBDSYCD": rec.get("AEBDSYCD", ""),
                "AESOC":    rec.get("AESOC", rec.get("AEBODSYS", "")),
                "AESOCCD":  rec.get("AESOCCD", ""),
                "AESTDTC":  ae_start,
                "AEENDTC":  ae_end,
                "AESTDY":   self._study_day(ref_strt, ae_start),
                "AEENDY":   self._study_day(ref_strt, ae_end),
                "AEDUR":    self._iso_duration(ae_start, ae_end),
                "AEENRF":   "",
                "AESEV":    rec.get("AESEV", ""),
                "AESER":    rec.get("AESER", "N"),
                "AEACN":    rec.get("AEACN", ""),
                "AEREL":    rec.get("AEREL", ""),
                "AEOUT":    rec.get("AEOUT", ""),
                "AESCAN":   rec.get("AESCAN", ""),
                "AESCONG":  rec.get("AESCONG", ""),
                "AESDTH":   rec.get("AESDTH", "N"),
                "AESHOSP":  rec.get("AESHOSP", "N"),
                "AESDISAB": rec.get("AESDISAB", "N"),
                "AESLIFE":  rec.get("AESLIFE", "N"),
                "AESMIE":   rec.get("AESMIE", "N"),
                "AETOXGR":  rec.get("AETOXGR", ""),
                "VISIT":    visit,
                "VISITNUM": VISIT_NUMBERS.get(visit.upper(), ""),
                "EPOCH":    "TREATMENT",
            })
        self._write_csv("AE", rows)
        return rows

    # ── VS ────────────────────────────────────────────────────────────────────

    def generate_vs(self, raw_vs: list[dict], dm_rows: list[dict]) -> list[dict]:
        dm_map = {r["USUBJID"]: r for r in dm_rows}
        rows   = []
        for rec in raw_vs:
            sid      = rec.get("USUBJID", "")
            dm       = dm_map.get(sid, {})
            ref_strt = dm.get("RFSTDTC", "")
            testcd   = str(rec.get("VSTESTCD", "")).upper()
            visit    = str(rec.get("VISIT", "")).upper()
            vsdtc    = rec.get("VSDTC", "")
            orres    = rec.get("VSORRES", "")
            try:
                stresn = float(str(orres).replace(",", "."))
                stresc = str(stresn)
            except (ValueError, TypeError):
                stresn = ""
                stresc = str(orres)
            rows.append({
                "STUDYID":  self.study_id,
                "DOMAIN":   "VS",
                "USUBJID":  sid,
                "VSSEQ":    rec.get("VSSEQ", ""),
                "VSTESTCD": testcd,
                "VSTEST":   VS_TEST_NAMES.get(testcd, testcd),
                "VSPOS":    rec.get("VSPOS", ""),
                "VSORRES":  orres,
                "VSORRESU": rec.get("VSORRESU", ""),
                "VSSTRESC": stresc,
                "VSSTRESN": stresn,
                "VSSTRESU": rec.get("VSORRESU", ""),
                "VSNRIND":  "",
                "VSBLFL":   "Y" if visit == "BASELINE" else "",
                "VSDRVFL":  "",
                "VISITNUM": VISIT_NUMBERS.get(visit, ""),
                "VISIT":    visit,
                "VSDTC":    vsdtc,
                "VSDY":     self._study_day(ref_strt, vsdtc),
            })
        self._write_csv("VS", rows)
        return rows

    # ── LB ────────────────────────────────────────────────────────────────────

    def generate_lb(self, raw_lb: list[dict], dm_rows: list[dict]) -> list[dict]:
        dm_map = {r["USUBJID"]: r for r in dm_rows}
        rows   = []
        for rec in raw_lb:
            sid      = rec.get("USUBJID", "")
            dm       = dm_map.get(sid, {})
            ref_strt = dm.get("RFSTDTC", "")
            testcd   = str(rec.get("LBTESTCD", "")).upper()
            visit    = str(rec.get("VISIT", "")).upper()
            lbdtc    = rec.get("LBDTC", "")
            orres    = rec.get("LBORRES", "")
            try:
                stresn = float(str(orres).replace(",", "."))
                stresc = str(stresn)
            except (ValueError, TypeError):
                stresn = ""
                stresc = str(orres)
            rows.append({
                "STUDYID":  self.study_id,
                "DOMAIN":   "LB",
                "USUBJID":  sid,
                "LBSEQ":    rec.get("LBSEQ", ""),
                "LBTESTCD": testcd,
                "LBTEST":   LB_TEST_NAMES.get(testcd, testcd),
                "LBCAT":    "CHEMISTRY" if testcd in
                            {"ALT","AST","BILI","CREAT","GGT","ALBUMIN","ALKPH","BUN","CHOL","TRIG","SODIUM","POTASSIUM","GLUCOSE"}
                            else "HEMATOLOGY",
                "LBORRES":  orres,
                "LBORRESU": rec.get("LBSTRESU", ""),
                "LBSTRESC": stresc,
                "LBSTRESN": stresn,
                "LBSTRESU": rec.get("LBSTRESU", ""),
                "LBNRLO":   rec.get("LBSTNRLO", ""),
                "LBNRHI":   rec.get("LBSTNRHI", ""),
                "LBNRIND":  rec.get("LBNRIND", ""),
                "LBBLFL":   "Y" if visit == "BASELINE" else "",
                "VISITNUM": VISIT_NUMBERS.get(visit, ""),
                "VISIT":    visit,
                "LBDTC":    lbdtc,
                "LBDY":     self._study_day(ref_strt, lbdtc),
            })
        self._write_csv("LB", rows)
        return rows

    # ── EX ────────────────────────────────────────────────────────────────────

    def generate_ex(self, raw_ex: list[dict], dm_rows: list[dict]) -> list[dict]:
        dm_map = {r["USUBJID"]: r for r in dm_rows}
        rows   = []
        for rec in raw_ex:
            sid      = rec.get("USUBJID", "")
            dm       = dm_map.get(sid, {})
            ref_strt = dm.get("RFSTDTC", "")
            exstdtc  = rec.get("EXSTDTC", "")
            exendtc  = rec.get("EXENDTC", "")
            visit    = rec.get("VISIT", "")
            rows.append({
                "STUDYID":  self.study_id,
                "DOMAIN":   "EX",
                "USUBJID":  sid,
                "EXSEQ":    rec.get("EXSEQ", ""),
                "EXTRT":    rec.get("EXTRT", ""),
                "EXDOSE":   rec.get("EXDOSE", ""),
                "EXDOSU":   rec.get("EXDOSU", "mg"),
                "EXDOSFRM": rec.get("EXDOSFRM", "TABLET"),
                "EXDOSFRQ": rec.get("EXDOSFRQ", ""),
                "EXROUTE":  rec.get("EXROUTE", "ORAL"),
                "EXSTDTC":  exstdtc,
                "EXENDTC":  exendtc,
                "EXSTDY":   self._study_day(ref_strt, exstdtc),
                "EXENDY":   self._study_day(ref_strt, exendtc),
                "VISIT":    visit,
                "VISITNUM": VISIT_NUMBERS.get(str(visit).upper(), ""),
                "EPOCH":    "TREATMENT",
            })
        self._write_csv("EX", rows)
        return rows

    # ── Run All ───────────────────────────────────────────────────────────────

    def run_all(self, raw_data: dict) -> dict:
        dm_rows = self.generate_dm(raw_data.get("DM", []))
        ae_rows = self.generate_ae(raw_data.get("AE", []), dm_rows)
        vs_rows = self.generate_vs(raw_data.get("VS", []), dm_rows)
        lb_rows = self.generate_lb(raw_data.get("LB", []), dm_rows)
        ex_rows = self.generate_ex(raw_data.get("EX", []), dm_rows)
        return {
            "DM": dm_rows, "AE": ae_rows,
            "VS": vs_rows, "LB": lb_rows, "EX": ex_rows,
        }


# ─── Define-XML 2.0 Generator ─────────────────────────────────────────────────

class DefineXMLGenerator:
    """
    Generates CDISC Define-XML 2.0 metadata file for FDA submission.
    This is the 'data dictionary' that accompanies SDTM datasets.
    """

    DEF_NS   = "http://www.cdisc.org/ns/def/v2.0"
    XLINK_NS = "http://www.w3.org/1999/xlink"
    ODM_NS   = "http://www.cdisc.org/ns/odm/v1.3"

    def __init__(self, study_id: str, datasets: list[dict]):
        self.study_id = study_id
        self.datasets = datasets

    def generate(self, output_path: str) -> str:
        ET.register_namespace("",      self.ODM_NS)
        ET.register_namespace("def",   self.DEF_NS)
        ET.register_namespace("xlink", self.XLINK_NS)

        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<ODM xmlns="http://www.cdisc.org/ns/odm/v1.3"',
            f'     xmlns:def="http://www.cdisc.org/ns/def/v2.0"',
            f'     xmlns:xlink="http://www.w3.org/1999/xlink"',
            f'     FileType="Snapshot" FileOID="{self.study_id}.define"',
            f'     CreationDateTime="{now}" AsOfDateTime="{now}"',
            f'     ODMVersion="1.3.2">',
            f'  <Study OID="{self.study_id}">',
            f'    <GlobalVariables>',
            f'      <StudyName>{self.study_id}</StudyName>',
            f'      <StudyDescription>Clinical Study {self.study_id}</StudyDescription>',
            f'      <ProtocolName>{self.study_id}</ProtocolName>',
            f'    </GlobalVariables>',
            f'    <MetaDataVersion OID="{self.study_id}.MDV" Name="SDTM Metadata"',
            f'      def:DefineVersion="2.0.0" def:StandardName="SDTM" def:StandardVersion="1.8">',
        ]

        # Dataset leaves
        for ds in self.datasets:
            domain = ds["domain"]
            lines.append(
                f'      <def:leaf ID="LF.{domain}" xlink:type="simple" '
                f'xlink:href="{domain.lower()}.csv">'
            )
            lines.append(f'        <def:title>{domain} — {ds["label"]}</def:title>')
            lines.append(f'      </def:leaf>')

        # ItemGroupDefs
        for ds in self.datasets:
            domain    = ds["domain"]
            ds_class  = SDTM_DOMAINS.get(domain, {}).get("class", "")
            repeating = "No" if domain == "DM" else "Yes"
            lines += [
                f'      <ItemGroupDef OID="IG.{domain}" Name="{domain}"',
                f'        Repeating="{repeating}" IsReferenceData="No"',
                f'        SASDatasetName="{domain}"',
                f'        def:Structure="{ds_class}" def:Class="{ds_class}"',
                f'        def:Purpose="Tabulation" def:ArchiveLocationID="LF.{domain}">',
                f'        <Description>{ds["label"]}</Description>',
            ]
            for idx, (var_name, var_type, var_label, required) in enumerate(ds["variables"], 1):
                lines.append(
                    f'        <ItemRef ItemOID="IT.{domain}.{var_name}" '
                    f'Mandatory="{"Yes" if required else "No"}" OrderNumber="{idx}"/>'
                )
            lines.append(f'      </ItemGroupDef>')

        # ItemDefs
        for ds in self.datasets:
            domain = ds["domain"]
            for var_name, var_type, var_label, required in ds["variables"]:
                dtype  = "float" if var_type == "Num" else "text"
                length = '' if var_type == "Num" else ' Length="200"'
                lines += [
                    f'      <ItemDef OID="IT.{domain}.{var_name}" Name="{var_name}"',
                    f'        DataType="{dtype}"{length} SASFieldName="{var_name}"',
                    f'        def:Label="{var_label}">',
                    f'        <Description>',
                    f'          <TranslatedText xml:lang="en">{var_label}</TranslatedText>',
                    f'        </Description>',
                    f'      </ItemDef>',
                ]

        lines += [
            '    </MetaDataVersion>',
            '  </Study>',
            '</ODM>',
        ]

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return output_path


# ─── Conformance Checker ──────────────────────────────────────────────────────

class SDTMConformanceChecker:
    """
    Dataset-level SDTM conformance checks (beyond record-level validation).
    """

    def __init__(self, datasets: dict):
        self.datasets = datasets
        self.issues   = []

    def _issue(self, domain, check_id, message, severity="WARNING"):
        self.issues.append({
            "domain": domain, "check_id": check_id,
            "message": message, "severity": severity,
        })

    def check_dm(self):
        dm = self.datasets.get("DM", [])
        if not dm:
            self._issue("DM", "CONF-DM01", "DM dataset is empty", "ERROR")
            return
        # Every subject in other datasets must exist in DM
        dm_subjects = {r.get("USUBJID") for r in dm}
        for domain in ["AE", "VS", "LB", "EX"]:
            for rec in self.datasets.get(domain, []):
                sid = rec.get("USUBJID")
                if sid and sid not in dm_subjects:
                    self._issue(domain, "CONF-REF01",
                                f"USUBJID '{sid}' in {domain} not found in DM", "ERROR")

    def check_sequences(self):
        for domain in ["AE", "VS", "LB", "EX"]:
            seq_field = f"{domain}SEQ"
            seen = {}
            for rec in self.datasets.get(domain, []):
                sid = rec.get("USUBJID")
                seq = rec.get(seq_field)
                key = (sid, seq)
                if key in seen:
                    self._issue(domain, "CONF-SEQ01",
                                f"Duplicate {seq_field}={seq} for subject {sid}", "ERROR")
                if seq:
                    seen[key] = True

    def check_studyid(self):
        for domain, rows in self.datasets.items():
            for rec in rows:
                if rec.get("STUDYID", "") == "":
                    self._issue(domain, "CONF-STDY01",
                                f"STUDYID missing in {domain} record", "ERROR")

    def check_domain_variable(self):
        for domain, rows in self.datasets.items():
            for rec in rows:
                if rec.get("DOMAIN", "") != domain:
                    self._issue(domain, "CONF-DOM01",
                                f"DOMAIN value '{rec.get('DOMAIN')}' does not match dataset '{domain}'",
                                "ERROR")

    def check_required_variables(self):
        for ds_meta in SDTM_DOMAINS.values():
            domain = None
            for d, m in SDTM_DOMAINS.items():
                if m is ds_meta:
                    domain = d
                    break
            if not domain:
                continue
            required_vars = [v[0] for v in ds_meta["variables"] if v[3]]
            for rec in self.datasets.get(domain, []):
                for var in required_vars:
                    val = rec.get(var)
                    if val is None or str(val).strip() == "":
                        self._issue(domain, "CONF-REQ01",
                                    f"Required variable {var} is empty for subject {rec.get('USUBJID')}",
                                    "WARNING")

    def run_all(self) -> list[dict]:
        self.issues = []
        self.check_dm()
        self.check_sequences()
        self.check_studyid()
        self.check_domain_variable()
        self.check_required_variables()
        return self.issues

    def summary(self) -> dict:
        errors   = [i for i in self.issues if i["severity"] == "ERROR"]
        warnings = [i for i in self.issues if i["severity"] == "WARNING"]
        return {
            "total": len(self.issues),
            "errors": len(errors),
            "warnings": len(warnings),
            "submission_ready": len(errors) == 0,
        }


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from cdisc_validation_engine import SAMPLE_DATA

    STUDY_ID   = "STUDY001"
    OUTPUT_DIR = "/home/claude/Mini_EDC_Project/reports/sdtm"

    print("\n" + "="*60)
    print("  Phase B: SDTM Dataset Generation")
    print("="*60)

    # Step 1: Generate SDTM datasets
    gen = SDTMGenerator(STUDY_ID, OUTPUT_DIR)
    datasets = gen.run_all(SAMPLE_DATA)

    print(f"\n✅ Generated {len(gen.generated_datasets)} SDTM datasets:")
    for ds in gen.generated_datasets:
        print(f"   {ds['domain']:4s} — {ds['label']:35s} ({ds['n_records']} records) → {os.path.basename(ds['filepath'])}")

    # Step 2: Generate define.xml
    define_path = os.path.join(OUTPUT_DIR, "define.xml")
    defgen = DefineXMLGenerator(STUDY_ID, gen.generated_datasets)
    defgen.generate(define_path)
    print(f"\n✅ define.xml generated → {define_path}")

    # Step 3: Conformance checks
    checker = SDTMConformanceChecker(datasets)
    issues  = checker.run_all()
    summary = checker.summary()

    print(f"\n{'='*60}")
    print(f"  SDTM Conformance Check Results")
    print(f"{'='*60}")
    print(f"  Total issues  : {summary['total']}")
    print(f"  Errors        : {summary['errors']}")
    print(f"  Warnings      : {summary['warnings']}")
    print(f"  Submission OK : {summary['submission_ready']}")
    print(f"{'='*60}\n")

    for issue in issues:
        icon = "🔴" if issue["severity"] == "ERROR" else "🟡"
        print(f"{icon} [{issue['check_id']}] {issue['domain']} | {issue['message']}")

    # Save conformance report
    report = {
        "study_id":   STUDY_ID,
        "generated":  datetime.utcnow().isoformat() + "Z",
        "datasets":   [{k: v for k, v in ds.items() if k != "variables"}
                       for ds in gen.generated_datasets],
        "conformance_summary": summary,
        "conformance_issues":  issues,
    }
    report_path = os.path.join(OUTPUT_DIR, "sdtm_conformance_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n✅ Conformance report saved → {report_path}")

    print(f"\n📁 Output folder: {OUTPUT_DIR}")
    print("   ├── dm.csv")
    print("   ├── ae.csv")
    print("   ├── vs.csv")
    print("   ├── lb.csv")
    print("   ├── ex.csv")
    print("   ├── define.xml")
    print("   └── sdtm_conformance_report.json")
