#!/usr/bin/env bash
# Serve the pygbag web build locally at http://localhost:8000 (rebuilds first).
# Run from anywhere; it cd's into web/ so pygbag picks up web/pygbag.ini, and
# points at ../main.py (which must stay at the repo root -- pygbag packs the
# folder that contains the entry script).
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-../.venv/Scripts/python.exe}"
[ -x "$PY" ] || PY="${PYTHON:-python}"
exec "$PY" -m pygbag --ume_block 0 --title "Death Lite Die" ../main.py
