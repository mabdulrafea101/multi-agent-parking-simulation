"""Flask routes for the Multi-Agent Parking Simulation dashboard."""
import csv
import copy
import json
import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timezone

from flask import (
    Blueprint,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from experiments import ExperimentRunner, RESULT_COLUMNS, SCENARIO_ORDER, STRATEGY_ORDER

RESULTS_TOOLTIPS = {
    "scenario": "Scenario | The traffic demand level used in this experiment. Higher demand means more drivers arrive in the same simulation window.",
    "strategy": "Strategy | The parking allocation policy. auction=bidding-based allocation, fcfs=first-come-first-served, random=random spot assignment, greedy=nearest available spot.",
    "replication": "Replication | Independent run index for the same scenario-strategy combination. Multiple replications reduce statistical noise.",
    "mean_pst": "Mean Parking Search Time (PST) | Average number of simulation ticks a driver spends searching before parking. Lower is better; high PST indicates congestion or scarcity.",
    "std_pst": "STD Parking Search Time (PST) | Standard deviation of searching time across drivers in one replication. Higher values mean inconsistent search experiences.",
    "mean_por": "Mean Parking Occupancy Rate (POR) | Average share of parking spots in use after warmup. Closer to 1.0 means fuller utilisation; very high POR can mean scarcity.",
    "rsr": "Resource Success Rate (RSR) | Fraction of arriving drivers who successfully find a parking spot. Higher is better; low RSR indicates unmet demand.",
    "mean_utility": "Mean Driver Utility | Average satisfaction score per parked driver, combining monetary cost and proximity to destination.",
    "tfi": "Traffic Flow Impact (TFI) | Sum of all parking search durations divided by total arrivals. Lower TFI means less accumulated congestion from cruising for parking.",
    "sumo_connected": "SUMO Connected | True when the traffic microsimulation backend (SUMO/TraCI) was active for this run. False means the run fell back to the abstract Mesa-only model.",
    "sumo_vehicles_completed": "SUMO Vehicles Completed | Vehicles that completed their route and exited the SUMO traffic network during this run. A shortfall against Total Arrivals has several causes - routes still in progress when the run ends, and departures SUMO rejected outright - so use SUMO Spawn Edges to judge how well the network was actually reached.",
    "sumo_spawn_edges": "SUMO Spawn Edges | Distinct network edges that actually received a departing vehicle during this run. A city network should show hundreds; a single-digit value means the simulation grid was mapped onto a small fragment of the network.",
    "min_sumo_spawn_edges": "Min SUMO Spawn Edges | Lowest distinct spawn-edge count across the SUMO-connected replications in this group. A low minimum flags a group whose grid-to-network mapping collapsed.",
    "n_replications": "N Replications | Number of independent simulation repetitions aggregated for this summary row.",
    "sumo_connected_runs": "SUMO Connected Runs | Count of replications in this group where SUMO/TraCI was active.",
    "mean_total_arrivals": "Mean Total Arrivals | Average number of driver arrivals recorded before the end of the simulation.",
    "std_total_arrivals": "STD Total Arrivals | Standard deviation of total arrivals across replications.",
    "mean_total_successful": "Mean Total Successful | Average number of drivers who successfully parked.",
    "std_total_successful": "STD Total Successful | Standard deviation of successful parking counts across replications.",
    "mean_total_failed": "Mean Total Failed | Average number of drivers who failed to find a parking spot.",
    "std_total_failed": "STD Total Failed | Standard deviation of failed parking counts across replications.",
    "mean_mean_pst": "Mean of Mean Parking Search Time (PST) | Average of PST means across multiple replications.",
    "std_mean_pst": "Standard Deviation of Mean Parking Search Time (PST) | Variation in PST means across replications.",
    "mean_std_por": "Mean of STD Parking Occupancy Rate (POR) | Average of POR standard deviations across replications.",
    "std_std_por": "Standard Deviation of STD Parking Occupancy Rate (POR) | Variation in POR standard deviations across replications.",
    "mean_rsr": "Mean Resource Success Rate (RSR) | Average RSR across multiple replications.",
    "std_rsr": "Standard Deviation of Resource Success Rate (RSR) | Variation in RSR across replications.",
    "mean_mean_utility": "Mean of Mean Driver Utility | Average of utility means across multiple replications.",
    "std_mean_utility": "Standard Deviation of Mean Driver Utility | Variation in utility means across replications.",
    "mean_tfi": "Mean Traffic Flow Impact (TFI) | Average TFI across multiple replications.",
    "std_tfi": "Standard Deviation of Traffic Flow Impact (TFI) | Variation in TFI across replications.",
    "replication": "Replication | Independent run index for the same scenario-strategy combination.",
    "total_arrivals": "Total Arrivals | Total number of driver arrivals in this replication.",
    "total_successful": "Total Successful | Total number of drivers who successfully parked.",
    "total_failed": "Total Failed | Total number of drivers who failed to find a parking spot.",
    "std_por": "STD Parking Occupancy Rate (POR) | Standard deviation of POR across ticks in one replication.",
}

PRIMARY_FIGURE_CATALOG = (
    {
        "filename": "pst_comparison.png",
        "title": "Mean Parking Search Time",
        "description": "Mean parking search time with 95% confidence intervals.",
        "alt": "Bar chart comparing mean parking search time by scenario and strategy.",
    },
    {
        "filename": "rsr_comparison.png",
        "title": "Reservation Success Rate",
        "description": "Reservation success rate with 95% confidence intervals.",
        "alt": "Bar chart comparing reservation success rate by scenario and strategy.",
    },
    {
        "filename": "utility_comparison.png",
        "title": "Mean Driver Utility",
        "description": "Mean driver utility with 95% confidence intervals.",
        "alt": "Bar chart comparing mean driver utility by scenario and strategy.",
    },
    {
        "filename": "tfi_comparison.png",
        "title": "Traffic Flow Impact",
        "description": "Traffic Flow Impact with 95% confidence intervals.",
        "alt": "Bar chart comparing traffic flow impact by scenario and strategy.",
    },
    {
        "filename": "pst_boxplot.png",
        "title": "Parking Search Time Distribution",
        "description": "Per-replication parking search time distributions by scenario and strategy.",
        "alt": "Box plot showing parking search time distributions by scenario and strategy.",
    },
    {
        "filename": "por_timeseries.png",
        "title": "Parking Occupancy Rate Over Time",
        "description": "Parking occupancy over time for all available demand scenarios and strategies.",
        "alt": "Time series chart showing parking occupancy rate over time.",
    },
)


def _primary_figures(figures, fallback_figures=()):
    """Return catalog figures, preferring the selected source over its fallback."""
    figures_by_name = {os.path.basename(figure): figure for figure in fallback_figures}
    figures_by_name.update({os.path.basename(figure): figure for figure in figures})
    return [
        {**metadata, "filename": figures_by_name[metadata["filename"]]}
        for metadata in PRIMARY_FIGURE_CATALOG
        if metadata["filename"] in figures_by_name
    ]


def _additional_figures(figures, primary_figures):
    primary_names = {os.path.basename(figure["filename"]) for figure in primary_figures}
    return [figure for figure in figures if os.path.basename(figure) not in primary_names]

experiment_state = {
    "status": "idle",  # idle | running | completed | error | stopped
    "scenario": None,
    "strategy": None,
    "replications": None,
    "simulation_type": "mesa",
    "city": None,
    "total_runs": None,
    "completed_runs": 0,
    "progress_log": [],
    "run_rows": [],
    "error_message": None,
    "run_id": None,
    "visualization_run_id": None,
}

experiment_lock = threading.Lock()
experiment_thread = None

bp = Blueprint("dashboard", __name__)

SIMULATION_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(SIMULATION_DIR, "output", "experiments.sqlite")


def _recover_stale_experiments():
    """Mark runs left active by an interrupted application as stopped."""
    conn = _get_db()
    conn.execute(
        """
        UPDATE experiments
        SET status='stopped', error=?
        WHERE status='running'
        """,
        ("Experiment was interrupted when the application stopped.",),
    )
    conn.commit()
    conn.close()


@bp.record_once
def _initialize_database(state):
    """Initialize the schema and recover runs during app creation."""
    _recover_stale_experiments()


def _get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT NOT NULL,
            scenario TEXT,
            strategy TEXT,
            replications INTEGER,
            total_runs INTEGER,
            results_path TEXT,
            rows_count INTEGER,
            rows_json TEXT,
            summary_json TEXT,
            figures_json TEXT,
            error TEXT
        )
        """
    )
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(experiments)").fetchall()
    }
    migrations = {
        "status": "ALTER TABLE experiments ADD COLUMN status TEXT DEFAULT 'completed'",
        "started_at": "ALTER TABLE experiments ADD COLUMN started_at TEXT",
        "completed_at": "ALTER TABLE experiments ADD COLUMN completed_at TEXT",
        "progress_json": "ALTER TABLE experiments ADD COLUMN progress_json TEXT",
        "kpis_json": "ALTER TABLE experiments ADD COLUMN kpis_json TEXT",
    }
    for column, statement in migrations.items():
        if column not in existing_columns:
            conn.execute(statement)
    conn.commit()
    return conn


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dumps(value):
    return json.dumps(value, default=str) if value is not None else None


def _load_run_config():
    config_path = os.path.join(SIMULATION_DIR, "config", "scenarios.json")
    with open(config_path, "r") as f:
        config = json.load(f)
    return {
        "simulation_types": config.get("simulation_types", {}),
        "osm_cities": config.get("osm_cities", {}),
    }


def _create_experiment_record(scenario, strategy, replications, total_runs):
    conn = _get_db()
    now = _utc_now()
    cursor = conn.execute(
        """
        INSERT INTO experiments (
            run_at, started_at, scenario, strategy, replications, total_runs,
            rows_count, status, progress_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            now,
            scenario or "all",
            strategy or "all",
            replications,
            total_runs,
            0,
            "running",
            _json_dumps({"completed_runs": 0, "total_runs": total_runs, "log": []}),
        ),
    )
    conn.commit()
    run_id = cursor.lastrowid
    conn.close()
    return run_id


