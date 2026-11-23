"""
Step 1: Load the ServiceNow incident event log into a SQLite database.

Source: "Incident management process enriched event log", UCI Machine Learning Repository
(Amaral, Fantinato, Peres; CC BY 4.0), https://doi.org/10.24432/C57S4H

Creates data/tickets.db with two tables:
  events     - one row per status change of a ticket (141,712 rows)
  incidents  - one row per ticket with its final state (built with SQL)
"""
import sqlite3
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_ZIP = ROOT / "data" / "raw" / "incident_event_log.zip"
DB = ROOT / "data" / "tickets.db"

DATE_COLUMNS = ["opened_at", "sys_created_at", "sys_updated_at", "resolved_at", "closed_at"]


def read_events() -> pd.DataFrame:
    with zipfile.ZipFile(RAW_ZIP) as z:
        with z.open("incident_event_log.csv") as f:
            df = pd.read_csv(f, na_values="?", low_memory=False)
    for col in DATE_COLUMNS:
        parsed = pd.to_datetime(df[col], format="%d/%m/%Y %H:%M", errors="coerce")
        df[col] = parsed.dt.strftime("%Y-%m-%d %H:%M:%S")  # ISO text, works with SQLite date functions
    for col in ["active", "made_sla", "knowledge", "u_priority_confirmation"]:
        df[col] = df[col].astype(str).str.lower().map({"true": 1, "false": 0})
    return df


BUILD_INCIDENTS = """
DROP TABLE IF EXISTS incidents;
CREATE TABLE incidents AS
SELECT number, incident_state AS final_state, reassignment_count, reopen_count, sys_mod_count,
       made_sla, contact_type, category, priority, impact, urgency, assignment_group,
       knowledge, opened_at, resolved_at, closed_at,
       ROUND((julianday(resolved_at) - julianday(opened_at)) * 24, 2) AS resolution_hours
FROM (
    SELECT e.*,
           ROW_NUMBER() OVER (PARTITION BY number
                              ORDER BY sys_mod_count DESC, sys_updated_at DESC) AS rn
    FROM events e
)
WHERE rn = 1;
CREATE INDEX idx_events_number ON events(number, sys_updated_at);
CREATE UNIQUE INDEX idx_incidents_number ON incidents(number);
"""


def main() -> None:
    events = read_events()
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as con:
        events.to_sql("events", con, if_exists="replace", index=False)
        con.executescript(BUILD_INCIDENTS)
        n_events = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        n_incidents = con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    print(f"Loaded {n_events:,} events and {n_incidents:,} incidents into {DB.name}")


if __name__ == "__main__":
    main()
