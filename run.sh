#!/usr/bin/env bash
# ==============================================================================
# The Extractor - macOS & Linux Launcher
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "======================================================================"
echo "  Starting The Extractor Server (Cross-Platform Edition)"
echo "  Dashboard URL: http://localhost:8000"
echo "======================================================================"

# Create or activate virtualenv
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "[*] Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# Try to open default browser
(sleep 2 && (xdg-open http://localhost:8000 2>/dev/null || open http://localhost:8000 2>/dev/null || true)) &

python3 server.py
