@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
".venv\Scripts\python.exe" -m uvicorn backend.app:app --port 8000
