#!/usr/bin/env bash
# run_experiments_retry.sh — Run the full 480-experiment suite
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export SUMO_HOME="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo"
export PATH="$SUMO_HOME/bin:$PATH"
export PYTHONUNBUFFERED=1

echo "=== 480-Experiment Suite ==="
echo "Start: $(date)"
echo "SUMO_HOME: $SUMO_HOME"

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
