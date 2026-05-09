"""
randomisation.py — Feature 13: Randomisation Module
Assigns subjects to treatment arms using blocked randomisation.
Save in: Mini_EDC_Project/python/randomisation.py
Run with: python randomisation.py
"""


import random
import hashlib
import pandas as pd
from datetime import datetime
from db_connection import get_conn, is_postgres

# ── Trial Arms — customise as needed ─────────────────────────
TREATMENT_ARMS = {
    "TRT-A": "Drug X 100mg",
    "TRT-B": "Drug X 200mg",
    "TRT-C": "Placebo",
}

ALLOCATION_RATIO = {
    "TRT-A": 2,  # 2:2:1 ratio
    "TRT-B": 2,
    "TRT-C": 1,
}

STRATIFICATION_FACTORS = ["siteid"]  # stratify by site


def init_randomisation_table():
    conn = get_conn()
    if is_postgres():
        conn.execute("""
            CREATE TABLE IF NOT EXISTS randomisation (
                rand_id         SERIAL PRIMARY KEY,
                rand_code       TEXT UNIQUE,
                usubjid         TEXT,
                siteid          TEXT,
                arm_code        TEXT,
                arm_description TEXT,
                randomised_at   TEXT,
                randomised_by   TEXT,
                block_id        INTEGER,
                seed_hash       TEXT,
                status          TEXT DEFAULT 'Active'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS randomisation_list (
                list_id     SERIAL PRIMARY KEY,
                rand_number INTEGER,
                siteid      TEXT,
                arm_code    TEXT,
                is_used     INTEGER DEFAULT 0,
                used_by     TEXT,
                used_at     TEXT
            )
        """)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS randomisation (
                rand_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                rand_code       TEXT UNIQUE,
                usubjid         TEXT,
                siteid          TEXT,
                arm_code        TEXT,
                arm_description TEXT,
                randomised_at   TEXT,
                randomised_by   TEXT,
                block_id        INTEGER,
                seed_hash       TEXT,
                status          TEXT DEFAULT 'Active'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS randomisation_list (
                list_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                rand_number INTEGER,
                siteid      TEXT,
                arm_code    TEXT,
                is_used     INTEGER DEFAULT 0,
                used_by     TEXT,
                used_at     TEXT
            )
        """)
    conn.commit()
    conn.close()


def generate_randomisation_list(seed: int = 42, subjects_per_site: int = 20):
    """
    Pre-generate a blocked randomisation list for all sites.
    Uses block randomisation to ensure balance.
    """
    init_randomisation_table()
    conn = get_conn()
    ph = "%s" if is_postgres() else "?"

    # Get sites from DB
    sites = conn.execute("SELECT DISTINCT siteid FROM subjects").fetchall()
    sites = [
        (s["siteid"] if isinstance(s, dict) else s[0]) for s in sites
    ] if sites else ["SITE01", "SITE02", "SITE03"]

    # Build block pattern from allocation ratio
    block_pattern = []
    for arm, count in ALLOCATION_RATIO.items():
        block_pattern.extend([arm] * count)

    rand_number = 1
    for site in sites:
        random.seed(seed + hash(site) % 1000)
        needed = subjects_per_site
        while needed > 0:
            block = block_pattern.copy()
            random.shuffle(block)
            for arm in block:
                if is_postgres():
                    conn.execute(
                        f"""
                        INSERT INTO randomisation_list
                        (rand_number, siteid, arm_code, is_used)
                        VALUES ({ph},{ph},{ph},0)
                        ON CONFLICT DO NOTHING
                    """,
                        (rand_number, site, arm),
                    )
                else:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO randomisation_list
                        (rand_number, siteid, arm_code, is_used)
                        VALUES (?, ?, ?, 0)
                    """,
                        (rand_number, site, arm),
                    )
                rand_number += 1
                needed -= 1
                if needed <= 0:
                    break

    conn.commit()
    conn.close()
    print(
        f"[RAND] Randomisation list generated: {rand_number-1} slots across {len(sites)} sites"
    )
    return rand_number - 1


