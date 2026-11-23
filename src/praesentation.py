"""
Step 4: Build the PowerPoint presentation (output/Ticket_Analyse.pptx) from the analysis results.
"""
import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
CHARTS = OUT / "diagramme"

RED = RGBColor(0xC8, 0x10, 0x2E)
DARK = RGBColor(0x1A, 0x1D, 0x24)
MUTED = RGBColor(0x64, 0x6B, 0x78)
LIGHT = RGBColor(0xF3, 0xF4, 0xF6)
RED_SOFT = RGBColor(0xFD, 0xE8, 0xEB)
GREEN = RGBColor(0x1F, 0x8A, 0x4C)
GREEN_SOFT = RGBColor(0xE7, 0xF5, 0xEC)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Segoe UI"


def de(x: float, digits: int = 1) -> str:
    return f"{x:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def text(slide, left, top, width, height, content, size=16, bold=False, color=DARK, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    lines = content if isinstance(content, list) else [content]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(6)
        run = p.add_run()
        run.text = line
        run.font.size, run.font.bold, run.font.color.rgb, run.font.name = Pt(size), bold, color, FONT
    return box


def header(slide, title: str, subtitle: str = "") -> None:
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), Inches(7.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = RED
    bar.line.fill.background()
    text(slide, Inches(0.6), Inches(0.35), Inches(12), Inches(0.8), title, size=28, bold=True)
    if subtitle:
        text(slide, Inches(0.6), Inches(1.05), Inches(12), Inches(0.5), subtitle, size=14, color=MUTED)


def box(slide, left, top, width, height, fill, line=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.adjustments[0] = 0.12
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(1.5)
    shape.shadow.inherit = False
    return shape


def box_text(shape, content: str, size=12, bold=False, color=DARK) -> None:
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, line in enumerate(content.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = line
        run.font.size, run.font.color.rgb, run.font.name = Pt(size), color, FONT
        run.font.bold = bold if i == 0 else False


def finding_slide(prs, title, subtitle, chart, bullets) -> None:
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, title, subtitle)
    s.shapes.add_picture(str(CHARTS / chart), Inches(0.6), Inches(1.7), width=Inches(7.6))
    text(s, Inches(8.6), Inches(1.9), Inches(4.3), Inches(4.8), ["• " + b for b in bullets], size=15)


def process_row(slide, top, steps, label, label_color) -> None:
    text(slide, Inches(0.6), top - Inches(0.45), Inches(6), Inches(0.4), label, size=14, bold=True,
         color=label_color)
    width, height, gap = Inches(2.15), Inches(1.15), Inches(0.42)
    left = Inches(0.6)
    previous = None
    for content, highlight in steps:
        fill, line, color = LIGHT, None, DARK
        if highlight == "problem":
            fill, line = RED_SOFT, RED
        elif highlight == "better":
            fill, line = GREEN_SOFT, GREEN
        shape = box(slide, left, top, width, height, fill, line)
        box_text(shape, content, size=11, bold=True, color=color)
        if previous is not None:
            conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, previous.left + previous.width,
                                              top + height // 2, left, top + height // 2)
            conn.line.color.rgb = MUTED
            conn.line.width = Pt(1.5)
            conn.line._get_or_add_ln().append(
                conn.line._get_or_add_ln().makeelement(
                    "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle"}))
        previous = shape
        left = Emu(left + width + gap)


def main() -> None:
    k = json.loads((OUT / "kennzahlen.json").read_text(encoding="utf-8"))
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]

    # 1 Title
    s = prs.slides.add_slide(blank)
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = DARK
    bg.line.fill.background()
    accent = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(2.6), Inches(1.2), Inches(0.12))
    accent.fill.solid()
    accent.fill.fore_color.rgb = RED
    accent.line.fill.background()
    text(s, Inches(0.8), Inches(2.9), Inches(11.5), Inches(1.2), "IT-Ticket-Analyse", size=44, bold=True, color=WHITE)
    text(s, Inches(0.8), Inches(3.9), Inches(11.5), Inches(1.2),
         f"Wo der Incident-Prozess Zeit und SLA verliert – Analyse von {de(k['tickets'], 0)} ServiceNow-Tickets",
         size=20, color=RGBColor(0xD0, 0xD4, 0xDB))
    text(s, Inches(0.8), Inches(6.4), Inches(11.5), Inches(0.5),
         "Adham Ibrahim · Datenquelle: UCI Machine Learning Repository (CC BY 4.0)", size=12,
         color=RGBColor(0x9A, 0xA1, 0xAD))

    # 2 Management summary
    s = prs.slides.add_slide(blank)
    header(s, "Management Summary", f"Zeitraum {k['zeitraum_von']} bis {k['zeitraum_bis']}")
    tiles = [
        (de(k["tickets"], 0), "Tickets"),
        (de(k["sla_quote_pct"]) + " %", "SLA eingehalten"),
        (de(k["anteil_weitergeleitet_pct"]) + " %", "weitergeleitet"),
        (de(k["anteil_warten_auf_nutzer_pct"]) + " %", "der Zeit: Warten auf Nutzer"),
    ]
    for i, (value, label) in enumerate(tiles):
        t = box(s, Inches(0.6 + i * 3.1), Inches(1.75), Inches(2.85), Inches(1.6), LIGHT)
        box_text(t, f"{value}\n{label}", size=13, bold=True)
        t.text_frame.paragraphs[0].runs[0].font.size = Pt(30)
        t.text_frame.paragraphs[0].runs[0].font.color.rgb = RED
    text(s, Inches(0.6), Inches(3.75), Inches(12.2), Inches(3.4), [
        f"1.  Weiterleitungen sind der größte Hebel: Ohne Weiterleitung wird das SLA zu "
        f"{de(k['sla_0_weiterleitungen_pct'])} % eingehalten, bei 3+ Weiterleitungen nur zu "
        f"{de(k['sla_3plus_weiterleitungen_pct'])} %.",
        f"2.  {de(k['anteil_warten_auf_nutzer_pct'])} % der Zeit bis zur Lösung warten Tickets auf Informationen "
        "vom Nutzer – vollständige Angaben bei der Erfassung sparen Zeit.",
        "3.  Empfehlung: Routing-Regeln, Pflichtfelder bei der Erfassung und automatische Erinnerungen.",
    ], size=17)

    # 3-5 Findings
    finding_slide(prs, "Befund 1: Jede Weiterleitung kostet SLA",
                  "SLA-Einhaltung nach Anzahl der Weiterleitungen", "01_sla_nach_weiterleitungen.png", [
                      f"{de(k['anteil_weitergeleitet_pct'])} % aller Tickets werden mindestens einmal weitergeleitet.",
                      f"SLA-Quote: {de(k['sla_0_weiterleitungen_pct'])} % ohne vs. "
                      f"{de(k['sla_3plus_weiterleitungen_pct'])} % bei 3+ Weiterleitungen.",
                      f"Median-Lösungszeit: {de(k['median_h_0_weiterleitungen'])} h vs. "
                      f"{de(k['median_h_3plus_weiterleitungen'])} h.",
                      "→ Tickets müssen beim ersten Mal im richtigen Team landen.",
                  ])
    finding_slide(prs, "Befund 2: Viel Zeit vergeht mit Warten",
                  "Anteil an der Zeit bis zur Lösung je Ticket-Status", "04_zeit_je_status.png", [
                      f"{de(k['anteil_warten_auf_nutzer_pct'])} % der Zeit: „Awaiting User Info“ – "
                      "Rückfragen an den Nutzer.",
                      "Über ein Viertel der Zeit liegen Tickets noch unbearbeitet im Status „New“.",
                      "→ Vollständige Angaben bei der Erfassung und schnelle Zuweisung verkürzen die Laufzeit.",
                  ])
    finding_slide(prs, "Befund 3: Große Unterschiede zwischen Teams",
                  "SLA-Einhaltung der 10 Teams mit den meisten Tickets", "06_top_teams.png", [
                      "Das größte Team (Group 70) bearbeitet 38 % aller Tickets mit 84 % SLA-Quote.",
                      "Group 25 und Group 20 liegen bei 42–43 %.",
                      "Teams mit vielen Weiterleitungen haben tendenziell niedrigere SLA-Quoten.",
                      "→ Ursachenanalyse in den Teams unter dem Durchschnitt.",
                  ])

    # 6 Process as-is / to-be
    s = prs.slides.add_slide(blank)
    header(s, "Incident-Prozess: Ist und Soll")
    process_row(s, Inches(2.05), [
        ("Ticket erfasst\n(99 % Telefon)", None),
        ("Status „New“\nwartet auf Zuweisung", "problem"),
        ("Weiterleitung\nzwischen Teams\n45,6 % der Tickets", "problem"),
        ("Rückfrage an Nutzer\n30 % der Zeit", "problem"),
        ("Gelöst /\ngeschlossen", None),
    ], "IST", RED)
    process_row(s, Inches(4.55), [
        ("Erfassung mit\nPflichtangaben", "better"),
        ("Automatisches\nRouting nach\nKategorie", "better"),
        ("Lösung im\nersten Team", "better"),
        ("Rückfrage mit\nErinnerung nach 24 h", "better"),
        ("Gelöst /\ngeschlossen", None),
    ], "SOLL", GREEN)
    text(s, Inches(0.6), Inches(6.2), Inches(12), Inches(0.6),
         "Rot = Schwachstelle laut Daten · Grün = Verbesserung. Vollständige Diagramme: docs/prozess.md",
         size=12, color=MUTED)

    # 7 Measures
    s = prs.slides.add_slide(blank)
    header(s, "Empfohlene Maßnahmen", "Jede Maßnahme mit einer Messgröße, um den Erfolg zu prüfen")
    rows = [
        ("Maßnahme", "Begründung (Daten)", "Messgröße"),
        ("Routing-Regeln Kategorie → Team", "Weiterleitungen gehen mit niedrigerer SLA-Quote einher",
         f"Anteil weitergeleitet (heute {de(k['anteil_weitergeleitet_pct'])} %)"),
        ("Pflichtfelder / Checkliste bei Erfassung", f"{de(k['anteil_warten_auf_nutzer_pct'])} % der Zeit "
         "Warten auf Nutzer", "Zeitanteil „Awaiting User Info“"),
        ("Automatische Erinnerung nach 24 h", "Wartezeiten blockieren die Lösung", "Ø Wartedauer auf Nutzer"),
        ("Dispatch-Ziel für neue Tickets", "Über ein Viertel der Zeit im Status „New“", "Zeitanteil „New“"),
        ("SLA für Priorität 1/2 prüfen", "SLA-Quote unter 2 %", "SLA-Quote Prio 1/2"),
    ]
    table = s.shapes.add_table(len(rows), 3, Inches(0.6), Inches(1.75), Inches(12.1), Inches(4.6)).table
    for c, w in enumerate((4.0, 4.6, 3.5)):
        table.columns[c].width = Inches(w)
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.text = value
            cell.fill.solid()
            cell.fill.fore_color.rgb = DARK if r == 0 else (LIGHT if r % 2 else WHITE)
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(14)
                    run.font.name = FONT
                    run.font.bold = r == 0 or c == 0
                    run.font.color.rgb = WHITE if r == 0 else DARK

    # 8 Method and data
    s = prs.slides.add_slide(blank)
    header(s, "Methodik und Datenquelle")
    text(s, Inches(0.6), Inches(1.7), Inches(12), Inches(5), [
        "• Daten: „Incident management process enriched event log“, UCI Machine Learning Repository "
        "(Amaral, Fantinato, Peres), CC BY 4.0 – anonymisiertes ServiceNow-Event-Log eines IT-Dienstleisters.",
        f"• Umfang: 141.712 Statusänderungen zu {de(k['tickets'], 0)} Tickets.",
        "• Aufbereitung: SQLite-Datenbank; Endstand je Ticket per SQL (ROW_NUMBER), Liegezeiten je Status "
        "per Window Function (LEAD).",
        "• Auswertung: Python (pandas, matplotlib), Excel-Dashboard (openpyxl), diese Präsentation (python-pptx).",
        "• Einschränkung: Die Zusammenhänge sind Korrelationen. Komplexe Tickets werden z. B. häufiger "
        "weitergeleitet und dauern ohnehin länger.",
        "• Reproduzierbar: Alle Schritte laufen mit einem Befehl (run_all.py).",
    ], size=16)

    path = OUT / "Ticket_Analyse.pptx"
    prs.save(path)
    print(f"Presentation with {len(prs.slides)} slides written to {path}")


if __name__ == "__main__":
    main()
