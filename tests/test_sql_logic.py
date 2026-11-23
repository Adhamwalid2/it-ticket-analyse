"""
Logic tests with small hand-made data, where the correct answer is known exactly.
They check the SQL in load_data.py and sql/kpis.sql independently of the real dataset.
"""
import sqlite3

import pandas as pd
import pytest

from analyse import load_queries
from load_data import BUILD_INCIDENTS

COLUMNS = ["number", "incident_state", "active", "reassignment_count", "reopen_count", "sys_mod_count",
           "made_sla", "contact_type", "category", "priority", "impact", "urgency", "assignment_group",
           "knowledge", "opened_at", "sys_updated_at", "resolved_at", "closed_at"]


def event(number, state, mod, updated, reassign=0, reopen=0, sla=1, prio="3 - Moderate", group="Group A",
          opened="2016-03-01 08:00:00", resolved="2016-03-01 12:00:00"):
    return [number, state, 1, reassign, reopen, mod, sla, "Phone", "Cat 1", prio, "2 - Medium", "2 - Medium",
            group, 0, opened, updated, resolved, "2016-03-02 08:00:00"]


@pytest.fixture
def con():
    """Two tickets:
    INC1: New 08:00 -> Active 10:00 -> Awaiting User Info 11:00 -> Resolved 15:00 -> Closed
          => New 2 h, Active 1 h, Awaiting User Info 4 h; final: 0 reassignments, SLA met
    INC2: New 09:00 -> Active 09:30 -> Resolved 12:30; final record has 2 reassignments, SLA missed
          => New 0.5 h, Active 3 h
    """
    rows = [
        event("INC1", "New", 0, "2016-03-01 08:00:00"),
        event("INC1", "Active", 1, "2016-03-01 10:00:00"),
        event("INC1", "Awaiting User Info", 2, "2016-03-01 11:00:00"),
        event("INC1", "Resolved", 3, "2016-03-01 15:00:00"),
        event("INC1", "Closed", 4, "2016-03-02 08:00:00"),
        event("INC2", "New", 0, "2016-03-01 09:00:00", opened="2016-03-01 09:00:00",
              resolved="2016-03-01 12:30:00"),
        event("INC2", "Active", 1, "2016-03-01 09:30:00", reassign=1, opened="2016-03-01 09:00:00",
              resolved="2016-03-01 12:30:00"),
        event("INC2", "Resolved", 2, "2016-03-01 12:30:00", reassign=2, sla=0, opened="2016-03-01 09:00:00",
              resolved="2016-03-01 12:30:00", group="Group B"),
    ]
    c = sqlite3.connect(":memory:")
    pd.DataFrame(rows, columns=COLUMNS).to_sql("events", c, index=False)
    c.executescript(BUILD_INCIDENTS)
    yield c
    c.close()


def run(con, name):
    return pd.read_sql(load_queries()[name], con)


def test_one_row_per_ticket_with_final_state(con):
    inc = pd.read_sql("SELECT * FROM incidents ORDER BY number", con)
    assert list(inc["number"]) == ["INC1", "INC2"]
    assert list(inc["final_state"]) == ["Closed", "Resolved"]
    # the final record wins: INC2 ends with 2 reassignments and a missed SLA
    assert inc.loc[1, "reassignment_count"] == 2
    assert inc.loc[1, "made_sla"] == 0
    assert inc.loc[1, "assignment_group"] == "Group B"


def test_resolution_hours(con):
    hours = pd.read_sql("SELECT number, resolution_hours FROM incidents ORDER BY number", con)
    assert list(hours["resolution_hours"]) == [4.0, 3.5]


def test_overview(con):
    ov = run(con, "ueberblick").iloc[0]
    assert ov["tickets"] == 2
    assert ov["sla_quote_pct"] == 50.0
    assert ov["anteil_weitergeleitet_pct"] == 50.0
    assert ov["mittlere_loesungszeit_h"] == 3.8  # (4.0 + 3.5) / 2 = 3.75, rounded


def test_sla_by_reassignment_buckets(con):
    df = run(con, "sla_nach_weiterleitungen").set_index("weiterleitungen")
    assert df.loc["0", "sla_quote_pct"] == 100.0
    assert df.loc["2", "sla_quote_pct"] == 0.0
    assert df["tickets"].sum() == 2


def test_reassignment_bucket_3_plus():
    c = sqlite3.connect(":memory:")
    rows = [event(f"INC{i}", "Closed", 1, "2016-03-01 10:00:00", reassign=n) for i, n in enumerate([3, 5, 9])]
    pd.DataFrame(rows, columns=COLUMNS).to_sql("events", c, index=False)
    c.executescript(BUILD_INCIDENTS)
    df = pd.read_sql(load_queries()["sla_nach_weiterleitungen"], c)
    assert list(df["weiterleitungen"]) == ["3+"]
    assert df.loc[0, "tickets"] == 3


def test_time_per_state_uses_next_status_change(con):
    df = run(con, "zeit_je_status").set_index("status")
    # Resolved/Closed are excluded: only time until resolution counts
    assert set(df.index) == {"New", "Active", "Awaiting User Info"}
    assert df.loc["New", "stunden_gesamt"] == pytest.approx(2.5)                  # INC1: 2 h + INC2: 0.5 h
    assert df.loc["Active", "stunden_gesamt"] == pytest.approx(4.0)               # INC1: 1 h + INC2: 3 h
    assert df.loc["Awaiting User Info", "stunden_gesamt"] == pytest.approx(4.0)   # INC1: 11:00 -> 15:00
    assert df.loc["Active", "tickets_mit_status"] == 2


def test_all_queries_run(con):
    for name in load_queries():
        assert not run(con, name).empty or name == "wiedereroeffnung", name
