"""
api_phase_f.py — Mini EDC Phase F REST API
Multi-study, Multi-site, Protocol & CRF Data Entry
"""

from fastapi import FastAPI, HTTPException, Depends, Query, Body, Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum
import hashlib
import hmac
import uuid
import os

# ── DB ────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL)
if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

PH = "%s"

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def db_exec(sql, params=(), fetchone=False, fetchall=False, commit=False):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    result = None
    if fetchone:
        row = cur.fetchone()
        result = dict(row) if row else None
    elif fetchall:
        rows = cur.fetchall()
        result = [dict(r) for r in rows]
    if commit:
        conn.commit()
    conn.close()
    return result

SECRET = b"mini_edc_phase_f_secret"

def make_token(user_id: str) -> str:
    payload = f"{user_id}:{datetime.utcnow().isoformat()}:{uuid.uuid4()}"
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="Mini EDC Phase F API",
    description="Multi-study, Multi-site Clinical Data Capture System with CRF Data Entry",
    version="2.0.0",
    openapi_tags=[
        {"name": "auth",      "description": "Authentication"},
        {"name": "studies",   "description": "Study management"},
        {"name": "sites",     "description": "Site management"},
        {"name": "subjects",  "description": "Subject enrollment"},
        {"name": "visits",    "description": "Protocol & subject visits"},
        {"name": "crf",       "description": "CRF data entry (DM, VS, LB, AE, EX, CM)"},
        {"name": "queries",   "description": "Data queries"},
        {"name": "audit",     "description": "Audit trail"},
        {"name": "system",    "description": "Health & stats"},
    ]
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if os.path.exists("/app/static"):
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")

@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    return FileResponse("/app/static/dashboard_phase_f.html")
# ── Models ────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    user_id: str = Field(..., example="ADMIN")
    password: str = Field(..., example="Admin@1234")

class LoginResponse(BaseModel):
    token: str
    user_id: str
    full_name: str
    role: str
    message: str

class StudyIn(BaseModel):
    study_id: str = Field(..., example="STUDY002")
    study_title: str = Field(..., example="A Phase II Study of Drug Y")
    protocol_no: Optional[str] = Field(None, example="PROTO-2024-002")
    phase: Optional[str] = Field(None, example="II")
    sponsor: Optional[str] = Field(None, example="Pharma Corp")
    indication: Optional[str] = Field(None, example="Diabetes")

class SiteIn(BaseModel):
    site_id: str = Field(..., example="SITE-04")
    site_name: str = Field(..., example="City Hospital")
    investigator: Optional[str] = Field(None, example="Dr. Kumar")
    country: Optional[str] = Field(None, example="IND")
    city: Optional[str] = Field(None, example="Mumbai")

class SubjectIn(BaseModel):
    usubjid: str = Field(..., example="STUDY001-SITE01-001")
    site_id: str = Field(..., example="SITE-01")
    subjid: Optional[str] = Field(None, example="001")
    initials: Optional[str] = Field(None, example="JS")
    sex: Literal["M","F","U","N"] = Field(..., example="M")
    race: Optional[str] = Field(None, example="WHITE")
    ethnic: Optional[str] = Field(None, example="NOT HISPANIC OR LATINO")
    country: Optional[str] = Field(None, example="USA")
    consent_date: str = Field(..., example="2024-01-15")
    enroll_date: Optional[str] = Field(None, example="2024-01-16")

class SubjectStatusUpdate(BaseModel):
    status: Literal["SCREENED","ENROLLED","COMPLETED","WITHDRAWN","SCREEN_FAILED"]
    withdraw_reason: Optional[str] = None

class VisitIn(BaseModel):
    visit_num: int = Field(..., example=1)
    visit_name: str = Field(..., example="SCREENING")
    visit_date: str = Field(..., example="2024-01-15")
    is_unscheduled: Optional[int] = Field(0, example=0)

class CRFDemographics(BaseModel):
    age: Optional[int] = Field(None, example=45)
    sex: Optional[str] = Field(None, example="M")
    race: Optional[str] = Field(None, example="WHITE")
    ethnic: Optional[str] = Field(None, example="NOT HISPANIC OR LATINO")
    country: Optional[str] = Field(None, example="USA")
    rfstdtc: Optional[str] = Field(None, example="2024-01-16")
    rfendtc: Optional[str] = Field(None, example="2024-06-30")
    dmdtc: Optional[str] = Field(None, example="2024-01-15")

class CRFVitalSigns(BaseModel):
    visit_num: int = Field(..., example=2)
    visit_name: Optional[str] = Field(None, example="BASELINE")
    vsdtc: str = Field(..., example="2024-01-16")
    sysbp: Optional[float] = Field(None, example=120.0)
    diabp: Optional[float] = Field(None, example=80.0)
    pulse: Optional[float] = Field(None, example=72.0)
    temp: Optional[float] = Field(None, example=36.8)
    weight: Optional[float] = Field(None, example=70.5)
    height: Optional[float] = Field(None, example=175.0)
    resp_rate: Optional[float] = Field(None, example=16.0)

class CRFLaboratory(BaseModel):
    visit_num: int = Field(..., example=2)
    visit_name: Optional[str] = Field(None, example="BASELINE")
    lbdtc: str = Field(..., example="2024-01-16")
    hgb: Optional[float] = Field(None, example=14.5)
    wbc: Optional[float] = Field(None, example=7.2)
    plt: Optional[float] = Field(None, example=250.0)
    alt: Optional[float] = Field(None, example=25.0)
    ast: Optional[float] = Field(None, example=22.0)
    creatinine: Optional[float] = Field(None, example=0.9)
    glucose: Optional[float] = Field(None, example=95.0)

class CRFAdverseEvent(BaseModel):
    aeterm: str = Field(..., example="HEADACHE")
    aedecod: Optional[str] = Field(None, example="Headache")
    aebodsys: Optional[str] = Field(None, example="NERVOUS SYSTEM DISORDERS")
    aestdtc: str = Field(..., example="2024-02-10")
    aeendtc: Optional[str] = Field(None, example="2024-02-12")
    aesev: Literal["MILD","MODERATE","SEVERE"] = Field(..., example="MILD")
    aeser: Literal["Y","N"] = Field(..., example="N")
    aerel: Optional[str] = Field(None, example="POSSIBLY RELATED")
    aeout: Optional[str] = Field(None, example="RECOVERED/RESOLVED")
    aesdth: Optional[str] = Field("N", example="N")

