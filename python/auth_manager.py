"""
auth_manager.py — Authentication, Role-Based Access & E-Signature
Phase 6 Addition — 21 CFR Part 11 Compliant
Save in: Mini_EDC_Project/python/auth_manager.py
"""

import hashlib
import secrets
from datetime import datetime

from db_connection import get_conn, is_postgres

# ── Roles & Permissions ───────────────────────────────────────
ROLES = {
    "DM": "Data Manager",
    "MONITOR": "Clinical Monitor",
    "SITE": "Site Staff",
    "ADMIN": "System Administrator",
}

PERMISSIONS = {
    "DM": [
        "view_dashboard",
        "view_queries",
        "view_saes",
        "view_audit",
        "close_query",
        "answer_query",
        "generate_pdf",
        "lock_data",
        "view_signatures",
    ],
    "MONITOR": [
        "view_dashboard",
        "view_queries",
        "view_saes",
        "view_audit",
        "generate_pdf",
        "view_signatures",
    ],
    "SITE": ["view_dashboard", "view_queries", "answer_query"],
    "ADMIN": [
        "view_dashboard",
        "view_queries",
        "view_saes",
        "view_audit",
        "close_query",
        "answer_query",
        "generate_pdf",
        "lock_data",
        "view_signatures",
        "manage_users",
    ],
}


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _ph():
    """Parameter placeholder for current DB backend."""
    return "%s" if is_postgres() else "?"


def init_auth_tables():
    conn = get_conn()
    cur = conn.cursor()

    if is_postgres():
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       TEXT PRIMARY KEY,
                full_name     TEXT NOT NULL,
                role          TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_active     INTEGER DEFAULT 1,
                created_at    TEXT,
                last_login    TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    TEXT REFERENCES users(user_id),
                created_at TEXT,
                expires_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS esignatures (
                sig_id            SERIAL PRIMARY KEY,
                user_id           TEXT REFERENCES users(user_id),
                full_name         TEXT,
                role              TEXT,
                action            TEXT,
                record_id         TEXT,
                meaning           TEXT,
                signed_at         TEXT,
                password_verified INTEGER DEFAULT 1
            )
        """)
    else:
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       TEXT PRIMARY KEY,
                full_name     TEXT NOT NULL,
                role          TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_active     INTEGER DEFAULT 1,
                created_at    TEXT,
                last_login    TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    TEXT REFERENCES users(user_id),
                created_at TEXT,
                expires_at TEXT
            );
            CREATE TABLE IF NOT EXISTS esignatures (
                sig_id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id           TEXT REFERENCES users(user_id),
                full_name         TEXT,
                role              TEXT,
                action            TEXT,
                record_id         TEXT,
                meaning           TEXT,
                signed_at         TEXT,
                password_verified INTEGER DEFAULT 1
            );
        """)

    # Default users
    ph = _ph()
    default_users = [
        ("DM_JOHN", "John Smith", "DM", "dm123"),
        ("MONITOR_01", "Sarah Jones", "MONITOR", "monitor123"),
        ("SITE_001", "Site Staff A", "SITE", "site123"),
        ("ADMIN", "System Admin", "ADMIN", "admin123"),
    ]
    for uid, name, role, pwd in default_users:
        if is_postgres():
            cur.execute(
                f"""
                INSERT INTO users (user_id, full_name, role, password_hash, created_at)
                VALUES ({ph},{ph},{ph},{ph},{ph})
                ON CONFLICT (user_id) DO NOTHING
                """,
                (uid, name, role, _hash(pwd), datetime.now().isoformat()),
            )
        else:
            cur.execute(
                f"""
                INSERT OR IGNORE INTO users (user_id, full_name, role, password_hash, created_at)
                VALUES ({ph},{ph},{ph},{ph},{ph})
                """,
                (uid, name, role, _hash(pwd), datetime.now().isoformat()),
            )

    conn.commit()
    conn.close()
    print("[AUTH] Tables initialised with default users")


def login(user_id: str, password: str):
    """Returns (success, user_dict, token)"""
    ph = _ph()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"SELECT user_id, full_name, role, password_hash, is_active FROM users WHERE user_id={ph}",
        (user_id,),
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return False, None, None

    row = dict(row)
    uid = row["user_id"]
    name = row["full_name"]
    role = row["role"]
    active = row["is_active"]
    pwd_hash = row["password_hash"]

    if not active:
        conn.close()
        return False, {"error": "Account disabled"}, None

    if pwd_hash != _hash(password):
        conn.close()
        return False, {"error": "Invalid credentials"}, None

    token = secrets.token_hex(32)
    cur.execute(
        f"INSERT INTO sessions (token, user_id, created_at) VALUES ({ph},{ph},{ph})",
        (token, uid, datetime.now().isoformat()),
    )
    cur.execute(
        f"UPDATE users SET last_login={ph} WHERE user_id={ph}",
        (datetime.now().isoformat(), uid),
    )
    conn.commit()
    conn.close()

    user = {
        "user_id": uid,
        "full_name": name,
        "role": role,
        "permissions": PERMISSIONS.get(role, []),
    }
    return True, user, token


def has_permission(user: dict, permission: str) -> bool:
    return permission in user.get("permissions", [])


def esign(user_id: str, password: str, action: str, record_id: str, meaning: str):
    """
    Creates a 21 CFR Part 11 compliant electronic signature.
    Returns (success, message)
    """
    ph = _ph()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"SELECT full_name, role, password_hash FROM users WHERE user_id={ph}",
        (user_id,),
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return False, "User not found"

    row = dict(row)
    name = row["full_name"]
    role = row["role"]
    pwd_hash = row["password_hash"]

    if pwd_hash != _hash(password):
        conn.close()
        return False, "Invalid password — signature rejected"

    cur.execute(
        f"""
        INSERT INTO esignatures
            (user_id, full_name, role, action, record_id, meaning, signed_at, password_verified)
        VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},1)
        """,
        (user_id, name, role, action, record_id, meaning, datetime.now().isoformat()),
    )
    cur.execute(
        f"""
        INSERT INTO audit_trail
            (event_time, action, table_name, record_id, field_name, new_value, performed_by)
        VALUES ({ph},{ph},'esignatures',{ph},'e-signature',{ph},{ph})
        """,
        (datetime.now().isoformat(), f"ESIGN_{action}", record_id, meaning, user_id),
    )

    conn.commit()
    conn.close()
    return (
        True,
        f"✅ E-Signature recorded for {name} ({role}) at {datetime.now().strftime('%d-%b-%Y %H:%M')}",
    )


def get_signatures(record_id: str = None):
    ph = _ph()
    conn = get_conn()
    cur = conn.cursor()
    if record_id:
        cur.execute(
            f"SELECT * FROM esignatures WHERE record_id={ph} ORDER BY signed_at DESC",
            (record_id,),
        )
    else:
        cur.execute("SELECT * FROM esignatures ORDER BY signed_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_all_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, full_name, role, is_active, last_login FROM users")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
