"""
pdf_report.py — Phase 4 Clinical Data Management PDF Audit Report
Generates a printable PDF report for monitors and sponsors.
Save in: Mini_EDC_Project/python/pdf_report.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from datetime import datetime
import os

# ── Colour palette ────────────────────────────────────────────
NAVY    = colors.HexColor("#0D2B55")
TEAL    = colors.HexColor("#00897B")
RED     = colors.HexColor("#C62828")
AMBER   = colors.HexColor("#F57F17")
LGRAY   = colors.HexColor("#F5F5F5")
MGRAY   = colors.HexColor("#BDBDBD")
WHITE   = colors.white
BLACK   = colors.black


def _styles():
    
    return {
        "title": ParagraphStyle("title", fontSize=20, textColor=WHITE,
                                 fontName="Helvetica-Bold", alignment=TA_CENTER,
                                 spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", fontSize=10, textColor=WHITE,
                                    fontName="Helvetica", alignment=TA_CENTER),
        "h1": ParagraphStyle("h1", fontSize=13, textColor=NAVY,
                              fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=4),
        "h2": ParagraphStyle("h2", fontSize=10, textColor=TEAL,
                              fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("body", fontSize=9, fontName="Helvetica",
                                leading=13, spaceAfter=3),
        "small": ParagraphStyle("small", fontSize=7.5, fontName="Helvetica",
                                  textColor=colors.grey),
        "footer": ParagraphStyle("footer", fontSize=7, textColor=MGRAY,
                                  fontName="Helvetica", alignment=TA_CENTER),
        "critical": ParagraphStyle("critical", fontSize=9, textColor=RED,
                                    fontName="Helvetica-Bold"),
        "major": ParagraphStyle("major", fontSize=9, textColor=AMBER,
                                 fontName="Helvetica-Bold"),
    }


def _header_table(trial_name, report_date, generated_by):
    """Dark navy header banner."""
    data = [[
        Paragraph(f"<b>{trial_name}</b>", ParagraphStyle(
            "th", fontSize=16, textColor=WHITE, fontName="Helvetica-Bold")),
        Paragraph(
            f"CDM Audit Report<br/><font size='8'>{report_date}</font>",
            ParagraphStyle("ts", fontSize=10, textColor=WHITE,
                           fontName="Helvetica", alignment=TA_RIGHT))
    ]]
    t = Table(data, colWidths=[11*cm, 7.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",(0,0), (-1,-1), 14),
        ("RIGHTPADDING",(0,0),(-1,-1), 14),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING",(0,0),(-1,-1), 14),
    ]))
    return t


def _kpi_row(kpis):
    """A row of KPI boxes: [(label, value, color), ...]"""
    cell_data = []
    for label, value, bg in kpis:
        cell = Table(
            [[Paragraph(str(value), ParagraphStyle(
                "kv", fontSize=22, fontName="Helvetica-Bold",
                textColor=WHITE, alignment=TA_CENTER))],
             [Paragraph(label, ParagraphStyle(
                "kl", fontSize=8, fontName="Helvetica",
                textColor=WHITE, alignment=TA_CENTER))]],
            colWidths=[4.4*cm]
        )
        cell.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), bg),
            ("TOPPADDING", (0,0), (-1,-1), 10),
            ("BOTTOMPADDING",(0,0),(-1,-1), 10),
            ("ROUNDEDCORNERS", [6]),
        ]))
        cell_data.append(cell)

    row = Table([cell_data], colWidths=[4.6*cm]*len(kpis))
    row.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1), 4),
        ("RIGHTPADDING",(0,0),(-1,-1), 4),
    ]))
    return row


def _query_table(queries, styles):
    """Styled table of queries."""
    header = ["Query ID", "Subject", "Site", "Field", "Severity", "Status", "Issue"]
    rows = [header]
    for q in queries:
        rows.append([
            q.get("query_id",""),
            q.get("usubjid",""),
            q.get("siteid",""),
            q.get("field",""),
            q.get("severity",""),
            q.get("status",""),
            Paragraph(q.get("issue",""), styles["small"]),
        ])

    col_w = [2.2*cm, 2.2*cm, 1.8*cm, 2.2*cm, 2*cm, 2*cm, 6.1*cm]
    t = Table(rows, colWidths=col_w, repeatRows=1)

    style = [
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LGRAY]),
        ("GRID",       (0,0), (-1,-1), 0.4, MGRAY),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",(0,0), (-1,-1), 5),
        ("RIGHTPADDING",(0,0),(-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]
    # Colour severity cells
    for i, q in enumerate(queries, start=1):
        sev = q.get("severity","")
        col = RED if sev == "Critical" else (AMBER if sev == "Major" else TEAL)
        style.append(("TEXTCOLOR", (4,i), (4,i), col))
        style.append(("FONTNAME",  (4,i), (4,i), "Helvetica-Bold"))
        # Status colour
        st = q.get("status","")
        sc = TEAL if st == "Closed" else (AMBER if st == "Answered" else RED)
        style.append(("TEXTCOLOR", (5,i), (5,i), sc))

    t.setStyle(TableStyle(style))
    return t


def _sae_table(saes, styles):
    """SAE reporting table."""
    header = ["Subject", "Site", "AE Term", "Severity", "Serious?", "Date", "Status"]
    rows = [header]
    for s in saes:
        rows.append([
            s.get("usubjid",""),
            s.get("siteid",""),
            s.get("aeterm",""),
            s.get("aesev",""),
            s.get("aeser",""),
            s.get("aestdtc",""),
            s.get("report_flag",""),
        ])
    col_w = [2.2*cm, 1.8*cm, 3.5*cm, 2.2*cm, 2*cm, 2.5*cm, 4.3*cm]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), RED),
        ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LGRAY]),
        ("GRID",       (0,0), (-1,-1), 0.4, MGRAY),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",(0,0), (-1,-1), 5),
        ("RIGHTPADDING",(0,0),(-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))
    return t


def _audit_table(audit_rows, styles):
    """Audit trail table."""
    header = ["Time", "Action", "Table", "Record", "Field", "Old", "New", "By"]
    rows = [header]
    for a in audit_rows:
        rows.append([
            a.get("event_time","")[:16],
            a.get("action",""),
            a.get("table_name",""),
            a.get("record_id",""),
            a.get("field","") or "-",
            a.get("old_value","") or "-",
            a.get("new_value","") or "-",
            a.get("performed_by",""),
        ])
    col_w = [2.8*cm, 2.8*cm, 2.5*cm, 2.2*cm, 2*cm, 2*cm, 2*cm, 2.2*cm]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), TEAL),
        ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 7.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LGRAY]),
        ("GRID",       (0,0), (-1,-1), 0.4, MGRAY),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",(0,0), (-1,-1), 4),
        ("RIGHTPADDING",(0,0),(-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
    ]))
    return t


def generate_pdf(
    output_path: str,
    trial_name: str,
    queries: list,
    saes: list,
    audit_rows: list,
    generated_by: str = "Data Management System",
    protocol: str = "PROTO-001",
):
    """
    Generate a full CDM Audit PDF report.

    Args:
        output_path: where to save the PDF
        trial_name:  e.g. "CARDIO-PHASE2 Trial"
        queries:     list of dicts with query_id, usubjid, siteid, field, severity, status, issue
        saes:        list of dicts with usubjid, siteid, aeterm, aesev, aeser, aestdtc, report_flag
        audit_rows:  list of dicts from audit_trail table
        generated_by: name/system generating the report
        protocol:    protocol number
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=2*cm,
    )
    s = _styles()
    story = []
    now = datetime.now().strftime("%d-%b-%Y %H:%M")

    # ── Cover Header ──────────────────────────────────────────
    story.append(_header_table(trial_name, now, generated_by))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"Protocol: {protocol} &nbsp;|&nbsp; Generated by: {generated_by} &nbsp;|&nbsp; "
        f"CONFIDENTIAL — For authorised personnel only",
        ParagraphStyle("meta", fontSize=8, textColor=MGRAY, fontName="Helvetica",
                        alignment=TA_CENTER)
    ))
    story.append(Spacer(1, 16))

    # ── KPI Summary ───────────────────────────────────────────
    open_q   = sum(1 for q in queries if q.get("status") == "Open")
    ans_q    = sum(1 for q in queries if q.get("status") == "Answered")
    closed_q = sum(1 for q in queries if q.get("status") == "Closed")
    crit_q   = sum(1 for q in queries if q.get("severity") == "Critical")

    story.append(Paragraph("Executive Summary", s["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY))
    story.append(Spacer(1, 8))
    story.append(_kpi_row([
        ("Total Queries",   len(queries), NAVY),
        ("Open",            open_q,       RED),
        ("Answered",        ans_q,        AMBER),
        ("Closed",          closed_q,     TEAL),
        ("Critical",        crit_q,       colors.HexColor("#6A1B9A")),
    ]))
    story.append(Spacer(1, 8))
    story.append(_kpi_row([
        ("Total SAEs",      len(saes),    RED),
        ("Pending Report",  sum(1 for s in saes if s.get("report_flag")=="PENDING"), AMBER),
        ("Audit Events",    len(audit_rows), TEAL),
        ("Subjects",        len({q.get("usubjid") for q in queries}), NAVY),
        ("Sites",           len({q.get("siteid") for q in queries}), colors.HexColor("#00695C")),
    ]))
    story.append(Spacer(1, 16))

    # ── Query Listing ─────────────────────────────────────────
    story.append(Paragraph("Data Query Listing", s["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY))
    story.append(Spacer(1, 6))

    if queries:
        # Open first
        open_list = [q for q in queries if q.get("status") == "Open"]
        other_list = [q for q in queries if q.get("status") != "Open"]
        story.append(Paragraph(f"Open Queries ({len(open_list)})", s["h2"]))
        if open_list:
            story.append(_query_table(open_list, s))
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"Answered / Closed Queries ({len(other_list)})", s["h2"]))
        if other_list:
            story.append(_query_table(other_list, s))
    else:
        story.append(Paragraph("No queries found.", s["body"]))

    story.append(PageBreak())

    # ── SAE Section ───────────────────────────────────────────
    story.append(Paragraph("Serious Adverse Events (SAE)", s["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=RED))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "The following SAEs require 24-hour expedited reporting per protocol.",
        s["body"]
    ))
    story.append(Spacer(1, 6))
    if saes:
        story.append(_sae_table(saes, s))
    else:
        story.append(Paragraph("No SAEs detected.", s["body"]))

    story.append(Spacer(1, 16))

    # ── Audit Trail ───────────────────────────────────────────
    story.append(Paragraph("21 CFR Part 11 Audit Trail", s["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=TEAL))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Complete record of all data changes, query events, and system actions.",
        s["body"]
    ))
    story.append(Spacer(1, 6))
    if audit_rows:
        story.append(_audit_table(audit_rows[:50], s))  # max 50 rows
        if len(audit_rows) > 50:
            story.append(Paragraph(
                f"... and {len(audit_rows)-50} more audit entries. See full DB for complete trail.",
                s["small"]
            ))
    else:
        story.append(Paragraph("No audit records found.", s["body"]))

    story.append(Spacer(1, 20))

    # ── Footer ────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=MGRAY))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"CONFIDENTIAL — {trial_name} | Generated: {now} | "
        f"This report is for authorised clinical trial personnel only.",
        s["footer"]
    ))

    doc.build(story)
    print(f"[PDF] Report saved → {output_path}")
    return output_path


if __name__ == "__main__":
    # Demo with sample data
    sample_queries = [
        {"query_id": "QRY-0001", "usubjid": "SUB001", "siteid": "SITE01",
         "field": "WEIGHTBL", "severity": "Major", "status": "Closed",
         "issue": "WEIGHTBL missing at baseline"},
        {"query_id": "QRY-0002", "usubjid": "SUB004", "siteid": "SITE01",
         "field": "AGE", "severity": "Critical", "status": "Answered",
         "issue": "AGE 145 out of range (1-120)"},
        {"query_id": "QRY-0003", "usubjid": "SUB005", "siteid": "SITE02",
         "field": "SEX", "severity": "Major", "status": "Open",
         "issue": "Invalid SEX value — CDISC requires M or F"},
        {"query_id": "QRY-0004", "usubjid": "SUB008", "siteid": "SITE02",
         "field": "LBTEST_HB", "severity": "Critical", "status": "Open",
         "issue": "Haemoglobin 3.2 g/dL out of range (8-18)"},
    ]
    sample_saes = [
        {"usubjid": "SUB010", "siteid": "SITE03", "aeterm": "Anaphylaxis",
         "aesev": "SEVERE", "aeser": "Y", "aestdtc": "2024-11-15",
         "report_flag": "PENDING"},
    ]
    sample_audit = [
        {"event_time": "2024-11-20 09:01:00", "action": "QUERY_OPEN",
         "table_name": "queries", "record_id": "QRY-0001",
         "field": "status", "old_value": None, "new_value": "Open",
         "performed_by": "SYSTEM"},
        {"event_time": "2024-11-21 14:30:00", "action": "QUERY_ANSWER",
         "table_name": "queries", "record_id": "QRY-0001",
         "field": "status", "old_value": "Open", "new_value": "Answered",
         "performed_by": "SITE_001"},
        {"event_time": "2024-11-22 10:00:00", "action": "QUERY_CLOSE",
         "table_name": "queries", "record_id": "QRY-0001",
         "field": "status", "old_value": "Answered", "new_value": "Closed",
         "performed_by": "DM_JOHN"},
        {"event_time": "2024-11-20 09:01:05", "action": "SAE_FLAG",
         "table_name": "adverse_events", "record_id": "SUB010",
         "field": "AESER", "old_value": None, "new_value": "Anaphylaxis",
         "performed_by": "SYSTEM"},
    ]
    generate_pdf(
        output_path="../reports/cdm_audit_report.pdf",
        trial_name="CARDIO-PHASE2 Trial",
        queries=sample_queries,
        saes=sample_saes,
        audit_rows=sample_audit,
        generated_by="Mini EDC System v3.0",
        protocol="PROTO-CARDIO-002",
    )
