@echo off
setlocal
cd /d "%~dp0"

echo Building a Windows executable launcher for the ERJOR dashboard...
echo This must be run on Windows with Python installed.
echo.

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set PYTHON=py -3
) else (
  set PYTHON=python
)

if not exist ".venv\Scripts\python.exe" (
  %PYTHON% -m venv .venv
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
".venv\Scripts\pyinstaller.exe" --onefile --name ERJOR_Citation_Dashboard launcher.py

echo.
echo If successful, your file is here:
echo dist\ERJOR_Citation_Dashboard.exe
pause
