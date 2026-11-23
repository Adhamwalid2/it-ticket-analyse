"""
Step 3: Build the Excel dashboard (output/Ticket_Dashboard.xlsx) from the analysis results.
Uses native Excel charts and conditional formatting, so everything stays editable in Excel.
"""
import json
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
TABLES = OUT / "tabellen"

RED = "C8102E"
DARK = "1A1D24"
LIGHT = "F3F4F6"
HEADER_FILL = PatternFill("solid", fgColor=DARK)
TILE_FILL = PatternFill("solid", fgColor=LIGHT)
THIN = Side(style="thin", color="E3E6EB")

SHEETS = [
    ("Weiterleitungen", "sla_nach_weiterleitungen", "SLA und Lösungszeit nach Anzahl Weiterleitungen"),
    ("Priorität", "sla_nach_prioritaet", "SLA und Lösungszeit nach Priorität"),
    ("Zeit je Status", "zeit_je_status", "Zeit bis zur Lösung, aufgeteilt nach Ticket-Status"),
    ("Teams", "top_teams", "Die 10 Teams mit den meisten Tickets"),
    ("Monate", "tickets_pro_monat", "Neue Tickets und SLA-Quote pro Monat"),
    ("Wiedereröffnung", "wiedereroeffnung", "Wiedereröffnete Tickets"),
]

HEADERS = {
    "weiterleitungen": "Weiterleitungen", "tickets": "Tickets", "sla_quote_pct": "SLA-Quote (%)",
    "mittlere_loesungszeit_h": "Ø Lösungszeit (h)", "median_loesungszeit_h": "Median Lösungszeit (h)",
    "prioritaet": "Priorität", "weiterleitungen_schnitt": "Ø Weiterleitungen", "status": "Status",
    "stunden_gesamt": "Stunden gesamt", "tickets_mit_status": "Tickets mit Status", "anteil_pct": "Anteil (%)",
    "team": "Team", "monat": "Monat",
}


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / f"{name}.csv", sep=";", decimal=",", encoding="utf-8-sig", dtype={"weiterleitungen": str})


def write_table(ws, df: pd.DataFrame, title: str, start_row: int = 1) -> int:
    ws.cell(start_row, 1, title).font = Font(size=14, bold=True, color=DARK)
    header_row = start_row + 2
    for c, col in enumerate(df.columns, start=1):
        cell = ws.cell(header_row, c, HEADERS.get(col, col))
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for r, row in enumerate(df.itertuples(index=False), start=header_row + 1):
        for c, value in enumerate(row, start=1):
            cell = ws.cell(r, c, value.item() if hasattr(value, "item") else value)
            cell.border = Border(bottom=THIN)
            if isinstance(value, float):
                cell.number_format = "#,##0.0"
            elif isinstance(value, int) or hasattr(value, "item"):
                cell.number_format = "#,##0"
    last_row = header_row + len(df)
    for c, col in enumerate(df.columns, start=1):
        width = max(len(HEADERS.get(col, col)), *(len(str(v)) for v in df[col])) + 3
        ws.column_dimensions[get_column_letter(c)].width = min(max(width, 12), 30)
        if col == "sla_quote_pct":  # red (bad) -> green (good)
            ws.conditional_formatting.add(
                f"{get_column_letter(c)}{header_row + 1}:{get_column_letter(c)}{last_row}",
                ColorScaleRule(start_type="num", start_value=0, start_color="F8696B",
                               mid_type="num", mid_value=50, mid_color="FFEB84",
                               end_type="num", end_value=100, end_color="63BE7B"))
    ws.freeze_panes = ws.cell(header_row + 1, 1)
    ws.row_dimensions[header_row].height = 32
    return header_row


def bar_chart(ws, header_row: int, n_rows: int, cat_col: int, val_col: int, title: str, y_title: str,
              horizontal: bool = False) -> BarChart:
    chart = BarChart()
    chart.type = "bar" if horizontal else "col"
    chart.title = title
    chart.y_axis.title = y_title
    chart.legend = None
    data = Reference(ws, min_col=val_col, min_row=header_row, max_row=header_row + n_rows)
    cats = Reference(ws, min_col=cat_col, min_row=header_row + 1, max_row=header_row + n_rows)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.series[0].graphicalProperties.solidFill = RED
    chart.series[0].graphicalProperties.line.solidFill = RED
    chart.dataLabels = DataLabelList()
    chart.dataLabels.showVal = True
    chart.y_axis.delete = False
    chart.x_axis.delete = False
    chart.height, chart.width = 8, 16
    return chart


