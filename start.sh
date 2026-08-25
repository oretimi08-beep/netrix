#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "========================================"
echo " NETRIX - Enterprise Network Planning"
echo "========================================"
if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 not found"
  exit 1
fi
if [ ! -d venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
echo "Installing dependencies..."
pip install -q -r requirements.txt
echo ""
echo "Starting server at http://127.0.0.1:5000"
echo "Press Ctrl+C to stop."
echo ""
python run.py
