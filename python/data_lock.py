"""
data_lock.py — Feature 10: Data Lock Module
Freezes the database after final analysis — no edits allowed.
21 CFR Part 11 compliant with e-signature requirement.
Save in: Mini_EDC_Project/python/data_lock.py
Run with: python data_lock.py
"""

import hashlib
from datetime import datetime

from db_connection import get_conn, is_postgres


def _ph():
    return "%s" if is_postgres() else "?"


def init_lock_table():
    conn = get_conn()
    cur = conn.cursor()
    if is_postgres():
        cur.execute("""
            CREATE TABLE IF NOT EXISTS data_lock (
                lock_id        SERIAL PRIMARY KEY,
                lock_type      TEXT NOT NULL,
                locked_by      TEXT NOT NULL,
                lock_reason    TEXT,
                locked_at      TEXT,
                unlocked_by    TEXT,
                unlocked_at    TEXT,
                is_active      INTEGER DEFAULT 1,
                db_checksum    TEXT,
                signature_hash TEXT
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS data_lock (
                lock_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                lock_type      TEXT NOT NULL,
                locked_by      TEXT NOT NULL,
                lock_reason    TEXT,
                locked_at      TEXT,
                unlocked_by    TEXT,
                unlocked_at    TEXT,
                is_active      INTEGER DEFAULT 1,
                db_checksum    TEXT,
                signature_hash TEXT
            )
        """)
    conn.commit()
    conn.close()


def _compute_checksum():
    conn = get_conn()
    cur = conn.cursor()
    tables = ["subjects", "visits", "adverse_events", "queries", "audit_trail"]
    combined = ""
    for table in tables:
        try:
            cur.execute(f"SELECT * FROM {table} ORDER BY 1")
            combined += str(cur.fetchall())
        except Exception as e:
            print(f"Error fetching data from {table}: {e}")
    conn.close()
    return hashlib.sha256(combined.encode()).hexdigest()


def _verify_user(user_id: str, password: str) -> bool:
    ph = _ph()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT password_hash FROM users WHERE user_id={ph} AND is_active=1",
            (user_id,),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            row = dict(row)
            return row["password_hash"] == hashlib.sha256(password.encode()).hexdigest()
    except Exception as e:
        print(f"Error verifying user: {e}")
        conn.close()
    return False


def is_locked():
    init_lock_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT lock_id, lock_type, locked_by, locked_at FROM data_lock WHERE is_active=1"
    )
    row = cur.fetchone()
    conn.close()
    return row is not None, dict(row) if row else None


def lock_database(locked_by: str, password: str, reason: str, lock_type: str = "FINAL"):
    init_lock_table()
    ph = _ph()

    locked, info = is_locked()
    if locked:
        return (
            False,
            f"❌ Database already locked by {info['locked_by']} at {info['locked_at']}",
        )

    if not _verify_user(locked_by, password):
        return False, "❌ Invalid credentials — lock rejected"

    checksum = _compute_checksum()
    sig_hash = hashlib.sha256(
        f"{locked_by}{reason}{datetime.now().isoformat()}".encode()
    ).hexdigest()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO data_lock (lock_type, locked_by, lock_reason, locked_at, is_active, db_checksum, signature_hash)
        VALUES ({ph},{ph},{ph},{ph},1,{ph},{ph})
        """,
        (lock_type, locked_by, reason, datetime.now().isoformat(), checksum, sig_hash),
    )
    cur.execute(
        f"""
        INSERT INTO audit_trail (event_time, action, table_name, record_id, field_name, new_value, performed_by)
        VALUES ({ph},'DATA_LOCK','data_lock','ALL_TABLES','lock_status',{ph},{ph})
        """,
        (datetime.now().isoformat(), f"LOCKED ({lock_type})", locked_by),
    )
    conn.commit()
    conn.close()
    return (
        True,
        f"✅ Database LOCKED ({lock_type}) by {locked_by} at {datetime.now().strftime('%d %b %Y %H:%M')}",
    )


def unlock_database(unlocked_by: str, password: str, reason: str):
    ph = _ph()
    locked, info = is_locked()
    if not locked:
        return False, "❌ Database is not currently locked"

    if not _verify_user(unlocked_by, password):
        return False, "❌ Invalid credentials — unlock rejected"

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE data_lock SET is_active=0, unlocked_by={ph}, unlocked_at={ph} WHERE is_active=1",
        (unlocked_by, datetime.now().isoformat()),
    )
    cur.execute(
        f"""
        INSERT INTO audit_trail (event_time, action, table_name, record_id, field_name, new_value, performed_by)
        VALUES ({ph},'DATA_UNLOCK','data_lock','ALL_TABLES','lock_status','UNLOCKED',{ph})
        """,
        (datetime.now().isoformat(), unlocked_by),
    )
    conn.commit()
    conn.close()
    return (
        True,
        f"✅ Database UNLOCKED by {unlocked_by} at {datetime.now().strftime('%d %b %Y %H:%M')}",
    )


def verify_integrity():
    locked, info = is_locked()
    if not locked:
        return None, None, None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT db_checksum FROM data_lock WHERE is_active=1")
    row = cur.fetchone()
    conn.close()

    current = _compute_checksum()
    stored = dict(row)["db_checksum"] if row else None
    return current == stored, current, stored


def get_lock_history():
    init_lock_table()
    conn = get_conn()
    try:
        import pandas as pd

        df = pd.read_sql_query("SELECT * FROM data_lock ORDER BY locked_at DESC", conn)
    except Exception as e:
        print(f"Error loading lock history: {e}")
        df = None
    conn.close()
    return df


def print_lock_status():
    print("\n" + "=" * 55)
    print("  DATA LOCK STATUS")
    print("=" * 55)
    locked, info = is_locked()
    if locked:
        print("  🔒 STATUS    : LOCKED")
        print(f"  Lock Type   : {info['lock_type']}")
        print(f"  Locked By   : {info['locked_by']}")
        print(f"  Locked At   : {info['locked_at']}")
        match, cur, stored = verify_integrity()
        if match is not None:
            icon = "✅" if match else "⚠️"
            print(
                f"\n  {icon} DB Integrity : {'VERIFIED — No changes since lock' if match else 'WARNING — Data may have changed!'}"
            )
            print(f"  Checksum    : {cur[:20]}...")
    else:
        print("  🔓 STATUS    : UNLOCKED")
        print("  Database is open for editing.")
    print()


if __name__ == "__main__":
    print_lock_status()
    print("To lock the database, call:")
    print("  from data_lock import lock_database")
    print(
        "  ok, msg = lock_database('DM_JOHN', 'dm123', 'Final database lock after DBL meeting')"
    )
    print("  print(msg)")
    print("\nTo unlock:")
    print("  from data_lock import unlock_database")
    print(
        "  ok, msg = unlock_database('ADMIN', 'admin123', 'Emergency unlock approved by sponsor')"
    )
    print("  print(msg)")