def kpi_tile(ws, row: int, col: int, value: str, label: str) -> None:
    for r in range(row, row + 3):
        for c in range(col, col + 2):
            ws.cell(r, c).fill = TILE_FILL
    ws.merge_cells(start_row=row, start_column=col, end_row=row + 1, end_column=col + 1)
    ws.merge_cells(start_row=row + 2, start_column=col, end_row=row + 2, end_column=col + 1)
    v = ws.cell(row, col, value)
    v.font = Font(size=22, bold=True, color=RED)
    v.alignment = Alignment(horizontal="center", vertical="center")
    l = ws.cell(row + 2, col, label)
    l.font = Font(size=10, color=DARK)
    l.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def de(x: float, digits: int = 1) -> str:
    return f"{x:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    k = json.loads((OUT / "kennzahlen.json").read_text(encoding="utf-8"))
    wb = Workbook()

    # --- Data sheets with tables ---
    header_rows = {}
    for sheet_name, table, title in SHEETS:
        ws = wb.create_sheet(sheet_name)
        df = read(table)
        header_rows[table] = (ws, write_table(ws, df, title), len(df))

    # --- Dashboard sheet ---
    ws = wb.active
    ws.title = "Dashboard"
    ws.sheet_view.showGridLines = False
    for c in range(1, 15):
        ws.column_dimensions[get_column_letter(c)].width = 11
    ws["A1"] = "IT-Ticket-Analyse – Dashboard"
    ws["A1"].font = Font(size=20, bold=True, color=DARK)
    ws["A2"] = (f"{de(k['tickets'], 0)} Incident-Tickets (ServiceNow), {k['zeitraum_von']} bis {k['zeitraum_bis']}"
                " · Quelle: UCI Machine Learning Repository (CC BY 4.0)")
    ws["A2"].font = Font(size=10, color="646B78")

    tiles = [
        (de(k["tickets"], 0), "Tickets gesamt"),
        (de(k["sla_quote_pct"]) + " %", "SLA eingehalten"),
        (de(k["anteil_weitergeleitet_pct"]) + " %", "Tickets weitergeleitet"),
        (de(k["median_loesungszeit_h"]) + " h", "Median Lösungszeit"),
        (de(k["anteil_warten_auf_nutzer_pct"]) + " %", "Zeit in „Warten auf Nutzer“"),
    ]
    for i, (value, label) in enumerate(tiles):
        kpi_tile(ws, 4, 1 + i * 3 - (0 if i == 0 else 0), value, label)

    ws["A8"] = "Kernaussage"
    ws["A8"].font = Font(size=12, bold=True, color=DARK)
    ws["A9"] = (f"Tickets ohne Weiterleitung erreichen zu {de(k['sla_0_weiterleitungen_pct'])} % das SLA, "
                f"Tickets mit 3+ Weiterleitungen nur zu {de(k['sla_3plus_weiterleitungen_pct'])} %. "
                f"Die Lösungszeit (Median) steigt von {de(k['median_h_0_weiterleitungen'])} h auf "
                f"{de(k['median_h_3plus_weiterleitungen'])} h.")
    ws.merge_cells("A9:N10")
    ws["A9"].alignment = Alignment(wrap_text=True, vertical="top")

    ws_r, hr, n = header_rows["sla_nach_weiterleitungen"]
    ws.add_chart(bar_chart(ws_r, hr, n, 1, 3, "SLA-Quote nach Weiterleitungen", "SLA (%)"), "A12")
    ws_r, hr, n = header_rows["zeit_je_status"]
    ws.add_chart(bar_chart(ws_r, hr, n, 1, 4, "Anteil der Zeit je Status", "Anteil (%)", horizontal=True), "H12")
    ws_r, hr, n = header_rows["top_teams"]
    ws.add_chart(bar_chart(ws_r, hr, n, 1, 3, "SLA-Quote der Top-10-Teams", "SLA (%)", horizontal=True), "A29")

    ws_r, hr, n = header_rows["tickets_pro_monat"]
    line = LineChart()
    line.title = "Neue Tickets pro Monat"
    line.legend = None
    line.add_data(Reference(ws_r, min_col=2, min_row=hr, max_row=hr + n), titles_from_data=True)
    line.set_categories(Reference(ws_r, min_col=1, min_row=hr + 1, max_row=hr + n))
    line.series[0].graphicalProperties.line.solidFill = RED
    line.series[0].graphicalProperties.line.width = 28000
    line.y_axis.delete = False
    line.x_axis.delete = False
    line.height, line.width = 8, 16
    ws.add_chart(line, "H29")

    # --- Source sheet ---
    src = wb.create_sheet("Datenquelle")
    rows = [
        ("Datensatz", "Incident management process enriched event log"),
        ("Herkunft", "UCI Machine Learning Repository, https://doi.org/10.24432/C57S4H"),
        ("Autoren", "C. Amaral, M. Fantinato, S. Peres"),
        ("Lizenz", "CC BY 4.0"),
        ("System", "ServiceNow (anonymisiertes Event-Log eines IT-Dienstleisters)"),
        ("Umfang", f"141.712 Statusänderungen zu {de(k['tickets'], 0)} Tickets"),
        ("Methode", "SQLite (SQL, Window Functions), Python/pandas, siehe sql/kpis.sql"),
        ("Hinweis", "Zusammenhänge sind Korrelationen, keine bewiesenen Ursachen."),
    ]
    for r, (a, b) in enumerate(rows, start=1):
        src.cell(r, 1, a).font = Font(bold=True)
        src.cell(r, 2, b)
    src.column_dimensions["A"].width = 14
    src.column_dimensions["B"].width = 80

    path = OUT / "Ticket_Dashboard.xlsx"
    wb.save(path)
    print(f"Excel dashboard written to {path}")


if __name__ == "__main__":
    main()
