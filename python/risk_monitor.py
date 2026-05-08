"""
risk_monitor.py — Feature 18: Risk-Based Monitoring
Scores each site (0–100) based on data quality, SAEs, and query age.
Save in: Mini_EDC_Project/python/risk_monitor.py

Run: python risk_monitor.py
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "sql", "cdm_phase3.db")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


# ── Scoring weights ───────────────────────────────────────────
# Total max = 100 points of risk (higher = worse)
WEIGHTS = {
    "critical_queries": 25,  # per critical open query
    "sae_pending": 30,  # per pending SAE report
    "major_queries": 10,  # per major open query
    "stale_queries_7d": 15,  # per query open 7+ days
    "unanswered_rate": 20,  # % of queries never answered × 0.2
}
MAX_SCORE = 100


def get_db():
    if not os.path.exists(DB_PATH):
        print(f"[RISK] Database not found: {DB_PATH}")
        print("[RISK] Run main_phase3.py first to create the database.")
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_sites():
    conn = get_db()
    if not conn:
        return []
    with conn:
        rows = conn.execute(
            "SELECT DISTINCT siteid FROM subjects ORDER BY siteid"
        ).fetchall()
    return [r["siteid"] for r in rows]


def score_site(conn, siteid):
    """Compute risk score for a single site. Returns score dict."""
    score = 0
    factors = []

    # 1. Critical open queries
    crit = conn.execute(
        "SELECT COUNT(*) FROM queries WHERE siteid=? AND severity='Critical' AND status='Open'",
        (siteid,),
    ).fetchone()[0]
    pts = min(crit * WEIGHTS["critical_queries"], 40)
    score += pts
    if crit:
        factors.append(
            {
                "factor": "Critical open queries",
                "count": crit,
                "points": pts,
                "level": "HIGH",
            }
        )

    # 2. SAE pending report
    sae = conn.execute(
        """
        SELECT COUNT(*) FROM adverse_events ae
        JOIN subjects s USING(usubjid)
        WHERE s.siteid=? AND ae.aeser='Y' AND ae.report_flag='PENDING'
    """,
        (siteid,),
    ).fetchone()[0]
    pts = min(sae * WEIGHTS["sae_pending"], 40)
    score += pts
    if sae:
        factors.append(
            {
                "factor": "SAEs pending 24hr report",
                "count": sae,
                "points": pts,
                "level": "CRITICAL",
            }
        )

    # 3. Major open queries
    major = conn.execute(
        "SELECT COUNT(*) FROM queries WHERE siteid=? AND severity='Major' AND status='Open'",
        (siteid,),
    ).fetchone()[0]
    pts = min(major * WEIGHTS["major_queries"], 20)
    score += pts
    if major:
        factors.append(
            {
                "factor": "Major open queries",
                "count": major,
                "points": pts,
                "level": "MEDIUM",
            }
        )

    # 4. Stale queries (7+ days)
    stale = conn.execute(
        """
        SELECT COUNT(*) FROM queries
        WHERE siteid=? AND status='Open'
          AND julianday('now') - julianday(created_at) > 7
    """,
        (siteid,),
    ).fetchone()[0]
    pts = min(stale * WEIGHTS["stale_queries_7d"], 20)
    score += pts
    if stale:
        factors.append(
            {
                "factor": "Stale queries (7+ days)",
                "count": stale,
                "points": pts,
                "level": "MEDIUM",
            }
        )

    # 5. Unanswered rate
    total_q = conn.execute(
        "SELECT COUNT(*) FROM queries WHERE siteid=?", (siteid,)
    ).fetchone()[0]
    open_q = conn.execute(
        "SELECT COUNT(*) FROM queries WHERE siteid=? AND status='Open'", (siteid,)
    ).fetchone()[0]
    unans_rate = (open_q / total_q * 100) if total_q else 0
    pts = min(int(unans_rate * WEIGHTS["unanswered_rate"] / 100), 20)
    score += pts
    if pts:
        factors.append(
            {
                "factor": f"Unanswered rate ({unans_rate:.0f}%)",
                "count": open_q,
                "points": pts,
                "level": "LOW",
            }
        )

    # Cap at 100
    score = min(score, MAX_SCORE)

    # Risk category
    if score >= 60:
        category = "HIGH RISK"
        action = "Immediate on-site visit required"
        icon = "🔴"
    elif score >= 30:
        category = "MEDIUM RISK"
        action = "Remote monitoring review within 2 weeks"
        icon = "🟡"
    else:
        category = "LOW RISK"
        action = "Routine monitoring schedule"
        icon = "🟢"

    # Site stats
    subjects = conn.execute(
        "SELECT COUNT(*) FROM subjects WHERE siteid=?", (siteid,)
    ).fetchone()[0]

    return {
        "siteid": siteid,
        "score": score,
        "category": category,
        "action": action,
        "icon": icon,
        "subjects": subjects,
        "critical_queries": crit,
        "major_queries": major,
        "sae_pending": sae,
        "stale_queries": stale,
        "unanswered_rate": round(unans_rate, 1),
        "factors": factors,
    }


def run_risk_assessment():
    print("\n" + "=" * 65)
    print("  FEATURE 18 — Risk-Based Monitoring Site Assessment")
    print("=" * 65)

    conn = get_db()
    if not conn:
        return []

    sites = get_sites()
    if not sites:
        print("[RISK] No sites found in database.")
        return []

    results = []
    with conn:
        for siteid in sites:
            results.append(score_site(conn, siteid))

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    # ── Console report ────────────────────────────────────────
    print(
        f"\n{'Site':<10} {'Score':>6} {'Category':<15} {'Subj':>5} {'Crit':>5} {'SAE':>5} {'Stale':>6}  Action"
    )
    print("─" * 90)
    for r in results:
        print(
            f"{r['icon']} {r['siteid']:<8} {r['score']:>5}/100  {r['category']:<15} "
            f"{r['subjects']:>5} {r['critical_queries']:>5} {r['sae_pending']:>5} "
            f"{r['stale_queries']:>6}  {r['action']}"
        )

    print("\n── Risk Factors Detail ─────────────────────────────────────")
    for r in results:
        if r["factors"]:
            print(f"\n  {r['icon']} {r['siteid']} (Score: {r['score']})")
            for f in r["factors"]:
                print(f"    [{f['level']:<8}] {f['factor']:<35} +{f['points']} pts")

    # ── Save JSON report ──────────────────────────────────────
    report = {
        "generated_at": datetime.now().isoformat(),
        "site_count": len(results),
        "high_risk": sum(1 for r in results if r["category"] == "HIGH RISK"),
        "medium_risk": sum(1 for r in results if r["category"] == "MEDIUM RISK"),
        "low_risk": sum(1 for r in results if r["category"] == "LOW RISK"),
        "sites": results,
    }
    json_path = os.path.join(REPORT_DIR, "risk_assessment.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n[RISK] Report saved → {json_path}")

    # ── Try to save Excel if openpyxl available ───────────────
    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Risk Assessment"

        # Header
        headers = [
            "Site ID",
            "Risk Score",
            "Category",
            "Action Required",
            "Subjects",
            "Critical Queries",
            "SAEs Pending",
            "Stale Queries",
            "Unans. Rate %",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="0D2B55")
            cell.alignment = Alignment(horizontal="center")

        # Data rows
        fill_high = PatternFill("solid", fgColor="FFCCCC")
        fill_medium = PatternFill("solid", fgColor="FFF3CC")
        fill_low = PatternFill("solid", fgColor="CCFFCC")

        for row_n, r in enumerate(results, 2):
            fill = (
                fill_high
                if r["score"] >= 60
                else (fill_medium if r["score"] >= 30 else fill_low)
            )
            vals = [
                r["siteid"],
                r["score"],
                r["category"],
                r["action"],
                r["subjects"],
                r["critical_queries"],
                r["sae_pending"],
                r["stale_queries"],
                r["unanswered_rate"],
            ]
            for col, v in enumerate(vals, 1):
                cell = ws.cell(row=row_n, column=col, value=v)
                cell.fill = fill

        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["C"].width = 16
        ws.column_dimensions["D"].width = 40

        xlsx_path = os.path.join(REPORT_DIR, "risk_assessment.xlsx")
        wb.save(xlsx_path)
        print(f"[RISK] Excel saved  → {xlsx_path}")
    except ImportError:
        print("[RISK] openpyxl not installed — skipping Excel export")

    print("\n" + "=" * 65)
    return results


if __name__ == "__main__":
    run_risk_assessment()
