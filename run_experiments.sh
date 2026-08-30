#!/usr/bin/env bash
# run_experiments.sh — Run the full 480-experiment suite with proper env setup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Environment setup ---
# Ask the same resolver the simulation uses instead of assuming an install path:
# exporting a SUMO_HOME that does not exist would override detection entirely.
if [ -z "${SUMO_HOME:-}" ]; then
    PROBE_PYTHON="./venv/bin/python"
    [ -x "$PROBE_PYTHON" ] || PROBE_PYTHON="python3"
    SUMO_HOME="$("$PROBE_PYTHON" -c 'from engine.sumo_integration import _default_sumo_home; print(_default_sumo_home())' 2>/dev/null || true)"
fi
if [ -n "${SUMO_HOME:-}" ] && [ -d "$SUMO_HOME" ]; then
    export SUMO_HOME
    export PATH="$SUMO_HOME/bin:$PATH"
else
    unset SUMO_HOME
fi
export PYTHONUNBUFFERED=1

echo "============================================"
echo "  Running 480-Experiment Suite"
echo "  SUMO_HOME: ${SUMO_HOME:-not found (Mesa-only)}"
echo "  Start: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

# --- Clean previous run outputs (keep v1_mesamostly as backup) ---
mkdir -p output/csv output/figures output/tables output/sumo
[ -f output/csv/experiment_results.csv ] && mv output/csv/experiment_results.csv output/csv/experiment_results_v1_mesamostly.csv
[ -f output/csv/summary_statistics.csv ] && mv output/csv/summary_statistics.csv output/csv/summary_statistics_v1_mesamostly.csv
[ -f output/csv/por_timeseries.csv ] && mv output/csv/por_timeseries.csv output/csv/por_timeseries_v1_mesamostly.csv

# --- Kill any stale SUMO processes ---
pkill -f "sumo.*remote-port" 2>/dev/null || true
sleep 2

# --- Run experiments ---
python3 experiments.py --all-scenarios --replications 30 2>&1 | tee output/experiment_run.log

EXIT_CODE=$?

echo ""
echo "============================================"
echo "  Experiment suite finished"
echo "  Exit code: $EXIT_CODE"
echo "  End: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

# --- Verify output ---
echo ""
echo "Output files:"
ls -la output/csv/experiment_results.csv 2>/dev/null || echo "  MISSING: experiment_results.csv"
ls -la output/csv/summary_statistics.csv 2>/dev/null || echo "  MISSING: summary_statistics.csv"
ls -la output/csv/por_timeseries.csv 2>/dev/null || echo "  MISSING: por_timeseries.csv"

# --- Count rows ---
if [ -f output/csv/experiment_results.csv ]; then
    ROWS=$(wc -l < output/csv/experiment_results.csv)
    echo "  experiment_results.csv: $ROWS lines (including header)"
    TRUE_COUNT=$(grep -c ",True" output/csv/experiment_results.csv 2>/dev/null || echo 0)
    echo "  sumo_connected=True: $TRUE_COUNT rows"
fi

exit $EXIT_CODE
