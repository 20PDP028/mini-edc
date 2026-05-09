"""
visit_tracker.py — Feature 8: Visit Completion Tracker
Tracks which subjects completed which visits.
Save in: Mini_EDC_Project/python/visit_tracker.py
Run with: python visit_tracker.py
"""

import os
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
import matplotlib.patches as mpatches
from db_connection import get_conn, is_postgres

BASE = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE, "..", "reports")

NAVY = "#0D2B55"
TEAL = "#00897B"
RED = "#C62828"
AMBER = "#F57F17"
LGRAY = "#F5F5F5"

# Expected visits in a trial — customise as needed
EXPECTED_VISITS = [
    "Screening",
    "Baseline",
    "Week 2",
    "Week 4",
    "Week 8",
    "Week 12",
    "End of Study",
]


def init_visit_table():
    """Add visit_completion table if not exists."""
    conn = get_conn()
    ph = "%s" if is_postgres() else "?"

    if is_postgres():
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visit_completion (
                vc_id       SERIAL PRIMARY KEY,
                usubjid     TEXT,
                siteid      TEXT,
                visit_name  TEXT,
                visit_date  TEXT,
                status      TEXT DEFAULT 'Completed',
                notes       TEXT,
                recorded_at TEXT
            )
        """)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visit_completion (
                vc_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                usubjid     TEXT,
                siteid      TEXT,
                visit_name  TEXT,
                visit_date  TEXT,
                status      TEXT DEFAULT 'Completed',
                notes       TEXT,
                recorded_at TEXT
            )
        """)
    conn.commit()

    # Populate from existing visits table
    existing = conn.execute("SELECT COUNT(*) FROM visit_completion").fetchone()[0]
    if existing == 0:
        visits = conn.execute("""
            SELECT v.usubjid, s.siteid, v.visit_date
            FROM visits v
            LEFT JOIN subjects s ON v.usubjid = s.usubjid
        """).fetchall()

        visit_names = ["Screening", "Baseline", "Week 4", "Week 8", "End of Study"]
        for i, (subj, site, vdate) in enumerate(visits):
            vname = visit_names[i % len(visit_names)]
            conn.execute(
                f"""
                INSERT INTO visit_completion (usubjid, siteid, visit_name, visit_date, status, recorded_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, 'Completed', {ph})
            """,
                (subj, site or "UNKNOWN", vname, vdate, datetime.now().isoformat()),
            )

    conn.commit()
    conn.close()


def get_completion_matrix():
    """Returns a subject × visit completion matrix."""
    conn = get_conn()
    df_vc = pd.read_sql_query("SELECT * FROM visit_completion", conn)
    df_sub = pd.read_sql_query("SELECT usubjid, siteid FROM subjects", conn)
    print(f"Loaded {len(df_vc)} visit completion records and {len(df_sub)} subjects")

    conn.close()

    if df_vc.empty:
        return pd.DataFrame()

    # Pivot: rows=subjects, cols=visit names
    matrix = df_vc.pivot_table(
        index="usubjid", columns="visit_name", values="status", aggfunc="first"
    ).fillna("Missing")

    return matrix