def _update_experiment_record(run_id, **fields):
    if not run_id:
        return
    conn = _get_db()
    assignments = ", ".join(f"{key}=?" for key in fields)
    conn.execute(
        f"UPDATE experiments SET {assignments} WHERE id=?",
        [*fields.values(), run_id],
    )
    conn.commit()
    conn.close()


def _derive_kpis(summary_rows):
    if not summary_rows:
        return {}
    kpis = {}
    for metric in ["mean_mean_pst", "mean_rsr", "mean_mean_utility", "mean_tfi", "mean_total_arrivals", "mean_total_successful"]:
        values = []
        for row in summary_rows:
            try:
                values.append(float(row.get(metric, 0)))
            except (TypeError, ValueError):
                pass
        if values:
            kpis[metric] = sum(values) / len(values)
    return kpis


def _load_current_outputs():
    results_csv = os.path.join(SIMULATION_DIR, "output", "csv", "experiment_results.csv")
    summary_csv = os.path.join(SIMULATION_DIR, "output", "csv", "summary_statistics.csv")
    rows = []
    summary_rows = []
    figures = []

    if os.path.exists(results_csv):
        with open(results_csv, newline="") as f:
            rows = list(csv.DictReader(f))
    if os.path.exists(summary_csv):
        with open(summary_csv, newline="") as f:
            summary_rows = list(csv.DictReader(f))

    figures_dir = os.path.join(SIMULATION_DIR, "output", "figures")
    if os.path.isdir(figures_dir):
        figures = sorted(f for f in os.listdir(figures_dir) if f.endswith(".png"))

    return results_csv, rows, summary_rows, figures


