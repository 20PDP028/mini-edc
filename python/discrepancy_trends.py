"""
discrepancy_trends.py — Feature 6: Discrepancy Trending
Charts showing which sites have most errors over time.
Save in: Mini_EDC_Project/python/discrepancy_trends.py
Run with: python discrepancy_trends.py
"""

import sqlite3
import os
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "..", "sql", "cdm_phase3.db")
REPORTS_DIR = os.path.join(BASE, "..", "reports")

NAVY = "#0D2B55"
TEAL = "#00897B"
RED = "#C62828"
AMBER = "#F57F17"
BLUE = "#1565C0"
PURPLE = "#6A1B9A"
LGRAY = "#F5F5F5"
COLORS = [NAVY, TEAL, RED, AMBER, BLUE, PURPLE]


def load_data():
    conn = sqlite3.connect(DB_PATH)
    df_q = pd.read_sql_query("SELECT * FROM queries", conn)
    df_s = pd.read_sql_query("SELECT * FROM adverse_events", conn)
    df_a = pd.read_sql_query("SELECT * FROM audit_trail", conn)
    conn.close()
    return df_q, df_s, df_a


def plot_queries_by_site(df_q, ax):
    """Bar chart: number of queries per site."""
    if df_q.empty or "siteid" not in df_q.columns:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return
    counts = df_q.groupby("siteid").size().sort_values(ascending=False)
    bars = ax.bar(
        counts.index,
        counts.values,
        color=[COLORS[i % len(COLORS)] for i in range(len(counts))],
        edgecolor="white",
        linewidth=0.5,
    )
    ax.set_title("Queries per Site", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    ax.set_xlabel("Site", fontsize=9, color="#555")
    ax.set_ylabel("Query Count", fontsize=9, color="#555")
    ax.set_facecolor(LGRAY)
    ax.tick_params(colors="#555")
    for bar, val in zip(bars, counts.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.05,
            str(val),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color=NAVY,
        )


def plot_severity_by_site(df_q, ax):
    """Stacked bar: severity breakdown per site."""
    if df_q.empty or "siteid" not in df_q.columns or "severity" not in df_q.columns:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return
    pivot = df_q.groupby(["siteid", "severity"]).size().unstack(fill_value=0)
    sev_colors = {"Critical": RED, "Major": AMBER, "Minor": TEAL}
    pivot.plot(
        kind="bar",
        ax=ax,
        stacked=True,
        color=[sev_colors.get(c, BLUE) for c in pivot.columns],
        edgecolor="white",
        linewidth=0.5,
    )
    ax.set_title(
        "Severity Breakdown by Site", fontsize=11, fontweight="bold", color=NAVY, pad=10
    )
    ax.set_xlabel("Site", fontsize=9, color="#555")
    ax.set_ylabel("Count", fontsize=9, color="#555")
    ax.set_facecolor(LGRAY)
    ax.tick_params(colors="#555", axis="x", rotation=0)
    ax.legend(title="Severity", fontsize=8, title_fontsize=8)


def plot_status_donut(df_q, ax):
    """Donut chart: query status distribution."""
    if df_q.empty or "status" not in df_q.columns:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return
    counts = df_q["status"].value_counts()
    status_colors = {"Open": RED, "Answered": AMBER, "Closed": TEAL}
    colors = [status_colors.get(s, BLUE) for s in counts.index]
    wedges, texts, autotexts = ax.pie(
        counts.values,
        labels=counts.index,
        colors=colors,
        autopct="%1.0f%%",
        startangle=90,
        wedgeprops=dict(width=0.55, edgecolor="white", linewidth=2),
        textprops=dict(fontsize=9),
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontweight("bold")
        at.set_fontsize(9)
    ax.set_title(
        "Query Status Distribution", fontsize=11, fontweight="bold", color=NAVY, pad=10
    )


def plot_top_error_fields(df_q, ax):
    """Horizontal bar: which fields have most errors."""
    if df_q.empty or "field_name" not in df_q.columns:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return
    counts = df_q["field_name"].value_counts().head(8)
    bars = ax.barh(
        counts.index[::-1],
        counts.values[::-1],
        color=TEAL,
        edgecolor="white",
        linewidth=0.5,
    )
    ax.set_title("Top Error Fields", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    ax.set_xlabel("Query Count", fontsize=9, color="#555")
    ax.set_facecolor(LGRAY)
    ax.tick_params(colors="#555")
    for bar, val in zip(bars, counts.values[::-1]):
        ax.text(
            bar.get_width() + 0.05,
            bar.get_y() + bar.get_height() / 2,
            str(val),
            va="center",
            fontsize=9,
            fontweight="bold",
            color=NAVY,
        )


def plot_sae_by_site(df_s, ax):
    """Bar: SAEs per site."""
    if df_s.empty or "siteid" not in df_s.columns:
        ax.text(0.5, 0.5, "No SAE data", ha="center", va="center")
        return
    counts = df_s.groupby("siteid").size().sort_values(ascending=False)
    bars = ax.bar(
        counts.index, counts.values, color=RED, edgecolor="white", linewidth=0.5
    )
    ax.set_title("SAEs per Site", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    ax.set_xlabel("Site", fontsize=9, color="#555")
    ax.set_ylabel("SAE Count", fontsize=9, color="#555")
    ax.set_facecolor(LGRAY)
    ax.tick_params(colors="#555")
    for bar, val in zip(bars, counts.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            str(val),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color=RED,
        )


def plot_critical_vs_major(df_q, ax):
    """Grouped bar: Critical vs Major per site."""
    if df_q.empty or "siteid" not in df_q.columns:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return
    pivot = (
        df_q[df_q["severity"].isin(["Critical", "Major"])]
        .groupby(["siteid", "severity"])
        .size()
        .unstack(fill_value=0)
    )
    x = range(len(pivot))
    w = 0.35
    if "Critical" in pivot.columns:
        ax.bar(
            [i - w / 2 for i in x],
            pivot["Critical"],
            w,
            label="Critical",
            color=RED,
            edgecolor="white",
        )
    if "Major" in pivot.columns:
        ax.bar(
            [i + w / 2 for i in x],
            pivot["Major"],
            w,
            label="Major",
            color=AMBER,
            edgecolor="white",
        )
    ax.set_xticks(list(x))
    ax.set_xticklabels(pivot.index, fontsize=9)
    ax.set_title(
        "Critical vs Major by Site", fontsize=11, fontweight="bold", color=NAVY, pad=10
    )
    ax.set_ylabel("Count", fontsize=9, color="#555")
    ax.set_facecolor(LGRAY)
    ax.tick_params(colors="#555")
    ax.legend(fontsize=8)


def generate_trend_report():
    """Generate a full discrepancy trending PDF chart report."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    df_q, df_s, df_a = load_data()

    fig = plt.figure(figsize=(16, 12))
    fig.patch.set_facecolor("white")

    # Title banner
    fig.text(
        0.5,
        0.97,
        "Clinical Trial — Discrepancy Trending Report",
        ha="center",
        va="top",
        fontsize=16,
        fontweight="bold",
        color=NAVY,
    )
    fig.text(
        0.5,
        0.945,
        f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}  |  Total Queries: {len(df_q)}  |  Total SAEs: {len(df_s)}",
        ha="center",
        va="top",
        fontsize=9,
        color="#777",
    )

    # 6 subplots in 2x3 grid
    ax1 = fig.add_subplot(3, 3, 1)
    ax2 = fig.add_subplot(3, 3, 2)
    ax3 = fig.add_subplot(3, 3, 3)
    ax4 = fig.add_subplot(3, 3, 4)
    ax5 = fig.add_subplot(3, 3, 5)
    ax6 = fig.add_subplot(3, 3, 6)

    plot_queries_by_site(df_q, ax1)
    plot_severity_by_site(df_q, ax2)
    plot_status_donut(df_q, ax3)
    plot_top_error_fields(df_q, ax4)
    plot_sae_by_site(df_s, ax5)
    plot_critical_vs_major(df_q, ax6)

    # Summary stats box
    open_q = len(df_q[df_q["status"] == "Open"]) if "status" in df_q.columns else 0
    crit_q = (
        len(df_q[df_q["severity"] == "Critical"]) if "severity" in df_q.columns else 0
    )
    pend_s = (
        len(df_s[df_s["report_flag"] == "PENDING"])
        if "report_flag" in df_s.columns
        else 0
    )
    fig.text(
        0.02,
        0.08,
        f"SUMMARY  |  Total Queries: {len(df_q)}  ·  Open: {open_q}  ·  Critical: {crit_q}  ·  SAEs Pending: {pend_s}",
        fontsize=9,
        color="white",
        bbox=dict(boxstyle="round,pad=0.5", facecolor=NAVY, alpha=0.9),
    )

    plt.tight_layout(rect=[0, 0.1, 1, 0.93])

    out_path = os.path.join(REPORTS_DIR, "discrepancy_trends.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"[TRENDS] Report saved → {out_path}")
    return out_path


def print_site_summary():
    """Print a text summary of discrepancies per site."""
    df_q, df_s, _ = load_data()
    print("\n" + "=" * 55)
    print("  DISCREPANCY SUMMARY BY SITE")
    print("=" * 55)
    if not df_q.empty and "siteid" in df_q.columns:
        for site in df_q["siteid"].unique():
            site_df = df_q[df_q["siteid"] == site]
            crit = (
                len(site_df[site_df["severity"] == "Critical"])
                if "severity" in site_df.columns
                else 0
            )
            maj = (
                len(site_df[site_df["severity"] == "Major"])
                if "severity" in site_df.columns
                else 0
            )
            opn = (
                len(site_df[site_df["status"] == "Open"])
                if "status" in site_df.columns
                else 0
            )
            print(
                f"  {site:10} | Total: {len(site_df):3} | Critical: {crit:2} | Major: {maj:2} | Open: {opn:2}"
            )
    print()


if __name__ == "__main__":
    print_site_summary()
    path = generate_trend_report()
    print(f"\n✅ Chart saved to: {path}")
    print("   Open reports/discrepancy_trends.png to view.")
