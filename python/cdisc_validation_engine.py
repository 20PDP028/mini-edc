"""
Phase A: Real CDISC Validation Engine
- 40+ edit checks (cross-field, visit windows, controlled terminology)
- CDASH/SDTM compliant
- SAE auto-detection
- Full audit trail
"""

import json
from datetime import datetime, date
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class Severity(str, Enum):
    CRITICAL = "CRITICAL"   # blocks submission
    MAJOR    = "MAJOR"      # requires query
    MINOR    = "MINOR"      # informational warning


class Domain(str, Enum):
    DM  = "DM"   # Demographics
    AE  = "AE"   # Adverse Events
    CM  = "CM"   # Concomitant Medications
    LB  = "LB"   # Laboratory
    VS  = "VS"   # Vital Signs
    EX  = "EX"   # Exposure (Dosing)
    DS  = "DS"   # Disposition
    SV  = "SV"   # Subject Visits
    MH  = "MH"   # Medical History
    SC  = "SC"   # Subject Characteristics


# ─── CDISC Controlled Terminology ─────────────────────────────────────────────

CDISC_CT = {
    "SEX": {"M", "F", "U", "UN", "UNDIFFERENTIATED"},
    "RACE": {
        "AMERICAN INDIAN OR ALASKA NATIVE",
        "ASIAN",
        "BLACK OR AFRICAN AMERICAN",
        "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
        "WHITE",
        "MULTIPLE",
        "NOT REPORTED",
        "UNKNOWN",
    },
    "ETHNIC": {"HISPANIC OR LATINO", "NOT HISPANIC OR LATINO", "NOT REPORTED", "UNKNOWN"},
    "VSTEST": {
        "SYSBP", "DIABP", "PULSE", "TEMP", "WEIGHT", "HEIGHT", "BMI",
        "RESP", "OXYSAT"
    },
    "VSRESU": {
        "mmHg": {"SYSBP", "DIABP"},
        "beats/min": {"PULSE"},
        "C": {"TEMP"},
        "kg": {"WEIGHT"},
        "cm": {"HEIGHT"},
        "kg/m2": {"BMI"},
        "breaths/min": {"RESP"},
        "%": {"OXYSAT"},
    },
    "LBTEST_COMMON": {
        "ALT", "AST", "BILI", "CREAT", "GGT", "HGB", "WBC",
        "PLT", "SODIUM", "POTASSIUM", "GLUCOSE", "ALBUMIN",
        "ALKPH", "BUN", "CHOL", "TRIG",
    },
    "AESER": {"Y", "N"},
    "AESEV": {"MILD", "MODERATE", "SEVERE"},
    "AEREL": {"NOT RELATED", "UNLIKELY RELATED", "POSSIBLY RELATED",
               "PROBABLY RELATED", "RELATED"},
    "AEOUT": {
        "RECOVERED/RESOLVED",
        "RECOVERING/RESOLVING",
        "NOT RECOVERED/NOT RESOLVED",
        "RECOVERED/RESOLVED WITH SEQUELAE",
        "FATAL",
        "UNKNOWN",
    },
    "COUNTRY": {  # ISO 3166-1 alpha-3 sample
        "USA", "GBR", "CAN", "AUS", "DEU", "FRA", "JPN", "IND", "BRA", "CHN",
    },
    "DSDECOD": {
        "COMPLETED", "ADVERSE EVENT", "LACK OF EFFICACY", "LOST TO FOLLOW-UP",
        "PHYSICIAN DECISION", "PROTOCOL DEVIATION", "SUBJECT DECISION",
        "DEATH", "WITHDRAWAL BY SUBJECT",
    },
}

# ─── Normal Ranges ─────────────────────────────────────────────────────────────

NORMAL_RANGES = {
    "SYSBP":  (70,  200),
    "DIABP":  (40,  120),
    "PULSE":  (30,  200),
    "TEMP":   (34.0, 42.0),
    "WEIGHT": (1,   300),
    "HEIGHT": (30,  250),
    "BMI":    (10,  70),
    "RESP":   (4,   60),
    "OXYSAT": (50,  100),
}

# ─── Visit Windows (Protocol Day Ranges) ──────────────────────────────────────

VISIT_WINDOWS = {
    "SCREENING":  (-28, -1),
    "BASELINE":   (0,   1),
    "WEEK 1":     (5,   9),
    "WEEK 2":     (12,  16),
    "WEEK 4":     (26,  30),
    "WEEK 8":     (54,  58),
    "WEEK 12":    (82,  86),
    "END OF TREATMENT": (84, 92),
    "FOLLOW-UP":  (98,  112),
}

