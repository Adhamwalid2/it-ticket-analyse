"""Run the whole pipeline: load data -> analysis -> Excel dashboard -> presentation."""
import runpy
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"

for step in ["load_data.py", "analyse.py", "excel_dashboard.py", "praesentation.py"]:
    print(f"\n=== {step} ===")
    runpy.run_path(str(SRC / step), run_name="__main__")
