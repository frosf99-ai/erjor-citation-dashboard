"""Windows-friendly launcher for the ERJOR Citation Trends dashboard.

This updates the OpenAlex snapshot, then starts Streamlit in the default browser.
It is designed to be packaged with PyInstaller on Windows.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str]) -> None:
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> None:
    print("ERJOR Citation Trends Dashboard")
    print("Updating citation data from OpenAlex...")
    run([sys.executable, "fetch_openalex.py"])
    print("Opening dashboard in your browser...")
    run([sys.executable, "-m", "streamlit", "run", "app.py"])


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"A command failed: {exc}")
        input("Press Enter to close...")
        raise
