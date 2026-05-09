"""
scheduler.py — Feature 17: Automated Scheduler
Runs validation + SAE checks daily and sends email alerts automatically.
Save in: Mini_EDC_Project/python/scheduler.py

Run once:  python scheduler.py --now
Run daemon: python scheduler.py
"""

import os
import time
import argparse
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from db_connection import get_conn, is_postgres

# ── Config ────────────────────────────────────────────────────
LOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "reports", "scheduler_log.json"
)
RUN_HOUR = 6  # run at 06:00 daily
CHECK_INTERVAL = 60  # check every 60 seconds if it's time to run

# Email config — update with your SMTP settings
EMAIL_CONFIG = {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "sender": "cdm4sara@gmail.com",
    "password": "pxfq ezyw rwsm kmpj",  # Gmail App Password
    "recipients": ["yourname@gmail.com"],
    "enabled": True,  # Set True when SMTP is configured
}

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


# ── Database helpers ──────────────────────────────────────────
def get_db():
    return get_conn()


def _stale_expr():
    """Return the correct date-diff expression for the active backend."""
    if is_postgres():
        return "EXTRACT(EPOCH FROM (NOW() - created_at::timestamp)) / 86400 > "
    return "julianday('now') - julianday(created_at) > "


def check_new_saes():
    """Return SAEs with report_flag = PENDING."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT ae.usubjid, s.siteid, ae.aeterm, ae.aesev, ae.aestdtc
            FROM adverse_events ae
            JOIN subjects s USING(usubjid)
            WHERE ae.aeser='Y' AND ae.report_flag='PENDING'
        """).fetchall()
    return [dict(zip(["usubjid", "siteid", "aeterm", "aesev", "aestdtc"], r)) for r in rows]


def check_critical_queries():
    """Return Open Critical queries."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT query_id, usubjid, siteid, field_name, issue_description, created_at
            FROM queries
            WHERE severity='Critical' AND status='Open'
            ORDER BY created_at ASC
        """).fetchall()
    return [dict(zip(["query_id", "usubjid", "siteid", "field_name", "issue_description", "created_at"], r)) for r in rows]


