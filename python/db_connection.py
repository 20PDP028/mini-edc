"""
db_connection.py — Centralised Database Connection
===================================================
Drop this file into python/ and import it everywhere instead of
using sqlite3.connect() directly.

Usage in any file:
    from db_connection import get_conn, placeholder, upsert_syntax

Automatically uses:
    - PostgreSQL if DATABASE_URL environment variable is set (Railway/cloud)
    - SQLite    if DATABASE_URL is not set (local development)
"""

import os
import sqlite3

# ── Detect environment ────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES  = bool(DATABASE_URL)

if USE_POSTGRES:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        raise ImportError(
            "psycopg2 not installed. Run: pip install psycopg2-binary"
        )

# SQLite fallback path (local dev)
BASE     = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE, "..", "sql", "cdm_phase3.db")


# ── Public API ────────────────────────────────────────────────────────────────

def get_conn():
    """
    Returns a database connection.
    PostgreSQL if DATABASE_URL is set, otherwise SQLite.

    Always use as a context manager or close manually:
        conn = get_conn()
        ...
        conn.close()
    """
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def placeholder(n=1):
    """
    Returns the correct parameter placeholder for the active DB.
    SQLite uses ?, PostgreSQL uses %s.

    Examples:
        cur.execute(f"SELECT * FROM t WHERE id = {placeholder()}", (id,))
        cols = placeholder(3)  → "?, ?, ?"  or  "%s, %s, %s"
    """
    ph = "%s" if USE_POSTGRES else "?"
    return ", ".join([ph] * n) if n > 1 else ph


def placeholders(keys):
    """
    Returns a comma-separated placeholder string for a list of keys.
    Useful for INSERT statements.

        placeholders(data.keys())  → "?, ?, ?"  or  "%s, %s, %s"
    """
    ph = "%s" if USE_POSTGRES else "?"
    return ", ".join([ph] * len(keys))


def upsert(table, data, conflict_col):
    """
    Executes an INSERT OR IGNORE (SQLite) / INSERT ... ON CONFLICT DO NOTHING (PostgreSQL).
    Returns nothing — call within an open connection.

    Usage:
        conn = get_conn()
        upsert(conn, "subjects", {"usubjid": "S001", "siteid": "SITE01"}, "usubjid")
        conn.commit()
        conn.close()
    """
    pass  # See execute_upsert() below for the full implementation


def execute_upsert(conn, table, data, conflict_col):
    """
    INSERT ignore-duplicate helper.

    conn          — open connection from get_conn()
    table         — table name string
    data          — dict of {column: value}
    conflict_col  — column name that defines uniqueness
    """
    cols = ", ".join(data.keys())
    vals = list(data.values())
    cur  = conn.cursor()

    if USE_POSTGRES:
        ph  = ", ".join(["%s"] * len(data))
        sql = (
            f"INSERT INTO {table} ({cols}) VALUES ({ph}) "
            f"ON CONFLICT ({conflict_col}) DO NOTHING"
        )
    else:
        ph  = ", ".join(["?"] * len(data))
        sql = f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({ph})"

    cur.execute(sql, vals)


def row_to_dict(row):
    """
    Converts a database row to a plain dict regardless of DB backend.
    SQLite returns sqlite3.Row, PostgreSQL returns RealDictRow.
    """
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows):
    """Converts a list of rows to a list of dicts."""
    return [dict(r) for r in rows]


def is_postgres():
    """Returns True if connected to PostgreSQL."""
    return USE_POSTGRES


def db_info():
    """Returns a string describing the active database backend."""
    if USE_POSTGRES:
        return f"PostgreSQL ({DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'cloud'})"
    return f"SQLite ({DB_PATH})"


# ── Schema helpers ────────────────────────────────────────────────────────────

def create_table_safe(conn, sql_sqlite, sql_postgres=None):
    """
    Executes a CREATE TABLE IF NOT EXISTS statement.
    If sql_postgres is provided, uses it for PostgreSQL (handles type differences).
    Otherwise uses sql_sqlite for both (works for simple schemas).
    """
    cur = conn.cursor()
    if USE_POSTGRES and sql_postgres:
        cur.execute(sql_postgres)
    else:
        cur.execute(sql_sqlite)


# ── Type mapping notes ────────────────────────────────────────────────────────
#
# SQLite → PostgreSQL type equivalents:
#   INTEGER PRIMARY KEY AUTOINCREMENT  →  SERIAL PRIMARY KEY
#   TEXT                               →  TEXT  (same)
#   REAL                               →  DOUBLE PRECISION
#   BLOB                               →  BYTEA
#   DEFAULT (datetime())               →  DEFAULT NOW()
#
# When creating tables for PostgreSQL, replace AUTOINCREMENT with SERIAL.
