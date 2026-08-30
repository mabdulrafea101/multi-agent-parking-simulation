# Multi-Agent Parking Simulation

A tier-2 simulation framework for intelligent urban parking allocation, built on
**Mesa** (agent-based modeling) with optional **SUMO** traffic simulation and
**OpenStreetMap** road network data (via **OSMnx**).

The project compares four allocation strategies — `auction`, `fcfs`, `random`,
`greedy` — across four demand scenarios — `low_demand`, `medium_demand`,
`high_demand`, `peak_demand` — and exposes everything through a **Flask**
dashboard with live progress, history, downloads, and a 3D visualization.

---

## Table of contents

- [Features](#features)
- [Project structure](#project-structure)
- [KPIs](#kpis)
- [Requirements](#requirements)
- [Installation — Windows](#installation--windows)
- [Installation — macOS](#installation--macos)
- [Installation — Linux](#installation--linux)
- [Running the simulation](#running-the-simulation)
- [Running the Flask dashboard](#running-the-flask-dashboard)
- [Running the full experiment suite](#running-the-full-experiment-suite)
- [Configuration](#configuration)
- [Output](#output)
- [Running tests](#running-tests)
- [Troubleshooting](#troubleshooting)

---

## Features

- Mesa-based multi-agent model (driver, parking spot, coordinator agents)
- SUMO + TraCI integration for realistic traffic flow
- OSMnx-based road network import from any OpenStreetMap place
- Four allocation strategies with comparative KPIs
- Flask web dashboard with live progress (SSE), history, downloads, and
  Three.js visualization of recorded frames
- SQLite-backed run history with WAL journal mode
- Cross-platform Python code (Windows / macOS / Linux)

---

## Project structure

```
multi-agent-parking-simulation/
├── agents/
│   ├── driver_agent.py        # Driver FSM: searching → reserving → parking
│   ├── parking_spot_agent.py  # Parking spot state and bids
│   └── coordinator_agent.py   # Auction coordinator / strategy router
├── engine/
│   ├── sumo_integration.py    # SUMO + OSM bridge (traci, sumolib, osmnx)
│   └── cities/                # City-specific network configurations
├── app/
│   ├── __init__.py            # Flask app factory
│   └── routes.py              # Dashboard blueprint, SSE progress, API
├── config/
│   ├── default_params.json    # Default simulation parameters
│   └── scenarios.json         # Demand scenarios + strategy definitions
├── templates/                 # Jinja2 templates for the dashboard
├── tests/                     # pytest suite
├── output/
│   ├── csv/                   # Raw + aggregated results
│   ├── figures/               # Generated plots
│   ├── tables/                # Generated tables
│   ├── sumo/                  # Generated networks + <city>/ OSM download cache
│   └── viz/                   # Recorded frames for 3D visualization
├── analysis.py                # Results analysis and visualization
├── chapter4_analysis.py       # Chapter 4 specific analysis
├── recorder.py                # Frame recorder for visualization
├── model.py                   # Main ParkingModel class (Mesa)
├── experiments.py             # Batch experiment runner
├── main.py                    # CLI entry point
├── run_exp_python.py          # Cross-platform experiment driver
├── run_dashboard.sh / .ps1 / .bat    # Dashboard launcher
├── run_experiments.sh / .ps1 / .bat  # Full 480-experiment suite launcher
└── run_experiments_retry.sh / .ps1 / .bat  # Same as above with timestamped backups
```

---

## KPIs

1. **PST** — Parking Search Time
2. **POR** — Parking Occupancy Rate
3. **RSR** — Reservation Success Rate
4. **Average Agent Utility**
5. **TFI** — Traffic Flow Impact

---

## Requirements

- **Python 3.10+** (tested on 3.14.7)
- **SUMO 1.x** (optional — the simulation runs in Mesa-only mode without it,
  but traffic-flow KPIs and OSM-import features require it)
  - Windows: https://sumo.dlr.de/docs/Downloads.php
  - macOS: `brew install sumo` (or download the EclipseSUMO framework)
  - Linux: `sudo apt install sumo`
- **Git** (only needed for cloning the repo)
- ~500 MB free disk for the Python venv + SUMO

---

## Installation — Windows

### 1. Install Python

Download Python 3.10+ from https://www.python.org/downloads/windows/.
During install, tick **"Add python.exe to PATH"**.

Verify in PowerShell:
```powershell
python --version
```

### 2. Clone the repo and create the venv

```powershell
git clone <your-fork-url> multi-agent-parking-simulation
cd multi-agent-parking-simulation
python -m venv venv
```

### 3. Install SUMO (optional but recommended)

You have two options on Windows. The pip wheel (Option A) is recommended
because it requires no admin rights, no MSI, and no `SUMO_HOME` env var.

**Option A — pip wheel (recommended)**:

```powershell
venv\Scripts\python.exe -m pip install eclipse-sumo
```

This installs the full SUMO 1.27 toolchain (binaries, libs, data files)
inside your venv at `venv\Lib\site-packages\sumo\bin\`. The project
auto-detects this path.

**Option B — official MSI installer**:

Download the 64-bit Windows installer from
https://sumo.dlr.de/docs/Downloads.php and install to one of:

- `C:\Program Files (x86)\Eclipse SUMO`
- `C:\Program Files\Eclipse SUMO`
- `C:\SUMO`

If you install elsewhere, set the `SUMO_HOME` env var to the directory
that contains `bin/`, `share/`, and `data/` (e.g. `C:\SUMO`).

If you skip this step entirely, the dashboard and all scripts still
work — they will run in Mesa-only mode and the `sumo_connected` column
in `output/csv/experiment_results.csv` will be `False` for every row.

### 4. Install all Python dependencies from `requirements.txt`

```powershell
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` is generated from `pip freeze` and includes the SUMO
wheel (if you went with Option A) plus all Python packages: `mesa`,
`numpy`, `pandas`, `scipy`, `matplotlib`, `flask`, `osmnx`, `pyproj`,
`seaborn`, `pytest`, `traci`, `sumolib`, and their transitive deps
(`geopandas`, `shapely`, `networkx`, etc.). If you used Option B (MSI),
this step also installs the matching `traci` and `sumolib` Python
modules from PyPI.

### 5. Verify the install (optional but recommended)

```powershell
venv\Scripts\python.exe -c "import traci, sumolib; from engine.sumo_integration import _sumo_bin; import os; print('traci:', traci.__file__); print('sumolib:', sumolib.__file__); print('sumo binary:', _sumo_bin('sumo'))"
```

You should see a non-empty path under `venv\Lib\site-packages\sumo\bin\`
(or your MSI install path) for the `sumo binary` line.

### 6. Run the dashboard

```powershell
# PowerShell
.\run_dashboard.ps1
.\run_dashboard.ps1 -Port 5050 -NoDebug

# CMD (double-click run_dashboard.bat or:)
run_dashboard.bat
run_dashboard.bat --port 5050 --no-debug
```

The `.bat` and `.ps1` scripts are equivalent. PowerShell offers named
parameters (`-Port`, `-NoDebug`); CMD uses long flags (`--port 5050`,
`--no-debug`).

Open http://127.0.0.1:5000 in your browser.

### TL;DR — full command sequence on Windows

```powershell
git clone <your-fork-url> multi-agent-parking-simulation
cd multi-agent-parking-simulation
python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install eclipse-sumo
venv\Scripts\python.exe -m pip install -r requirements.txt
.\run_dashboard.ps1
```

---

## Installation — macOS

### 1. Install Python (if not already)

macOS ships with an old Python. Install a modern one with Homebrew:
```bash
brew install python@3.14
```

Or download from https://www.python.org/downloads/macos/.

### 2. Clone the repo and create the venv

```bash
git clone <your-fork-url> multi-agent-parking-simulation
cd multi-agent-parking-simulation
python3 -m venv venv
```

### 3. Install SUMO (optional but recommended)

You have two options on macOS. The pip wheel (Option A) is recommended
because it requires no Homebrew, no GUI pkg, and no `SUMO_HOME` env var.

**Option A — pip wheel (recommended)**:

```bash
./venv/bin/pip install eclipse-sumo
```

This installs the full SUMO 1.27 toolchain (binaries, libs, data files)
inside your venv. The project auto-detects this path.

**Option B — Homebrew**:

```bash
brew install sumo
```

This installs SUMO under `/opt/homebrew/opt/sumo/share/sumo` (Apple
Silicon) or `/usr/local/opt/sumo/share/sumo` (Intel). Both paths are
auto-detected by the launchers. To use a manual install, set:
```bash
export SUMO_HOME="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo"
```

If you skip this step entirely, the dashboard and all scripts still
work — they will run in Mesa-only mode and the `sumo_connected` column
in `output/csv/experiment_results.csv` will be `False` for every row.

### 4. Install all Python dependencies from `requirements.txt`

```bash
./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements.txt
```

`requirements.txt` is generated from `pip freeze` and includes the SUMO
wheel (if you went with Option A) plus all Python packages: `mesa`,
`numpy`, `pandas`, `scipy`, `matplotlib`, `flask`, `osmnx`, `pyproj`,
`seaborn`, `pytest`, `traci`, `sumolib`, and their transitive deps. If
you used Option B (Homebrew), this step also installs the matching
`traci` and `sumolib` Python modules from PyPI.

### 5. Verify the install (optional but recommended)

```bash
./venv/bin/python -c "import traci, sumolib; from engine.sumo_integration import _sumo_bin; import os; print('traci:', traci.__file__); print('sumolib:', sumolib.__file__); print('sumo binary:', _sumo_bin('sumo'))"
```

You should see a non-empty path under `venv/lib/python*/site-packages/sumo/bin/`
(or your Homebrew install path) for the `sumo binary` line.

### 6. Run the dashboard

```bash
./run_dashboard.sh                # default port 5000, debug on
./run_dashboard.sh --port 5050    # custom port
./run_dashboard.sh --no-debug     # disable debug / reloader
```

Open http://127.0.0.1:5000 (or your chosen port) in a browser.

### TL;DR — full command sequence on macOS

```bash
git clone <your-fork-url> multi-agent-parking-simulation
cd multi-agent-parking-simulation
python3 -m venv venv
./venv/bin/python -m pip install --upgrade pip
./venv/bin/pip install eclipse-sumo
./venv/bin/python -m pip install -r requirements.txt
./run_dashboard.sh
```

---

## Installation — Linux

The repository includes no `.sh` for Linux specifically, but the same scripts
work on any Unix-like system.

```bash
sudo apt install python3-venv python3-dev sumo  # Debian/Ubuntu
git clone <your-fork-url> multi-agent-parking-simulation
cd multi-agent-parking-simulation
python3 -m venv venv
./venv/bin/python -m pip install --upgrade pip
./venv/bin/pip install eclipse-sumo
./venv/bin/python -m pip install -r requirements.txt
./run_dashboard.sh
```

For X11 forwarding if you want SUMO GUI, ensure `$DISPLAY` is set.

---

## Running the simulation

The CLI entry point is `main.py`. It accepts a strategy, a scenario, a
replication count, and several optional flags.

```bash
# Single run with the default scenario
python main.py --strategy auction --replications 1

# Pick a demand scenario
python main.py --scenario high_demand --strategy fcfs --replications 5

# Run the full 4 × 4 × 30 = 480-run suite
python main.py --all-scenarios --replications 30

# Use real OpenStreetMap data (requires SUMO)
python main.py --osm "Kuala Lumpur, Malaysia" --strategy auction

# Launch SUMO GUI instead of headless
python main.py --strategy auction --gui
```

For the batch experiment runner, choose a simulation backend with
`--simulation-type`. When you run via `run_experiments.*` or
`run_exp_python.py`, the launcher auto-detects SUMO and uses it; otherwise
Mesa-only is the default.

```bash
# Mesa-only (default, fastest, no SUMO required)
python experiments.py --all-scenarios --replications 30

# Mesa + SUMO synthetic grid (auto-selected when SUMO is installed)
python experiments.py --all-scenarios --replications 30 --simulation-type sumo

# Mesa + SUMO + real OpenStreetMap city (requires SUMO)
python experiments.py --all-scenarios --replications 30 \
    --simulation-type osm_city --city kuala_lumpur

# ...and force a re-download of that city's OSM data first
python experiments.py --all-scenarios --replications 30 \
    --simulation-type osm_city --city kuala_lumpur --refresh-osm
```

### OSM city data is downloaded once

`--simulation-type osm_city` fetches the city's road network from Overpass and
converts it with `netconvert` **once**, caching both artifacts under
`output/sumo/<city>/` (`<city>.osm.xml` and `<city>.net.xml`). Every later
replication, batch, or dashboard run reuses them from disk — including runs on
a machine with no network access. For a 480-run suite that means one fetch
instead of 480, and one `netconvert` instead of 480.

To pick up edited city bounds or refreshed OpenStreetMap data, pass
`--refresh-osm` (or tick **Re-download OSM data** on the dashboard's run form).
It clears that city's cached files once, before the first replication; the rest
of the batch then reuses the freshly built network. Delete
`output/sumo/<city>/` by hand for the same effect.

Batch order of operations is prepare-then-run: the network is fetched,
converted and parsed before replication 1 starts, and every replication is
handed that same file. If the network cannot be produced the batch aborts with
an error instead of running early replications on the synthetic grid while later
ones use the city, which would silently mix two road networks into one result
set.

On Windows, use the venv Python directly:
```powershell
venv\Scripts\python.exe main.py --strategy auction --replications 1
venv\Scripts\python.exe experiments.py --all-scenarios --replications 30 --simulation-type sumo
```

Results land under `output/csv/`, `output/figures/`, and `output/tables/`.
The `sumo_connected` column in `output/csv/experiment_results.csv` reports
whether SUMO was active for each run (`True` = Mesa+SUMO, `False` = Mesa-only).

Two further columns describe how much of the network SUMO actually used, since
"connected" alone can hide a collapsed mapping: `sumo_vehicles_completed`
(vehicles that finished a route; a shortfall against `total_arrivals` has several
causes, including routes still running when the replication ends, and departures
SUMO rejected outright) and `sumo_spawn_edges` (how many distinct edges received
a vehicle - hundreds on a city network, not a handful, and the direct measure of
mapping quality). `summary_statistics.csv` reports `min_sumo_spawn_edges` per
scenario/strategy group. Neither participates in the KPI aggregates.

When SUMO connects, the run log also states the mapped extent and the share of
edges that accept cars, e.g.
`SUMO: grid 100x100 -> network extent 6138x7763 m (7615 of 30319 edges take cars)`,
followed by `SUMO: spawn mapping used 459 distinct edges across 933 mapped cells`
when the replication ends.

---

## Running the Flask dashboard

The dashboard exposes a UI for launching experiments, watching live progress
via Server-Sent Events, browsing past runs, downloading CSVs, and inspecting
recorded frames in a 3D Three.js viewer.

### Windows
```powershell
# PowerShell
.\run_dashboard.ps1
.\run_dashboard.ps1 -Port 5050 -NoDebug

# CMD (double-click run_dashboard.bat or:)
run_dashboard.bat
run_dashboard.bat --port 5050 --no-debug
```

The `.bat` and `.ps1` scripts are equivalent. PowerShell offers named
parameters (`-Port`, `-NoDebug`); CMD uses long flags (`--port 5050`,
`--no-debug`).

### macOS / Linux
```bash
./run_dashboard.sh                # default port 5000, debug on
./run_dashboard.sh --port 5050    # custom port
./run_dashboard.sh --no-debug     # disable debug / reloader
```

The script:
- sets `FLASK_APP=app:create_app`
- probes for SUMO with the same resolver the simulation uses (`_default_sumo_home()`)
  and exports `SUMO_HOME` from it, so the banner can't disagree with the app
- creates `output/csv`, `output/figures`, `output/tables` if missing
- starts Flask on `127.0.0.1:$PORT`

Open http://127.0.0.1:5000 (or your chosen port) in a browser.

### Dashboard routes (for reference)

| Route | Purpose |
| --- | --- |
| `GET /` | Dashboard index |
| `GET\|POST /run` | Launch experiment form |
| `GET /progress` | SSE stream of live progress |
| `GET /progress.json` | JSON snapshot of progress |
| `GET /results` | Results table + figures |
| `GET /history` | List past runs |
| `GET /history/run/<id>` | View a specific run |
| `POST /history/run/<id>/delete` | Delete a run |
| `GET /history/run/<id>/download/<file>` | Download run CSV |
| `GET /download/<file>` | Download global CSV |
| `GET /figure/<name>` | Serve a PNG figure |
| `POST /reset` | Clear experiment state |
| `GET /visualize` | Three.js visualization page |
| `GET /api/viz/runs` | List recorded runs |
| `GET /api/viz/frames/<run_id>` | Frames JSON for a run |
| `GET /api/viz/meta/<run_id>` | Metadata for a run |
| `POST /api/viz/record` | Record a new run |

---

## Running the full experiment suite

The scripts under `run_experiments.*` and `run_experiments_retry.*` run the
full 4 × 4 × 30 = **480-experiment** matrix in a single child process, with
logging, output verification, and stale-process cleanup.

### Windows
```powershell
# PowerShell
.\run_experiments.ps1
.\run_experiments.ps1 -Replications 5
.\run_experiments_retry.ps1

# CMD
run_experiments.bat
run_experiments.bat 5
run_experiments_retry.bat
```

In CMD, pass the replication count as the first positional argument
(e.g. `run_experiments.bat 5`).

### macOS / Linux
```bash
./run_experiments.sh
./run_experiments.sh                 # no args = 30 reps; pass extra args to experiments.py
./run_experiments_retry.sh
```

What the scripts do:
1. Resolve `SUMO_HOME` via the simulation's own `_default_sumo_home()` probe
   (pip wheel, Homebrew, apt or MSI) and export it only when found
2. Back up any existing `experiment_results.csv`, `summary_statistics.csv`,
   `por_timeseries.csv` (the original script renames to `*_v1_mesamostly.csv`;
   the retry variant uses a Unix timestamp suffix)
3. Kill any stale SUMO processes (`taskkill` on Windows, `pkill` elsewhere)
4. Run `python experiments.py --all-scenarios --replications <N>` with output
   teed to `output/experiment_run.log`
5. Print a summary including row count and the number of
   `sumo_connected=True` rows

Equivalent manual invocation (cross-platform):
```bash
python run_exp_python.py --all-scenarios --replications 30
```

---

## Configuration

Edit `config/default_params.json` to change:
- Grid size, parking spots, zones
- Arrival rate, parking duration
- Simulation ticks, warmup period

Edit `config/scenarios.json` to change:
- Demand scenarios (low/medium/high/peak)
- Allocation strategies (auction/fcfs/random/greedy)
- Number of replications

---

## Output

After a run, check:

- **`output/csv/experiment_results.csv`** — per-replication metrics
- **`output/csv/summary_statistics.csv`** — aggregated statistics
- **`output/csv/por_timeseries.csv`** — POR over time
- **`output/figures/*.png`** — KPI comparison plots, time series, box plots
- **`output/tables/*.csv`** — summary tables
- **`output/sumo/<city>/`** — cached OSM data and built network, reused by every later run
- **`output/viz/<run_id>/`** — frame recordings for the 3D viewer
- **`output/experiments.sqlite`** — run metadata for the dashboard history

Run `analysis.py` to regenerate figures and tables from the CSVs:
```bash
python analysis.py
```

---

## Running tests

```bash
# macOS / Linux
./venv/bin/python -m pytest tests/ -v

# Windows
venv\Scripts\python.exe -m pytest tests/ -v
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'traci'`
`traci` ships with SUMO, not PyPI. Either install SUMO (recommended — see
[Requirements](#requirements)) or accept Mesa-only mode (the simulation still
runs, but SUMO traffic-flow features and OSM import are disabled).

### `SUMO: Binary not found at .../sumo.exe`
SUMO is not installed, or `SUMO_HOME` is not set to a directory containing a
`bin/` subfolder with `sumo` / `sumo-gui` / `netconvert` / `netgenerate`.

Verify:
```bash
# macOS / Linux
ls "$SUMO_HOME/bin"
# Windows
dir "%SUMO_HOME%\bin"
```

The launchers auto-detect these paths on Windows:
- `C:\Program Files (x86)\Eclipse SUMO`
- `C:\Program Files\Eclipse SUMO`
- `C:\SUMO`

And on macOS:
- `/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo`
- `/opt/homebrew/share/sumo`
- `/usr/local/share/sumo`

### Port 5000 already in use (macOS AirPlay receiver)
macOS Monterey+ reserves port 5000 for AirPlay. Either disable it in
**System Settings → AirDrop & Handoff → AirPlay Receiver**, or use a
different port:
```bash
./run_dashboard.sh --port 5050
```

### `unable to open database file` on first run
The `output/` directory did not exist when Flask tried to open
`output/experiments.sqlite`. The launchers create the directory automatically
on dashboard start. If you bypass them, run:
```bash
mkdir -p output/csv output/figures output/tables
```

### Stale SUMO processes holding the TraCI port
The `start_sumo()` helper in `engine/sumo_integration.py` does a best-effort
cleanup before each run — `taskkill` on Windows, `pkill`/`lsof` elsewhere.
If a process is still stuck:
```powershell
# Windows
taskkill /F /IM sumo.exe
taskkill /F /IM sumo-gui.exe
```
```bash
# macOS / Linux
pkill -f "sumo.*-c.*traci_config"
```

### Flask server log is empty
On Windows, Flask's default logging writes to stderr which the launcher
captures. Check `output/experiment_run.log` for run output, and
`%TEMP%\commandcode\...` for the launcher's combined stdout/stderr.

### `pkill`/`lsof`/`pgrep` not found (Windows)
These commands don't exist on Windows. The project detects the platform and
uses `taskkill` instead — no action needed if you use the bundled scripts
(`run_dashboard.ps1`/`.bat`, `run_experiments.ps1`/`.bat`).

### PowerShell execution policy blocks `.ps1` scripts
On a fresh Windows machine, the default execution policy may prevent running
`.ps1` scripts. Either:
- Use the `.bat` versions instead (`run_dashboard.bat`, `run_experiments.bat`)
- Or allow local scripts in PowerShell:
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```

---

## License

See project root for license information.
