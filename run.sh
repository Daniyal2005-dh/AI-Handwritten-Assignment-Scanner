#!/usr/bin/env bash
# One-command dev run for Linux/macOS (and Git Bash on Windows).
set -e
cd "$(dirname "$0")"
if [ ! -f ".venv/bin/python" ] && [ ! -f ".venv/Scripts/python.exe" ]; then
  python -m venv .venv
fi
if [ -f ".venv/bin/python" ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python.exe; fi
"$PY" -m pip install --quiet -r requirements.txt
"$PY" -m uvicorn backend.app:app --port 8000
