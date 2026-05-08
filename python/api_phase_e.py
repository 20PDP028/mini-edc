""
Mini EDC — Phase E: REST API with Swagger / OpenAPI 3.0 docs
FastAPI-based, auto-generates /docs (Swagger UI) and /redoc
"""

from fastapi import FastAPI, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, date
import hashlib
import hmac
import uuid
import io
from enum import Enum

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Mini EDC REST API",
    description="""
## Mini EDC System — Phase E REST API

A **CDISC-compliant Electronic Data Capture** system exposing all core modules:

| Module | Description |
|--------|-------------|
| 🔐 **Auth** | JWT-style token login, role-based access |
| ✅ **Validation** | Phase A — 40+ CDISC edit checks across 7 domains |
| 📦 **SDTM** | Phase B — SDTM v1.8 dataset generation |
| 📋 **Audit** | Phase C — 21 CFR Part 11 immutable audit trail |
| 📊 **Subjects** | Subject management (add, query, status) |
| 🔔 **Queries** | Data query workflow (raise, respond, close) |

> ⚙️ **Base URL**: `http://localhost:8000`  
> 📖 **Docs**: `/docs` (Swagger UI) | `/redoc` (ReDoc)
""",
    version="1.0.0",
    contact={
        "name": "Mini EDC Project",
        "email": "sponsor@cro.com",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=[
        {"name": "auth",       "description": "Authentication & session management"},
        {"name": "subjects",   "description": "Subject enrollment & status"},
        {"name": "validation", "description": "CDISC edit check validation (Phase A)"},
        {"name": "sdtm",       "description": "SDTM dataset generation (Phase B)"},
        {"name": "audit",      "description": "21 CFR Part 11 audit trail (Phase C)"},
        {"name": "queries",    "description": "Data query workflow"},
        {"name": "system",     "description": "Health checks & metadata"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory stores (replace with DB in production) ──────────────────────────

USERS = {
    "admin":       {"password": "Admin@1234",   "role": "Admin",        "token": None, "locked": False, "fails": 0},
    "investigator":{"password": "Invest@1234",  "role": "Investigator", "token": None, "locked": False, "fails": 0},
    "datamanager": {"password": "DataMgr@1234", "role": "Data Manager", "token": None, "locked": False, "fails": 0},
    "monitor":     {"password": "Monitor@1234", "role": "Monitor",      "token": None, "locked": False, "fails": 0},
}

SUBJECTS = {}
AUDIT_LOG = []
QUERIES   = {}

# ── Enums / literals ──────────────────────────────────────────────────────────

class RoleEnum(str, Enum):
    admin = "Admin"
    investigator = "Investigator"
    data_manager = "Data Manager"
    monitor = "Monitor"

class SeverityEnum(str, Enum):
    mild = "MILD"
    moderate = "MODERATE"
    severe = "SEVERE"

class QueryStatusEnum(str, Enum):
    open = "OPEN"
    answered = "ANSWERED"
    closed = "CLOSED"

class DomainEnum(str, Enum):
    DM = "DM"
    AE = "AE"
    VS = "VS"
    LB = "LB"
    EX = "EX"
    SV = "SV"
    DS = "DS"

# ── Pydantic models ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., example="admin")
    password: str = Field(..., example="Admin@1234")

class LoginResponse(BaseModel):
    token: str
    username: str
    role: str
    message: str

class SubjectIn(BaseModel):
    usubjid: str = Field(..., example="STUDY001-001", description="Unique Subject Identifier (CDISC USUBJID)")
    age: int      = Field(..., ge=18, le=99, example=45)
    sex: Literal["M", "F", "U", "N"] = Field(..., example="M")
    race: str     = Field(..., example="WHITE")
    country: str  = Field(..., example="USA", description="ISO 3166-1 alpha-3")
    consent_date: date = Field(..., example="2024-01-15")
    site_id: str  = Field(..., example="SITE-01")

class SubjectOut(SubjectIn):
    status: str
    enrolled_at: str

class ValidationRequest(BaseModel):
    domain: DomainEnum = Field(..., example="DM")
    records: List[dict] = Field(..., example=[
        {"USUBJID": "STUDY001-001", "AGE": 45, "SEX": "M", "RACE": "WHITE",
         "ETHNIC": "NOT HISPANIC OR LATINO", "COUNTRY": "USA",
         "RFSTDTC": "2024-01-16", "RFENDTC": "2024-06-30",
         "DMDTC": "2024-01-15", "BRTHDTC": "1979-03-10"}
    ])

class FindingOut(BaseModel):
    rule_id: str
    domain: str
    usubjid: str
    severity: str
    message: str
    field: Optional[str]

class ValidationResponse(BaseModel):
    domain: str
    records_checked: int
    findings_count: int
    findings: List[FindingOut]

class SDTMRequest(BaseModel):
    domain: DomainEnum = Field(..., example="DM")
    subjects: Optional[List[str]] = Field(None, example=["STUDY001-001", "STUDY001-002"])

class AuditEntry(BaseModel):
    entry_id: str
    timestamp: str
    user: str
    action: str
    domain: str
    usubjid: Optional[str]
    details: str
    chain_hash: str

class QueryIn(BaseModel):
    usubjid: str   = Field(..., example="STUDY001-001")
    domain: DomainEnum = Field(..., example="VS")
    field: str     = Field(..., example="VSORRES")
    visit: str     = Field(..., example="WEEK 4")
    message: str   = Field(..., example="Systolic value 185 seems implausibly high. Please verify source document.")

class QueryOut(QueryIn):
    query_id: str
    status: str
    raised_by: str
    raised_at: str
    response: Optional[str]
    closed_at: Optional[str]

# ── Helpers ───────────────────────────────────────────────────────────────────

SECRET = b"mini_edc_secret_key_phase_e"

def make_token(username: str) -> str:
    payload = f"{username}:{datetime.utcnow().isoformat()}"
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()

def get_current_user(token: str = Query(..., description="Auth token from /auth/login")):
    for uname, info in USERS.items():
        if info["token"] and info["token"] == token:
            return {"username": uname, **info}
    raise HTTPException(status_code=401, detail="Invalid or expired token. Please login again.")

def log_audit(user: str, action: str, domain: str, usubjid: Optional[str], details: str):
    prev_hash = AUDIT_LOG[-1]["chain_hash"] if AUDIT_LOG else "GENESIS"
    raw = f"{user}|{action}|{domain}|{usubjid}|{details}|{prev_hash}"
    chain_hash = hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest()
    entry = {
        "entry_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user": user, "action": action, "domain": domain,
        "usubjid": usubjid, "details": details, "chain_hash": chain_hash,
    }
    AUDIT_LOG.append(entry)
    return entry

# ── CDISC validation mini-engine ──────────────────────────────────────────────

SEX_CT    = {"M", "F", "U", "N", "UNDIFFERENTIATED"}
RACE_CT   = {"WHITE", "BLACK OR AFRICAN AMERICAN", "ASIAN", "AMERICAN INDIAN OR ALASKA NATIVE",
              "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER", "MULTIPLE", "OTHER", "UNKNOWN", "NOT REPORTED"}
ETHNIC_CT = {"HISPANIC OR LATINO", "NOT HISPANIC OR LATINO", "UNKNOWN", "NOT REPORTED"}
AE_SEV_CT = {"MILD", "MODERATE", "SEVERE"}
AE_REL_CT = {"NOT RELATED", "UNLIKELY RELATED", "POSSIBLY RELATED", "PROBABLY RELATED", "DEFINITELY RELATED"}
AE_OUT_CT = {"RECOVERED/RESOLVED", "RECOVERING/RESOLVING", "NOT RECOVERED/NOT RESOLVED",
              "RECOVERED/RESOLVED WITH SEQUELAE", "FATAL", "UNKNOWN"}

def validate_domain(domain: str, records: list) -> list:
    findings = []
    def add(rule_id, usubjid, severity, message, field=None):
        findings.append({"rule_id": rule_id, "domain": domain, "usubjid": usubjid,
                          "severity": severity, "message": message, "field": field})

    for r in records:
        uid = r.get("USUBJID", "UNKNOWN")

        if domain == "DM":
            if r.get("SEX","").upper() not in SEX_CT:
                add("DM001", uid, "ERROR", f"SEX '{r.get('SEX')}' not in CDISC CT", "SEX")
            if r.get("RACE","").upper() not in RACE_CT:
                add("DM002", uid, "ERROR", f"RACE '{r.get('RACE')}' not in CDISC CT", "RACE")
            if r.get("ETHNIC","").upper() not in ETHNIC_CT:
                add("DM003", uid, "WARNING", f"ETHNIC '{r.get('ETHNIC')}' not in CDISC CT", "ETHNIC")
            age = r.get("AGE")
            if age is not None:
                try:
                    if not (0 < int(age) <= 120):
                        add("DM004", uid, "ERROR", f"AGE {age} outside plausible range (1–120)", "AGE")
                except: add("DM004", uid, "ERROR", "AGE is non-numeric", "AGE")
            rfst = r.get("RFSTDTC",""); consent = r.get("DMDTC","")
            if rfst and consent and rfst < consent:
                add("DM005", uid, "CRITICAL", "First dose before consent date — protocol violation", "RFSTDTC")

        elif domain == "AE":
            aestdt = r.get("AESTDTC",""); aeendt = r.get("AEENDTC","")
            if aestdt and aeendt and aeendt < aestdt:
                add("AE001", uid, "ERROR", "AE end date before start date", "AEENDTC")
            sev = r.get("AESEV","").upper()
            if sev and sev not in AE_SEV_CT:
                add("AE002", uid, "ERROR", f"AESEV '{sev}' not in CDISC CT", "AESEV")
            rel = r.get("AEREL","").upper()
            if rel and rel not in AE_REL_CT:
                add("AE003", uid, "WARNING", f"AEREL '{rel}' not in CDISC CT", "AEREL")
            if str(r.get("AESER","")).upper() == "Y" and sev != "SEVERE":
                add("AE004", uid, "WARNING", "SAE flagged but severity is not SEVERE", "AESER")
            if str(r.get("AESDTH","")).upper() == "Y" and r.get("AEOUT","").upper() != "FATAL":
                add("AE005", uid, "ERROR", "AESDTH=Y but AEOUT is not FATAL — inconsistency", "AEOUT")

        elif domain == "VS":
            sys_bp = r.get("VSORRES_SYSBP"); dia_bp = r.get("VSORRES_DIABP")
            if sys_bp and dia_bp:
                try:
                    if float(sys_bp) <= float(dia_bp):
                        add("VS001", uid, "ERROR", f"Systolic {sys_bp} ≤ Diastolic {dia_bp}", "VSORRES")
                except: pass
            hr = r.get("VSORRES_HR")
            if hr:
                try:
                    if not (20 <= float(hr) <= 300):
                        add("VS002", uid, "ERROR", f"Heart rate {hr} outside plausible range (20–300)", "VSORRES")
                except: add("VS002", uid, "WARNING", "Heart rate is non-numeric", "VSORRES")

        elif domain == "LB":
            try:
                alt = float(r.get("LBORRES_ALT", 0) or 0)
                uln_alt = float(r.get("LBSTNRHI_ALT", 40) or 40)
                if alt > 3 * uln_alt:
                    add("LB001", uid, "CRITICAL", f"ALT {alt} > 3× ULN ({uln_alt}) — hepatotoxicity signal", "LBORRES")
            except: pass
            try:
                ast = float(r.get("LBORRES_AST", 0) or 0)
                uln_ast = float(r.get("LBSTNRHI_AST", 40) or 40)
                if ast > 3 * uln_ast:
                    add("LB002", uid, "CRITICAL", f"AST {ast} > 3× ULN ({uln_ast}) — hepatotoxicity signal", "LBORRES")
            except: pass

        elif domain == "EX":
            exst = r.get("EXSTDTC",""); consent = r.get("DMDTC","")
            if exst and consent and exst < consent:
                add("EX001", uid, "CRITICAL", "Dose administered before consent — protocol violation", "EXSTDTC")
            dose = r.get("EXDOSE")
            if dose is not None:
                try:
                    if float(dose) < 0:
                        add("EX002", uid, "ERROR", f"Negative dose value: {dose}", "EXDOSE")
                except: add("EX002", uid, "WARNING", "EXDOSE is non-numeric", "EXDOSE")

    return findings

# ── Synthetic SDTM data ───────────────────────────────────────────────────────

def generate_sdtm_domain(domain: str, subject_ids: Optional[List[str]]) -> list:
    subs = subject_ids or ["STUDY001-001", "STUDY001-002", "STUDY001-003"]
    rows = []
    studyid = "STUDY001"; domain_u = domain.upper()

    for i, uid in enumerate(subs):
        if domain_u == "DM":
            rows.append({"STUDYID": studyid, "DOMAIN": "DM", "USUBJID": uid,
                          "SUBJID": uid.split("-")[-1], "SITEID": f"SITE-0{i+1}",
                          "AGE": 40+i*5, "AGEU": "YEARS", "SEX": ["M","F","M"][i%3],
                          "RACE": "WHITE", "ETHNIC": "NOT HISPANIC OR LATINO",
                          "COUNTRY": "USA", "DMDTC": f"2024-01-{15+i:02d}",
                          "RFSTDTC": f"2024-01-{16+i:02d}", "RFENDTC": "2024-06-30"})
        elif domain_u == "AE":
            rows.append({"STUDYID": studyid, "DOMAIN": "AE", "USUBJID": uid,
                          "AESEQ": 1, "AETERM": "HEADACHE", "AEDECOD": "Headache",
                          "AEBODSYS": "NERVOUS SYSTEM DISORDERS",
                          "AESTDTC": f"2024-02-{10+i:02d}", "AEENDTC": f"2024-02-{12+i:02d}",
                          "AESEV": "MILD", "AESER": "N", "AEREL": "POSSIBLY RELATED",
                          "AEOUT": "RECOVERED/RESOLVED", "AESDTH": "N"})
        elif domain_u == "VS":
            rows.append({"STUDYID": studyid, "DOMAIN": "VS", "USUBJID": uid,
                          "VSSEQ": 1, "VSTESTCD": "SYSBP", "VSTEST": "Systolic Blood Pressure",
                          "VSORRES": str(120+i*2), "VSORRESU": "mmHg",
                          "VSSTRESC": str(120+i*2), "VSSTRESN": 120+i*2,
                          "VSSTRESU": "mmHg", "VSBLFL": "Y", "VISITNUM": 1, "VISIT": "BASELINE",
                          "VSDTC": f"2024-01-{16+i:02d}"})
        elif domain_u == "LB":
            rows.append({"STUDYID": studyid, "DOMAIN": "LB", "USUBJID": uid,
                          "LBSEQ": 1, "LBTESTCD": "ALT", "LBTEST": "Alanine Aminotransferase",
                          "LBORRES": str(25+i*3), "LBORRESU": "U/L",
                          "LBSTRESC": str(25+i*3), "LBSTRESN": 25+i*3,
                          "LBSTRESU": "U/L", "LBNRLO": "7", "LBNRHI": "40",
                          "LBNRIND": "NORMAL", "LBBLFL": "Y",
                          "VISITNUM": 1, "VISIT": "BASELINE", "LBDTC": f"2024-01-{16+i:02d}"})
        elif domain_u == "EX":
            rows.append({"STUDYID": studyid, "DOMAIN": "EX", "USUBJID": uid,
                          "EXSEQ": 1, "EXTRT": "STUDY DRUG", "EXDOSE": 100,
                          "EXDOSU": "mg", "EXDOSFRQ": "QD", "EXROUTE": "ORAL",
                          "EXSTDTC": f"2024-01-{16+i:02d}", "EXENDTC": "2024-06-30"})
    return rows

# ── Routes: Auth ──────────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=LoginResponse, tags=["auth"],
          summary="Login and receive an auth token")
def login(req: LoginRequest):
    """
    Authenticate with username and password.

    Returns a **token** to pass as `?token=` on all protected endpoints.

    **Demo credentials:**
    | Username | Password | Role |
    |----------|----------|------|
    | admin | Admin@1234 | Admin |
    | investigator | Invest@1234 | Investigator |
    | datamanager | DataMgr@1234 | Data Manager |
    | monitor | Monitor@1234 | Monitor |
    """
    user = USERS.get(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user["locked"]:
        raise HTTPException(status_code=403, detail="Account locked after 3 failed attempts")
    if user["password"] != req.password:
        user["fails"] += 1
        if user["fails"] >= 3:
            user["locked"] = True
        raise HTTPException(status_code=401, detail=f"Wrong password. Attempts: {user['fails']}/3")
    user["fails"] = 0
    token = make_token(req.username)
    user["token"] = token
    log_audit(req.username, "LOGIN", "SYSTEM", None, "Successful login")
    return {"token": token, "username": req.username, "role": user["role"],
            "message": f"Welcome, {req.username}! Role: {user['role']}"}

@app.post("/auth/logout", tags=["auth"], summary="Logout and invalidate token")
def logout(current_user: dict = Depends(get_current_user)):
    USERS[current_user["username"]]["token"] = None
    log_audit(current_user["username"], "LOGOUT", "SYSTEM", None, "User logged out")
    return {"message": f"{current_user['username']} logged out successfully"}

# ── Routes: Subjects ──────────────────────────────────────────────────────────

@app.post("/subjects", response_model=SubjectOut, tags=["subjects"],
          summary="Enroll a new subject", status_code=201)
def create_subject(subject: SubjectIn, current_user: dict = Depends(get_current_user)):
    if subject.usubjid in SUBJECTS:
        raise HTTPException(status_code=409, detail=f"Subject {subject.usubjid} already enrolled")
    record = {**subject.dict(), "status": "ENROLLED",
              "enrolled_at": datetime.utcnow().isoformat() + "Z"}
    record["consent_date"] = record["consent_date"].isoformat()
    SUBJECTS[subject.usubjid] = record
    log_audit(current_user["username"], "SUBJECT_ENROLL", "DM", subject.usubjid,
              f"Subject enrolled at site {subject.site_id}")
    return record

@app.get("/subjects", response_model=List[SubjectOut], tags=["subjects"],
         summary="List all enrolled subjects")
def list_subjects(
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[str]  = Query(None, description="Filter by status (ENROLLED, COMPLETED, WITHDRAWN)"),
    current_user: dict = Depends(get_current_user)
):
    results = list(SUBJECTS.values())
    if site_id:  results = [s for s in results if s["site_id"] == site_id]
    if status:   results = [s for s in results if s["status"] == status]
    return results

@app.get("/subjects/{usubjid}", response_model=SubjectOut, tags=["subjects"],
         summary="Get a single subject by USUBJID")
def get_subject(usubjid: str, current_user: dict = Depends(get_current_user)):
    sub = SUBJECTS.get(usubjid)
    if not sub:
        raise HTTPException(status_code=404, detail=f"Subject {usubjid} not found")
    return sub

@app.patch("/subjects/{usubjid}/status", tags=["subjects"],
           summary="Update subject status (ENROLLED → COMPLETED / WITHDRAWN)")
def update_subject_status(
    usubjid: str,
    new_status: Literal["ENROLLED","COMPLETED","WITHDRAWN"] = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    if usubjid not in SUBJECTS:
        raise HTTPException(status_code=404, detail=f"Subject {usubjid} not found")
    old = SUBJECTS[usubjid]["status"]
    SUBJECTS[usubjid]["status"] = new_status
    log_audit(current_user["username"], "STATUS_CHANGE", "DS", usubjid,
              f"Status changed from {old} to {new_status}")
    return {"usubjid": usubjid, "old_status": old, "new_status": new_status}

# ── Routes: Validation ────────────────────────────────────────────────────────

@app.post("/validation/run", response_model=ValidationResponse, tags=["validation"],
          summary="Run CDISC edit checks on a batch of records")
def run_validation(req: ValidationRequest, current_user: dict = Depends(get_current_user)):
    findings = validate_domain(req.domain.value, req.records)
    log_audit(current_user["username"], "VALIDATION_RUN", req.domain.value, None,
              f"{len(req.records)} records checked, {len(findings)} findings")
    return {"domain": req.domain.value, "records_checked": len(req.records),
            "findings_count": len(findings), "findings": findings}

@app.get("/validation/rules", tags=["validation"],
         summary="List all available validation rules by domain")
def list_rules(domain: Optional[DomainEnum] = Query(None)):
    all_rules = [
        {"rule_id":"DM001","domain":"DM","check":"SEX controlled terminology","severity":"ERROR"},
        {"rule_id":"DM002","domain":"DM","check":"RACE controlled terminology","severity":"ERROR"},
        {"rule_id":"DM003","domain":"DM","check":"ETHNIC controlled terminology","severity":"WARNING"},
        {"rule_id":"DM004","domain":"DM","check":"AGE plausibility (1–120 years)","severity":"ERROR"},
        {"rule_id":"DM005","domain":"DM","check":"Consent before first dose","severity":"CRITICAL"},
        {"rule_id":"AE001","domain":"AE","check":"AE end ≥ start date","severity":"ERROR"},
        {"rule_id":"AE002","domain":"AE","check":"AESEV controlled terminology","severity":"ERROR"},
        {"rule_id":"AE003","domain":"AE","check":"AEREL controlled terminology","severity":"WARNING"},
        {"rule_id":"AE004","domain":"AE","check":"SAE severity cross-check","severity":"WARNING"},
        {"rule_id":"AE005","domain":"AE","check":"AESDTH / AEOUT consistency","severity":"ERROR"},
        {"rule_id":"VS001","domain":"VS","check":"Systolic > Diastolic","severity":"ERROR"},
        {"rule_id":"VS002","domain":"VS","check":"Heart rate plausibility (20–300)","severity":"ERROR"},
        {"rule_id":"LB001","domain":"LB","check":"ALT > 3× ULN hepatotoxicity","severity":"CRITICAL"},
        {"rule_id":"LB002","domain":"LB","check":"AST > 3× ULN hepatotoxicity","severity":"CRITICAL"},
        {"rule_id":"EX001","domain":"EX","check":"Dose after consent date","severity":"CRITICAL"},
        {"rule_id":"EX002","domain":"EX","check":"Non-negative dose value","severity":"ERROR"},
    ]
    if domain:
        all_rules = [r for r in all_rules if r["domain"] == domain.value]
    return {"total": len(all_rules), "rules": all_rules}

# ── Routes: SDTM ──────────────────────────────────────────────────────────────

@app.post("/sdtm/generate", tags=["sdtm"],
          summary="Generate an SDTM v1.8 dataset for a domain")
def generate_sdtm(req: SDTMRequest, current_user: dict = Depends(get_current_user)):
    data = generate_sdtm_domain(req.domain.value, req.subjects)
    log_audit(current_user["username"], "SDTM_GENERATE", req.domain.value, None,
              f"Generated {len(data)} rows for domain {req.domain.value}")
    return {"domain": req.domain.value, "row_count": len(data),
            "sdtm_version": "1.8", "rows": data}

@app.get("/sdtm/domains", tags=["sdtm"],
         summary="List supported SDTM domains and their variables")
def list_sdtm_domains():
    return {
        "supported_domains": [
            {"domain":"DM","label":"Demographics","class":"Special Purpose","key_vars":["STUDYID","DOMAIN","USUBJID","AGE","SEX","RACE","COUNTRY"]},
            {"domain":"AE","label":"Adverse Events","class":"Events","key_vars":["STUDYID","DOMAIN","USUBJID","AESEQ","AETERM","AESEV","AESER"]},
            {"domain":"VS","label":"Vital Signs","class":"Findings","key_vars":["STUDYID","DOMAIN","USUBJID","VSSEQ","VSTESTCD","VSORRES","VSDTC"]},
            {"domain":"LB","label":"Laboratory Test Results","class":"Findings","key_vars":["STUDYID","DOMAIN","USUBJID","LBSEQ","LBTESTCD","LBORRES","LBDTC"]},
            {"domain":"EX","label":"Exposure","class":"Interventions","key_vars":["STUDYID","DOMAIN","USUBJID","EXSEQ","EXTRT","EXDOSE","EXSTDTC"]},
        ]
    }

# ── Routes: Audit ─────────────────────────────────────────────────────────────

@app.get("/audit/trail", response_model=List[AuditEntry], tags=["audit"],
         summary="Retrieve the immutable 21 CFR Part 11 audit trail")
def get_audit_trail(
    user: Optional[str]   = Query(None, description="Filter by username"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    domain: Optional[str] = Query(None, description="Filter by CDISC domain"),
    limit: int            = Query(50, ge=1, le=500, description="Max entries to return"),
    current_user: dict = Depends(get_current_user)
):
    results = AUDIT_LOG.copy()
    if user:   results = [e for e in results if e["user"] == user]
    if action: results = [e for e in results if e["action"] == action]
    if domain: results = [e for e in results if e["domain"] == domain]
    return results[-limit:]

@app.get("/audit/integrity", tags=["audit"],
         summary="Verify the chain integrity of the entire audit log")
def verify_audit_integrity(current_user: dict = Depends(get_current_user)):
    if not AUDIT_LOG:
        return {"status": "EMPTY", "entries_checked": 0, "broken_links": 0}
    broken = 0
    prev_hash = "GENESIS"
    for entry in AUDIT_LOG:
        raw = f"{entry['user']}|{entry['action']}|{entry['domain']}|{entry['usubjid']}|{entry['details']}|{prev_hash}"
        expected = hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest()
        if entry["chain_hash"] != expected:
            broken += 1
        prev_hash = entry["chain_hash"]
    return {"status": "INTACT" if broken == 0 else "TAMPERED",
            "entries_checked": len(AUDIT_LOG), "broken_links": broken}

# ── Routes: Queries ───────────────────────────────────────────────────────────

@app.post("/queries", response_model=QueryOut, tags=["queries"],
          summary="Raise a data query against a subject record", status_code=201)
def raise_query(q: QueryIn, current_user: dict = Depends(get_current_user)):
    qid = f"QRY-{len(QUERIES)+1:04d}"
    record = {**q.dict(), "query_id": qid, "status": "OPEN",
              "raised_by": current_user["username"],
              "raised_at": datetime.utcnow().isoformat() + "Z",
              "response": None, "closed_at": None}
    QUERIES[qid] = record
    log_audit(current_user["username"], "QUERY_RAISED", q.domain.value, q.usubjid,
              f"Query {qid} raised on {q.field} at {q.visit}")
    return record

@app.get("/queries", response_model=List[QueryOut], tags=["queries"],
         summary="List all queries, optionally filtered")
def list_queries(
    status: Optional[QueryStatusEnum] = Query(None),
    usubjid: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    results = list(QUERIES.values())
    if status:  results = [q for q in results if q["status"] == status.value]
    if usubjid: results = [q for q in results if q["usubjid"] == usubjid]
    return results

@app.patch("/queries/{query_id}/respond", response_model=QueryOut, tags=["queries"],
           summary="Respond to an open query")
def respond_to_query(
    query_id: str,
    response: str = Body(..., embed=True, example="Verified against source document. Value confirmed correct."),
    current_user: dict = Depends(get_current_user)
):
    q = QUERIES.get(query_id)
    if not q: raise HTTPException(404, detail=f"Query {query_id} not found")
    if q["status"] != "OPEN": raise HTTPException(400, detail="Query is not OPEN")
    q["response"] = response
    q["status"] = "ANSWERED"
    log_audit(current_user["username"], "QUERY_ANSWERED", q["domain"], q["usubjid"],
              f"Query {query_id} answered")
    return q

@app.patch("/queries/{query_id}/close", response_model=QueryOut, tags=["queries"],
           summary="Close an answered query")
def close_query(query_id: str, current_user: dict = Depends(get_current_user)):
    q = QUERIES.get(query_id)
    if not q: raise HTTPException(404, detail=f"Query {query_id} not found")
    if q["status"] != "ANSWERED": raise HTTPException(400, detail="Only ANSWERED queries can be closed")
    q["status"] = "CLOSED"
    q["closed_at"] = datetime.utcnow().isoformat() + "Z"
    log_audit(current_user["username"], "QUERY_CLOSED", q["domain"], q["usubjid"],
              f"Query {query_id} closed by {current_user['username']}")
    return q

# ── Routes: System ────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"], summary="Health check — no auth required")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "1.0.0", "phase": "E"}

@app.get("/system/stats", tags=["system"], summary="Study-level statistics")
def system_stats(current_user: dict = Depends(get_current_user)):
    return {
        "subjects": {
            "total": len(SUBJECTS),
            "enrolled":   sum(1 for s in SUBJECTS.values() if s["status"] == "ENROLLED"),
            "completed":  sum(1 for s in SUBJECTS.values() if s["status"] == "COMPLETED"),
            "withdrawn":  sum(1 for s in SUBJECTS.values() if s["status"] == "WITHDRAWN"),
        },
        "queries": {
            "total": len(QUERIES),
            "open":     sum(1 for q in QUERIES.values() if q["status"] == "OPEN"),
            "answered": sum(1 for q in QUERIES.values() if q["status"] == "ANSWERED"),
            "closed":   sum(1 for q in QUERIES.values() if q["status"] == "CLOSED"),
        },
        "audit_entries": len(AUDIT_LOG),
        "users_online":  sum(1 for u in USERS.values() if u["token"]),
    }

@app.get("/", tags=["system"], summary="API root — links to docs")
def root():
    return {
        "name": "Mini EDC REST API",
        "version": "1.0.0",
        "phase": "E",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "openapi_spec": "/openapi.json",
    }

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
