#!/usr/bin/env bash
# Rebuild and serve the pygbag web build locally at http://localhost:8000.
# Run from anywhere; it cd's here so pygbag picks up ./pygbag.ini (read from
# the current working directory) and points at ../../main.py, which must stay
# at the repo root because pygbag packs the folder that contains the entry
# script. pygbag serves from <repo>/build/web, its fixed output folder.
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-../../.venv/Scripts/python.exe}"
[ -x "$PY" ] || PY="${PYTHON:-python}"
exec "$PY" -m pygbag --ume_block 0 --title "Deathlite Game" ../../main.py