class CRFExposure(BaseModel):
    visit_num: int = Field(..., example=2)
    visit_name: Optional[str] = Field(None, example="BASELINE")
    extrt: str = Field(..., example="STUDY DRUG")
    exdose: Optional[float] = Field(None, example=100.0)
    exdosu: Optional[str] = Field(None, example="mg")
    exdosfrq: Optional[str] = Field(None, example="QD")
    exroute: Optional[str] = Field(None, example="ORAL")
    exstdtc: Optional[str] = Field(None, example="2024-01-16")
    exendtc: Optional[str] = Field(None, example="2024-06-30")
    ex_reason_mod: Optional[str] = None

class CRFConcomitantMed(BaseModel):
    cmtrt: str = Field(..., example="ASPIRIN")
    cmdose: Optional[float] = Field(None, example=100.0)
    cmdosu: Optional[str] = Field(None, example="mg")
    cmroute: Optional[str] = Field(None, example="ORAL")
    cmstdtc: Optional[str] = Field(None, example="2024-01-01")
    cmendtc: Optional[str] = Field(None, example="2024-06-30")
    cmindc: Optional[str] = Field(None, example="Pain relief")

class QueryIn(BaseModel):
    usubjid: str = Field(..., example="STUDY001-SITE01-001")
    domain: str = Field(..., example="VS")
    visit_num: Optional[int] = None
    field: str = Field(..., example="SYSBP")
    value: Optional[str] = None
    issue: str = Field(..., example="Value seems implausibly high")
    severity: Literal["Critical","Major","Minor"] = Field(..., example="Major")

class UserIn(BaseModel):
    user_id: str = Field(..., example="DM_002")
    full_name: str = Field(..., example="Jane Doe")
    email: Optional[str] = Field(None, example="jane@study.com")
    role: Literal["ADMIN","DM","MONITOR","INVESTIGATOR","SITE_STAFF","CRA"]
    password: str = Field(..., example="Pass@1234")

# ── Auth helpers ──────────────────────────────────────────────

def get_current_user(token: str = Query(..., description="Auth token from /auth/login")):
    row = db_exec(f"SELECT user_id, study_id FROM global_sessions WHERE token={PH}", (token,), fetchone=True)
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please login again.")
    user = db_exec(f"SELECT user_id, full_name, role FROM global_users WHERE user_id={PH}", (row["user_id"],), fetchone=True)
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    user["study_id"] = row["study_id"]
    return user

def log_audit(study_id, user_id, action, table_name, record_id, field_name=None, old_value=None, new_value=None, reason=None):
    db_exec(
        f"INSERT INTO audit_trail (study_id,event_time,table_name,record_id,field_name,old_value,new_value,action,performed_by,reason) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
        (study_id, datetime.utcnow().isoformat()+"Z", table_name, record_id, field_name, old_value, new_value, action, user_id, reason),
        commit=True
    )

# ── Validation Rules ──────────────────────────────────────────

VS_RULES = [
    ("sysbp",    "SysBP",       60,  200,  "Critical"),
    ("diabp",    "DiaBP",       40,  130,  "Critical"),
    ("pulse",    "Pulse",       30,  150,  "Major"),
    ("temp",     "Temperature", 34.0,40.5, "Major"),
    ("weight",   "Weight",       3,  300,  "Minor"),
    ("resp_rate","Resp Rate",    8,   40,  "Minor"),
]

LB_RULES = [
    ("hgb",        "Hemoglobin",  4.0,  20.0, "Major"),
    ("wbc",        "WBC",         1.0,  50.0, "Major"),
    ("plt",        "Platelets",   10,   900,  "Major"),
    ("alt",        "ALT",         0,    500,  "Major"),
    ("ast",        "AST",         0,    500,  "Major"),
    ("creatinine", "Creatinine",  0.3,  15.0, "Critical"),
    ("glucose",    "Glucose",     40,   600,  "Critical"),
]