def _write_por_timeseries(run_output_dir, rows):
    if not rows:
        return False
    os.makedirs(run_output_dir, exist_ok=True)
    path = os.path.join(run_output_dir, "por_timeseries.csv")
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["scenario", "strategy", "replication", "tick", "por"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return True


def _snapshot_run_rows():
    with experiment_lock:
        return list(experiment_state.get("run_rows", []))


def _load_csv_rows(path):
    if not os.path.isfile(path):
        return []
    with open(path, newline="") as file:
        return list(csv.DictReader(file))


def _write_summary_csv(path, summary_rows):
    fieldnames = list(summary_rows[0].keys()) if summary_rows else [
        "scenario", "strategy", "n_replications"
    ]
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)


def _run_experiment_async(scenario, strategy, replications, simulation_type="mesa", city=None, refresh_osm=False):
    """Run the experiment in a background thread."""
    global experiment_state
    simulation_type = simulation_type or "mesa"
    city = city if simulation_type == "osm_city" else None
    refresh_osm = bool(refresh_osm and city)
    selected_scenarios = [scenario] if scenario else None
    selected_strategies = [strategy] if strategy else None
    total_runs = (len(selected_scenarios) if selected_scenarios else 4) * (
        len(selected_strategies) if selected_strategies else 4
    ) * int(replications)
    run_id = _create_experiment_record(scenario, strategy, int(replications), total_runs)

    with experiment_lock:
        experiment_state.update(
            {
                "status": "running",
                "started_at": time.time(),
                "scenario": scenario,
                "strategy": strategy,
                "replications": int(replications),
                "simulation_type": simulation_type,
                "city": city,
                "total_runs": total_runs,
                "completed_runs": 0,
                "progress_log": ["Experiment queued."],
                "error_message": None,
                "run_rows": [],
                "returncode": None,
                "run_id": run_id,
                "visualization_run_id": None,
            }
        )

    try:
        runner = ExperimentRunner(
            config_dir=os.path.join(SIMULATION_DIR, "config"),
            output_dir=os.path.join(SIMULATION_DIR, "output"),
        )

        def on_progress(completed, total, scenario, strategy, replication, result):
            log_line = (
                f"{scenario} / {strategy} replication {replication + 1}: "
                f"PST={float(result.get('mean_pst', 0)):.2f}, "
                f"RSR={float(result.get('rsr', 0)):.1f}%"
            )
            with experiment_lock:
                experiment_state.setdefault("run_rows", []).append(result)
                experiment_state["completed_runs"] = completed
                experiment_state["total_runs"] = total
                experiment_state["progress_log"].append(log_line)
                progress = {
                    "completed_runs": completed,
                    "total_runs": total,
                    "log": list(experiment_state["progress_log"]),
                }
            _update_experiment_record(run_id, progress_json=_json_dumps(progress))

        runner.run_batch(
            scenarios=selected_scenarios,
            strategies=selected_strategies,
            replication_end=int(replications),
            simulation_type=simulation_type,
            city=city,
            refresh_osm=refresh_osm,
            progress_callback=on_progress,
        )

        run_rows = _snapshot_run_rows()

        run_output_dir = os.path.join(SIMULATION_DIR, "output", f"run_{run_id}")
        os.makedirs(run_output_dir, exist_ok=True)
        run_results_csv = os.path.join(run_output_dir, "experiment_results.csv")
        with open(run_results_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=RESULT_COLUMNS)
            writer.writeheader()
            for row in run_rows:
                # RESULT_COLUMNS is the single source of truth, so a field the
                # runner produces can never be dropped from the dashboard CSV.
                writer.writerow({key: row.get(key, "") for key in RESULT_COLUMNS})

        por_rows = [
            timeseries_row
            for result in run_rows
            for timeseries_row in result.get("_timeseries", [])
        ]
        _write_por_timeseries(run_output_dir, por_rows)

        run_figures_dir = os.path.join(SIMULATION_DIR, "output", "figures", f"run_{run_id}")
        try:
            from analysis import SimulationAnalyzer

            analyzer = SimulationAnalyzer(
                results_dir=run_output_dir,
                figures_dir=run_figures_dir,
                tables_dir=os.path.join(SIMULATION_DIR, "output", "tables"),
            )
            analyzer.load_results(csv_file=run_results_csv)
            analyzer.generate_all()
            with experiment_lock:
                experiment_state["progress_log"].append("Analysis and figures regenerated.")
        except Exception as exc:
            with experiment_lock:
                experiment_state["progress_log"].append(f"Analysis failed: {exc}")
            raise

        rows = _load_csv_rows(run_results_csv)
        if not rows:
            raise RuntimeError("Results file was not created or contained no rows.")

        summary_input = [
            {
                **row,
                "sumo_connected": str(row.get("sumo_connected", "")).lower() == "true",
            }
            for row in rows
        ]
        summary_rows = runner.compute_summary(summary_input)
        _write_summary_csv(os.path.join(run_output_dir, "summary_statistics.csv"), summary_rows)

        recording_scenario = scenario or (run_rows[0].get("scenario") if run_rows else None)
        recording_strategy = strategy or (run_rows[0].get("strategy") if run_rows else None)
        visualization_run_id = None
        try:
            visualization_run_id = _record_dashboard_experiment(
                scenario=recording_scenario,
                strategy=recording_strategy,
                simulation_type=simulation_type,
                city=city,
                experiment_run_id=run_id,
                config=getattr(runner, "base_config", None),
                scenario_config=(
                    getattr(runner, "scenarios_config", {}).get("scenarios", {}).get(recording_scenario, {})
                    if recording_scenario else {}
                ),
            )
            with experiment_lock:
                experiment_state["visualization_run_id"] = visualization_run_id
                experiment_state["progress_log"].append(
                    f"Visualization recording saved as {visualization_run_id}."
                )
        except Exception as exc:
            with experiment_lock:
                experiment_state["progress_log"].append(
                    f"Visualization recording failed: {exc}"
                )

        run_figures_dir = os.path.join(SIMULATION_DIR, "output", "figures", f"run_{run_id}")
        os.makedirs(run_figures_dir, exist_ok=True)

        copied_figures = [
            f"run_{run_id}/{fig}"
            for fig in sorted(os.listdir(run_figures_dir))
            if fig.endswith(".png")
        ]

        kpis = _derive_kpis(summary_rows)
        with experiment_lock:
            experiment_state["status"] = "completed"
            experiment_state["completed_runs"] = total_runs
            progress = {
                "completed_runs": experiment_state["completed_runs"],
                "total_runs": total_runs,
                "log": list(experiment_state["progress_log"]),
                "visualization_run_id": visualization_run_id,
            }
        _update_experiment_record(
            run_id,
            completed_at=_utc_now(),
            status="completed",
            results_path=run_results_csv,
            rows_count=len(rows),
            rows_json=_json_dumps(rows),
            summary_json=_json_dumps(summary_rows),
            figures_json=_json_dumps(copied_figures),
            kpis_json=_json_dumps(kpis),
            progress_json=_json_dumps(progress),
            error=None,
        )
    except Exception as exc:
        with experiment_lock:
            experiment_state["status"] = "error"
            experiment_state["error_message"] = str(exc)
            progress = {
                "completed_runs": experiment_state["completed_runs"],
                "total_runs": total_runs,
                "log": list(experiment_state["progress_log"]),
            }
        _update_experiment_record(
            run_id,
            completed_at=_utc_now(),
            status="error",
            progress_json=_json_dumps(progress),
            error=str(exc),
        )