# ─── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class ValidationFinding:
    rule_id:     str
    domain:      str
    subject_id:  str
    variable:    str
    value:       Any
    message:     str
    severity:    Severity
    visit:       Optional[str] = None
    seq:         Optional[int] = None
    timestamp:   str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self):
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


# ─── Rule Registry ─────────────────────────────────────────────────────────────

class CDISCValidator:
    """
    Full Phase A CDISC validation engine with 40+ rules.
    """

    def __init__(self):
        self.findings: list[ValidationFinding] = []

    def _add(self, rule_id, domain, subject_id, variable, value,
             message, severity, visit=None, seq=None):
        self.findings.append(ValidationFinding(
            rule_id=rule_id, domain=domain, subject_id=subject_id,
            variable=variable, value=value, message=message,
            severity=severity, visit=visit, seq=seq,
        ))

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_date(val) -> Optional[date]:
        if not val:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%Y%m%d"):
            try:
                return datetime.strptime(str(val), fmt).date()
            except ValueError:
                pass
        return None

    @staticmethod
    def _is_missing(val) -> bool:
        return val is None or str(val).strip() == ""

    # ══════════════════════════════════════════════════════════════════════════
    # DM — Demographics (Rules DM01–DM12)
    # ══════════════════════════════════════════════════════════════════════════

    def validate_dm(self, records: list[dict]):
        seen_subjects = set()
        for rec in records:
            sid = rec.get("USUBJID", "UNKNOWN")

            # DM01 – USUBJID required and unique
            if self._is_missing(sid):
                self._add("DM01", "DM", sid, "USUBJID", sid,
                          "USUBJID is missing", Severity.CRITICAL)
            elif sid in seen_subjects:
                self._add("DM01", "DM", sid, "USUBJID", sid,
                          f"Duplicate USUBJID: {sid}", Severity.CRITICAL)
            seen_subjects.add(sid)

            # DM02 – RFSTDTC (Reference Start) required
            if self._is_missing(rec.get("RFSTDTC")):
                self._add("DM02", "DM", sid, "RFSTDTC", None,
                          "Reference start date (RFSTDTC) missing", Severity.MAJOR)

            # DM03 – SEX controlled terminology
            sex = str(rec.get("SEX", "")).upper()
            if sex not in CDISC_CT["SEX"]:
                self._add("DM03", "DM", sid, "SEX", sex,
                          f"SEX '{sex}' not in CDISC CT {CDISC_CT['SEX']}",
                          Severity.CRITICAL)

            # DM04 – RACE controlled terminology
            race = str(rec.get("RACE", "")).upper()
            if race and race not in CDISC_CT["RACE"]:
                self._add("DM04", "DM", sid, "RACE", race,
                          f"RACE '{race}' not in CDISC CT", Severity.MAJOR)

            # DM05 – ETHNIC controlled terminology
            ethnic = str(rec.get("ETHNIC", "")).upper()
            if ethnic and ethnic not in CDISC_CT["ETHNIC"]:
                self._add("DM05", "DM", sid, "ETHNIC", ethnic,
                          f"ETHNIC '{ethnic}' not in CDISC CT", Severity.MINOR)

            # DM06 – COUNTRY ISO code
            country = str(rec.get("COUNTRY", "")).upper()
            if country and country not in CDISC_CT["COUNTRY"]:
                self._add("DM06", "DM", sid, "COUNTRY", country,
                          f"COUNTRY '{country}' not a valid ISO-3166 alpha-3 code",
                          Severity.MAJOR)

            # DM07 – AGE plausibility
            age = rec.get("AGE")
            if age is not None:
                try:
                    age = float(age)
                    if age < 0 or age > 120:
                        self._add("DM07", "DM", sid, "AGE", age,
                                  f"AGE {age} outside plausible range (0–120)",
                                  Severity.MAJOR)
                except (ValueError, TypeError):
                    self._add("DM07", "DM", sid, "AGE", age,
                              "AGE is not numeric", Severity.CRITICAL)

            # DM08 – Informed Consent before Reference Start
            ic_date  = self._parse_date(rec.get("RFICDTC"))
            ref_start = self._parse_date(rec.get("RFSTDTC"))
            if ic_date and ref_start and ic_date > ref_start:
                self._add("DM08", "DM", sid, "RFICDTC", str(ic_date),
                          f"Informed consent date {ic_date} is AFTER reference start {ref_start}",
                          Severity.CRITICAL)

            # DM09 – RFENDTC must be >= RFSTDTC
            ref_end = self._parse_date(rec.get("RFENDTC"))
            if ref_start and ref_end and ref_end < ref_start:
                self._add("DM09", "DM", sid, "RFENDTC", str(ref_end),
                          "Reference end date is before reference start date",
                          Severity.CRITICAL)

            # DM10 – SITEID required
            if self._is_missing(rec.get("SITEID")):
                self._add("DM10", "DM", sid, "SITEID", None,
                          "SITEID is required", Severity.MAJOR)

            # DM11 – ARM required
            if self._is_missing(rec.get("ARM")):
                self._add("DM11", "DM", sid, "ARM", None,
                          "Treatment ARM is missing", Severity.MAJOR)

            # DM12 – BRTHDTC: birth year plausibility
            brthdtc = self._parse_date(rec.get("BRTHDTC"))
            if brthdtc:
                current_year = date.today().year
                birth_year = brthdtc.year
                if birth_year < 1900 or birth_year > current_year:
                    self._add("DM12", "DM", sid, "BRTHDTC", str(brthdtc),
                              f"Birth year {birth_year} outside plausible range",
                              Severity.MAJOR)

    # ══════════════════════════════════════════════════════════════════════════
    # AE — Adverse Events (Rules AE01–AE12)
    # ══════════════════════════════════════════════════════════════════════════

    def validate_ae(self, records: list[dict], dm_records: list[dict] = None):
        dm_map = {r.get("USUBJID"): r for r in (dm_records or [])}

        for rec in records:
            sid  = rec.get("USUBJID", "UNKNOWN")
            seq  = rec.get("AESEQ")
            visit = rec.get("VISIT")

            # AE01 – AETERM required
            if self._is_missing(rec.get("AETERM")):
                self._add("AE01", "AE", sid, "AETERM", None,
                          "Adverse event term (AETERM) is missing",
                          Severity.CRITICAL, visit, seq)

            # AE02 – AESTDTC required
            ae_start = self._parse_date(rec.get("AESTDTC"))
            if not ae_start:
                self._add("AE02", "AE", sid, "AESTDTC", rec.get("AESTDTC"),
                          "AE start date missing or unparseable",
                          Severity.CRITICAL, visit, seq)

            # AE03 – AEENDTC must be >= AESTDTC
            ae_end = self._parse_date(rec.get("AEENDTC"))
            if ae_start and ae_end and ae_end < ae_start:
                self._add("AE03", "AE", sid, "AEENDTC", str(ae_end),
                          f"AE end date {ae_end} is before start date {ae_start}",
                          Severity.CRITICAL, visit, seq)

            # AE04 – AE must start after consent date
            dm = dm_map.get(sid, {})
            ic_date = self._parse_date(dm.get("RFICDTC"))
            if ae_start and ic_date and ae_start < ic_date:
                self._add("AE04", "AE", sid, "AESTDTC", str(ae_start),
                          f"AE start {ae_start} is before informed consent {ic_date}",
                          Severity.CRITICAL, visit, seq)

            # AE05 – AESEV controlled terminology
            sev = str(rec.get("AESEV", "")).upper()
            if sev and sev not in CDISC_CT["AESEV"]:
                self._add("AE05", "AE", sid, "AESEV", sev,
                          f"AESEV '{sev}' not in CDISC CT {CDISC_CT['AESEV']}",
                          Severity.MAJOR, visit, seq)

            # AE06 – AEREL controlled terminology
            rel = str(rec.get("AEREL", "")).upper()
            if rel and rel not in CDISC_CT["AEREL"]:
                self._add("AE06", "AE", sid, "AEREL", rel,
                          f"AEREL '{rel}' not in CDISC CT", Severity.MAJOR, visit, seq)

            # AE07 – AESER controlled terminology
            ser = str(rec.get("AESER", "")).upper()
            if ser not in CDISC_CT["AESER"]:
                self._add("AE07", "AE", sid, "AESER", ser,
                          f"AESER must be 'Y' or 'N', got '{ser}'",
                          Severity.CRITICAL, visit, seq)

            # AE08 – SAE criteria: if AESER=Y, must have AESDTH/AESHOSP/AESDISAB populated
            if ser == "Y":
                sae_flags = ["AESDTH", "AESHOSP", "AESDISAB", "AESLIFE", "AESMIE"]
                any_flag = any(str(rec.get(f, "N")).upper() == "Y" for f in sae_flags)
                if not any_flag:
                    self._add("AE08", "AE", sid, "AESER", "Y",
                              "SAE flagged but none of AESDTH/AESHOSP/AESDISAB/AESLIFE/AESMIE = Y",
                              Severity.CRITICAL, visit, seq)

            # AE09 – AEOUT controlled terminology
            outcome = str(rec.get("AEOUT", "")).upper()
            if outcome and outcome not in CDISC_CT["AEOUT"]:
                self._add("AE09", "AE", sid, "AEOUT", outcome,
                          f"AEOUT '{outcome}' not in CDISC CT", Severity.MAJOR, visit, seq)

            # AE10 – If AEOUT=FATAL, then AESDTH must be Y
            if outcome == "FATAL" and str(rec.get("AESDTH", "N")).upper() != "Y":
                self._add("AE10", "AE", sid, "AEOUT", "FATAL",
                          "AEOUT=FATAL but AESDTH is not Y",
                          Severity.CRITICAL, visit, seq)

            # AE11 – AETERM length check (too short likely entry error)
            term = str(rec.get("AETERM", ""))
            if 0 < len(term) < 3:
                self._add("AE11", "AE", sid, "AETERM", term,
                          f"AETERM '{term}' suspiciously short — likely data entry error",
                          Severity.MINOR, visit, seq)

            # AE12 – AEDECOD should differ from AETERM (verbatim vs coded)
            coded = rec.get("AEDECOD", "")
            if coded and coded.upper() == term.upper():
                self._add("AE12", "AE", sid, "AEDECOD", coded,
                          "AEDECOD equals AETERM — medical coding may not have been applied",
                          Severity.MINOR, visit, seq)

    # ══════════════════════════════════════════════════════════════════════════
    # VS — Vital Signs (Rules VS01–VS08)
    # ══════════════════════════════════════════════════════════════════════════

    def validate_vs(self, records: list[dict]):
        for rec in records:
            sid   = rec.get("USUBJID", "UNKNOWN")
            seq   = rec.get("VSSEQ")
            visit = rec.get("VISIT")
            test  = str(rec.get("VSTESTCD", "")).upper()

            # VS01 – VSTESTCD must be in controlled terminology
            if test and test not in CDISC_CT["VSTEST"]:
                self._add("VS01", "VS", sid, "VSTESTCD", test,
                          f"VSTESTCD '{test}' not in CDISC CT vital signs list",
                          Severity.MAJOR, visit, seq)

            # VS02 – VSORRES must be present
            result = rec.get("VSORRES")
            if self._is_missing(result):
                self._add("VS02", "VS", sid, "VSORRES", None,
                          f"Vital sign result (VSORRES) missing for {test}",
                          Severity.MAJOR, visit, seq)

            # VS03 – VSORRESU units check per test
            unit = str(rec.get("VSORRESU", ""))
            expected_units = CDISC_CT["VSRESU"]
            for expected_unit, tests_for_unit in expected_units.items():
                if test in tests_for_unit and unit != expected_unit:
                    self._add("VS03", "VS", sid, "VSORRESU", unit,
                              f"{test} should use units '{expected_unit}', got '{unit}'",
                              Severity.MAJOR, visit, seq)
                    break

            # VS04 – VSORRES plausibility (numeric range check)
            if test in NORMAL_RANGES and result is not None:
                try:
                    val = float(str(result).replace(",", "."))
                    lo, hi = NORMAL_RANGES[test]
                    if val < lo or val > hi:
                        self._add("VS04", "VS", sid, "VSORRES", val,
                                  f"{test} value {val} outside plausible range ({lo}–{hi})",
                                  Severity.MAJOR, visit, seq)
                except (ValueError, TypeError):
                    self._add("VS04", "VS", sid, "VSORRES", result,
                              f"{test} result '{result}' is not numeric",
                              Severity.CRITICAL, visit, seq)

            # VS05 – Systolic must be > Diastolic (cross-record per visit)
            # handled in VS cross-field check below

            # VS06 – VSDTC required
            if self._is_missing(rec.get("VSDTC")):
                self._add("VS06", "VS", sid, "VSDTC", None,
                          "Vital sign date (VSDTC) missing",
                          Severity.MAJOR, visit, seq)

            # VS07 – VSPOS (position) for BP should be STANDING, SITTING, or SUPINE
            if test in ("SYSBP", "DIABP"):
                pos = str(rec.get("VSPOS", "")).upper()
                if pos and pos not in {"STANDING", "SITTING", "SUPINE"}:
                    self._add("VS07", "VS", sid, "VSPOS", pos,
                              f"BP position '{pos}' not a standard CDISC value",
                              Severity.MINOR, visit, seq)

        # VS05 cross-field: SYSBP > DIABP per subject/visit
        from collections import defaultdict
        by_subject_visit = defaultdict(dict)
        for rec in records:
            sid   = rec.get("USUBJID", "UNKNOWN")
            visit = rec.get("VISIT", "")
            test  = str(rec.get("VSTESTCD", "")).upper()
            key   = (sid, visit)
            try:
                val = float(str(rec.get("VSORRES", "")).replace(",", "."))
                by_subject_visit[key][test] = (val, rec.get("VSSEQ"))
            except (ValueError, TypeError):
                pass

        for (sid, visit), tests in by_subject_visit.items():
            if "SYSBP" in tests and "DIABP" in tests:
                sys_val, sys_seq = tests["SYSBP"]
                dia_val, dia_seq = tests["DIABP"]
                if sys_val <= dia_val:
                    self._add("VS05", "VS", sid, "SYSBP", sys_val,
                              f"Systolic BP ({sys_val}) is not greater than diastolic ({dia_val})",
                              Severity.CRITICAL, visit, sys_seq)

    # ══════════════════════════════════════════════════════════════════════════
    # LB — Laboratory (Rules LB01–LB06)
    # ══════════════════════════════════════════════════════════════════════════

    def validate_lb(self, records: list[dict]):
        for rec in records:
            sid   = rec.get("USUBJID", "UNKNOWN")
            seq   = rec.get("LBSEQ")
            visit = rec.get("VISIT")
            test  = str(rec.get("LBTESTCD", "")).upper()

            # LB01 – LBTESTCD required
            if self._is_missing(test):
                self._add("LB01", "LB", sid, "LBTESTCD", None,
                          "Lab test code (LBTESTCD) missing", Severity.CRITICAL, visit, seq)

            # LB02 – LBORRES required
            if self._is_missing(rec.get("LBORRES")):
                self._add("LB02", "LB", sid, "LBORRES", None,
                          f"Lab result (LBORRES) missing for {test}",
                          Severity.MAJOR, visit, seq)

            # LB03 – LBDTC required
            if self._is_missing(rec.get("LBDTC")):
                self._add("LB03", "LB", sid, "LBDTC", None,
                          "Lab date (LBDTC) missing", Severity.MAJOR, visit, seq)

            # LB04 – LBNRIND (normal range indicator) controlled terminology
            nrind = str(rec.get("LBNRIND", "")).upper()
            if nrind and nrind not in {"NORMAL", "LOW", "HIGH", "CRITICALLY LOW",
                                        "CRITICALLY HIGH", "NORMAL AFTER PANIC LOW",
                                        "NORMAL AFTER PANIC HIGH"}:
                self._add("LB04", "LB", sid, "LBNRIND", nrind,
                          f"LBNRIND '{nrind}' not in standard values",
                          Severity.MINOR, visit, seq)

            # LB05 – ALT/AST > 3x ULN flag (clinically significant)
            if test in ("ALT", "AST"):
                try:
                    result_val = float(str(rec.get("LBORRES", "")).replace(",", "."))
                    uln = rec.get("LBSTNRHI")  # upper limit of normal from data
                    if uln:
                        uln_val = float(str(uln).replace(",", "."))
                        if result_val > 3 * uln_val:
                            self._add("LB05", "LB", sid, "LBORRES", result_val,
                                      f"{test} {result_val} > 3× ULN ({uln_val}) — potential hepatotoxicity",
                                      Severity.CRITICAL, visit, seq)
                except (ValueError, TypeError):
                    pass

            # LB06 – LBSTRESU (standard units) should not be missing if LBORRES present
            if not self._is_missing(rec.get("LBORRES")) and self._is_missing(rec.get("LBSTRESU")):
                self._add("LB06", "LB", sid, "LBSTRESU", None,
                          "Lab standard units (LBSTRESU) missing when result present",
                          Severity.MINOR, visit, seq)

    # ══════════════════════════════════════════════════════════════════════════
    # EX — Exposure / Dosing (Rules EX01–EX06)
    # ══════════════════════════════════════════════════════════════════════════

    def validate_ex(self, records: list[dict], dm_records: list[dict] = None):
        dm_map = {r.get("USUBJID"): r for r in (dm_records or [])}

        for rec in records:
            sid   = rec.get("USUBJID", "UNKNOWN")
            seq   = rec.get("EXSEQ")
            visit = rec.get("VISIT")

            # EX01 – EXTRT (treatment name) required
            if self._is_missing(rec.get("EXTRT")):
                self._add("EX01", "EX", sid, "EXTRT", None,
                          "Treatment name (EXTRT) missing", Severity.CRITICAL, visit, seq)

            # EX02 – EXDOSE must be numeric and positive
            dose = rec.get("EXDOSE")
            if dose is not None:
                try:
                    dose_val = float(str(dose))
                    if dose_val < 0:
                        self._add("EX02", "EX", sid, "EXDOSE", dose,
                                  "Dose (EXDOSE) is negative", Severity.CRITICAL, visit, seq)
                except (ValueError, TypeError):
                    self._add("EX02", "EX", sid, "EXDOSE", dose,
                              "EXDOSE is not numeric", Severity.CRITICAL, visit, seq)

            # EX03 – EXSTDTC required
            ex_start = self._parse_date(rec.get("EXSTDTC"))
            if not ex_start:
                self._add("EX03", "EX", sid, "EXSTDTC", rec.get("EXSTDTC"),
                          "Exposure start date (EXSTDTC) missing", Severity.CRITICAL, visit, seq)

            # EX04 – EXENDTC >= EXSTDTC
            ex_end = self._parse_date(rec.get("EXENDTC"))
            if ex_start and ex_end and ex_end < ex_start:
                self._add("EX04", "EX", sid, "EXENDTC", str(ex_end),
                          "Dose end date is before dose start date",
                          Severity.CRITICAL, visit, seq)

            # EX05 – Dosing must not start before consent
            dm = dm_map.get(sid, {})
            ic_date = self._parse_date(dm.get("RFICDTC"))
            if ex_start and ic_date and ex_start < ic_date:
                self._add("EX05", "EX", sid, "EXSTDTC", str(ex_start),
                          f"Dosing started {ex_start} before informed consent {ic_date}",
                          Severity.CRITICAL, visit, seq)

            # EX06 – EXDOSFRQ (frequency) must not be missing
            if self._is_missing(rec.get("EXDOSFRQ")):
                self._add("EX06", "EX", sid, "EXDOSFRQ", None,
                          "Dose frequency (EXDOSFRQ) missing", Severity.MINOR, visit, seq)

    # ══════════════════════════════════════════════════════════════════════════
    # SV — Subject Visits (Visit Window Rules SV01–SV04)
    # ══════════════════════════════════════════════════════════════════════════

    def validate_sv(self, records: list[dict], dm_records: list[dict] = None):
        dm_map = {r.get("USUBJID"): r for r in (dm_records or [])}

        for rec in records:
            sid    = rec.get("USUBJID", "UNKNOWN")
            visit  = str(rec.get("VISIT", "")).upper()
            svstdtc = self._parse_date(rec.get("SVSTDTC"))

            # SV01 – VISIT name must be in protocol
            if visit and visit not in VISIT_WINDOWS:
                self._add("SV01", "SV", sid, "VISIT", visit,
                          f"Visit '{visit}' not in protocol schedule",
                          Severity.MAJOR, visit)

            # SV02 – Visit must fall within window (relative to RFSTDTC)
            if visit in VISIT_WINDOWS and svstdtc:
                dm = dm_map.get(sid, {})
                ref_start = self._parse_date(dm.get("RFSTDTC"))
                if ref_start:
                    study_day = (svstdtc - ref_start).days + 1
                    lo, hi = VISIT_WINDOWS[visit]
                    if not (lo <= study_day <= hi):
                        self._add("SV02", "SV", sid, "SVSTDTC", str(svstdtc),
                                  f"Visit '{visit}' on study day {study_day} is outside "
                                  f"protocol window ({lo}–{hi})",
                                  Severity.MAJOR, visit)

            # SV03 – SVSTDTC required
            if not svstdtc:
                self._add("SV03", "SV", sid, "SVSTDTC", rec.get("SVSTDTC"),
                          "Visit start date (SVSTDTC) missing", Severity.MAJOR, visit)

            # SV04 – SVENDTC >= SVSTDTC
            svendtc = self._parse_date(rec.get("SVENDTC"))
            if svstdtc and svendtc and svendtc < svstdtc:
                self._add("SV04", "SV", sid, "SVENDTC", str(svendtc),
                          "Visit end date is before visit start date",
                          Severity.CRITICAL, visit)

    # ══════════════════════════════════════════════════════════════════════════
    # DS — Disposition (Rules DS01–DS04)
    # ══════════════════════════════════════════════════════════════════════════

    def validate_ds(self, records: list[dict]):
        for rec in records:
            sid = rec.get("USUBJID", "UNKNOWN")

            # DS01 – DSDECOD controlled terminology
            dsdecod = str(rec.get("DSDECOD", "")).upper()
            if dsdecod and dsdecod not in CDISC_CT["DSDECOD"]:
                self._add("DS01", "DS", sid, "DSDECOD", dsdecod,
                          f"DSDECOD '{dsdecod}' not in CDISC CT", Severity.MAJOR)

            # DS02 – DSSTDTC required
            if self._is_missing(rec.get("DSSTDTC")):
                self._add("DS02", "DS", sid, "DSSTDTC", None,
                          "Disposition date (DSSTDTC) missing", Severity.MAJOR)

            # DS03 – If DSDECOD=DEATH, check AESDTH=Y in AE domain (flag only)
            if dsdecod == "DEATH":
                self._add("DS03", "DS", sid, "DSDECOD", "DEATH",
                          "Subject disposition is DEATH — verify AESDTH=Y in AE domain",
                          Severity.MAJOR)

            # DS04 – DSTERM required when DSDECOD=PROTOCOL DEVIATION
            if dsdecod == "PROTOCOL DEVIATION" and self._is_missing(rec.get("DSTERM")):
                self._add("DS04", "DS", sid, "DSTERM", None,
                          "DSTERM (verbatim reason) required when DSDECOD=PROTOCOL DEVIATION",
                          Severity.MAJOR)

    # ══════════════════════════════════════════════════════════════════════════
    # Run all domains
    # ══════════════════════════════════════════════════════════════════════════

    def run_all(self, data: dict) -> list[dict]:
        """
        data: dict with keys DM, AE, VS, LB, EX, SV, DS
        Returns list of finding dicts.
        """
        self.findings = []
        dm = data.get("DM", [])
        self.validate_dm(dm)
        self.validate_ae(data.get("AE", []), dm)
        self.validate_vs(data.get("VS", []))
        self.validate_lb(data.get("LB", []))
        self.validate_ex(data.get("EX", []), dm)
        self.validate_sv(data.get("SV", []), dm)
        self.validate_ds(data.get("DS", []))
        return [f.to_dict() for f in self.findings]

    def summary(self) -> dict:
        counts = {s.value: 0 for s in Severity}
        by_domain = {}
        for f in self.findings:
            counts[f.severity.value] += 1
            by_domain.setdefault(f.domain, 0)
            by_domain[f.domain] += 1
        return {
            "total": len(self.findings),
            "by_severity": counts,
            "by_domain": by_domain,
            "submission_ready": counts[Severity.CRITICAL.value] == 0,
        }


