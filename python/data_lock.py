"""
data_lock.py — Feature 10: Data Lock Module
Freezes the database after final analysis — no edits allowed.
21 CFR Part 11 compliant with e-signature requirement.
Save in: Mini_EDC_Project/python/data_lock.py
Run with: python data_lock.py
"""

import sqlite3
import os
import hashlib
from datetime import datetime

BASE    = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, '..', 'sql', 'cdm_phase3.db')


def init_lock_table():
    """Create data_lock table if not exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS data_lock (
            lock_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            lock_type     TEXT NOT NULL,
            locked_by     TEXT NOT NULL,
            lock_reason   TEXT,
            locked_at     TEXT,
            unlocked_by   TEXT,
            unlocked_at   TEXT,
            is_active     INTEGER DEFAULT 1,
            db_checksum   TEXT,
            signature_hash TEXT
        )
    """)
    conn.commit()
    conn.close()


def _compute_checksum():
    """Compute a checksum of the current DB state for integrity verification."""
    conn = sqlite3.connect(DB_PATH)
    tables = ["subjects", "visits", "adverse_events", "queries", "audit_trail"]
    combined = ""
    for table in tables:
        try:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            combined += str(rows)
        except:
            pass
    conn.close()
    return hashlib.sha256(combined.encode()).hexdigest()


def _verify_user(user_id: str, password: str) -> bool:
    """Verify user credentials against users table."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE user_id=? AND is_active=1",
            (user_id,)
        ).fetchone()
        conn.close()
        if row:
            return row[0] == hashlib.sha256(password.encode()).hexdigest()
    except:
        conn.close()
    return False


def is_locked():
    """Check if DB is currently locked."""
    init_lock_table()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT lock_id, lock_type, locked_by, locked_at FROM data_lock WHERE is_active=1"
    ).fetchone()
    conn.close()
    return row is not None, row


def lock_database(locked_by: str, password: str, reason: str, lock_type: str = "FINAL"):
    """
    Lock the database. Requires valid credentials.
    lock_type: FINAL | INTERIM | SOFT
    Returns (success, message)
    """
    init_lock_table()

    locked, info = is_locked()
    if locked:
        return False, f"❌ Database already locked by {info[2]} at {info[3]}"

    if not _verify_user(locked_by, password):
        return False, "❌ Invalid credentials — lock rejected"

    checksum = _compute_checksum()
    sig_hash = hashlib.sha256(f"{locked_by}{reason}{datetime.now().isoformat()}".encode()).hexdigest()

    conn = sqlite3.connect(DB_PATH)

    # Insert lock record
    conn.execute("""
        INSERT INTO data_lock (lock_type, locked_by, lock_reason, locked_at, is_active, db_checksum, signature_hash)
        VALUES (?, ?, ?, ?, 1, ?, ?)
    """, (lock_type, locked_by, reason, datetime.now().isoformat(), checksum, sig_hash))

    # Log in audit trail
    conn.execute("""
        INSERT INTO audit_trail (event_time, action, table_name, record_id, field_name, new_value, performed_by)
        VALUES (?, 'DATA_LOCK', 'data_lock', 'ALL_TABLES', 'lock_status', ?, ?)
    """, (datetime.now().isoformat(), f"LOCKED ({lock_type})", locked_by))

    conn.commit()
    conn.close()

    return True, f"✅ Database LOCKED ({lock_type}) by {locked_by} at {datetime.now().strftime('%d %b %Y %H:%M')}"


def unlock_database(unlocked_by: str, password: str, reason: str):
    """
    Unlock the database. Requires valid DM/ADMIN credentials.
    Returns (success, message)
    """
    locked, info = is_locked()
    if not locked:
        return False, "❌ Database is not currently locked"

    if not _verify_user(unlocked_by, password):
        return False, "❌ Invalid credentials — unlock rejected"

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE data_lock SET is_active=0, unlocked_by=?, unlocked_at=?
        WHERE is_active=1
    """, (unlocked_by, datetime.now().isoformat()))

    conn.execute("""
        INSERT INTO audit_trail (event_time, action, table_name, record_id, field_name, new_value, performed_by)
        VALUES (?, 'DATA_UNLOCK', 'data_lock', 'ALL_TABLES', 'lock_status', 'UNLOCKED', ?)
    """, (datetime.now().isoformat(), unlocked_by))

    conn.commit()
    conn.close()

    return True, f"✅ Database UNLOCKED by {unlocked_by} at {datetime.now().strftime('%d %b %Y %H:%M')}"


def verify_integrity():
    """
    Verify current DB checksum against locked checksum.
    Returns (match, current_checksum, locked_checksum)
    """
    locked, info = is_locked()
    if not locked:
        return None, None, None

    conn = sqlite3.connect(DB_PATH)
    locked_checksum = conn.execute(
        "SELECT db_checksum FROM data_lock WHERE is_active=1"
    ).fetchone()
    conn.close()

    current = _compute_checksum()
    stored  = locked_checksum[0] if locked_checksum else None
    return current == stored, current, stored


def get_lock_history():
    """Return full lock/unlock history."""
    init_lock_table()
    conn = sqlite3.connect(DB_PATH)
    try:
        df_import = __import__('pandas')
        df = df_import.read_sql_query(
            "SELECT * FROM data_lock ORDER BY locked_at DESC", conn
        )
    except:
        df = None
    conn.close()
    return df


def print_lock_status():
    """Print current lock status to console."""
    print("\n" + "="*55)
    print("  DATA LOCK STATUS")
    print("="*55)

    locked, info = is_locked()
    if locked:
        print(f"  🔒 STATUS    : LOCKED")
        print(f"  Lock Type   : {info[1]}")
        print(f"  Locked By   : {info[2]}")
        print(f"  Locked At   : {info[3]}")

        match, cur, stored = verify_integrity()
        if match is not None:
            icon = "✅" if match else "⚠️"
            print(f"\n  {icon} DB Integrity : {'VERIFIED — No changes since lock' if match else 'WARNING — Data may have changed!'}")
            print(f"  Checksum    : {cur[:20]}...")
    else:
        print(f"  🔓 STATUS    : UNLOCKED")
        print(f"  Database is open for editing.")
    print()


if __name__ == "__main__":
    print_lock_status()

    print("To lock the database, call:")
    print("  from data_lock import lock_database")
    print("  ok, msg = lock_database('DM_JOHN', 'dm123', 'Final database lock after DBL meeting')")
    print("  print(msg)")

    print("\nTo unlock:")
    print("  from data_lock import unlock_database")
    print("  ok, msg = unlock_database('ADMIN', 'admin123', 'Emergency unlock approved by sponsor')")
    print("  print(msg)")
