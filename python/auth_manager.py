"""
auth_manager.py — Authentication, Role-Based Access & E-Signature
Phase 6 Addition — 21 CFR Part 11 Compliant
Save in: Mini_EDC_Project/python/auth_manager.py
"""

import sqlite3
import hashlib
import os
import secrets
from datetime import datetime

BASE    = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, '..', 'sql', 'cdm_phase3.db')

# ── Roles & Permissions ───────────────────────────────────────
ROLES = {
    "DM":      "Data Manager",
    "MONITOR": "Clinical Monitor",
    "SITE":    "Site Staff",
    "ADMIN":   "System Administrator",
}

PERMISSIONS = {
    "DM": [
        "view_dashboard", "view_queries", "view_saes", "view_audit",
        "close_query", "answer_query", "generate_pdf", "lock_data",
        "view_signatures"
    ],
    "MONITOR": [
        "view_dashboard", "view_queries", "view_saes", "view_audit",
        "generate_pdf", "view_signatures"
    ],
    "SITE": [
        "view_dashboard", "view_queries", "answer_query"
    ],
    "ADMIN": [
        "view_dashboard", "view_queries", "view_saes", "view_audit",
        "close_query", "answer_query", "generate_pdf", "lock_data",
        "view_signatures", "manage_users"
    ],
}


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_auth_tables():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     TEXT PRIMARY KEY,
            full_name   TEXT NOT NULL,
            role        TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT,
            last_login  TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token       TEXT PRIMARY KEY,
            user_id     TEXT REFERENCES users(user_id),
            created_at  TEXT,
            expires_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS esignatures (
            sig_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT REFERENCES users(user_id),
            full_name   TEXT,
            role        TEXT,
            action      TEXT,
            record_id   TEXT,
            meaning     TEXT,
            signed_at   TEXT,
            password_verified INTEGER DEFAULT 1
        );
    """)

    # Default users
    default_users = [
        ("DM_JOHN",    "John Smith",     "DM",      "dm123"),
        ("MONITOR_01", "Sarah Jones",    "MONITOR", "monitor123"),
        ("SITE_001",   "Site Staff A",   "SITE",    "site123"),
        ("ADMIN",      "System Admin",   "ADMIN",   "admin123"),
    ]
    for uid, name, role, pwd in default_users:
        conn.execute("""
            INSERT OR IGNORE INTO users (user_id, full_name, role, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (uid, name, role, _hash(pwd), datetime.now().isoformat()))

    conn.commit()
    conn.close()
    print("[AUTH] Tables initialised with default users")


def login(user_id: str, password: str):
    """Returns (success, user_dict, token) """
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT user_id, full_name, role, password_hash, is_active FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False, None, None

    uid, name, role, pwd_hash, active = row

    if not active:
        conn.close()
        return False, {"error": "Account disabled"}, None

    if pwd_hash != _hash(password):
        conn.close()
        return False, {"error": "Invalid credentials"}, None

    # Create session token
    token = secrets.token_hex(32)
    conn.execute("""
        INSERT INTO sessions (token, user_id, created_at)
        VALUES (?, ?, ?)
    """, (token, uid, datetime.now().isoformat()))
    conn.execute("UPDATE users SET last_login=? WHERE user_id=?",
                 (datetime.now().isoformat(), uid))
    conn.commit()
    conn.close()

    user = {"user_id": uid, "full_name": name, "role": role,
            "permissions": PERMISSIONS.get(role, [])}
    return True, user, token


def has_permission(user: dict, permission: str) -> bool:
    return permission in user.get("permissions", [])


def esign(user_id: str, password: str, action: str, record_id: str, meaning: str):
    """
    Creates a 21 CFR Part 11 compliant electronic signature.
    Returns (success, message)
    """
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT full_name, role, password_hash FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False, "User not found"

    name, role, pwd_hash = row

    if pwd_hash != _hash(password):
        conn.close()
        return False, "Invalid password — signature rejected"

    conn.execute("""
        INSERT INTO esignatures (user_id, full_name, role, action, record_id, meaning, signed_at, password_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """, (user_id, name, role, action, record_id, meaning, datetime.now().isoformat()))

    # Also log in audit trail
    conn.execute("""
        INSERT INTO audit_trail (event_time, action, table_name, record_id, field_name, new_value, performed_by)
        VALUES (?, ?, 'esignatures', ?, 'e-signature', ?, ?)
    """, (datetime.now().isoformat(), f"ESIGN_{action}", record_id, meaning, user_id))

    conn.commit()
    conn.close()
    return True, f"✅ E-Signature recorded for {name} ({role}) at {datetime.now().strftime('%d-%b-%Y %H:%M')}"


def get_signatures(record_id: str = None):
    conn = sqlite3.connect(DB_PATH)
    if record_id:
        rows = conn.execute(
            "SELECT * FROM esignatures WHERE record_id=? ORDER BY signed_at DESC", (record_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM esignatures ORDER BY signed_at DESC"
        ).fetchall()
    conn.close()
    return rows


def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT user_id, full_name, role, is_active, last_login FROM users"
    ).fetchall()
    conn.close()
    return rows
