#!/usr/bin/env bash
# macOS / Linux / Raspberry Pi: set up (first time) and start the web app.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -r requirements.txt
else
  . .venv/bin/activate
fi
[ -f .env ] || { cp .env.example .env; echo "Fill in .env, then run ./start.sh again"; exit 0; }
python -m tunimix seeds
python -m tunimix web "$@"