@bp.route("/")
def index():
    """Dashboard home page."""
    with experiment_lock:
        state = dict(experiment_state)
    return render_template("index.html", state=state)


@bp.route("/run", methods=["GET", "POST"])
def run_experiment():
    """Run a new experiment."""
    global experiment_thread

    if request.method == "POST":
        scenario = request.form.get("scenario", "")
        strategy = request.form.get("strategy", "auction")
        replications = int(request.form.get("replications", 2))
        simulation_type = request.form.get("simulation_type") or "mesa"
        city = request.form.get("city") or None
        if simulation_type != "osm_city":
            city = None
        refresh_osm = bool(request.form.get("refresh_osm")) and city is not None

        with experiment_lock:
            if experiment_state["status"] == "running":
                return redirect(url_for("dashboard.run_experiment"))

            # Reserve the launch before releasing the lock so a second POST
            # cannot pass the status check while the worker is starting.
            experiment_state.update(
                {
                    "status": "running",
                    "started_at": time.time(),
                    "scenario": scenario,
                    "strategy": strategy,
                    "replications": replications,
                    "simulation_type": simulation_type,
                    "city": city,
                    "total_runs": (len([scenario]) if scenario else 4)
                    * (len([strategy]) if strategy else 4)
                    * replications,
                    "completed_runs": 0,
                    "progress_log": ["Experiment queued."],
                    "error_message": None,
                    "run_rows": [],
                    "returncode": None,
                    "run_id": None,
                    "visualization_run_id": None,
                }
            )
            thread = threading.Thread(
                target=_run_experiment_async,
                args=(scenario, strategy, replications, simulation_type, city, refresh_osm),
                daemon=True,
            )
            experiment_thread = thread
        thread.start()
        return redirect(url_for("dashboard.run_experiment"))

    with experiment_lock:
        state = dict(experiment_state)
    return render_template("run.html", state=state, **_load_run_config())


