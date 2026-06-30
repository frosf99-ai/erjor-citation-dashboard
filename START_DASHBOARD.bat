@echo off
setlocal
cd /d "%~dp0"

echo ERJOR Citation Trends Dashboard
echo =================================
echo.

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set PYTHON=py -3
) else (
  where python >nul 2>nul
  if %ERRORLEVEL% EQU 0 (
    set PYTHON=python
  ) else (
    echo Python was not found.
    echo Please install Python from https://www.python.org/downloads/
    echo IMPORTANT: tick "Add Python to PATH" during installation.
    pause
    exit /b 1
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment...
  %PYTHON% -m venv .venv
  if %ERRORLEVEL% NEQ 0 (
    echo Could not create the Python environment.
    pause
    exit /b 1
  )
)

echo Installing/updating required packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
  echo Package installation failed.
  pause
  exit /b 1
)

if not exist "erjor_citations.sqlite" (
  echo First run: downloading ERJOR citation data from OpenAlex...
  ".venv\Scripts\python.exe" fetch_openalex.py
) else (
  echo Updating ERJOR citation data from OpenAlex...
  ".venv\Scripts\python.exe" fetch_openalex.py
)

if %ERRORLEVEL% NEQ 0 (
  echo Data download failed. Check your internet connection and try again.
  pause
  exit /b 1
)

echo.
echo Opening dashboard. Leave this window open while using it.
echo Press Ctrl+C here when finished.
".venv\Scripts\python.exe" -m streamlit run app.py
pause