def completion_rate_by_site():
    """Returns completion % per site."""
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT siteid,
               COUNT(*) as total,
               SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) as completed
        FROM visit_completion
        GROUP BY siteid
    """,
        conn,
    )
    conn.close()
    if not df.empty:
        df["rate"] = (df["completed"] / df["total"] * 100).round(1)
    return df


def print_visit_summary():
    """Print text summary of visit completion."""
    init_visit_table()
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM visit_completion").fetchone()[0]
    complete = conn.execute(
        "SELECT COUNT(*) FROM visit_completion WHERE status='Completed'"
    ).fetchone()[0]
    missing = conn.execute(
        "SELECT COUNT(*) FROM visit_completion WHERE status='Missing'"
    ).fetchone()[0]
    conn.close()

    print("\n" + "=" * 55)
    print("  VISIT COMPLETION TRACKER")
    print("=" * 55)
    print(f"  Total Visits Recorded : {total}")
    print(f"  Completed             : {complete}")
    print(f"  Missing               : {missing}")
    rate = round(complete / total * 100, 1) if total > 0 else 0
    print(f"  Overall Rate          : {rate}%")

    rate_df = completion_rate_by_site()
    if not rate_df.empty:
        print("\n  Completion Rate by Site:")
        for _, row in rate_df.iterrows():
            bar = "█" * int(row["rate"] / 5) + "░" * (20 - int(row["rate"] / 5))
            print(f"  {row['siteid']:10} [{bar}] {row['rate']}%")
    print()


def generate_visit_chart():
    """Generate visit completion heatmap and bar chart."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    init_visit_table()

    matrix = get_completion_matrix()
    rate_df = completion_rate_by_site()

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.patch.set_facecolor("white")
    fig.suptitle(
        "Visit Completion Tracker", fontsize=14, fontweight="bold", color=NAVY, y=0.98
    )

    # ── Heatmap ───────────────────────────────────────────────
    ax1 = axes[0]
    if not matrix.empty:
        numeric = matrix.replace({"Completed": 1, "Missing": 0, "Partial": 0.5})

        ax1.imshow(
            numeric.values.astype(float),
            cmap="RdYlGn",
            aspect="auto",
            vmin=0,
            vmax=1,
        )

        ax1.set_xticks(range(len(matrix.columns)))
        ax1.set_xticklabels(matrix.columns, rotation=30, ha="right", fontsize=8)
        ax1.set_yticks(range(len(matrix.index)))
        ax1.set_yticklabels(matrix.index, fontsize=8)

        symbol_map = {"Completed": "✓", "Missing": "✗", "Partial": "~"}
        text_color_map = {"Completed": "white", "Missing": "#333", "Partial": "#333"}

        for i in range(len(matrix.index)):
            for j in range(len(matrix.columns)):
                val = matrix.iloc[i, j]
                ax1.text(
                    j,
                    i,
                    symbol_map.get(val, "?"),
                    ha="center",
                    va="center",
                    fontsize=10,
                    color=text_color_map.get(val, "#333"),
                )

        ax1.set_title(
            "Subject × Visit Completion Matrix",
            fontsize=11,
            fontweight="bold",
            color=NAVY,
            pad=10,
        )
        ax1.set_xlabel("Visit", fontsize=9, color="#555")
        ax1.set_ylabel("Subject ID", fontsize=9, color="#555")

        legend_handles = [
            mpatches.Patch(fc=TEAL, label="Completed"),
            mpatches.Patch(fc=AMBER, label="Partial"),
            mpatches.Patch(fc=RED, label="Missing"),
        ]
        ax1.legend(handles=legend_handles, loc="upper right", fontsize=8)

    else:
        ax1.text(0.5, 0.5, "No visit data", ha="center", va="center")

    # ── Bar chart: completion rate by site ────────────────────
    ax2 = axes[1]
    if not rate_df.empty:
        colors = [
            TEAL if r >= 80 else AMBER if r >= 60 else RED for r in rate_df["rate"]
        ]
        bars = ax2.bar(
            rate_df["siteid"],
            rate_df["rate"],
            color=colors,
            edgecolor="white",
            linewidth=0.5,
        )
        ax2.axhline(
            y=80,
            color=TEAL,
            linestyle="--",
            linewidth=1.5,
            alpha=0.7,
            label="80% Target",
        )
        ax2.set_ylim(0, 110)
        ax2.set_title(
            "Visit Completion Rate by Site",
            fontsize=11,
            fontweight="bold",
            color=NAVY,
            pad=10,
        )
        ax2.set_xlabel("Site", fontsize=9, color="#555")
        ax2.set_ylabel("Completion %", fontsize=9, color="#555")
        ax2.set_facecolor(LGRAY)
        ax2.tick_params(colors="#555")
        ax2.legend(fontsize=8)
        for bar, val in zip(bars, rate_df["rate"]):
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{val}%",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color=NAVY,
            )
    else:
        ax2.text(0.5, 0.5, "No site data", ha="center", va="center")

    plt.tight_layout()
    out_path = os.path.join(REPORTS_DIR, "visit_completion.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"[VISITS] Chart saved → {out_path}")
    return out_path


if __name__ == "__main__":
    print_visit_summary()
    generate_visit_chart()
    print("✅ Visit completion chart saved to reports/visit_completion.png")
