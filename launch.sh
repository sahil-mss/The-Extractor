#!/usr/bin/env bash
# =======================================================================
#              THE EXTRACTOR - SMART LAUNCHER (macOS & LINUX)
# =======================================================================

set -e

# Change to script directory
cd "$(dirname "$0")"

# Check for Python 3
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3 was not found on your system!"
    echo "Please install Python 3 (e.g. via brew install python3 or apt install python3 python3-venv)"
    exit 1
fi

# Run launcher.py which automatically configures .venv, requirements, and launches app
exec "$PYTHON_BIN" launcher.py "$@"
