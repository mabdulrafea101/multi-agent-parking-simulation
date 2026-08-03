#!/usr/bin/env bash
# run_dashboard.sh — Launch the Multi-Agent Parking Simulation Web Dashboard
# Usage: ./run_dashboard.sh [--port 5000] [--debug]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Environment setup ---
export FLASK_APP="app:create_app"
export FLASK_ENV="development"
export PYTHONUNBUFFERED=1

# SUMO configuration (optional — simulation falls back to Mesa-only if absent)
if [ -z "${SUMO_HOME:-}" ]; then
    # Common macOS Homebrew path
    if [ -d "/opt/homebrew/opt/sumo/share/sumo" ]; then
        export SUMO_HOME="/opt/homebrew/opt/sumo/share/sumo"
    elif [ -d "/usr/local/opt/sumo/share/sumo" ]; then
        export SUMO_HOME="/usr/local/opt/sumo/share/sumo"
    fi
    if [ -n "${SUMO_HOME:-}" ]; then
        export PATH="$SUMO_HOME/bin:$PATH"
        echo "[run_dashboard] SUMO_HOME=$SUMO_HOME"
    else
        echo "[run_dashboard] SUMO not found — running in Mesa-only mode"
    fi
fi

# Display for SUMO GUI (macOS: XQuartz; Linux: DISPLAY)
if [ -z "${DISPLAY:-}" ] && [ "$(uname)" != "Darwin" ]; then
    export DISPLAY="${DISPLAY:-:0}"
fi

# --- Ensure outputs exist ---
mkdir -p output/csv output/figures output/tables

# --- Parse args ---
PORT=5000
DEBUG="--debug"
while [[ $# -gt 0 ]]; do
    case $1 in
        --port) PORT="$2"; shift 2 ;;
        --debug) DEBUG="--debug"; shift ;;
        --no-debug) DEBUG=""; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

echo "============================================"
echo "  Multi-Agent Parking Simulation Dashboard"
echo "============================================"
echo "  URL:    http://localhost:${PORT}"
echo "  Debug:  ${DEBUG:-off}"
echo "  SUMO:   ${SUMO_HOME:-not found (Mesa-only)}"
echo "============================================"

# --- Launch ---
exec flask run --host=127.0.0.1 --port="$PORT" $DEBUG
