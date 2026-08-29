#!/usr/bin/env bash
# Build the pygbag web bundle without serving. Output lands in ../build/web/
# (pygbag derives that path from the entry script's location; it is gitignored).
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-../.venv/Scripts/python.exe}"
[ -x "$PY" ] || PY="${PYTHON:-python}"
exec "$PY" -m pygbag --build --ume_block 0 --title "Death Lite Die" ../main.py
