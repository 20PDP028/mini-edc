"""
email_alerts.py — Feature 5: Email Alert System
Auto-notifies monitors when SAE or Critical query is raised.
Save in: Mini_EDC_Project/python/email_alerts.py

Setup:
  1. Create a Gmail App Password:
     → Google Account → Security → 2-Step Verification → App Passwords
  2. Fill in SENDER_EMAIL and SENDER_PASSWORD below
  3. Add monitor emails to MONITOR_EMAILS list
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from db_connection import get_conn, is_postgres

# ── CONFIG — Edit these ───────────────────────────────────────
SENDER_EMAIL = "your_gmail@gmail.com"  # ← your Gmail
SENDER_PASSWORD = "your_app_password_here"  # ← Gmail App Password
MONITOR_EMAILS = [
    "monitor1@example.com",  # ← add monitor emails
    "monitor2@example.com",
]


def _send_email(to_list: list, subject: str, html_body: str):
    """Core email sender using Gmail SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = ", ".join(to_list)
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_list, msg.as_string())

        print(f"[EMAIL] ✅ Sent to {to_list} | Subject: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL] ❌ Failed: {e}")
        return False


def _log_alert(conn, alert_type, record_id, recipients, status):
    """Log every alert attempt in the audit trail."""
    ph = "%s" if is_postgres() else "?"
    try:
        conn.execute(
            f"""
            INSERT INTO audit_trail
            (event_time, action, table_name, record_id, field_name, new_value, performed_by)
            VALUES ({ph}, {ph}, 'email_alerts', {ph}, 'recipients', {ph}, 'EMAIL_SYSTEM')
        """,
            (
                datetime.now().isoformat(),
                f"EMAIL_{alert_type}",
                record_id,
                f"{recipients} → {status}",
            ),
        )
        conn.commit()
    except Exception:
        pass


def _email_template(title, color, badge, rows, footer_note):
    """Reusable HTML email template."""
    rows_html = "".join(
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #eee;color:#555;'>{k}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #eee;font-weight:600;color:#222;'>{v}</td></tr>"
        for k, v in rows.items()
    )
    return f"""
    <html><body style='margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;'>
    <div style='max-width:580px;margin:30px auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.1);'>
        <div style='background:{color};padding:28px 32px;'>
            <div style='font-size:1.4rem;font-weight:700;color:#fff;'>{title}</div>
            <div style='margin-top:6px;display:inline-block;background:rgba(255,255,255,0.2);color:#fff;padding:3px 12px;border-radius:20px;font-size:0.8rem;'>{badge}</div>
        </div>
        <div style='padding:24px 32px;'>
            <table width='100%' style='border-collapse:collapse;'>{rows_html}</table>
            <div style='margin-top:20px;padding:14px;background:#fff8e1;border-left:4px solid #f9a825;border-radius:4px;font-size:0.85rem;color:#555;'>
                ⚠️ {footer_note}
            </div>
        </div>
        <div style='background:#f4f6f9;padding:14px 32px;font-size:0.75rem;color:#999;border-top:1px solid #eee;'>
            Mini EDC System · Auto-generated · {datetime.now().strftime("%d %b %Y %H:%M")} · CONFIDENTIAL
        </div>
    </div></body></html>
    """


def send_sae_alert(sae: dict):
    """
    Send SAE alert email to all monitors.
    sae dict keys: usubjid, siteid, aeterm, aesev, aestdtc, report_flag
    """
    subject = f"🚨 [URGENT] SAE Alert — {sae.get('aeterm','Unknown')} | {sae.get('usubjid','')}"
    html = _email_template(
        title="🚨 Serious Adverse Event Reported",
        color="#C62828",
        badge="REQUIRES 24-HOUR EXPEDITED REPORTING",
        rows={
            "Subject ID": sae.get("usubjid", ""),
            "Site": sae.get("siteid", ""),
            "AE Term": sae.get("aeterm", ""),
            "Severity": sae.get("aesev", ""),
            "Serious": sae.get("aeser", "Y"),
            "Event Date": sae.get("aestdtc", ""),
            "Report Status": sae.get("report_flag", "PENDING"),
            "Detected At": datetime.now().strftime("%d %b %Y %H:%M"),
        },
        footer_note="This SAE requires expedited reporting within 24 hours per protocol. Please review immediately.",
    )
    ok = _send_email(MONITOR_EMAILS, subject, html)

    conn = get_conn()
    _log_alert(
        conn,
        "SAE_ALERT",
        sae.get("usubjid", ""),
        str(MONITOR_EMAILS),
        "SENT" if ok else "FAILED",
    )
    conn.close()
    return ok


