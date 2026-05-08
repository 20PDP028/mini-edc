"""
Mini EDC — Phase F: Automated test suite
Run with: pytest tests/test_api.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

import pytest
from fastapi.testclient import TestClient
from api_phase_e import app, SUBJECTS, AUDIT_LOG, QUERIES, USERS

client = TestClient(app)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_state():
    """Clear all in-memory state before each test."""
    SUBJECTS.clear()
    AUDIT_LOG.clear()
    QUERIES.clear()
    for u in USERS.values():
        u["token"] = None
        u["fails"] = 0
        u["locked"] = False
    yield

@pytest.fixture
def admin_token():
    r = client.post("/auth/login", json={"username": "admin", "password": "Admin@1234"})
    return r.json()["token"]

@pytest.fixture
def monitor_token():
    r = client.post("/auth/login", json={"username": "monitor", "password": "Monitor@1234"})
    return r.json()["token"]

SAMPLE_SUBJECT = {
    "usubjid": "STUDY001-001", "age": 45, "sex": "M",
    "race": "WHITE", "country": "USA",
    "consent_date": "2024-01-15", "site_id": "SITE-01"
}

# ── System ────────────────────────────────────────────────────────────────────

class TestSystem:
    def test_health_no_auth(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_root_shows_links(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "docs" in r.json()

    def test_stats_requires_auth(self):
        r = client.get("/system/stats?token=bad_token")
        assert r.status_code == 401

# ── Auth ──────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_login_success(self):
        r = client.post("/auth/login", json={"username": "admin", "password": "Admin@1234"})
        assert r.status_code == 200
        assert "token" in r.json()
        assert r.json()["role"] == "Admin"

    def test_login_wrong_password(self):
        r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401

    def test_account_locks_after_3_fails(self):
        for _ in range(3):
            client.post("/auth/login", json={"username": "investigator", "password": "bad"})
        r = client.post("/auth/login", json={"username": "investigator", "password": "Invest@1234"})
        assert r.status_code == 403
        assert "locked" in r.json()["detail"].lower()

    def test_unknown_user(self):
        r = client.post("/auth/login", json={"username": "nobody", "password": "x"})
        assert r.status_code == 401

    def test_logout(self, admin_token):
        r = client.post(f"/auth/logout?token={admin_token}")
        assert r.status_code == 200
        # Token should now be invalid
        r = client.get(f"/subjects?token={admin_token}")
        assert r.status_code == 401

# ── Subjects ──────────────────────────────────────────────────────────────────

class TestSubjects:
    def test_enroll_subject(self, admin_token):
        r = client.post(f"/subjects?token={admin_token}", json=SAMPLE_SUBJECT)
        assert r.status_code == 201
        assert r.json()["usubjid"] == "STUDY001-001"
        assert r.json()["status"] == "ENROLLED"

    def test_duplicate_subject_rejected(self, admin_token):
        client.post(f"/subjects?token={admin_token}", json=SAMPLE_SUBJECT)
        r = client.post(f"/subjects?token={admin_token}", json=SAMPLE_SUBJECT)
        assert r.status_code == 409

    def test_list_subjects(self, admin_token):
        client.post(f"/subjects?token={admin_token}", json=SAMPLE_SUBJECT)
        r = client.get(f"/subjects?token={admin_token}")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_get_subject_by_id(self, admin_token):
        client.post(f"/subjects?token={admin_token}", json=SAMPLE_SUBJECT)
        r = client.get(f"/subjects/STUDY001-001?token={admin_token}")
        assert r.status_code == 200

    def test_subject_not_found(self, admin_token):
        r = client.get(f"/subjects/NONEXISTENT?token={admin_token}")
        assert r.status_code == 404

    def test_update_subject_status(self, admin_token):
        client.post(f"/subjects?token={admin_token}", json=SAMPLE_SUBJECT)
        r = client.patch(f"/subjects/STUDY001-001/status?token={admin_token}",
                         json={"new_status": "COMPLETED"})
        assert r.status_code == 200
        assert r.json()["new_status"] == "COMPLETED"

    def test_filter_by_site(self, admin_token):
        client.post(f"/subjects?token={admin_token}", json=SAMPLE_SUBJECT)
        r = client.get(f"/subjects?token={admin_token}&site_id=SITE-01")
        assert len(r.json()) == 1
        r2 = client.get(f"/subjects?token={admin_token}&site_id=SITE-99")
        assert len(r2.json()) == 0

# ── Validation ────────────────────────────────────────────────────────────────

class TestValidation:
    def test_clean_dm_record_no_findings(self, admin_token):
        r = client.post(f"/validation/run?token={admin_token}", json={
            "domain": "DM",
            "records": [{"USUBJID": "TEST-001", "AGE": 45, "SEX": "M",
                          "RACE": "WHITE", "ETHNIC": "NOT HISPANIC OR LATINO",
                          "COUNTRY": "USA", "RFSTDTC": "2024-01-16", "DMDTC": "2024-01-15"}]
        })
        assert r.status_code == 200
        assert r.json()["findings_count"] == 0

    def test_invalid_sex_caught(self, admin_token):
        r = client.post(f"/validation/run?token={admin_token}", json={
            "domain": "DM",
            "records": [{"USUBJID": "TEST-001", "AGE": 45, "SEX": "INVALID",
                          "RACE": "WHITE", "ETHNIC": "NOT HISPANIC OR LATINO",
                          "COUNTRY": "USA"}]
        })
        assert r.status_code == 200
        rule_ids = [f["rule_id"] for f in r.json()["findings"]]
        assert "DM001" in rule_ids

    def test_dose_before_consent_critical(self, admin_token):
        r = client.post(f"/validation/run?token={admin_token}", json={
            "domain": "DM",
            "records": [{"USUBJID": "VIOL-001", "AGE": 30, "SEX": "F",
                          "RACE": "WHITE", "ETHNIC": "NOT HISPANIC OR LATINO",
                          "COUNTRY": "USA", "RFSTDTC": "2024-01-01", "DMDTC": "2024-01-15"}]
        })
        findings = r.json()["findings"]
        crits = [f for f in findings if f["severity"] == "CRITICAL"]
        assert len(crits) >= 1

    def test_hepatotoxicity_flag_lb(self, admin_token):
        r = client.post(f"/validation/run?token={admin_token}", json={
            "domain": "LB",
            "records": [{"USUBJID": "LB-001", "LBORRES_ALT": 200, "LBSTNRHI_ALT": 40}]
        })
        rule_ids = [f["rule_id"] for f in r.json()["findings"]]
        assert "LB001" in rule_ids

    def test_rules_catalogue(self, admin_token):
        r = client.get(f"/validation/rules?token={admin_token}")
        assert r.status_code == 200
        assert r.json()["total"] >= 16

    def test_rules_filter_by_domain(self, admin_token):
        r = client.get(f"/validation/rules?token={admin_token}&domain=DM")
        for rule in r.json()["rules"]:
            assert rule["domain"] == "DM"

# ── SDTM ──────────────────────────────────────────────────────────────────────

class TestSDTM:
    def test_generate_dm_domain(self, admin_token):
        r = client.post(f"/sdtm/generate?token={admin_token}", json={"domain": "DM"})
        assert r.status_code == 200
        d = r.json()
        assert d["domain"] == "DM"
        assert d["row_count"] >= 1
        assert "USUBJID" in d["rows"][0]
        assert "AGE" in d["rows"][0]

    def test_generate_ae_domain(self, admin_token):
        r = client.post(f"/sdtm/generate?token={admin_token}", json={"domain": "AE"})
        assert r.status_code == 200
        assert "AETERM" in r.json()["rows"][0]

    def test_generate_with_specific_subjects(self, admin_token):
        r = client.post(f"/sdtm/generate?token={admin_token}",
                        json={"domain": "LB", "subjects": ["STUDY001-001"]})
        assert r.json()["row_count"] == 1

    def test_sdtm_version_is_18(self, admin_token):
        r = client.post(f"/sdtm/generate?token={admin_token}", json={"domain": "VS"})
        assert r.json()["sdtm_version"] == "1.8"

    def test_list_domains(self, admin_token):
        r = client.get(f"/sdtm/domains?token={admin_token}")
        assert r.status_code == 200
        domains = [d["domain"] for d in r.json()["supported_domains"]]
        assert "DM" in domains and "AE" in domains

# ── Audit ─────────────────────────────────────────────────────────────────────

class TestAudit:
    def test_login_creates_audit_entry(self, admin_token):
        r = client.get(f"/audit/trail?token={admin_token}")
        actions = [e["action"] for e in r.json()]
        assert "LOGIN" in actions

    def test_subject_enroll_audited(self, admin_token):
        client.post(f"/subjects?token={admin_token}", json=SAMPLE_SUBJECT)
        r = client.get(f"/audit/trail?token={admin_token}")
        actions = [e["action"] for e in r.json()]
        assert "SUBJECT_ENROLL" in actions

    def test_chain_integrity_intact(self, admin_token):
        client.post(f"/subjects?token={admin_token}", json=SAMPLE_SUBJECT)
        r = client.get(f"/audit/integrity?token={admin_token}")
        assert r.json()["status"] == "INTACT"

    def test_audit_filter_by_action(self, admin_token):
        r = client.get(f"/audit/trail?token={admin_token}&action=LOGIN")
        for entry in r.json():
            assert entry["action"] == "LOGIN"

# ── Queries ───────────────────────────────────────────────────────────────────

class TestQueries:
    SAMPLE_QUERY = {
        "usubjid": "STUDY001-001", "domain": "VS",
        "field": "VSORRES", "visit": "WEEK 4",
        "message": "Please verify this high value"
    }

    def test_raise_query(self, admin_token):
        r = client.post(f"/queries?token={admin_token}", json=self.SAMPLE_QUERY)
        assert r.status_code == 201
        assert r.json()["status"] == "OPEN"
        assert r.json()["query_id"].startswith("QRY-")

    def test_full_query_lifecycle(self, admin_token):
        r = client.post(f"/queries?token={admin_token}", json=self.SAMPLE_QUERY)
        qid = r.json()["query_id"]

        # Respond
        r = client.patch(f"/queries/{qid}/respond?token={admin_token}",
                         json={"response": "Verified OK"})
        assert r.json()["status"] == "ANSWERED"

        # Close
        r = client.patch(f"/queries/{qid}/close?token={admin_token}")
        assert r.json()["status"] == "CLOSED"
        assert r.json()["closed_at"] is not None

    def test_cannot_close_open_query(self, admin_token):
        r = client.post(f"/queries?token={admin_token}", json=self.SAMPLE_QUERY)
        qid = r.json()["query_id"]
        r = client.patch(f"/queries/{qid}/close?token={admin_token}")
        assert r.status_code == 400

    def test_filter_open_queries(self, admin_token):
        client.post(f"/queries?token={admin_token}", json=self.SAMPLE_QUERY)
        r = client.get(f"/queries?token={admin_token}&status=OPEN")
        assert all(q["status"] == "OPEN" for q in r.json())
