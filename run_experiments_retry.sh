#!/usr/bin/env bash
# run_experiments_retry.sh — Run the full 480-experiment suite
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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

echo "=== 480-Experiment Suite ==="
echo "Start: $(date)"
echo "SUMO_HOME: ${SUMO_HOME:-not found (Mesa-only)}"

mkdir -p output/csv output/figures output/tables output/sumo

# Backup old results
for f in experiment_results.csv summary_statistics.csv por_timeseries.csv; do
    [ -f "output/csv/$f" ] && mv "output/csv/$f" "output/csv/${f}.bak.$(date +%s)"
done

# Kill stale SUMO
pkill -f "sumo.*remote-port" 2>/dev/null || true
sleep 2

# Run
python3 experiments.py --all-scenarios --replications 30 2>&1 | tee output/experiment_run.log

echo ""
echo "=== Finished: $(date) ==="
echo "Results:"
ls -la output/csv/experiment_results.csv 2>/dev/null || echo "MISSING"
wc -l output/csv/experiment_results.csv 2>/dev/null || echo "No results file"
