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

# SUMO configuration (optional — simulation falls back to Mesa-only if absent).
# Ask the same resolver the simulation uses, so this banner can never disagree
# with what the app actually finds (pip wheel, Homebrew, apt or MSI install).
if [ -z "${SUMO_HOME:-}" ]; then
    PROBE_PYTHON="./venv/bin/python"
    [ -x "$PROBE_PYTHON" ] || PROBE_PYTHON="python3"
    PROBED_HOME="$("$PROBE_PYTHON" -c 'from engine.sumo_integration import _default_sumo_home; print(_default_sumo_home())' 2>/dev/null || true)"
    if [ -n "$PROBED_HOME" ]; then
        export SUMO_HOME="$PROBED_HOME"
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