def check_stale_queries(days=7):
    """Queries Open for more than N days with no answer."""
    stale_expr = _stale_expr() + str(days)
    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT query_id, usubjid, siteid, field_name, severity, created_at
            FROM queries
            WHERE status='Open'
              AND {stale_expr}
            ORDER BY created_at ASC
        """).fetchall()
    return [dict(zip(["query_id", "usubjid", "siteid", "field_name", "severity", "created_at"], r)) for r in rows]


def get_summary():
    """Get overall counts for the daily report."""
    with get_db() as conn:
        return {
            "open": conn.execute(
                "SELECT COUNT(*) FROM queries WHERE status='Open'"
            ).fetchone()[0],
            "critical": conn.execute(
                "SELECT COUNT(*) FROM queries WHERE severity='Critical' AND status='Open'"
            ).fetchone()[0],
            "saes": conn.execute(
                "SELECT COUNT(*) FROM adverse_events WHERE aeser='Y' AND report_flag='PENDING'"
            ).fetchone()[0],
            "subjects": conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0],
        }


# ── Email ─────────────────────────────────────────────────────
def build_email_html(saes, criticals, stale, summary):
    now = datetime.now().strftime("%d-%b-%Y %H:%M")
    rows_sae = (
        "".join(
            f"<tr><td>{r['usubjid']}</td><td>{r['siteid']}</td>"
            f"<td>{r['aeterm']}</td><td style='color:#C62828'>{r['aesev']}</td></tr>"
            for r in saes
        )
        or "<tr><td colspan='4' style='color:#388E3C'>None — all clear</td></tr>"
    )

    rows_crit = (
        "".join(
            f"<tr><td>{r['query_id']}</td><td>{r['usubjid']}</td>"
            f"<td>{r['siteid']}</td><td>{r['field_name']}</td><td>{r['issue_description'][:60]}</td></tr>"
            for r in criticals
        )
        or "<tr><td colspan='5' style='color:#388E3C'>None — all clear</td></tr>"
    )

    rows_stale = (
        "".join(
            f"<tr><td>{r['query_id']}</td><td>{r['usubjid']}</td>"
            f"<td>{r['siteid']}</td><td>{r['severity']}</td><td>{r['created_at'][:10]}</td></tr>"
            for r in stale
        )
        or "<tr><td colspan='5' style='color:#388E3C'>None</td></tr>"
    )

    return f"""
    <html><body style='font-family:Arial,sans-serif;max-width:700px;margin:auto'>
    <div style='background:#0D2B55;color:white;padding:20px;border-radius:8px 8px 0 0'>
      <h2 style='margin:0'>CDM Daily Scheduler Report</h2>
      <p style='margin:4px 0 0;opacity:.8'>{now}</p>
    </div>
    <div style='background:#f5f5f5;padding:16px;display:flex;gap:12px'>
      <div style='background:#C62828;color:white;padding:12px 20px;border-radius:6px;text-align:center'>
        <div style='font-size:28px;font-weight:bold'>{summary.get('saes',0)}</div>
        <div style='font-size:11px'>SAEs Pending</div>
      </div>
      <div style='background:#F57F17;color:white;padding:12px 20px;border-radius:6px;text-align:center'>
        <div style='font-size:28px;font-weight:bold'>{summary.get('critical',0)}</div>
        <div style='font-size:11px'>Critical Queries</div>
      </div>
      <div style='background:#1565C0;color:white;padding:12px 20px;border-radius:6px;text-align:center'>
        <div style='font-size:28px;font-weight:bold'>{summary.get('open',0)}</div>
        <div style='font-size:11px'>Open Queries</div>
      </div>
      <div style='background:#2E7D32;color:white;padding:12px 20px;border-radius:6px;text-align:center'>
        <div style='font-size:28px;font-weight:bold'>{summary.get('subjects',0)}</div>
        <div style='font-size:11px'>Subjects</div>
      </div>
    </div>

    <div style='padding:16px'>
      <h3 style='color:#C62828'>🚨 SAEs Requiring 24hr Report ({len(saes)})</h3>
      <table style='width:100%;border-collapse:collapse;font-size:13px'>
        <tr style='background:#C62828;color:white'>
          <th style='padding:6px'>Subject</th><th>Site</th><th>AE Term</th><th>Severity</th>
        </tr>{rows_sae}
      </table>

      <h3 style='color:#F57F17;margin-top:20px'>⚠️ Open Critical Queries ({len(criticals)})</h3>
      <table style='width:100%;border-collapse:collapse;font-size:13px'>
        <tr style='background:#F57F17;color:white'>
          <th style='padding:6px'>Query ID</th><th>Subject</th><th>Site</th><th>Field</th><th>Issue</th>
        </tr>{rows_crit}
      </table>

      <h3 style='color:#1565C0;margin-top:20px'>📋 Stale Queries (7+ days, no answer) ({len(stale)})</h3>
      <table style='width:100%;border-collapse:collapse;font-size:13px'>
        <tr style='background:#1565C0;color:white'>
          <th style='padding:6px'>Query ID</th><th>Subject</th><th>Site</th><th>Severity</th><th>Opened</th>
        </tr>{rows_stale}
      </table>
    </div>

    <div style='background:#f5f5f5;padding:12px;font-size:11px;color:#888;text-align:center;border-radius:0 0 8px 8px'>
      Mini EDC CDM Automated Scheduler — CONFIDENTIAL — For authorised personnel only
    </div>
    </body></html>
    """


def send_email(saes, criticals, stale, summary):
    if not EMAIL_CONFIG["enabled"]:
        print(
            "[SCHEDULER] Email disabled — set EMAIL_CONFIG['enabled']=True with SMTP details"
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"[CDM ALERT] {len(saes)} SAEs | {len(criticals)} Critical Queries — {datetime.now().strftime('%d-%b-%Y')}"
    )
    msg["From"] = EMAIL_CONFIG["sender"]
    msg["To"] = ", ".join(EMAIL_CONFIG["recipients"])
    msg.attach(MIMEText(build_email_html(saes, criticals, stale, summary), "html"))

    try:
        with smtplib.SMTP(EMAIL_CONFIG["smtp_host"], EMAIL_CONFIG["smtp_port"]) as s:
            s.starttls()
            s.login(EMAIL_CONFIG["sender"], EMAIL_CONFIG["password"])
            s.sendmail(
                EMAIL_CONFIG["sender"], EMAIL_CONFIG["recipients"], msg.as_string()
            )
        print(f"[SCHEDULER] Email sent to {EMAIL_CONFIG['recipients']}")
    except Exception as e:
        print(f"[SCHEDULER] Email failed: {e}")


# ── Main Job ──────────────────────────────────────────────────
def run_job():
    print(
        f"\n[SCHEDULER] Job started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    saes = check_new_saes()
    criticals = check_critical_queries()
    stale = check_stale_queries(days=7)
    summary = get_summary()

    print(f"[SCHEDULER] SAEs pending report : {len(saes)}")
    print(f"[SCHEDULER] Critical open queries: {len(criticals)}")
    print(f"[SCHEDULER] Stale queries (7d+)  : {len(stale)}")
    print(f"[SCHEDULER] Summary              : {summary}")

    # Log run to JSON file
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "saes": len(saes),
        "criticals": len(criticals),
        "stale": len(stale),
        "summary": summary,
        "email_sent": EMAIL_CONFIG["enabled"],
    }
    logs = []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            try:
                logs = json.load(f)
            except Exception:
                logs = []
    logs.append(log_entry)
    with open(LOG_PATH, "w") as f:
        json.dump(logs[-100:], f, indent=2)  # keep last 100 runs
    print(f"[SCHEDULER] Log saved → {LOG_PATH}")

    # Send email if anything needs attention
    if saes or criticals:
        send_email(saes, criticals, stale, summary)
    else:
        print("[SCHEDULER] No alerts — skipping email")

    print("[SCHEDULER] Job complete\n")
    return log_entry


# ── Daemon loop ───────────────────────────────────────────────
def run_daemon():
    print(f"\n{'='*60}")
    print("  CDM Automated Scheduler — Feature 17")
    print(f"  Runs daily at {RUN_HOUR:02d}:00")
    print("  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    last_run_date = None
    while True:
        now = datetime.now()
        if now.hour == RUN_HOUR and now.date() != last_run_date:
            run_job()
            last_run_date = now.date()
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CDM Automated Scheduler")
    parser.add_argument(
        "--now", action="store_true", help="Run job immediately instead of waiting"
    )
    args = parser.parse_args()

    if args.now:
        run_job()
    else:
        run_daemon()
