"""Create a realistic demo workbook that can be uploaded through the UI."""
from pathlib import Path

from create_test_workbooks import main


if __name__ == "__main__":
    main()
    path = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "workbooks" / "14_complex_combined.xlsx"
    print(f"Upload this demo file from Home: {path}")

