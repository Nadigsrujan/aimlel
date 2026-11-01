@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Workspace Python is missing. Read docs\RUN_SERVER.md for setup.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "scripts\run_local.py" --open %*
if errorlevel 1 pause
