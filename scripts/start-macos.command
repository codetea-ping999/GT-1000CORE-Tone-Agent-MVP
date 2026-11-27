#!/bin/zsh
set -e
cd "$(dirname "$0")/.."
if [[ ! -f ".venv/bin/python" ]]; then
  echo "[Tone Agent] Creating Python virtual environment..."
  python3 -m venv .venv
fi
echo "[Tone Agent] Installing dependencies..."
.venv/bin/python -m pip install -r requirements.txt
echo "Open http://127.0.0.1:8765 in your browser. Press Ctrl+C to stop."
.venv/bin/python -m gtcore_agent.server