def auto_raise_query(study_id, usubjid, domain, visit_num, field, value, issue, severity, user_id):
    try:
        site = db_exec(f"SELECT site_id FROM subjects WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
        site_id = site["site_id"] if site else None
        count = db_exec(f"SELECT COUNT(*) as c FROM queries WHERE study_id={PH}", (study_id,), fetchone=True)
        qid = f"QRY-{(count['c'] if count else 0)+1:04d}"
        ts = datetime.utcnow().isoformat() + "Z"
        db_exec(
            f"INSERT INTO queries (query_id,study_id,usubjid,site_id,domain,visit_num,field,value,issue,severity,status,raised_by,raised_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (qid, study_id, usubjid, site_id, domain, visit_num, field, str(value), issue, severity, "Open", user_id, ts),
            commit=True
        )
        log_audit(study_id, user_id, "AUTO_QUERY_RAISED", "queries", qid)
    except Exception:
        pass

def validate_vs(study_id, usubjid, visit_num, data: dict, user_id: str):
    flags = []
    for field, label, lo, hi, sev in VS_RULES:
        val = data.get(field)
        if val is not None:
            if val < lo or val > hi:
                issue = f"{label} value {val} is outside normal range ({lo}–{hi})"
                auto_raise_query(study_id, usubjid, "VS", visit_num, field.upper(), val, issue, sev, user_id)
                flags.append({"field": field, "value": val, "issue": issue, "severity": sev})
    return flags

def validate_lb(study_id, usubjid, visit_num, data: dict, user_id: str):
    flags = []
    for field, label, lo, hi, sev in LB_RULES:
        val = data.get(field)
        if val is not None:
            if val < lo or val > hi:
                issue = f"{label} value {val} is outside normal range ({lo}–{hi})"
                auto_raise_query(study_id, usubjid, "LB", visit_num, field.upper(), val, issue, sev, user_id)
                flags.append({"field": field, "value": val, "issue": issue, "severity": sev})
    return flags

def validate_ae(study_id, usubjid, data: dict, user_id: str):
    flags = []
    if data.get("aeser") == "Y" and data.get("aeout") in (None, "", "RECOVERED/RESOLVED") and data.get("aesdth") == "Y":
        issue = "SAE marked as fatal but outcome shows recovered — please verify"
        auto_raise_query(study_id, usubjid, "AE", None, "AEOUT", data.get("aeout",""), issue, "Critical", user_id)
        flags.append({"field": "aeout", "issue": issue, "severity": "Critical"})
    if data.get("aeser") == "Y" and data.get("aesev") == "MILD":
        issue = "SAE (serious=Y) flagged as MILD severity — please verify"
        auto_raise_query(study_id, usubjid, "AE", None, "AESEV", "MILD", issue, "Major", user_id)
        flags.append({"field": "aesev", "issue": issue, "severity": "Major"})
    return flags

# ── Startup ───────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    # Seed default admin if not exists
    existing = db_exec(f"SELECT user_id FROM global_users WHERE user_id={PH}", ("ADMIN",), fetchone=True)
    if not existing:
        db_exec(
            f"INSERT INTO global_users (user_id, full_name, email, role, password_hash) VALUES ({PH},{PH},{PH},{PH},{PH}) ON CONFLICT (user_id) DO NOTHING",
            ("ADMIN", "System Administrator", "admin@mini-edc.com", "ADMIN", hash_password("Admin@1234")),
            commit=True
        )

# ── Routes: Auth ──────────────────────────────────────────────

@app.post("/auth/login", response_model=LoginResponse, tags=["auth"], summary="Login")
def login(req: LoginRequest):
    user = db_exec(f"SELECT * FROM global_users WHERE user_id={PH} AND is_active=1", (req.user_id,), fetchone=True)
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    if user["password_hash"] != hash_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    token = make_token(req.user_id)
    db_exec(f"INSERT INTO global_sessions (token, user_id, created_at) VALUES ({PH},{PH},{PH})", (token, req.user_id, datetime.utcnow().isoformat()), commit=True)
    db_exec(f"UPDATE global_users SET last_login={PH} WHERE user_id={PH}", (datetime.utcnow().isoformat(), req.user_id), commit=True)
    log_audit(None, req.user_id, "LOGIN", "global_sessions", req.user_id)
    return {"token": token, "user_id": user["user_id"], "full_name": user["full_name"], "role": user["role"], "message": f"Welcome, {user['full_name']}!"}

@app.post("/auth/logout", tags=["auth"], summary="Logout")
def logout(current_user: dict = Depends(get_current_user), token: str = Query(...)):
    db_exec(f"DELETE FROM global_sessions WHERE token={PH}", (token,), commit=True)
    log_audit(None, current_user["user_id"], "LOGOUT", "global_sessions", current_user["user_id"])
    return {"message": f"{current_user['user_id']} logged out successfully"}

@app.post("/auth/users", tags=["auth"], summary="Create a new user (Admin only)")
def create_user(user: UserIn, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin only")
    existing = db_exec(f"SELECT user_id FROM global_users WHERE user_id={PH}", (user.user_id,), fetchone=True)
    if existing:
        raise HTTPException(status_code=409, detail=f"User {user.user_id} already exists")
    db_exec(
        f"INSERT INTO global_users (user_id, full_name, email, role, password_hash) VALUES ({PH},{PH},{PH},{PH},{PH})",
        (user.user_id, user.full_name, user.email, user.role, hash_password(user.password)),
        commit=True
    )
    log_audit(None, current_user["user_id"], "USER_CREATE", "global_users", user.user_id)
    return {"message": f"User {user.user_id} created successfully", "user_id": user.user_id, "role": user.role}

@app.get("/auth/users", tags=["auth"], summary="List all users (Admin only)")
def list_users(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin only")
    return db_exec("SELECT user_id, full_name, email, role, is_active, last_login FROM global_users ORDER BY user_id", fetchall=True) or []

# ── Routes: Studies ───────────────────────────────────────────

@app.post("/studies", tags=["studies"], summary="Create a new study", status_code=201)
def create_study(study: StudyIn, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("ADMIN", "DM"):
        raise HTTPException(status_code=403, detail="Admin or DM only")
    existing = db_exec(f"SELECT study_id FROM studies WHERE study_id={PH}", (study.study_id,), fetchone=True)
    if existing:
        raise HTTPException(status_code=409, detail=f"Study {study.study_id} already exists")
    db_exec(
        f"INSERT INTO studies (study_id, study_title, protocol_no, phase, status, sponsor, indication, created_by) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
        (study.study_id, study.study_title, study.protocol_no, study.phase, "ACTIVE", study.sponsor, study.indication, current_user["user_id"]),
        commit=True
    )
    log_audit(study.study_id, current_user["user_id"], "STUDY_CREATE", "studies", study.study_id)
    return {"message": f"Study {study.study_id} created", **study.dict(), "status": "ACTIVE"}

@app.get("/studies", tags=["studies"], summary="List all studies")
def list_studies(current_user: dict = Depends(get_current_user)):
    return db_exec("SELECT * FROM studies ORDER BY created_at DESC", fetchall=True) or []

@app.get("/studies/{study_id}", tags=["studies"], summary="Get study details")
def get_study(study_id: str, current_user: dict = Depends(get_current_user)):
    study = db_exec(f"SELECT * FROM studies WHERE study_id={PH}", (study_id,), fetchone=True)
    if not study:
        raise HTTPException(status_code=404, detail=f"Study {study_id} not found")
    sites = db_exec(f"SELECT * FROM sites WHERE study_id={PH}", (study_id,), fetchall=True) or []
    visits = db_exec(f"SELECT * FROM protocol_visits WHERE study_id={PH} ORDER BY visit_num", (study_id,), fetchall=True) or []
    subj_count = db_exec(f"SELECT COUNT(*) as c FROM subjects WHERE study_id={PH}", (study_id,), fetchone=True)
    return {**study, "sites": sites, "protocol_visits": visits, "subject_count": subj_count["c"] if subj_count else 0}

# ── Routes: Sites ─────────────────────────────────────────────

@app.post("/studies/{study_id}/sites", tags=["sites"], summary="Add a site to a study", status_code=201)
def add_site(study_id: str, site: SiteIn, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("ADMIN", "DM"):
        raise HTTPException(status_code=403, detail="Admin or DM only")
    study = db_exec(f"SELECT study_id FROM studies WHERE study_id={PH}", (study_id,), fetchone=True)
    if not study:
        raise HTTPException(status_code=404, detail=f"Study {study_id} not found")
    existing = db_exec(f"SELECT site_id FROM sites WHERE site_id={PH} AND study_id={PH}", (site.site_id, study_id), fetchone=True)
    if existing:
        raise HTTPException(status_code=409, detail=f"Site {site.site_id} already exists in {study_id}")
    db_exec(
        f"INSERT INTO sites (site_id, study_id, site_name, investigator, country, city, status, activated_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
        (site.site_id, study_id, site.site_name, site.investigator, site.country, site.city, "ACTIVE", datetime.utcnow().isoformat()),
        commit=True
    )
    log_audit(study_id, current_user["user_id"], "SITE_ADD", "sites", site.site_id)
    return {"message": f"Site {site.site_id} added to {study_id}", "site_id": site.site_id, "study_id": study_id, **site.dict()}

@app.get("/studies/{study_id}/sites", tags=["sites"], summary="List all sites for a study")
def list_sites(study_id: str, current_user: dict = Depends(get_current_user)):
    return db_exec(f"SELECT * FROM sites WHERE study_id={PH} ORDER BY site_id", (study_id,), fetchall=True) or []

# ── Routes: Protocol Visits ───────────────────────────────────

@app.get("/studies/{study_id}/protocol", tags=["visits"], summary="Get protocol visit schedule")
def get_protocol(study_id: str, current_user: dict = Depends(get_current_user)):
    visits = db_exec(f"SELECT * FROM protocol_visits WHERE study_id={PH} ORDER BY visit_num", (study_id,), fetchall=True)
    if not visits:
        raise HTTPException(status_code=404, detail=f"No protocol visits found for {study_id}")
    return {"study_id": study_id, "visit_count": len(visits), "visits": visits}

# ── Routes: Subjects ──────────────────────────────────────────

@app.post("/studies/{study_id}/subjects", tags=["subjects"], summary="Enroll a subject", status_code=201)
def enroll_subject(study_id: str, subject: SubjectIn, current_user: dict = Depends(get_current_user)):
    study = db_exec(f"SELECT study_id FROM studies WHERE study_id={PH}", (study_id,), fetchone=True)
    if not study:
        raise HTTPException(status_code=404, detail=f"Study {study_id} not found")
    existing = db_exec(f"SELECT usubjid FROM subjects WHERE usubjid={PH} AND study_id={PH}", (subject.usubjid, study_id), fetchone=True)
    if existing:
        raise HTTPException(status_code=409, detail=f"Subject {subject.usubjid} already enrolled")
    ts = datetime.utcnow().isoformat() + "Z"
    db_exec(
        f"INSERT INTO subjects (usubjid, study_id, site_id, subjid, initials, sex, race, ethnic, country, consent_date, enroll_date, status, created_at, created_by) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
        (subject.usubjid, study_id, subject.site_id, subject.subjid, subject.initials, subject.sex, subject.race, subject.ethnic, subject.country, subject.consent_date, subject.enroll_date, "ENROLLED", ts, current_user["user_id"]),
        commit=True
    )
    # Create planned visits for subject
    visits = db_exec(f"SELECT visit_num, visit_name FROM protocol_visits WHERE study_id={PH}", (study_id,), fetchall=True) or []
    for v in visits:
        db_exec(
            f"INSERT INTO subject_visits (usubjid, study_id, site_id, visit_num, visit_name, status) VALUES ({PH},{PH},{PH},{PH},{PH},{PH}) ON CONFLICT (usubjid, study_id, visit_num) DO NOTHING",
            (subject.usubjid, study_id, subject.site_id, v["visit_num"], v["visit_name"], "PLANNED"),
            commit=True
        )
    log_audit(study_id, current_user["user_id"], "SUBJECT_ENROLL", "subjects", subject.usubjid, reason=f"Enrolled at {subject.site_id}")
    return {**subject.dict(), "study_id": study_id, "status": "ENROLLED", "enrolled_at": ts}

@app.get("/studies/{study_id}/subjects", tags=["subjects"], summary="List all subjects in a study")
def list_subjects(
    study_id: str,
    site_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    sql = f"SELECT * FROM subjects WHERE study_id={PH}"
    params = [study_id]
    if site_id:
        sql += f" AND site_id={PH}"; params.append(site_id)
    if status:
        sql += f" AND status={PH}"; params.append(status)
    sql += " ORDER BY usubjid"
    return db_exec(sql, tuple(params), fetchall=True) or []

@app.get("/studies/{study_id}/subjects/{usubjid}", tags=["subjects"], summary="Get subject details with visit schedule")
def get_subject(study_id: str, usubjid: str, current_user: dict = Depends(get_current_user)):
    subject = db_exec(f"SELECT * FROM subjects WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject {usubjid} not found")
    visits = db_exec(f"SELECT * FROM subject_visits WHERE usubjid={PH} AND study_id={PH} ORDER BY visit_num", (usubjid, study_id), fetchall=True) or []
    queries = db_exec(f"SELECT * FROM queries WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchall=True) or []
    return {**subject, "visits": visits, "queries": queries}

@app.patch("/studies/{study_id}/subjects/{usubjid}/status", tags=["subjects"], summary="Update subject status")
def update_subject_status(study_id: str, usubjid: str, update: SubjectStatusUpdate, current_user: dict = Depends(get_current_user)):
    subject = db_exec(f"SELECT status FROM subjects WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject {usubjid} not found")
    old_status = subject["status"]
    db_exec(f"UPDATE subjects SET status={PH}, withdraw_reason={PH} WHERE usubjid={PH} AND study_id={PH}", (update.status, update.withdraw_reason, usubjid, study_id), commit=True)
    log_audit(study_id, current_user["user_id"], "STATUS_CHANGE", "subjects", usubjid, "status", old_status, update.status)
    return {"usubjid": usubjid, "study_id": study_id, "old_status": old_status, "new_status": update.status}

# ── Routes: Subject Visits ────────────────────────────────────

@app.get("/studies/{study_id}/subjects/{usubjid}/visits", tags=["visits"], summary="Get visit schedule for a subject")
def get_subject_visits(study_id: str, usubjid: str, current_user: dict = Depends(get_current_user)):
    return db_exec(f"SELECT * FROM subject_visits WHERE usubjid={PH} AND study_id={PH} ORDER BY visit_num", (usubjid, study_id), fetchall=True) or []

@app.patch("/studies/{study_id}/subjects/{usubjid}/visits/{visit_num}", tags=["visits"], summary="Update visit status")
def update_visit(study_id: str, usubjid: str, visit_num: int, visit_date: str = Body(..., embed=True), current_user: dict = Depends(get_current_user)):
    db_exec(f"UPDATE subject_visits SET visit_date={PH}, status='COMPLETED' WHERE usubjid={PH} AND study_id={PH} AND visit_num={PH}", (visit_date, usubjid, study_id, visit_num), commit=True)
    log_audit(study_id, current_user["user_id"], "VISIT_COMPLETE", "subject_visits", f"{usubjid}-V{visit_num}", "visit_date", None, visit_date)
    return {"usubjid": usubjid, "study_id": study_id, "visit_num": visit_num, "visit_date": visit_date, "status": "COMPLETED"}

# ── Routes: CRF ───────────────────────────────────────────────

@app.post("/studies/{study_id}/subjects/{usubjid}/crf/dm", tags=["crf"], summary="Submit Demographics CRF")
def submit_crf_dm(study_id: str, usubjid: str, crf: CRFDemographics, current_user: dict = Depends(get_current_user)):
    subject = db_exec(f"SELECT site_id FROM subjects WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject {usubjid} not found")
    site_id = subject["site_id"]
    ts = datetime.utcnow().isoformat() + "Z"
    existing = db_exec(f"SELECT id FROM crf_dm WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    if existing:
        db_exec(f"UPDATE crf_dm SET age={PH},sex={PH},race={PH},ethnic={PH},country={PH},rfstdtc={PH},rfendtc={PH},dmdtc={PH},created_by={PH},created_at={PH} WHERE usubjid={PH} AND study_id={PH}",
            (crf.age, crf.sex, crf.race, crf.ethnic, crf.country, crf.rfstdtc, crf.rfendtc, crf.dmdtc, current_user["user_id"], ts, usubjid, study_id), commit=True)
        action = "CRF_DM_UPDATE"
    else:
        db_exec(f"INSERT INTO crf_dm (usubjid,study_id,age,sex,race,ethnic,country,rfstdtc,rfendtc,dmdtc,created_by,created_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (usubjid, study_id, crf.age, crf.sex, crf.race, crf.ethnic, crf.country, crf.rfstdtc, crf.rfendtc, crf.dmdtc, current_user["user_id"], ts), commit=True)
        action = "CRF_DM_SUBMIT"
    log_audit(study_id, current_user["user_id"], action, "crf_dm", usubjid)
    return {"message": "Demographics CRF saved", "usubjid": usubjid, "study_id": study_id, **crf.dict(), "filled_by": current_user["user_id"], "filled_at": ts}

@app.get("/studies/{study_id}/subjects/{usubjid}/crf/dm", tags=["crf"], summary="Get Demographics CRF")
def get_crf_dm(study_id: str, usubjid: str, current_user: dict = Depends(get_current_user)):
    row = db_exec(f"SELECT * FROM crf_dm WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    if not row:
        raise HTTPException(status_code=404, detail="Demographics CRF not yet submitted")
    return row

@app.post("/studies/{study_id}/subjects/{usubjid}/crf/vs", tags=["crf"], summary="Submit Vital Signs CRF")
def submit_crf_vs(study_id: str, usubjid: str, crf: CRFVitalSigns, current_user: dict = Depends(get_current_user)):
    subject = db_exec(f"SELECT site_id FROM subjects WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject {usubjid} not found")
    site_id = subject["site_id"]
    ts = datetime.utcnow().isoformat() + "Z"
    existing = db_exec(f"SELECT id FROM crf_vs WHERE usubjid={PH} AND study_id={PH} AND visit_num={PH}", (usubjid, study_id, crf.visit_num), fetchone=True)
    if existing:
        db_exec(f"UPDATE crf_vs SET vsdtc={PH},sysbp={PH},diabp={PH},pulse={PH},temp={PH},weight={PH},height={PH},resp_rate={PH},created_by={PH},created_at={PH} WHERE usubjid={PH} AND study_id={PH} AND visit_num={PH}",
            (crf.vsdtc, crf.sysbp, crf.diabp, crf.pulse, crf.temp, crf.weight, crf.height, crf.resp_rate, current_user["user_id"], ts, usubjid, study_id, crf.visit_num), commit=True)
    else:
        db_exec(f"INSERT INTO crf_vs (usubjid,study_id,visit_num,visit_name,vsdtc,sysbp,diabp,pulse,temp,weight,height,resp_rate,created_by,created_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (usubjid, study_id, crf.visit_num, crf.visit_name, crf.vsdtc, crf.sysbp, crf.diabp, crf.pulse, crf.temp, crf.weight, crf.height, crf.resp_rate, current_user["user_id"], ts), commit=True)
    log_audit(study_id, current_user["user_id"], "CRF_VS_SUBMIT", "crf_vs", f"{usubjid}-V{crf.visit_num}")
    flags = validate_vs(study_id, usubjid, crf.visit_num, crf.dict(), current_user["user_id"])
    return {"message": "Vital Signs CRF saved", "usubjid": usubjid, "study_id": study_id, "visit_num": crf.visit_num, **crf.dict(), "filled_by": current_user["user_id"], "filled_at": ts, "validation_flags": flags}

@app.get("/studies/{study_id}/subjects/{usubjid}/crf/vs", tags=["crf"], summary="Get all Vital Signs CRF records")
def get_crf_vs(study_id: str, usubjid: str, current_user: dict = Depends(get_current_user)):
    return db_exec(f"SELECT * FROM crf_vs WHERE usubjid={PH} AND study_id={PH} ORDER BY visit_num", (usubjid, study_id), fetchall=True) or []

@app.post("/studies/{study_id}/subjects/{usubjid}/crf/lb", tags=["crf"], summary="Submit Laboratory CRF")
def submit_crf_lb(study_id: str, usubjid: str, crf: CRFLaboratory, current_user: dict = Depends(get_current_user)):
    subject = db_exec(f"SELECT site_id FROM subjects WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject {usubjid} not found")
    site_id = subject["site_id"]
    ts = datetime.utcnow().isoformat() + "Z"
    existing = db_exec(f"SELECT id FROM crf_lb WHERE usubjid={PH} AND study_id={PH} AND visit_num={PH}", (usubjid, study_id, crf.visit_num), fetchone=True)
    if existing:
        db_exec(f"UPDATE crf_lb SET lbdtc={PH},hgb={PH},wbc={PH},plt={PH},alt={PH},ast={PH},creatinine={PH},glucose={PH},created_by={PH},created_at={PH} WHERE usubjid={PH} AND study_id={PH} AND visit_num={PH}",
            (crf.lbdtc, crf.hgb, crf.wbc, crf.plt, crf.alt, crf.ast, crf.creatinine, crf.glucose, current_user["user_id"], ts, usubjid, study_id, crf.visit_num), commit=True)
    else:
        db_exec(f"INSERT INTO crf_lb (usubjid,study_id,visit_num,visit_name,lbdtc,hgb,wbc,plt,alt,ast,creatinine,glucose,created_by,created_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (usubjid, study_id, crf.visit_num, crf.visit_name, crf.lbdtc, crf.hgb, crf.wbc, crf.plt, crf.alt, crf.ast, crf.creatinine, crf.glucose, current_user["user_id"], ts), commit=True)
    log_audit(study_id, current_user["user_id"], "CRF_LB_SUBMIT", "crf_lb", f"{usubjid}-V{crf.visit_num}")
    flags = validate_lb(study_id, usubjid, crf.visit_num, crf.dict(), current_user["user_id"])
    return {"message": "Laboratory CRF saved", "usubjid": usubjid, "study_id": study_id, "visit_num": crf.visit_num, **crf.dict(), "filled_by": current_user["user_id"], "filled_at": ts, "validation_flags": flags}

@app.get("/studies/{study_id}/subjects/{usubjid}/crf/lb", tags=["crf"], summary="Get all Laboratory CRF records")
def get_crf_lb(study_id: str, usubjid: str, current_user: dict = Depends(get_current_user)):
    return db_exec(f"SELECT * FROM crf_lb WHERE usubjid={PH} AND study_id={PH} ORDER BY visit_num", (usubjid, study_id), fetchall=True) or []

@app.post("/studies/{study_id}/subjects/{usubjid}/crf/ae", tags=["crf"], summary="Submit Adverse Event CRF")
def submit_crf_ae(study_id: str, usubjid: str, crf: CRFAdverseEvent, current_user: dict = Depends(get_current_user)):
    subject = db_exec(f"SELECT site_id FROM subjects WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject {usubjid} not found")
    site_id = subject["site_id"]
    ts = datetime.utcnow().isoformat() + "Z"
    db_exec(f"INSERT INTO crf_ae (usubjid,study_id,aeterm,aedecod,aebodsys,aestdtc,aeendtc,aesev,aeser,aerel,aeout,aesdth,created_by,created_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
        (usubjid, study_id, crf.aeterm, crf.aedecod, crf.aebodsys, crf.aestdtc, crf.aeendtc, crf.aesev, crf.aeser, crf.aerel, crf.aeout, crf.aesdth, current_user["user_id"], ts), commit=True)
    log_audit(study_id, current_user["user_id"], "CRF_AE_SUBMIT", "crf_ae", usubjid)
    flags = validate_ae(study_id, usubjid, crf.dict(), current_user["user_id"])
    return {"message": "Adverse Event CRF saved", "usubjid": usubjid, "study_id": study_id, **crf.dict(), "created_by": current_user["user_id"], "created_at": ts, "validation_flags": flags}

@app.get("/studies/{study_id}/subjects/{usubjid}/crf/ae", tags=["crf"], summary="Get all Adverse Event CRF records")
def get_crf_ae(study_id: str, usubjid: str, current_user: dict = Depends(get_current_user)):
    return db_exec(f"SELECT * FROM crf_ae WHERE usubjid={PH} AND study_id={PH} ORDER BY id", (usubjid, study_id), fetchall=True) or []

@app.post("/studies/{study_id}/subjects/{usubjid}/crf/ex", tags=["crf"], summary="Submit Exposure CRF")
def submit_crf_ex(study_id: str, usubjid: str, crf: CRFExposure, current_user: dict = Depends(get_current_user)):
    subject = db_exec(f"SELECT site_id FROM subjects WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject {usubjid} not found")
    site_id = subject["site_id"]
    ts = datetime.utcnow().isoformat() + "Z"
    existing = db_exec(f"SELECT id FROM crf_ex WHERE usubjid={PH} AND study_id={PH} AND visit_num={PH}", (usubjid, study_id, crf.visit_num), fetchone=True)
    if existing:
        db_exec(f"UPDATE crf_ex SET extrt={PH},exdose={PH},exdosu={PH},exdosfrq={PH},exroute={PH},exstdtc={PH},exendtc={PH},ex_reason_mod={PH},created_by={PH},created_at={PH} WHERE usubjid={PH} AND study_id={PH} AND visit_num={PH}",
            (crf.extrt, crf.exdose, crf.exdosu, crf.exdosfrq, crf.exroute, crf.exstdtc, crf.exendtc, crf.ex_reason_mod, current_user["user_id"], ts, usubjid, study_id, crf.visit_num), commit=True)
    else:
        db_exec(f"INSERT INTO crf_ex (usubjid,study_id,visit_num,visit_name,extrt,exdose,exdosu,exdosfrq,exroute,exstdtc,exendtc,ex_reason_mod,created_by,created_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (usubjid, study_id, crf.visit_num, crf.visit_name, crf.extrt, crf.exdose, crf.exdosu, crf.exdosfrq, crf.exroute, crf.exstdtc, crf.exendtc, crf.ex_reason_mod, current_user["user_id"], ts), commit=True)
    log_audit(study_id, current_user["user_id"], "CRF_EX_SUBMIT", "crf_ex", f"{usubjid}-V{crf.visit_num}")
    return {"message": "Exposure CRF saved", "usubjid": usubjid, "study_id": study_id, "visit_num": crf.visit_num, **crf.dict(), "created_by": current_user["user_id"], "created_at": ts}

@app.get("/studies/{study_id}/subjects/{usubjid}/crf/ex", tags=["crf"], summary="Get all Exposure CRF records")
def get_crf_ex(study_id: str, usubjid: str, current_user: dict = Depends(get_current_user)):
    return db_exec(f"SELECT * FROM crf_ex WHERE usubjid={PH} AND study_id={PH} ORDER BY visit_num", (usubjid, study_id), fetchall=True) or []

@app.post("/studies/{study_id}/subjects/{usubjid}/crf/cm", tags=["crf"], summary="Submit Concomitant Medication CRF")
def submit_crf_cm(study_id: str, usubjid: str, crf: CRFConcomitantMed, current_user: dict = Depends(get_current_user)):
    subject = db_exec(f"SELECT site_id FROM subjects WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject {usubjid} not found")
    site_id = subject["site_id"]
    ts = datetime.utcnow().isoformat() + "Z"
    db_exec(f"INSERT INTO crf_cm (usubjid,study_id,cmtrt,cmdose,cmdosu,cmroute,cmstdtc,cmendtc,cmindc,created_by,created_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
        (usubjid, study_id, crf.cmtrt, crf.cmdose, crf.cmdosu, crf.cmroute, crf.cmstdtc, crf.cmendtc, crf.cmindc, current_user["user_id"], ts), commit=True)
    log_audit(study_id, current_user["user_id"], "CRF_CM_SUBMIT", "crf_cm", usubjid)
    return {"message": "Concomitant Medication CRF saved", "usubjid": usubjid, **crf.dict(), "created_by": current_user["user_id"], "created_at": ts}

@app.get("/studies/{study_id}/subjects/{usubjid}/crf/cm", tags=["crf"], summary="Get all Concomitant Medication records")
def get_crf_cm(study_id: str, usubjid: str, current_user: dict = Depends(get_current_user)):
    return db_exec(f"SELECT * FROM crf_cm WHERE usubjid={PH} AND study_id={PH} ORDER BY id", (usubjid, study_id), fetchall=True) or []

# ── CRF Edit Endpoints ────────────────────────────────────────

@app.patch("/studies/{study_id}/subjects/{usubjid}/crf/vs/{visit_num}", tags=["crf"], summary="Edit Vital Signs CRF record")
def edit_crf_vs(study_id: str, usubjid: str, visit_num: int, crf: CRFVitalSigns, current_user: dict = Depends(get_current_user)):
    existing = db_exec(f"SELECT * FROM crf_vs WHERE usubjid={PH} AND study_id={PH} AND visit_num={PH}", (usubjid, study_id, visit_num), fetchone=True)
    if not existing:
        raise HTTPException(status_code=404, detail="VS record not found")
    ts = datetime.utcnow().isoformat() + "Z"
    for field in ["sysbp","diabp","pulse","temp","weight","height","resp_rate"]:
        old = existing.get(field); new = getattr(crf, field, None)
        if old != new:
            log_audit(study_id, current_user["user_id"], "CRF_VS_EDIT", "crf_vs", f"{usubjid}-V{visit_num}", field, str(old), str(new))
    db_exec(f"UPDATE crf_vs SET vsdtc={PH},sysbp={PH},diabp={PH},pulse={PH},temp={PH},weight={PH},height={PH},resp_rate={PH},created_by={PH},created_at={PH} WHERE usubjid={PH} AND study_id={PH} AND visit_num={PH}",
        (crf.vsdtc, crf.sysbp, crf.diabp, crf.pulse, crf.temp, crf.weight, crf.height, crf.resp_rate, current_user["user_id"], ts, usubjid, study_id, visit_num), commit=True)
    flags = validate_vs(study_id, usubjid, visit_num, crf.dict(), current_user["user_id"])
    return {"message": "VS record updated", "validation_flags": flags}

@app.patch("/studies/{study_id}/subjects/{usubjid}/crf/lb/{visit_num}", tags=["crf"], summary="Edit Laboratory CRF record")
def edit_crf_lb(study_id: str, usubjid: str, visit_num: int, crf: CRFLaboratory, current_user: dict = Depends(get_current_user)):
    existing = db_exec(f"SELECT * FROM crf_lb WHERE usubjid={PH} AND study_id={PH} AND visit_num={PH}", (usubjid, study_id, visit_num), fetchone=True)
    if not existing:
        raise HTTPException(status_code=404, detail="LB record not found")
    ts = datetime.utcnow().isoformat() + "Z"
    for field in ["hgb","wbc","plt","alt","ast","creatinine","glucose"]:
        old = existing.get(field); new = getattr(crf, field, None)
        if old != new:
            log_audit(study_id, current_user["user_id"], "CRF_LB_EDIT", "crf_lb", f"{usubjid}-V{visit_num}", field, str(old), str(new))
    db_exec(f"UPDATE crf_lb SET lbdtc={PH},hgb={PH},wbc={PH},plt={PH},alt={PH},ast={PH},creatinine={PH},glucose={PH},created_by={PH},created_at={PH} WHERE usubjid={PH} AND study_id={PH} AND visit_num={PH}",
        (crf.lbdtc, crf.hgb, crf.wbc, crf.plt, crf.alt, crf.ast, crf.creatinine, crf.glucose, current_user["user_id"], ts, usubjid, study_id, visit_num), commit=True)
    flags = validate_lb(study_id, usubjid, visit_num, crf.dict(), current_user["user_id"])
    return {"message": "LB record updated", "validation_flags": flags}

@app.patch("/studies/{study_id}/subjects/{usubjid}/crf/dm", tags=["crf"], summary="Edit Demographics CRF")
def edit_crf_dm(study_id: str, usubjid: str, crf: CRFDemographics, current_user: dict = Depends(get_current_user)):
    existing = db_exec(f"SELECT * FROM crf_dm WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    if not existing:
        raise HTTPException(status_code=404, detail="DM record not found")
    ts = datetime.utcnow().isoformat() + "Z"
    for field in ["age","sex","race","ethnic","country","rfstdtc","rfendtc","dmdtc"]:
        old = existing.get(field); new = getattr(crf, field, None)
        if str(old) != str(new):
            log_audit(study_id, current_user["user_id"], "CRF_DM_EDIT", "crf_dm", usubjid, field, str(old), str(new))
    db_exec(f"UPDATE crf_dm SET age={PH},sex={PH},race={PH},ethnic={PH},country={PH},rfstdtc={PH},rfendtc={PH},dmdtc={PH},created_by={PH},created_at={PH} WHERE usubjid={PH} AND study_id={PH}",
        (crf.age, crf.sex, crf.race, crf.ethnic, crf.country, crf.rfstdtc, crf.rfendtc, crf.dmdtc, current_user["user_id"], ts, usubjid, study_id), commit=True)
    return {"message": "DM record updated"}

# ── Data Completeness ─────────────────────────────────────────

@app.get("/studies/{study_id}/subjects/{usubjid}/completeness", tags=["crf"], summary="Check CRF completeness for a subject")
def check_completeness(study_id: str, usubjid: str, current_user: dict = Depends(get_current_user)):
    completed_visits = db_exec(f"SELECT visit_num FROM subject_visits WHERE usubjid={PH} AND study_id={PH} AND status='COMPLETED'", (usubjid, study_id), fetchall=True) or []
    completed_nums = [v["visit_num"] for v in completed_visits]
    has_dm = db_exec(f"SELECT id FROM crf_dm WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchone=True)
    vs_visits = {r["visit_num"] for r in (db_exec(f"SELECT visit_num FROM crf_vs WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchall=True) or [])}
    lb_visits = {r["visit_num"] for r in (db_exec(f"SELECT visit_num FROM crf_lb WHERE usubjid={PH} AND study_id={PH}", (usubjid, study_id), fetchall=True) or [])}
    missing = []
    if not has_dm:
        missing.append({"domain": "DM", "visit_num": None, "issue": "Demographics CRF not submitted"})
    for vnum in completed_nums:
        if vnum not in vs_visits:
            missing.append({"domain": "VS", "visit_num": vnum, "issue": f"Vital Signs missing for completed visit {vnum}"})
        if vnum not in lb_visits:
            missing.append({"domain": "LB", "visit_num": vnum, "issue": f"Lab results missing for completed visit {vnum}"})
    total_expected = 1 + (len(completed_nums) * 2)
    total_present = (1 if has_dm else 0) + len(vs_visits) + len(lb_visits)
    pct = round((total_present / total_expected * 100) if total_expected > 0 else 100, 1)
    return {"usubjid": usubjid, "study_id": study_id, "completed_visits": len(completed_nums), "completeness_pct": pct, "missing": missing}

@app.get("/studies/{study_id}/completeness", tags=["crf"], summary="Completeness summary for all subjects in a study")
def study_completeness(study_id: str, current_user: dict = Depends(get_current_user)):
    subjects = db_exec(f"SELECT usubjid FROM subjects WHERE study_id={PH}", (study_id,), fetchall=True) or []
    results = []
    for s in subjects:
        uid = s["usubjid"]
        completed_visits = db_exec(f"SELECT visit_num FROM subject_visits WHERE usubjid={PH} AND study_id={PH} AND status='COMPLETED'", (uid, study_id), fetchall=True) or []
        completed_nums = [v["visit_num"] for v in completed_visits]
        has_dm = bool(db_exec(f"SELECT id FROM crf_dm WHERE usubjid={PH} AND study_id={PH}", (uid, study_id), fetchone=True))
        vs_count = (db_exec(f"SELECT COUNT(*) as c FROM crf_vs WHERE usubjid={PH} AND study_id={PH}", (uid, study_id), fetchone=True) or {}).get("c", 0)
        lb_count = (db_exec(f"SELECT COUNT(*) as c FROM crf_lb WHERE usubjid={PH} AND study_id={PH}", (uid, study_id), fetchone=True) or {}).get("c", 0)
        total_expected = 1 + (len(completed_nums) * 2)
        total_present = (1 if has_dm else 0) + vs_count + lb_count
        pct = round((total_present / total_expected * 100) if total_expected > 0 else 100, 1)
        results.append({"usubjid": uid, "completed_visits": len(completed_nums), "completeness_pct": pct, "has_dm": has_dm})
    return sorted(results, key=lambda x: x["completeness_pct"])

@app.post("/studies/{study_id}/queries", tags=["queries"], summary="Raise a data query", status_code=201)
def raise_query(study_id: str, q: QueryIn, current_user: dict = Depends(get_current_user)):
    count = db_exec(f"SELECT COUNT(*) as c FROM queries WHERE study_id={PH}", (study_id,), fetchone=True)
    qid = f"QRY-{(count['c'] if count else 0)+1:04d}"
    ts = datetime.utcnow().isoformat() + "Z"
    site = db_exec(f"SELECT site_id FROM subjects WHERE usubjid={PH} AND study_id={PH}", (q.usubjid, study_id), fetchone=True)
    site_id = site["site_id"] if site else None
    db_exec(
        f"INSERT INTO queries (query_id,study_id,usubjid,site_id,domain,visit_num,field,value,issue,severity,status,raised_by,raised_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
        (qid, study_id, q.usubjid, site_id, q.domain, q.visit_num, q.field, q.value, q.issue, q.severity, "Open", current_user["user_id"], ts),
        commit=True
    )
    log_audit(study_id, current_user["user_id"], "QUERY_RAISED", "queries", qid)
    return {"query_id": qid, "study_id": study_id, **q.dict(), "status": "Open", "raised_by": current_user["user_id"], "raised_at": ts}

@app.get("/studies/{study_id}/queries", tags=["queries"], summary="List all queries for a study")
def list_queries(study_id: str, status: Optional[str] = Query(None), usubjid: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
    sql = f"SELECT * FROM queries WHERE study_id={PH}"
    params = [study_id]
    if status:
        sql += f" AND status={PH}"; params.append(status)
    if usubjid:
        sql += f" AND usubjid={PH}"; params.append(usubjid)
    sql += " ORDER BY raised_at DESC"
    return db_exec(sql, tuple(params), fetchall=True) or []

@app.get("/studies/{study_id}/protocol-visits")
def get_protocol_visits(
    study_id: str,
    current_user: dict = Depends(get_current_user)
):

    visits = db_exec(
        f"""
        SELECT
            visit_num,
            visit_name,
            visit_window_before,
            visit_window_after,
            is_required
        FROM protocol_visits
        WHERE study_id={PH}
        ORDER BY visit_num
        """,
        (study_id,),
        fetchall=True
    ) or []

    return visits
@app.patch("/studies/{study_id}/queries/{query_id}/close", tags=["queries"], summary="Close an answered query")
def close_query(study_id: str, query_id: str, current_user: dict = Depends(get_current_user)):
    q = db_exec(f"SELECT * FROM queries WHERE query_id={PH} AND study_id={PH}", (query_id, study_id), fetchone=True)
    if not q:
        raise HTTPException(status_code=404, detail=f"Query {query_id} not found")
    if q["status"] != "Answered":
        raise HTTPException(status_code=400, detail="Only Answered queries can be closed")
    ts = datetime.utcnow().isoformat() + "Z"
    db_exec(f"UPDATE queries SET status='Closed', closed_by={PH}, closed_at={PH} WHERE query_id={PH} AND study_id={PH}",
        (current_user["user_id"], ts, query_id, study_id), commit=True)
    log_audit(study_id, current_user["user_id"], "QUERY_CLOSED", "queries", query_id)
    return {"query_id": query_id, "status": "Closed", "closed_by": current_user["user_id"], "closed_at": ts}

# ── Routes: Audit ─────────────────────────────────────────────

@app.get("/studies/{study_id}/audit", tags=["audit"], summary="Get audit trail for a study")
def get_audit(study_id: str, limit: int = Query(100, ge=1, le=500), current_user: dict = Depends(get_current_user)):
    return db_exec(f"SELECT * FROM audit_trail WHERE study_id={PH} ORDER BY event_time DESC LIMIT {PH}", (study_id, limit), fetchall=True) or []

# ── Routes: System ────────────────────────────────────────────

@app.get("/health", tags=["system"], summary="Health check")
def health():
    return {"status": "healthy", "version": "2.0.0", "phase": "F", "timestamp": datetime.utcnow().isoformat()+"Z"}

@app.get("/studies/{study_id}/stats", tags=["system"], summary="Study statistics")
def study_stats(study_id: str, current_user: dict = Depends(get_current_user)):
    subj = db_exec(f"SELECT status, COUNT(*) as c FROM subjects WHERE study_id={PH} GROUP BY status", (study_id,), fetchall=True) or []
    subj_map = {r["status"]: r["c"] for r in subj}
    qry = db_exec(f"SELECT status, COUNT(*) as c FROM queries WHERE study_id={PH} GROUP BY status", (study_id,), fetchall=True) or []
    qry_map = {r["status"]: r["c"] for r in qry}
    ae_count = db_exec(f"SELECT COUNT(*) as c FROM crf_ae WHERE study_id={PH}", (study_id,), fetchone=True)
    sae_count = db_exec(f"SELECT COUNT(*) as c FROM crf_ae WHERE study_id={PH} AND aeser='Y'", (study_id,), fetchone=True)
    return {
        "study_id": study_id,
        "subjects": {"total": sum(subj_map.values()), "enrolled": subj_map.get("ENROLLED",0), "completed": subj_map.get("COMPLETED",0), "withdrawn": subj_map.get("WITHDRAWN",0), "screen_failed": subj_map.get("SCREEN_FAILED",0)},
        "queries": {"total": sum(qry_map.values()), "open": qry_map.get("Open",0), "answered": qry_map.get("Answered",0), "closed": qry_map.get("Closed",0)},
        "adverse_events": {"total": ae_count["c"] if ae_count else 0, "serious": sae_count["c"] if sae_count else 0}
    }

@app.get("/", tags=["system"], summary="API root")
def root():
    return {"name": "Mini EDC Phase F REST API", "version": "2.0.0", "phase": "F", "docs": "/docs", "health": "/health"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