@bp.route("/progress")
def progress():
    """SSE stream with experiment progress."""

    def event_stream():
        while True:
            with experiment_lock:
                state = dict(experiment_state)
            data = json.dumps(state)
            yield f"data: {data}\n\n"
            if state["status"] in ("completed", "error", "stopped"):
                break
            time.sleep(1)

    return Response(event_stream(), mimetype="text/event-stream")


@bp.route("/progress.json")
def progress_json():
    """JSON endpoint for current experiment progress."""
    with experiment_lock:
        return jsonify(dict(experiment_state))


@bp.route("/results")
def results():
    """View experiment results."""
    with experiment_lock:
        state = dict(experiment_state)

    suppress_current_outputs = state.get("status") in ("running", "error")
    results_csv = os.path.join(SIMULATION_DIR, "output", "csv", "experiment_results.csv")
    summary_csv = os.path.join(os.path.dirname(results_csv), "summary_statistics.csv")

    rows = []
    if not suppress_current_outputs and os.path.exists(results_csv):
        with open(results_csv, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

    summary_rows = []
    if not suppress_current_outputs and os.path.exists(summary_csv):
        with open(summary_csv, newline="") as f:
            reader = csv.DictReader(f)
            summary_rows = list(reader)

    figures_dir = os.path.join(SIMULATION_DIR, "output", "figures")
    all_figures = []

    # Get all PNG files - both in root and in run_* subdirectories
    if not suppress_current_outputs and os.path.isdir(figures_dir):
        # Root level figures
        all_figures = sorted(f for f in os.listdir(figures_dir) if f.endswith(".png"))

        # Also scan run_* subdirectories for figures
        for item in os.listdir(figures_dir):
            subdir = os.path.join(figures_dir, item)
            if os.path.isdir(subdir) and item.startswith("run_"):
                for f in os.listdir(subdir):
                    if f.endswith(".png"):
                        all_figures.append(f"{item}/{f}")

        all_figures = sorted(all_figures)

    # Get latest run's figures (highest run number)
    latest_figures = []
    latest_run_id = None
    if all_figures:
        # Extract run numbers from figure paths like "run_25/pst_comparison.png"
        import re
        run_numbers = set()
        for fig in all_figures:
            match = re.search(r'run_(\d+)/', fig)
            if match:
                run_numbers.add(int(match.group(1)))

        if run_numbers:
            latest_run_id = max(run_numbers)
            # Get figures for the latest run
            latest_figures = sorted(f for f in all_figures if f.startswith(f"run_{latest_run_id}/"))

    root_figures = [figure for figure in all_figures if "/" not in figure]
    primary_figures = _primary_figures(latest_figures, root_figures) if latest_figures else _primary_figures(root_figures)

    return render_template(
        "results.html",
        rows=rows,
        summary_rows=summary_rows,
        figures=all_figures,
        additional_figures=_additional_figures(all_figures, primary_figures),
        primary_figures=primary_figures,
        latest_figures=latest_figures,
        latest_run_id=latest_run_id,
        state=state,
        tooltips=RESULTS_TOOLTIPS,
    )


@bp.route("/history")
def history():
    """View past experiment runs from SQLite history."""
    conn = _get_db()
    runs = conn.execute(
        """
        SELECT id, run_at, scenario, strategy, replications, total_runs, rows_count,
               status, summary_json, kpis_json, error
        FROM experiments
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()
    return render_template(
        "history.html",
        runs=[dict(run) for run in runs],
        tooltips=RESULTS_TOOLTIPS,
    )


@bp.route("/history/run/<int:run_id>")
def history_run(run_id):
    """View the stored results for a specific experiment run."""
    conn = _get_db()
    row = conn.execute(
        """
        SELECT id, run_at, results_path, rows_json, summary_json, figures_json, status, error
        FROM experiments WHERE id=?
        """,
        (run_id,),
    ).fetchone()
    conn.close()

    if not row:
        return redirect(url_for("dashboard.history"))

    rows = _load_csv_rows(row["results_path"]) if row["results_path"] else []
    if not rows:
        rows = json.loads(row["rows_json"] or "[]")
    summary_rows = json.loads(row["summary_json"] or "[]")
    figures = json.loads(row["figures_json"] or "[]")
    primary_figures = _primary_figures(figures)
    return render_template(
        "results.html",
        rows=rows,
        summary_rows=summary_rows,
        figures=figures,
        additional_figures=_additional_figures(figures, primary_figures),
        primary_figures=primary_figures,
        latest_figures=figures,
        latest_run_id=run_id,
        state={"status": row["status"], "error_message": row["error"], "progress_log": []},
        tooltips=RESULTS_TOOLTIPS,
        history_run_id=run_id,
        run_at=row["run_at"],
    )


@bp.route("/history/run/<int:run_id>/delete", methods=["POST"])
def history_delete(run_id):
    """Delete one historical run and its run-local artifacts."""
    conn = _get_db()
    row = conn.execute(
        "SELECT results_path FROM experiments WHERE id=?", (run_id,)
    ).fetchone()
    if not row or not row["results_path"]:
        conn.close()
        return "Not found", 404

    output_path = os.path.join(SIMULATION_DIR, "output")
    output_dir = os.path.realpath(output_path)
    literal_run_dir = os.path.join(output_path, f"run_{run_id}")
    expected_run_dir = os.path.join(output_dir, f"run_{run_id}")
    # Reject any directory link here: os.path.islink() misses Windows junctions,
    # and rmtree would then follow the link into an unrelated tree.
    if not os.path.isdir(literal_run_dir) or os.path.realpath(literal_run_dir) != expected_run_dir:
        conn.close()
        return "Not found", 404

    results_path = os.path.realpath(row["results_path"])
    run_dir = os.path.realpath(os.path.dirname(row["results_path"]))
    try:
        safe_results_path = (
            run_dir == expected_run_dir
            and results_path != expected_run_dir
            and os.path.commonpath([expected_run_dir, results_path]) == expected_run_dir
        )
    except ValueError:
        safe_results_path = False
    if not safe_results_path:
        conn.close()
        return "Not found", 404

    figure_dir = os.path.realpath(os.path.join(output_dir, "figures", f"run_{run_id}"))
    try:
        inside_output = os.path.commonpath([output_dir, figure_dir]) == output_dir
    except ValueError:
        inside_output = False
    if not inside_output:
        conn.close()
        return "Not found", 404

    if os.path.isdir(run_dir):
        shutil.rmtree(run_dir)
    if os.path.isdir(figure_dir):
        shutil.rmtree(figure_dir)
    conn.execute("DELETE FROM experiments WHERE id=?", (run_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard.history"))


@bp.route("/history.json")
def history_json():
    """JSON history for interactive charts on the history page."""
    conn = _get_db()
    rows = conn.execute(
        """
        SELECT id, run_at, scenario, strategy, replications, total_runs, rows_count,
               status, summary_json, kpis_json, error
        FROM experiments
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()
    data = [dict(r) for r in rows]
    return jsonify(data)


@bp.route("/download/<path:filename>")
def download(filename):
    """Download a CSV file from the output directory."""
    safe_files = {
        "experiment_results.csv": "experiment_results.csv",
        "summary_statistics.csv": "summary_statistics.csv",
        "por_timeseries.csv": "por_timeseries.csv",
    }
    if filename not in safe_files:
        return "File not found", 404

    filepath = os.path.join(SIMULATION_DIR, "output", "csv", safe_files[filename])
    if not os.path.exists(filepath):
        return f"{filename} not found. Run an experiment first.", 404

    with open(filepath, "r") as f:
        data = f.read()

    return Response(
        data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={safe_files[filename]}"},
    )


@bp.route("/history/run/<int:run_id>/download/<path:filename>")
def history_download(run_id, filename):
    """Download an artifact belonging to one historical run."""
    safe_files = {
        "experiment_results.csv": "experiment_results.csv",
        "summary_statistics.csv": "summary_statistics.csv",
        "por_timeseries.csv": "por_timeseries.csv",
    }
    if filename not in safe_files:
        return "File not found", 404

    conn = _get_db()
    row = conn.execute("SELECT results_path FROM experiments WHERE id=?", (run_id,)).fetchone()
    conn.close()
    if not row or not row["results_path"]:
        return "File not found", 404

    output_dir = os.path.realpath(os.path.join(SIMULATION_DIR, "output"))
    run_dir = os.path.dirname(os.path.realpath(row["results_path"]))
    filepath = os.path.realpath(os.path.join(run_dir, safe_files[filename]))
    try:
        inside_output = os.path.commonpath([output_dir, run_dir]) == output_dir
        inside_run = os.path.commonpath([run_dir, filepath]) == run_dir
    except ValueError:
        inside_output = False
        inside_run = False
    if not inside_output or not inside_run or not os.path.isfile(filepath):
        return f"{filename} not found. Run an experiment first.", 404

    with open(filepath, "r") as file:
        data = file.read()
    return Response(
        data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={safe_files[filename]}"},
    )


@bp.route("/figure/<path:name>")
def figure(name):
    """Serve a saved figure, including per-run figures like run_12/...png."""
    if not name.endswith(".png"):
        return "Not found", 404

    figures_dir = os.path.realpath(os.path.join(SIMULATION_DIR, "output", "figures"))
    filepath = os.path.realpath(os.path.join(figures_dir, name))
    try:
        inside_figures = os.path.commonpath([figures_dir, filepath]) == figures_dir
    except ValueError:
        inside_figures = False
    if inside_figures and os.path.isfile(filepath):
        with open(filepath, "rb") as f:
            data = f.read()
        return Response(data, mimetype="image/png")

    return "Not found", 404


@bp.route("/reset", methods=["POST"])
def reset():
    """Reset experiment state."""
    global experiment_state
    with experiment_lock:
        experiment_state = {
            "status": "idle",
            "returncode": None,
            "started_at": None,
            "scenario": None,
            "strategy": None,
            "replications": None,
            "simulation_type": "mesa",
            "city": None,
            "total_runs": None,
            "completed_runs": 0,
            "progress_log": [],
            "error_message": None,
            "run_rows": [],
            "run_id": None,
            "visualization_run_id": None,
        }
    return redirect(url_for("dashboard.index"))


# ── Visualization endpoints ─────────────────────────────────────────────
VIZ_FRAMES_DIR = os.path.join(SIMULATION_DIR, "output", "frames")


def _record_dashboard_experiment(
    scenario,
    strategy,
    simulation_type="mesa",
    city=None,
    experiment_run_id=None,
    config=None,
    scenario_config=None,
):
    """Record one completed dashboard configuration for visualization."""
    from engine.cities import get_city_config
    from model import ParkingModel
    from recorder import FrameRecorder

    if config is None:
        with open(os.path.join(SIMULATION_DIR, "config", "default_params.json")) as file:
            config = json.load(file)
    config = copy.deepcopy(config)
    scenario_config = scenario_config or {}
    if scenario_config.get("arrival_rate_lambda") is not None:
        config.setdefault("demand", {})["arrival_rate_lambda"] = scenario_config["arrival_rate_lambda"]
    config["strategy"] = strategy

    city_config = None
    if city:
        city_config = get_city_config(city)

    model = ParkingModel(
        config_dict=config,
        strategy=strategy,
        simulation_type=simulation_type,
        city=city,
    )
    recorder = FrameRecorder(model, city_config=city_config, record_interval=1)
    model.recorder = recorder
    for _ in range(model.total_ticks):
        model.step()
    recorder.capture_tick()
    requested_run_id = (
        f"run_dashboard_{experiment_run_id}" if experiment_run_id is not None else None
    )
    run_id, meta_path, _ = recorder.save(VIZ_FRAMES_DIR, run_id=requested_run_id)

    with open(meta_path, "r") as file:
        metadata = json.load(file)
    metadata["scenario"] = scenario
    metadata["dashboard_experiment_id"] = experiment_run_id
    with open(meta_path, "w") as file:
        json.dump(metadata, file)
    return run_id


@bp.route("/visualize")
def visualize():
    """Render the Three.js visualization page."""
    # List available recorded runs
    runs = []
    if os.path.isdir(VIZ_FRAMES_DIR):
        for fname in sorted(os.listdir(VIZ_FRAMES_DIR), reverse=True):
            if fname.endswith("_meta.json"):
                run_id = fname.replace("_meta.json", "")
                try:
                    with open(os.path.join(VIZ_FRAMES_DIR, fname)) as f:
                        meta = json.load(f)
                    runs.append({"run_id": run_id, "meta": meta})
                except Exception:
                    pass
    return render_template("visualize.html", runs=runs)


@bp.route("/api/viz/runs")
def viz_runs():
    """List available recorded simulation runs."""
    runs = []
    if os.path.isdir(VIZ_FRAMES_DIR):
        for fname in sorted(os.listdir(VIZ_FRAMES_DIR), reverse=True):
            if fname.endswith("_meta.json"):
                run_id = fname.replace("_meta.json", "")
                try:
                    with open(os.path.join(VIZ_FRAMES_DIR, fname)) as f:
                        meta = json.load(f)
                    runs.append({"run_id": run_id, "meta": meta})
                except Exception:
                    pass
    return jsonify(runs)


@bp.route("/api/viz/frames/<run_id>")
def viz_frames(run_id):
    """Return frame data for a specific run."""
    frames_path = os.path.join(VIZ_FRAMES_DIR, f"{run_id}_frames.json")
    if not os.path.exists(frames_path):
        return jsonify({"error": "Run not found"}), 404
    with open(frames_path) as f:
        frames = json.load(f)
    return jsonify(frames)


@bp.route("/api/viz/meta/<run_id>")
def viz_meta(run_id):
    """Return metadata for a specific run."""
    meta_path = os.path.join(VIZ_FRAMES_DIR, f"{run_id}_meta.json")
    if not os.path.exists(meta_path):
        return jsonify({"error": "Run not found"}), 404
    with open(meta_path) as f:
        meta = json.load(f)
    return jsonify(meta)


@bp.route("/api/viz/record", methods=["POST"])
def viz_record():
    """Run a simulation with frame recording for visualization."""
    from model import ParkingModel
    from recorder import FrameRecorder
    from engine.cities import get_city_config

    data = request.get_json() or {}
    strategy = data.get("strategy", "auction")
    city = data.get("city", None)
    total_ticks = data.get("total_ticks", 200)
    arrival_rate = data.get("arrival_rate", 5)
    grid_width = data.get("grid_width", 100)
    grid_height = data.get("grid_height", 100)
    num_spots = data.get("num_spots", 200)
    num_zones = data.get("num_zones", 8)
    warmup_ticks = data.get("warmup_ticks", 50)

    # Build config
    config = {
        "grid": {"width": grid_width, "height": grid_height, "cell_size_meters": 10},
        "parking": {"num_spots": num_spots, "num_zones": num_zones, "price_range": [1, 10]},
        "demand": {
            "arrival_rate_lambda": arrival_rate,
            "parking_duration_mean_ticks": 50,
            "parking_duration_std_ticks": 15,
            "search_radius_cells": 15,
            "max_search_duration_ticks": 30,
        },
        "simulation": {
            "total_ticks": total_ticks,
            "warmup_ticks": warmup_ticks,
            "random_seed": 42,
        },
        "strategy": strategy,
    }

    # Get city config if specified
    city_config = None
    if city:
        try:
            city_config = get_city_config(city)
        except ValueError:
            pass

    # Create model with recording
    model = ParkingModel(config_dict=config, strategy=strategy)
    recorder = FrameRecorder(model, city_config=city_config, record_interval=1)
    model.recorder = recorder

    # Run simulation
    results = model.run_simulation(output_dir=VIZ_FRAMES_DIR)
    run_id = results.get("frame_run_id")

    return jsonify({
        "status": "completed",
        "frames": len(recorder.frames),
        "run_id": run_id,
    })
