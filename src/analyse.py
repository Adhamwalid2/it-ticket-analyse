"""
Step 2: Run the KPI queries from sql/kpis.sql, add medians with pandas,
and create the charts.

Outputs:
  output/tabellen/*.csv   - one table per query
  output/kennzahlen.json  - headline numbers for Excel and PowerPoint
  output/diagramme/*.png  - charts
"""
import json
import re
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "tickets.db"
SQL_FILE = ROOT / "sql" / "kpis.sql"
OUT = ROOT / "output"
TABLES = OUT / "tabellen"
CHARTS = OUT / "diagramme"

ACCENT = "#C8102E"
GREY = "#9AA1AD"
TEXT = "#1A1D24"


def load_queries() -> dict[str, str]:
    """Split kpis.sql into {name: sql} using the '-- name:' markers."""
    parts = re.split(r"^-- name:\s*(\w+)\s*$", SQL_FILE.read_text(encoding="utf-8"), flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def style(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=TEXT, pad=12)
    ax.set_xlabel(xlabel, color=TEXT)
    ax.set_ylabel(ylabel, color=TEXT)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(GREY)
    ax.spines["bottom"].set_color(GREY)
    ax.tick_params(colors=TEXT)
    ax.grid(axis="y", color="#E3E6EB", linewidth=0.8)
    ax.set_axisbelow(True)


def label_bars(ax, bars, fmt: str) -> None:
    for b in bars:
        ax.annotate(fmt.format(b.get_height()), (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=10, color=TEXT, xytext=(0, 3),
                    textcoords="offset points")


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(CHARTS / name, dpi=160)
    plt.close(fig)


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    CHARTS.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB) as con:
        results = {name: pd.read_sql(sql, con) for name, sql in load_queries().items()}
        incidents = pd.read_sql("SELECT reassignment_count, priority, resolution_hours FROM incidents", con)

    # Medians (SQLite has no MEDIAN function): resolution times are very skewed, so the median is fairer.
    incidents["weiterleitungen"] = incidents["reassignment_count"].clip(upper=3).astype(int).astype(str).replace("3", "3+")
    med_reassign = incidents.groupby("weiterleitungen")["resolution_hours"].median().round(1)
    results["sla_nach_weiterleitungen"]["median_loesungszeit_h"] = (
        results["sla_nach_weiterleitungen"]["weiterleitungen"].map(med_reassign))
    med_prio = incidents.groupby("priority")["resolution_hours"].median().round(1)
    results["sla_nach_prioritaet"]["median_loesungszeit_h"] = results["sla_nach_prioritaet"]["prioritaet"].map(med_prio)

    states = results["zeit_je_status"]
    states["anteil_pct"] = (states["stunden_gesamt"] / states["stunden_gesamt"].sum() * 100).round(1)

    for name, df in results.items():
        df.to_csv(TABLES / f"{name}.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")

    # Headline numbers
    ov = results["ueberblick"].iloc[0]
    re_ = results["sla_nach_weiterleitungen"].set_index("weiterleitungen")
    waiting = states.set_index("status")["anteil_pct"]
    kennzahlen = {
        "tickets": int(ov["tickets"]),
        "zeitraum_von": ov["zeitraum_von"][:10],
        "zeitraum_bis": ov["zeitraum_bis"][:10],
        "sla_quote_pct": float(ov["sla_quote_pct"]),
        "anteil_weitergeleitet_pct": float(ov["anteil_weitergeleitet_pct"]),
        "anteil_wiedereroeffnet_pct": float(ov["anteil_wiedereroeffnet_pct"]),
        "median_loesungszeit_h": float(incidents["resolution_hours"].median().round(1)),
        "sla_0_weiterleitungen_pct": float(re_.loc["0", "sla_quote_pct"]),
        "sla_3plus_weiterleitungen_pct": float(re_.loc["3+", "sla_quote_pct"]),
        "median_h_0_weiterleitungen": float(re_.loc["0", "median_loesungszeit_h"]),
        "median_h_3plus_weiterleitungen": float(re_.loc["3+", "median_loesungszeit_h"]),
        "anteil_warten_auf_nutzer_pct": float(waiting.get("Awaiting User Info", 0.0)),
    }
    (OUT / "kennzahlen.json").write_text(json.dumps(kennzahlen, indent=2, ensure_ascii=False), encoding="utf-8")

    # Chart 1: SLA by reassignments (key finding)
    df = results["sla_nach_weiterleitungen"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(df["weiterleitungen"], df["sla_quote_pct"],
                  color=[GREY, GREY, GREY, ACCENT][: len(df)], width=0.6)
    label_bars(ax, bars, "{:.0f} %")
    ax.set_ylim(0, 100)
    style(ax, "SLA-Einhaltung sinkt mit jeder Weiterleitung", "Anzahl Weiterleitungen an andere Teams",
          "SLA eingehalten (%)")
    save(fig, "01_sla_nach_weiterleitungen.png")

    # Chart 2: median resolution time by reassignments
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(df["weiterleitungen"], df["median_loesungszeit_h"],
                  color=[GREY, GREY, GREY, ACCENT][: len(df)], width=0.6)
    label_bars(ax, bars, "{:.0f} h")
    style(ax, "Lösungszeit (Median) nach Weiterleitungen", "Anzahl Weiterleitungen", "Stunden bis zur Lösung")
    save(fig, "02_loesungszeit_nach_weiterleitungen.png")

    # Chart 3: SLA by priority
    df = results["sla_nach_prioritaet"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    colors = [ACCENT if v < 50 else GREY for v in df["sla_quote_pct"]]
    bars = ax.bar(df["prioritaet"], df["sla_quote_pct"], color=colors, width=0.6)
    label_bars(ax, bars, "{:.0f} %")
    ax.set_ylim(0, 100)
    style(ax, "SLA-Einhaltung nach Priorität", "", "SLA eingehalten (%)")
    save(fig, "03_sla_nach_prioritaet.png")

    # Chart 4: where does the time go?
    df = states.sort_values("anteil_pct")
    fig, ax = plt.subplots(figsize=(7, 4.2))
    colors = [ACCENT if s == "Awaiting User Info" else GREY for s in df["status"]]
    bars = ax.barh(df["status"], df["anteil_pct"], color=colors)
    for b in bars:
        ax.annotate(f"{b.get_width():.1f} %".replace(".", ","), (b.get_width(), b.get_y() + b.get_height() / 2),
                    va="center", fontsize=10, color=TEXT, xytext=(4, 0), textcoords="offset points")
    style(ax, "Wo verbringen Tickets ihre Zeit? (bis zur Lösung)", "Anteil an der Gesamtzeit (%)")
    ax.grid(axis="x", color="#E3E6EB")
    ax.grid(axis="y", visible=False)
    save(fig, "04_zeit_je_status.png")

    # Chart 5: tickets per month
    df = results["tickets_pro_monat"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(df["monat"], df["tickets"], color=ACCENT, marker="o", linewidth=2)
    style(ax, "Tickets pro Monat", "", "Neue Tickets")
    ax.tick_params(axis="x", rotation=45)
    save(fig, "05_tickets_pro_monat.png")

    # Chart 6: top teams
    df = results["top_teams"].sort_values("tickets")
    fig, ax = plt.subplots(figsize=(7, 4.2))
    colors = [ACCENT if v < kennzahlen["sla_quote_pct"] else GREY for v in df["sla_quote_pct"]]
    bars = ax.barh(df["team"], df["sla_quote_pct"], color=colors)
    for b, n in zip(bars, df["tickets"]):
        ax.annotate(f"{b.get_width():.0f} %  ({n:,} Tickets)".replace(",", "."),
                    (b.get_width(), b.get_y() + b.get_height() / 2), va="center", fontsize=9,
                    color=TEXT, xytext=(4, 0), textcoords="offset points",
                    bbox=dict(boxstyle="square,pad=0.15", facecolor="white", edgecolor="none"))
    avg = kennzahlen["sla_quote_pct"]
    ax.axvline(avg, color=TEXT, linestyle="--", linewidth=1, zorder=0)
    ax.text(avg, len(df) - 0.35, f"Ø {avg:.0f} %", ha="center", va="bottom", fontsize=9, color=TEXT)
    ax.set_xlim(0, 115)
    style(ax, "Top-10-Teams: SLA-Einhaltung (rot = unter Ø)", "SLA eingehalten (%)")
    ax.grid(axis="x", color="#E3E6EB")
    ax.grid(axis="y", visible=False)
    save(fig, "06_top_teams.png")

    print(json.dumps(kennzahlen, indent=2, ensure_ascii=False))
    print(f"{len(results)} tables and 6 charts written to {OUT}")


if __name__ == "__main__":
    main()
