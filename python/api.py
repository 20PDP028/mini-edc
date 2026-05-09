"""
api.py — Feature 16: REST API Layer
Exposes your CDM system as HTTP endpoints for external EDC integration.
Save in: Mini_EDC_Project/python/api.py

Run:  python api.py
Test: http://localhost:5000/api/queries
"""

from flask import Flask, request, jsonify, g
from db_connection import get_conn, is_postgres
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "sql", "cdm_phase3.db")

# ── Simple API key auth ───────────────────────────────────────
API_KEYS = {
    "CDM-KEY-DM-001": "Data Manager",
    "CDM-KEY-MON-001": "Monitor",
    "CDM-KEY-SITE-001": "Site Staff",
    "CDM-KEY-ADMIN-001": "Administrator",
}


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key not in API_KEYS:
            return jsonify({"error": "Unauthorised — invalid API key"}), 401
        g.role = API_KEYS[key]
        return f(*args, **kwargs)

    return decorated


def get_db():
    conn = get_conn()
    if not is_postgres():
        conn.execute("PRAGMA foreign_keys = ON")  # SQLite only
    return conn

def rows_to_list(rows):
    return [dict(r) for r in rows]


# ── Health Check ─────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "system": "Mini EDC CDM API",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
        }
    )


# ── Subjects ─────────────────────────────────────────────────
@app.route("/api/subjects", methods=["GET"])
@require_api_key
def get_subjects():
    siteid = request.args.get("siteid")
    with get_db() as conn:
        if siteid:
            rows = conn.execute(
                "SELECT * FROM subjects WHERE siteid=? ORDER BY usubjid", (siteid,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM subjects ORDER BY usubjid").fetchall()
    return jsonify({"count": len(rows), "subjects": rows_to_list(rows)})


@app.route("/api/subjects/<usubjid>", methods=["GET"])
@require_api_key
def get_subject(usubjid):
    with get_db() as conn:
        subject = conn.execute(
            "SELECT * FROM subjects WHERE usubjid=?", (usubjid,)
        ).fetchone()
        if not subject:
            return jsonify({"error": f"Subject {usubjid} not found"}), 404
        visits = conn.execute(
            "SELECT * FROM visits WHERE usubjid=? ORDER BY visitnum", (usubjid,)
        ).fetchall()
        aes = conn.execute(
            "SELECT * FROM adverse_events WHERE usubjid=?", (usubjid,)
        ).fetchall()
    return jsonify(
        {
            "subject": dict(subject),
            "visits": rows_to_list(visits),
            "adverse_events": rows_to_list(aes),
        }
    )


# ── Queries ──────────────────────────────────────────────────
@app.route("/api/queries", methods=["GET"])
@require_api_key
def get_queries():
    status = request.args.get("status")
    severity = request.args.get("severity")
    siteid = request.args.get("siteid")

    sql = "SELECT * FROM queries WHERE 1=1"
    params = []
    if status:
        sql += " AND status=?"
        params.append(status)
    if severity:
        sql += " AND severity=?"
        params.append(severity)
    if siteid:
        sql += " AND siteid=?"
        params.append(siteid)
    sql += " ORDER BY opened_at DESC"

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return jsonify({"count": len(rows), "queries": rows_to_list(rows)})


@app.route("/api/queries/<query_id>/answer", methods=["POST"])
@require_api_key
def answer_query(query_id):
    data = request.get_json() or {}
    answer = data.get("answer_text", "").strip()
    if not answer:
        return jsonify({"error": "answer_text is required"}), 400

    with get_db() as conn:
        q = conn.execute(
            "SELECT status FROM queries WHERE query_id=?", (query_id,)
        ).fetchone()
        if not q:
            return jsonify({"error": f"Query {query_id} not found"}), 404
        if q["status"] != "Open":
            return (
                jsonify(
                    {
                        "error": f"Query is '{q['status']}' — can only answer Open queries"
                    }
                ),
                409,
            )
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        conn.execute(
            "UPDATE queries SET status='Answered', answered_at=?, answer_text=? WHERE query_id=?",
            (now, answer, query_id),
        )
        conn.execute(
            """
            INSERT INTO audit_trail (table_name, record_id, field, old_value, new_value, action, performed_by, reason)
            VALUES ('queries', ?, 'status', 'Open', 'Answered', 'QUERY_ANSWER', ?, ?)
        """,
            (query_id, g.role, answer),
        )
    return jsonify({"success": True, "query_id": query_id, "new_status": "Answered"})


@app.route("/api/queries/<query_id>/close", methods=["POST"])
@require_api_key
def close_query(query_id):
    if g.role not in ("Data Manager", "Administrator"):
        return jsonify({"error": "Only Data Managers can close queries"}), 403

    data = request.get_json() or {}
    reason = data.get("reason", "Verified by DM")

    with get_db() as conn:
        q = conn.execute(
            "SELECT status FROM queries WHERE query_id=?", (query_id,)
        ).fetchone()
        if not q:
            return jsonify({"error": f"Query {query_id} not found"}), 404
        if q["status"] != "Answered":
            return (
                jsonify(
                    {
                        "error": f"Query is '{q['status']}' — can only close Answered queries"
                    }
                ),
                409,
            )
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        conn.execute(
            "UPDATE queries SET status='Closed', closed_at=?, closed_by=? WHERE query_id=?",
            (now, g.role, query_id),
        )
        conn.execute(
            """
            INSERT INTO audit_trail (table_name, record_id, field, old_value, new_value, action, performed_by, reason)
            VALUES ('queries', ?, 'status', 'Answered', 'Closed', 'QUERY_CLOSE', ?, ?)
        """,
            (query_id, g.role, reason),
        )
    return jsonify({"success": True, "query_id": query_id, "new_status": "Closed"})


# ── SAEs ─────────────────────────────────────────────────────
@app.route("/api/saes", methods=["GET"])
@require_api_key
def get_saes():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT ae.*, s.siteid FROM adverse_events ae
            JOIN subjects s USING(usubjid)
            WHERE ae.aeser='Y' OR ae.aesev='SEVERE'
            ORDER BY ae.created_at DESC
        """).fetchall()
    return jsonify({"count": len(rows), "saes": rows_to_list(rows)})


# ── Validate ─────────────────────────────────────────────────
@app.route("/api/validate", methods=["POST"])
@require_api_key
def validate_data():
    """
    POST JSON array of CDISC records → returns validation issues + SAEs.
    Example body: [{"USUBJID":"SUB099","AGE":145,"SEX":"X",...}]
    """
    records = request.get_json()
    if not isinstance(records, list):
        return jsonify({"error": "Body must be a JSON array of records"}), 400

    import sys

    sys.path.insert(0, os.path.dirname(__file__))
    try:
        import pandas as pd
        from validation_phase2 import validate

        df = pd.DataFrame(records)
        issues, saes = validate(df)
        return jsonify(
            {
                "record_count": len(records),
                "issue_count": len(issues),
                "sae_count": len(saes),
                "issues": issues,
                "saes": saes,
            }
        )
    except ImportError:
        return jsonify({"error": "validation_phase2.py not found in python/"}), 500


# ── Summary / Dashboard ───────────────────────────────────────
@app.route("/api/summary", methods=["GET"])
@require_api_key
def summary():
    with get_db() as conn:
        q_open = conn.execute(
            "SELECT COUNT(*) FROM queries WHERE status='Open'"
        ).fetchone()[0]
        q_ans = conn.execute(
            "SELECT COUNT(*) FROM queries WHERE status='Answered'"
        ).fetchone()[0]
        q_closed = conn.execute(
            "SELECT COUNT(*) FROM queries WHERE status='Closed'"
        ).fetchone()[0]
        q_crit = conn.execute(
            "SELECT COUNT(*) FROM queries WHERE severity='Critical' AND status='Open'"
        ).fetchone()[0]
        sae_pend = conn.execute(
            "SELECT COUNT(*) FROM adverse_events WHERE aeser='Y' AND report_flag='PENDING'"
        ).fetchone()[0]
        subjects = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        sites = conn.execute("SELECT COUNT(DISTINCT siteid) FROM subjects").fetchone()[
            0
        ]

    return jsonify(
        {
            "subjects": subjects,
            "sites": sites,
            "queries_open": q_open,
            "queries_answered": q_ans,
            "queries_closed": q_closed,
            "critical_open": q_crit,
            "saes_pending_report": sae_pend,
            "generated_at": datetime.now().isoformat(),
        }
    )


# ── Audit Trail ───────────────────────────────────────────────
@app.route("/api/audit", methods=["GET"])
@require_api_key
def audit_trail():
    if g.role not in ("Data Manager", "Administrator"):
        return (
            jsonify({"error": "Only Data Managers and Admins can view audit trail"}),
            403,
        )
    limit = int(request.args.get("limit", 50))
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_trail ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return jsonify({"count": len(rows), "audit": rows_to_list(rows)})


# ── Run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Mini EDC REST API — Feature 16")
    print("=" * 60)
    print("\n  Base URL : http://localhost:5000/api")
    print("\n  Endpoints:")
    print("    GET  /api/health")
    print("    GET  /api/summary")
    print("    GET  /api/subjects          ?siteid=SITE01")
    print("    GET  /api/subjects/<id>")
    print("    GET  /api/queries           ?status=Open&severity=Critical")
    print("    POST /api/queries/<id>/answer")
    print("    POST /api/queries/<id>/close")
    print("    GET  /api/saes")
    print("    POST /api/validate")
    print("    GET  /api/audit             ?limit=50")
    print("  API Keys (add header: X-API-Key: <key>):")
    for k, v in API_KEYS.items():
        print(f"    {k:<25} → {v}")
    print("\n" + "=" * 60 + "\n")
    app.run(debug=True, port=5000)