def randomise_subject(usubjid: str, siteid: str, randomised_by: str = "DM"):
    """
    Assign the next available randomisation slot to a subject.
    Returns (success, arm_code, arm_description, rand_code)
    """
    init_randomisation_table()
    conn = get_conn()
    ph = "%s" if is_postgres() else "?"

    # Check if subject already randomised
    existing = conn.execute(
        f"SELECT rand_code, arm_code FROM randomisation WHERE usubjid={ph}", (usubjid,)
    ).fetchone()
    if existing:
        conn.close()
        rc  = existing["rand_code"] if isinstance(existing, dict) else existing[0]
        ac  = existing["arm_code"]  if isinstance(existing, dict) else existing[1]
        return False, ac, TREATMENT_ARMS.get(ac, ""), rc

    # Get next available slot for this site
    slot = conn.execute(
        f"""
        SELECT list_id, rand_number, arm_code FROM randomisation_list
        WHERE siteid={ph} AND is_used=0
        ORDER BY rand_number ASC LIMIT 1
    """,
        (siteid,),
    ).fetchone()

    if not slot:
        conn.close()
        return False, None, "No randomisation slots available for this site", None

    list_id    = slot["list_id"]    if isinstance(slot, dict) else slot[0]
    rand_number= slot["rand_number"]if isinstance(slot, dict) else slot[1]
    arm_code   = slot["arm_code"]   if isinstance(slot, dict) else slot[2]
    arm_desc = TREATMENT_ARMS.get(arm_code, arm_code)
    rand_code = f"RAND-{rand_number:05d}"
    seed_hash = hashlib.md5(
        f"{usubjid}{arm_code}{datetime.now().isoformat()}".encode()
    ).hexdigest()[:12]

    # Mark slot as used
    conn.execute(
        f"""
        UPDATE randomisation_list SET is_used=1, used_by={ph}, used_at={ph} WHERE list_id={ph}
    """,
        (usubjid, datetime.now().isoformat(), list_id),
    )

    # Record randomisation
    block_id = (rand_number - 1) // sum(ALLOCATION_RATIO.values()) + 1
    conn.execute(
        f"""
        INSERT INTO randomisation
        (rand_code, usubjid, siteid, arm_code, arm_description,
         randomised_at, randomised_by, block_id, seed_hash)
        VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
    """,
        (
            rand_code,
            usubjid,
            siteid,
            arm_code,
            arm_desc,
            datetime.now().isoformat(),
            randomised_by,
            block_id,
            seed_hash,
        ),
    )

    # Audit trail
    conn.execute(
        f"""
        INSERT INTO audit_trail
        (event_time, action, table_name, record_id, field_name, new_value, performed_by)
        VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})
    """,
        (
            datetime.now().isoformat(),
            "RANDOMISED",
            "randomisation",
            rand_code,
            "arm_code",
            arm_code,
            randomised_by,
        ),
    )

    conn.commit()
    conn.close()

    print(f"[RAND] {usubjid} → {arm_code} ({arm_desc}) | Code: {rand_code}")
    return True, arm_code, arm_desc, rand_code


def randomise_all_subjects():
    """Randomise all existing subjects who haven't been randomised yet."""
    conn = get_conn()
    subjects = conn.execute("SELECT usubjid, siteid FROM subjects").fetchall()
    conn.close()

    randomised = 0
    for row in subjects:
        usubjid = row["usubjid"] if isinstance(row, dict) else row[0]
        siteid  = row["siteid"]  if isinstance(row, dict) else row[1]
        ok, arm, desc, code = randomise_subject(usubjid, siteid or "SITE01")
        if ok:
            randomised += 1
    print(f"[RAND] Randomised {randomised} subjects")
    return randomised


def get_arm_balance():
    """Check treatment arm balance across sites."""
    conn = get_conn()
    try:
        df = pd.read_sql_query(
            """
            SELECT siteid, arm_code, arm_description, COUNT(*) as n
            FROM randomisation
            WHERE status='Active'
            GROUP BY siteid, arm_code
            ORDER BY siteid, arm_code
        """,
            conn,
        )
    except Exception as e:
        print(f"Error fetching arm balance: {e}")
        df = pd.DataFrame()
    conn.close()
    return df


def print_randomisation_report():
    """Print randomisation summary."""
    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM randomisation").fetchone()[0]
        by_arm = conn.execute("""
            SELECT arm_code, arm_description, COUNT(*) as n
            FROM randomisation GROUP BY arm_code
        """).fetchall()
    except Exception as e:
        total = 0
        by_arm = []
        print(f"Error fetching randomisation summary: {e}")
    conn.close()

    print("\n" + "=" * 65)
    print("  RANDOMISATION REPORT")
    print("=" * 65)
    print(f"  Total Randomised Subjects : {total}")

    if by_arm:
        print("\n  Treatment Arm Balance:")
        for row in by_arm:
            arm_code = row["arm_code"]        if isinstance(row, dict) else row[0]
            arm_desc = row["arm_description"] if isinstance(row, dict) else row[1]
            n        = row["n"]               if isinstance(row, dict) else row[2]
            bar = "█" * n + "░" * max(0, 10 - n)
            print(f"  {arm_code} ({arm_desc:<18}) [{bar}] n={n}")

    balance_df = get_arm_balance()
    if not balance_df.empty:
        print("\n  Balance by Site:")
        for site, grp in balance_df.groupby("siteid"):
            arms = " | ".join(
                [f"{r['arm_code']}:n={r['n']}" for _, r in grp.iterrows()]
            )
            print(f"  {site:10} — {arms}")
    print()


if __name__ == "__main__":
    init_randomisation_table()
    generate_randomisation_list(seed=42)
    randomise_all_subjects()
    print_randomisation_report()
