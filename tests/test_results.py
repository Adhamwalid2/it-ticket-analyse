"""
Checks on the real dataset and on the generated files.
Requires the pipeline to have run first (python run_all.py).
"""
import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook
from pptx import Presentation

from analyse import load_queries

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "tickets.db"
OUT = ROOT / "output"

pytestmark = pytest.mark.skipif(not DB.exists(), reason="run `python run_all.py` first")


@pytest.fixture(scope="module")
def con():
    c = sqlite3.connect(DB)
    yield c
    c.close()


@pytest.fixture(scope="module")
def kennzahlen():
    return json.loads((OUT / "kennzahlen.json").read_text(encoding="utf-8"))


def q(con, name):
    return pd.read_sql(load_queries()[name], con)


# --- data integrity -------------------------------------------------------------------------

def test_row_counts(con):
    assert con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 141_712
    distinct = con.execute("SELECT COUNT(DISTINCT number) FROM events").fetchone()[0]
    assert con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == distinct == 24_918


def test_no_negative_resolution_times(con):
    assert con.execute("SELECT COUNT(*) FROM incidents WHERE resolution_hours < 0").fetchone()[0] == 0


def test_made_sla_is_boolean(con):
    values = {r[0] for r in con.execute("SELECT DISTINCT made_sla FROM incidents")}
    assert values <= {0, 1}


# --- KPI consistency ------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["sla_nach_weiterleitungen", "sla_nach_prioritaet", "wiedereroeffnung"])
def test_groups_add_up_to_all_tickets(con, name):
    assert q(con, name)["tickets"].sum() == 24_918


@pytest.mark.parametrize("name", ["ueberblick", "sla_nach_weiterleitungen", "sla_nach_prioritaet",
                                  "top_teams", "tickets_pro_monat", "wiedereroeffnung"])
def test_percentages_between_0_and_100(con, name):
    pct = q(con, name)["sla_quote_pct"]
    assert pct.between(0, 100).all()


def test_time_shares_sum_to_100():
    df = pd.read_csv(OUT / "tabellen" / "zeit_je_status.csv", sep=";", decimal=",", encoding="utf-8-sig")
    assert df["anteil_pct"].sum() == pytest.approx(100, abs=0.5)


def test_top_teams_sorted_and_limited(con):
    df = q(con, "top_teams")
    assert len(df) == 10
    assert df["tickets"].is_monotonic_decreasing


def test_key_finding_holds(kennzahlen):
    """The central statement of the project: SLA gets worse with more reassignments."""
    assert kennzahlen["sla_0_weiterleitungen_pct"] > kennzahlen["sla_quote_pct"] > kennzahlen["sla_3plus_weiterleitungen_pct"]
    assert kennzahlen["median_h_3plus_weiterleitungen"] > kennzahlen["median_h_0_weiterleitungen"]


def test_sla_decreases_monotonically_with_reassignments(con):
    df = q(con, "sla_nach_weiterleitungen")
    assert df["sla_quote_pct"].is_monotonic_decreasing


def test_numbers_in_docs_match_results(kennzahlen):
    """The numbers written in README and docs must match the computed ones."""
    def de(x):
        return f"{x:.1f}".replace(".", ",")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    prozess = (ROOT / "docs" / "prozess.md").read_text(encoding="utf-8")
    for key in ["sla_quote_pct", "anteil_weitergeleitet_pct", "sla_0_weiterleitungen_pct",
                "sla_3plus_weiterleitungen_pct", "median_h_0_weiterleitungen", "median_h_3plus_weiterleitungen",
                "anteil_warten_auf_nutzer_pct"]:
        assert de(kennzahlen[key]) in readme, f"README: {key}"
    for key in ["anteil_weitergeleitet_pct", "sla_0_weiterleitungen_pct", "sla_3plus_weiterleitungen_pct",
                "anteil_warten_auf_nutzer_pct"]:
        assert de(kennzahlen[key]) in prozess, f"prozess.md: {key}"


# --- generated files ------------------------------------------------------------------------

def test_charts_exist():
    charts = sorted((OUT / "diagramme").glob("*.png"))
    assert len(charts) == 6
    for chart in charts:
        assert chart.stat().st_size > 10_000, chart.name


def test_excel_dashboard(kennzahlen):
    wb = load_workbook(OUT / "Ticket_Dashboard.xlsx")
    assert wb.sheetnames == ["Dashboard", "Weiterleitungen", "Priorität", "Zeit je Status", "Teams", "Monate",
                             "Wiedereröffnung", "Datenquelle"]
    dash = wb["Dashboard"]
    assert dash["A4"].value == f"{kennzahlen['tickets']:,}".replace(",", ".")
    assert dash["D4"].value == f"{kennzahlen['sla_quote_pct']:.1f} %".replace(".", ",")
    assert len(dash._charts) == 4
    # tables contain the same numbers as the SQL results
    ws = wb["Weiterleitungen"]
    assert [ws.cell(r, 1).value for r in range(4, 8)] == ["0", "1", "2", "3+"]


def test_presentation(kennzahlen):
    prs = Presentation(OUT / "Ticket_Analyse.pptx")
    assert len(prs.slides) == 8
    all_text = " ".join(shape.text_frame.text for slide in prs.slides for shape in slide.shapes
                        if shape.has_text_frame)
    assert "IT-Ticket-Analyse" in all_text
    assert f"{kennzahlen['sla_3plus_weiterleitungen_pct']:.1f}".replace(".", ",") in all_text
    pictures = sum(1 for slide in prs.slides for shape in slide.shapes if shape.shape_type == 13)
    assert pictures == 3