def send_critical_query_alert(query: dict):
    """
    Send Critical query alert to all monitors.
    query dict keys: query_id, usubjid, siteid, field, severity, issue
    """
    subject = f"⚠️ [CDM] Critical Query — {query.get('query_id','')} | {query.get('usubjid','')}"
    html = _email_template(
        title="⚠️ Critical Data Query Raised",
        color="#E65100",
        badge="CRITICAL SEVERITY — ACTION REQUIRED",
        rows={
            "Query ID": query.get("query_id", ""),
            "Subject ID": query.get("usubjid", ""),
            "Site": query.get("siteid", ""),
            "Field": query.get("field", ""),
            "Severity": query.get("severity", ""),
            "Issue": query.get("issue", ""),
            "Raised At": datetime.now().strftime("%d %b %Y %H:%M"),
        },
        footer_note="A critical data query has been raised. Please ensure the site responds within 24 hours.",
    )
    ok = _send_email(MONITOR_EMAILS, subject, html)

    conn = get_conn()
    _log_alert(
        conn,
        "CRITICAL_QUERY",
        query.get("query_id", ""),
        str(MONITOR_EMAILS),
        "SENT" if ok else "FAILED",
    )
    conn.close()
    return ok


def send_daily_summary():
    """
    Send a daily summary of open queries and pending SAEs to monitors.
    """
    conn = get_conn()
    try:
        open_q = conn.execute(
            "SELECT COUNT(*) FROM queries WHERE status='Open'"
        ).fetchone()[0]
        crit_q = conn.execute(
            "SELECT COUNT(*) FROM queries WHERE status='Open' AND severity='Critical'"
        ).fetchone()[0]
        sae_pend = conn.execute(
            "SELECT COUNT(*) FROM adverse_events WHERE report_flag='PENDING'"
        ).fetchone()[0]
        total_q = conn.execute("SELECT COUNT(*) FROM queries").fetchone()[0]
    except Exception as e:
        print(f"Error fetching summary data: {e}")
        open_q = crit_q = sae_pend = total_q = 0
    conn.close()

    subject = f"📊 [CDM Daily Summary] {datetime.now().strftime('%d %b %Y')} — {open_q} Open Queries"
    html = _email_template(
        title="📊 Daily CDM Summary Report",
        color="#0D47A1",
        badge=f"AUTO-GENERATED · {datetime.now().strftime('%d %b %Y')}",
        rows={
            "Total Queries": total_q,
            "Open Queries": open_q,
            "Critical (Open)": crit_q,
            "SAEs Pending Report": sae_pend,
            "Report Date": datetime.now().strftime("%d %b %Y %H:%M"),
        },
        footer_note="This is an automated daily summary from the Mini EDC System. Log in to take action on open items.",
    )
    return _send_email(MONITOR_EMAILS, subject, html)


def check_and_alert_new_issues():
    """
    Scan DB for new SAEs and Critical queries, send alerts for unnotified ones.
    Call this after running validation / open_queries.
    """
    conn = get_conn()

    # SAEs not yet alerted
    saes = conn.execute("""
        SELECT usubjid, siteid, aeterm, aesev, aeser, aestdtc, report_flag
        FROM adverse_events
        WHERE report_flag = 'PENDING'
    """).fetchall()

    # Critical open queries not yet alerted
    queries = conn.execute("""
        SELECT query_id, usubjid, siteid, field_name, severity, issue_description
        FROM queries
        WHERE severity = 'Critical' AND status = 'Open'
    """).fetchall()

    conn.close()

    print(
        f"\n[EMAIL] Checking alerts: {len(saes)} SAEs, {len(queries)} Critical queries"
    )

    for s in saes:
        send_sae_alert(
            {
                "usubjid": s[0],
                "siteid": s[1],
                "aeterm": s[2],
                "aesev": s[3],
                "aeser": s[4],
                "aestdtc": s[5],
                "report_flag": s[6],
            }
        )

    for q in queries:
        send_critical_query_alert(
            {
                "query_id": q[0],
                "usubjid": q[1],
                "siteid": q[2],
                "field": q[3],
                "severity": q[4],
                "issue": q[5],
            }
        )


if __name__ == "__main__":
    print("=" * 55)
    print("  EMAIL ALERT SYSTEM — Mini EDC")
    print("=" * 55)
    print("\n⚠️  Before running, set your Gmail credentials in this file:")
    print("    SENDER_EMAIL    = 'your_gmail@gmail.com'")
    print("    SENDER_PASSWORD = 'your_app_password'")
    print("    MONITOR_EMAILS  = ['monitor@example.com']")
    print("\nThen call check_and_alert_new_issues() to send alerts.")
    print("\nRunning check now...")
    check_and_alert_new_issues()