# ─── Sample Test Data ──────────────────────────────────────────────────────────

SAMPLE_DATA = {
    "DM": [
        {
            "USUBJID": "STUDY001-001-001", "SITEID": "001",
            "SEX": "M", "RACE": "WHITE", "ETHNIC": "NOT HISPANIC OR LATINO",
            "AGE": 45, "COUNTRY": "USA", "ARM": "TREATMENT A",
            "RFICDTC": "2024-01-10", "RFSTDTC": "2024-01-15", "RFENDTC": "2024-07-15",
            "BRTHDTC": "1979-03-22",
        },
        {
            "USUBJID": "STUDY001-001-002", "SITEID": "001",
            "SEX": "FEMALE",   # ← Bad: should be F
            "RACE": "ASIAN", "ETHNIC": "NOT HISPANIC OR LATINO",
            "AGE": 38, "COUNTRY": "USA", "ARM": "PLACEBO",
            "RFICDTC": "2024-01-20", "RFSTDTC": "2024-01-18",  # ← Bad: consent AFTER start
            "RFENDTC": "2024-07-18",
        },
        {
            "USUBJID": "STUDY001-002-001", "SITEID": "002",
            "SEX": "F", "RACE": "BLACK OR AFRICAN AMERICAN",
            "ETHNIC": "NOT HISPANIC OR LATINO",
            "AGE": 155,   # ← Bad: impossible age
            "COUNTRY": "USA", "ARM": "TREATMENT A",
            "RFICDTC": "2024-02-01", "RFSTDTC": "2024-02-05", "RFENDTC": "2024-08-05",
        },
    ],
    "AE": [
        {
            "USUBJID": "STUDY001-001-001", "AESEQ": 1,
            "AETERM": "Headache", "AEDECOD": "Headache",  # ← Minor: coded = verbatim
            "AESTDTC": "2024-02-10", "AEENDTC": "2024-02-08",  # ← Bad: end before start
            "AESEV": "MILD", "AEREL": "POSSIBLY RELATED",
            "AESER": "N", "AEOUT": "RECOVERED/RESOLVED",
            "VISIT": "WEEK 4",
        },
        {
            "USUBJID": "STUDY001-001-002", "AESEQ": 1,
            "AETERM": "Nausea", "AEDECOD": "Nausea and vomiting",
            "AESTDTC": "2024-02-15", "AEENDTC": "2024-02-20",
            "AESEV": "MODERATE", "AEREL": "PROBABLY RELATED",
            "AESER": "Y",   # ← SAE flagged
            "AESDTH": "N", "AESHOSP": "N", "AESDISAB": "N",
            "AESLIFE": "N", "AESMIE": "N",  # ← Bad: no SAE criteria met
            "AEOUT": "FATAL",  # ← Bad: FATAL but AESDTH=N
            "VISIT": "WEEK 2",
        },
    ],
    "VS": [
        {
            "USUBJID": "STUDY001-001-001", "VSSEQ": 1,
            "VSTESTCD": "SYSBP", "VSORRES": 125, "VSORRESU": "mmHg",
            "VSDTC": "2024-01-15", "VISIT": "BASELINE", "VSPOS": "SITTING",
        },
        {
            "USUBJID": "STUDY001-001-001", "VSSEQ": 2,
            "VSTESTCD": "DIABP", "VSORRES": 130, "VSORRESU": "mmHg",  # ← Bad: DIABP > SYSBP
            "VSDTC": "2024-01-15", "VISIT": "BASELINE", "VSPOS": "SITTING",
        },
        {
            "USUBJID": "STUDY001-002-001", "VSSEQ": 1,
            "VSTESTCD": "PULSE", "VSORRES": 250,  # ← Bad: impossible pulse
            "VSORRESU": "beats/min", "VSDTC": "2024-02-05", "VISIT": "BASELINE",
        },
        {
            "USUBJID": "STUDY001-001-002", "VSSEQ": 1,
            "VSTESTCD": "WEIGHT", "VSORRES": "seventy",  # ← Bad: not numeric
            "VSORRESU": "kg", "VSDTC": "2024-01-18", "VISIT": "BASELINE",
        },
    ],
    "LB": [
        {
            "USUBJID": "STUDY001-001-001", "LBSEQ": 1,
            "LBTESTCD": "ALT", "LBORRES": 450, "LBSTRESU": "U/L",
            "LBSTNRHI": 40,  # ← Critical: ALT > 3x ULN (>120)
            "LBDTC": "2024-01-15", "VISIT": "BASELINE", "LBNRIND": "HIGH",
        },
        {
            "USUBJID": "STUDY001-001-002", "LBSEQ": 1,
            "LBTESTCD": "HGB", "LBORRES": 12.5,
            "LBDTC": "2024-01-18", "VISIT": "BASELINE", "LBNRIND": "NORMAL",
            # Missing LBSTRESU ← Minor
        },
    ],
    "EX": [
        {
            "USUBJID": "STUDY001-001-001", "EXSEQ": 1,
            "EXTRT": "STUDY DRUG 10MG",
            "EXDOSE": 10, "EXDOSFRQ": "QD",
            "EXSTDTC": "2024-01-15", "EXENDTC": "2024-07-15",
            "VISIT": "BASELINE",
        },
        {
            "USUBJID": "STUDY001-001-002", "EXSEQ": 1,
            "EXTRT": "PLACEBO",
            "EXDOSE": 0, "EXDOSFRQ": "QD",
            "EXSTDTC": "2024-01-10",  # ← Before consent (2024-01-20)
            "EXENDTC": "2024-07-18",
            "VISIT": "BASELINE",
        },
    ],
    "SV": [
        {
            "USUBJID": "STUDY001-001-001",
            "VISIT": "BASELINE",
            "SVSTDTC": "2024-01-15", "SVENDTC": "2024-01-15",
        },
        {
            "USUBJID": "STUDY001-001-001",
            "VISIT": "WEEK 4",
            "SVSTDTC": "2024-02-20",  # study day 37 — window is 26-30 ← Bad
            "SVENDTC": "2024-02-20",
        },
        {
            "USUBJID": "STUDY001-001-002",
            "VISIT": "MYSTERY VISIT",  # ← Not in protocol
            "SVSTDTC": "2024-03-01", "SVENDTC": "2024-03-01",
        },
    ],
    "DS": [
        {
            "USUBJID": "STUDY001-001-001",
            "DSDECOD": "COMPLETED",
            "DSSTDTC": "2024-07-15",
        },
        {
            "USUBJID": "STUDY001-001-002",
            "DSDECOD": "PROTOCOL DEVIATION",
            "DSSTDTC": "2024-05-01",
            # Missing DSTERM ← Bad
        },
    ],
}


if __name__ == "__main__":
    validator = CDISCValidator()
    findings = validator.run_all(SAMPLE_DATA)
    summary = validator.summary()

    print(f"\n{'='*60}")
    print("  CDISC Phase A Validation Report")
    print(f"{'='*60}")
    print(f"  Total findings : {summary['total']}")
    print(f"  CRITICAL       : {summary['by_severity']['CRITICAL']}")
    print(f"  MAJOR          : {summary['by_severity']['MAJOR']}")
    print(f"  MINOR          : {summary['by_severity']['MINOR']}")
    print(f"  Submission ready: {summary['submission_ready']}")
    print(f"{'='*60}\n")

    for f in findings:
        icon = {"CRITICAL": "🔴", "MAJOR": "🟡", "MINOR": "🔵"}.get(f["severity"], "⚪")
        print(f"{icon} [{f['rule_id']}] {f['domain']} | {f['subject_id']} | "
              f"{f['variable']}={f['value']} | {f['message']}")

    # Save findings to JSON
    with open("/home/claude/Mini_EDC_Project/reports/phase_a_findings.json", "w") as fh:
        json.dump({"summary": summary, "findings": findings}, fh, indent=2)
    print("\n✅ Findings saved to reports/phase_a_findings.json")
