#!/usr/bin/env bash
# Build the pygbag web bundle without serving.
#
# pygbag hard-codes where it writes: <folder of the entry script>/build/web,
# with its cache beside it in build/web-cache, and offers no flag to move it.
# The entry is ../../main.py, so the build itself runs in <repo>/build/web; the
# finished bundle is then copied to out/ beside this script, which is the
# deliverable. Both locations are gitignored. serve.sh serves build/web
# directly through pygbag's own dev server.
#
# Run from anywhere: it cd's here so pygbag picks up ./pygbag.ini, which it
# reads from the current working directory.
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-../../.venv/Scripts/python.exe}"
[ -x "$PY" ] || PY="${PYTHON:-python}"
"$PY" -m pygbag --build --ume_block 0 --title "Deathlite Game" ../../main.py
rm -rf out
cp -r ../../build/web out
echo "bundle : $(pwd)/out"
