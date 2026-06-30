# ERJOR OpenAlex Citation Trends Dashboard

Free local dashboard for ERJ Open Research citation trends using OpenAlex and SQLite.

## Easiest Windows launch

1. Extract the ZIP file.
2. Open the extracted folder.
3. Double-click `START_DASHBOARD.bat`.

On first run it will:

- create a local Python environment in `.venv`,
- install the free packages,
- download ERJOR citation data from OpenAlex,
- open the dashboard in your browser.

Leave the black command window open while using the dashboard.

## Requirements

You need Python 3 installed on Windows. Install from python.org and tick **Add Python to PATH**.

## Manual commands

```cmd
pip install -r requirements.txt
python fetch_openalex.py
streamlit run app.py
```

## Optional: build a Windows EXE launcher

A true `.exe` has to be built on Windows. Once Python is installed, double-click:

```cmd
BUILD_WINDOWS_EXE.bat
```

If successful, the executable will appear at:

```cmd
dist\ERJOR_Citation_Dashboard.exe
```

Note: this `.exe` is a launcher for the dashboard. It still uses the bundled project files and local Python packages created by the build process.

## What the dashboard shows

- total tracked ERJOR papers,
- total citation count,
- 7/30/90-day citation gains,
- total citations over time,
- new citations by snapshot,
- fastest-rising papers,
- citation age curve,
- publication-year cohort performance,
- article search by title, DOI, author, or institution.

## Important note about trends

OpenAlex provides the current citation count. Trends appear after you run the dashboard on multiple days because the app stores one local snapshot per day in `erjor_citations.sqlite`.
