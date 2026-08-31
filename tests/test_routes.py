"""Regression tests for the results dashboard figure metadata."""
import csv
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app import routes


PRIMARY_FIGURE_METADATA = {
    "pst_comparison.png": (
        "Mean Parking Search Time",
        "Mean parking search time with 95% confidence intervals.",
    ),
    "rsr_comparison.png": (
        "Reservation Success Rate",
        "Reservation success rate with 95% confidence intervals.",
    ),
    "utility_comparison.png": (
        "Mean Driver Utility",
        "Mean driver utility with 95% confidence intervals.",
    ),
    "tfi_comparison.png": (
        "Traffic Flow Impact",
        "Traffic Flow Impact with 95% confidence intervals.",
    ),
    "pst_boxplot.png": (
        "Parking Search Time Distribution",
        "Per-replication parking search time distributions by scenario and strategy.",
    ),
    "por_timeseries.png": (
        "Parking Occupancy Rate Over Time",
        "Parking occupancy over time for all available demand scenarios and strategies.",
    ),
}


def test_results_renders_primary_figure_titles_and_descriptions(tmp_path, monkeypatch):
    figures_dir = tmp_path / "output" / "figures"
    figures_dir.mkdir(parents=True)
    for filename in PRIMARY_FIGURE_METADATA:
        (figures_dir / filename).touch()

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    response = create_app().test_client().get("/results")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for filename, (title, description) in PRIMARY_FIGURE_METADATA.items():
        figure_start = f'data-figure="{filename}"'
        assert figure_start in body
        figure_markup = body.split(figure_start, 1)[1]
        next_figure = figure_markup.find("data-figure=")
        if next_figure != -1:
            figure_markup = figure_markup[:next_figure]
        assert title in figure_markup
        assert description in figure_markup


def test_results_uses_stable_catalog_order_and_alt_text(tmp_path, monkeypatch):
    figures_dir = tmp_path / "output" / "figures"
    figures_dir.mkdir(parents=True)
    for filename in reversed(list(PRIMARY_FIGURE_METADATA)):
        (figures_dir / filename).touch()

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    body = create_app().test_client().get("/results").get_data(as_text=True)

    assert re.findall(r'data-figure="([^"]+)"', body) == list(PRIMARY_FIGURE_METADATA)
    for metadata in routes.PRIMARY_FIGURE_CATALOG:
        assert f'alt="{metadata["alt"]}"' in body

    assert 'alt="Bar chart comparing mean parking search time by scenario and strategy."' in body
    assert 'alt="Bar chart comparing reservation success rate by scenario and strategy."' in body
    assert 'alt="Bar chart comparing mean driver utility by scenario and strategy."' in body
    assert 'alt="Bar chart comparing traffic flow impact by scenario and strategy."' in body


def test_results_falls_back_to_root_figures_for_missing_latest_run_files(tmp_path, monkeypatch):
    figures_dir = tmp_path / "output" / "figures"
    latest_dir = figures_dir / "run_9"
    latest_dir.mkdir(parents=True)
    for filename in PRIMARY_FIGURE_METADATA:
        (figures_dir / filename).touch()
    (latest_dir / "pst_comparison.png").touch()

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    body = create_app().test_client().get("/results").get_data(as_text=True)

    assert re.findall(r'data-figure="([^"]+)"', body) == [
        "run_9/pst_comparison.png",
        *list(PRIMARY_FIGURE_METADATA)[1:],
    ]
    assert "Figures (Run #9)" in body


def test_results_does_not_render_none_run_for_root_figures(tmp_path, monkeypatch):
    figures_dir = tmp_path / "output" / "figures"
    figures_dir.mkdir(parents=True)
    (figures_dir / "pst_comparison.png").touch()

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    body = create_app().test_client().get("/results").get_data(as_text=True)

    assert "Figures (Run #None)" not in body
    assert "<h2>Figures</h2>" in body


@pytest.mark.parametrize("status", ["running", "error"])
@pytest.mark.parametrize("run_id", [8, None])
def test_results_suppresses_global_outputs_for_active_run(tmp_path, monkeypatch, status, run_id):
    csv_dir = tmp_path / "output" / "csv"
    figures_dir = tmp_path / "output" / "figures"
    csv_dir.mkdir(parents=True)
    figures_dir.mkdir(parents=True)
    (csv_dir / "experiment_results.csv").write_text("scenario,mean_pst\nstale,99\n")
    (csv_dir / "summary_statistics.csv").write_text("scenario,mean_mean_pst\nstale,99\n")
    (figures_dir / "pst_comparison.png").touch()

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(
        routes,
        "experiment_state",
        {
            "status": status,
            "run_id": run_id,
            "progress_log": ["low_demand / auction replication 1: PST=2.00, RSR=90.0%"],
        },
    )

    body = create_app().test_client().get("/results").get_data(as_text=True)

    assert "stale" not in body
    assert "pst_comparison.png" not in body
    assert "low_demand / auction replication 1" in body


def test_analysis_failure_marks_run_error_instead_of_completed(tmp_path, monkeypatch):
    result = {
        "scenario": "low_demand",
        "strategy": "auction",
        "replication": 0,
        "total_arrivals": 1,
        "total_successful": 1,
        "total_failed": 0,
        "mean_pst": 1.0,
        "std_por": 0.1,
        "rsr": 100.0,
        "mean_utility": 0.5,
        "tfi": 0.0,
        "sumo_connected": False,
        "_timeseries": [],
    }

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        def run_batch(self, **kwargs):
            kwargs["progress_callback"](1, 1, "low_demand", "auction", 0, result)

        def compute_summary(self, rows):
            return [{"scenario": "low_demand", "strategy": "auction", "n_replications": 1}]

    class FailingAnalyzer:
        def __init__(self, **kwargs):
            pass

        def load_results(self, csv_file=None):
            pass

        def generate_all(self):
            raise RuntimeError("figure generation failed")

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "ExperimentRunner", FakeRunner)
    import analysis
    monkeypatch.setattr(analysis, "SimulationAnalyzer", FailingAnalyzer)
    monkeypatch.setattr(routes, "experiment_state", {"status": "idle", "run_rows": [], "progress_log": []})

    routes._run_experiment_async("", "", 1)

    conn = routes._get_db()
    stored = conn.execute("SELECT status, error FROM experiments WHERE id=1").fetchone()
    conn.close()
    assert stored["status"] == "error"
    assert "figure generation failed" in stored["error"]
    assert routes.experiment_state["status"] == "error"


def test_results_keeps_additional_pngs_without_duplicate_primary_figures(tmp_path, monkeypatch):
    figures_dir = tmp_path / "output" / "figures"
    figures_dir.mkdir(parents=True)
    for filename in PRIMARY_FIGURE_METADATA:
        (figures_dir / filename).touch()
    (figures_dir / "custom_plot.png").touch()

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    body = create_app().test_client().get("/results").get_data(as_text=True)

    assert body.count("custom_plot.png") == 2
    for filename in PRIMARY_FIGURE_METADATA:
        assert body.count(filename) == 2


def test_history_run_renders_primary_metadata_and_stored_result_content(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    conn = routes._get_db()
    conn.execute(
        """
        INSERT INTO experiments (
            id, run_at, scenario, strategy, replications, total_runs,
            rows_count, rows_json, summary_json, figures_json, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            7,
            "2026-08-03T12:00:00",
            "high",
            "auction",
            2,
            1,
            1,
            json.dumps([{"scenario": "high", "mean_pst": "4.5"}]),
            json.dumps([{"scenario": "high", "mean_mean_pst": "4.5"}]),
            json.dumps(["pst_comparison.png"]),
            "completed",
        ),
    )
    conn.commit()
    conn.close()

    response = create_app().test_client().get("/history/run/7")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Run #7 — 2026-08-03T12:00:00" in body
    assert 'data-figure="pst_comparison.png"' in body
    assert "Mean Parking Search Time" in body
    assert "Mean parking search time with 95% confidence intervals." in body
    assert "4.5" in body
    assert 'href="/history/run/7/download/experiment_results.csv"' in body
    assert 'href="/download/experiment_results.csv"' not in body


def test_history_renders_stored_status_and_error(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    conn = routes._get_db()
    conn.execute(
        """
        INSERT INTO experiments (
            id, run_at, scenario, strategy, replications, total_runs,
            rows_count, status, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (9, "2026-08-03T12:00:00", "high", "auction", 1, 1, 0, "running", None),
    )
    conn.execute(
        """
        INSERT INTO experiments (
            id, run_at, scenario, strategy, replications, total_runs,
            rows_count, status, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (10, "2026-08-03T12:01:00", "high", "auction", 1, 1, 0, "error", "analysis failed"),
    )
    conn.commit()
    conn.close()

    client = create_app().test_client()
    body = client.get("/history").get_data(as_text=True)
    assert "Stopped" in body
    assert "Completed" not in body
    assert "Error" in body

    detail_body = client.get("/history/run/10").get_data(as_text=True)
    assert "analysis failed" in detail_body


def test_completed_run_stores_run_local_outputs_and_history_downloads(tmp_path, monkeypatch):
    result = {
        "scenario": "low_demand",
        "strategy": "auction",
        "replication": 0,
        "total_arrivals": 1,
        "total_successful": 1,
        "total_failed": 0,
        "mean_pst": 1.0,
        "std_por": 0.1,
        "rsr": 100.0,
        "mean_utility": 0.5,
        "tfi": 0.0,
        "sumo_connected": False,
        "_timeseries": [{
            "scenario": "low_demand",
            "strategy": "auction",
            "replication": 0,
            "tick": 7,
            "por": 0.42,
        }],
    }

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        def run_batch(self, **kwargs):
            kwargs["progress_callback"](1, 1, "low_demand", "auction", 0, result)

        def compute_summary(self, rows):
            return [{"scenario": rows[0]["scenario"], "strategy": rows[0]["strategy"], "n_replications": 1}]

    class FakeAnalyzer:
        def __init__(self, figures_dir, **kwargs):
            self.figures_dir = figures_dir

        def load_results(self, csv_file=None):
            self.csv_file = csv_file

        def generate_all(self):
            os.makedirs(self.figures_dir, exist_ok=True)
            (os.path.join(self.figures_dir, "por_timeseries.png"))
            with open(os.path.join(self.figures_dir, "por_timeseries.png"), "wb") as file:
                file.write(b"png")

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "ExperimentRunner", FakeRunner)
    monkeypatch.setattr(routes, "_load_current_outputs", lambda: ("global.csv", [{"scenario": "stale"}], [{"scenario": "stale"}], []))
    import analysis
    monkeypatch.setattr(analysis, "SimulationAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(routes, "experiment_state", {"status": "idle", "run_rows": [], "progress_log": []})
    global_csv_dir = tmp_path / "output" / "csv"
    global_csv_dir.mkdir(parents=True)
    (global_csv_dir / "por_timeseries.csv").write_text(
        "scenario,strategy,replication,tick,por\n"
        "stale,random,9,99,0.01\n"
    )

    routes._run_experiment_async("", "", 1)

    conn = routes._get_db()
    stored = conn.execute("SELECT results_path, rows_json, summary_json, figures_json FROM experiments WHERE id=1").fetchone()
    conn.close()
    run_dir = tmp_path / "output" / "run_1"
    assert stored["results_path"] == str(run_dir / "experiment_results.csv")
    assert json.loads(stored["rows_json"])[0]["scenario"] == "low_demand"
    assert json.loads(stored["summary_json"])[0]["scenario"] == "low_demand"
    assert json.loads(stored["figures_json"]) == ["run_1/por_timeseries.png"]
    assert (run_dir / "por_timeseries.csv").read_text() == (
        "scenario,strategy,replication,tick,por\n"
        "low_demand,auction,0,7,0.42\n"
    )
    (global_csv_dir / "por_timeseries.csv").write_text("scenario,strategy,replication,tick,por\nchanged,random,8,88,0.99\n")

    client = create_app().test_client()
    history_body = client.get("/history/run/1").get_data(as_text=True)
    assert "low_demand" in history_body
    assert "stale" not in history_body
    download = client.get("/history/run/1/download/experiment_results.csv")
    assert download.status_code == 200
    assert b"low_demand" in download.data
    assert b"stale" not in download.data
    assert b"changed" not in client.get("/history/run/1/download/por_timeseries.csv").data
    assert b"low_demand" in client.get("/history/run/1/download/por_timeseries.csv").data
    assert client.get("/history/run/1/download/../experiment_results.csv").status_code == 404


def test_results_preserves_csv_result_and_summary_content(tmp_path, monkeypatch):
    csv_dir = tmp_path / "output" / "csv"
    csv_dir.mkdir(parents=True)
    with (csv_dir / "experiment_results.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["scenario", "mean_pst"])
        writer.writeheader()
        writer.writerow({"scenario": "low", "mean_pst": "3.25"})
    with (csv_dir / "summary_statistics.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["scenario", "mean_mean_pst"])
        writer.writeheader()
        writer.writerow({"scenario": "low", "mean_mean_pst": "3.25"})

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    body = create_app().test_client().get("/results").get_data(as_text=True)

    assert "Raw Results (1 runs)" in body
    assert "Summary Statistics" in body
    assert body.count("3.25") >= 2


def test_results_uses_traffic_flow_impact_headings_for_tfi_columns(tmp_path, monkeypatch):
    csv_dir = tmp_path / "output" / "csv"
    csv_dir.mkdir(parents=True)
    with (csv_dir / "experiment_results.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["tfi", "mean_tfi", "std_tfi"])
        writer.writeheader()
        writer.writerow({"tfi": "1.2", "mean_tfi": "1.2", "std_tfi": "0.1"})
    with (csv_dir / "summary_statistics.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["tfi", "mean_tfi", "std_tfi"])
        writer.writeheader()
        writer.writerow({"tfi": "1.2", "mean_tfi": "1.2", "std_tfi": "0.1"})

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    body = create_app().test_client().get("/results").get_data(as_text=True)

    expected_headings = (
        "Traffic Flow Impact (TFI)",
        "Mean Traffic Flow Impact (TFI)",
        "Standard Deviation of Traffic Flow Impact (TFI)",
    )
    tables = re.findall(r"<table class=\"tooltip-table\">(.*?)</table>", body, re.S)
    assert len(tables) == 2
    for table in tables:
        headings = re.findall(r"<th>\s*(.*?)\s*<span", table, re.S)
        assert headings == list(expected_headings)
        assert "Tfi" not in table


def test_figure_serves_nested_run_file_but_rejects_traversal(tmp_path, monkeypatch):
    figures_dir = tmp_path / "output" / "figures"
    run_dir = figures_dir / "run_7"
    run_dir.mkdir(parents=True)
    (run_dir / "pst_comparison.png").write_bytes(b"png")
    (tmp_path / "output" / "secret.png").write_bytes(b"secret")
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    client = create_app().test_client()

    nested = client.get("/figure/run_7/pst_comparison.png")
    traversal = client.get("/figure/%2e%2e/secret.png")

    assert nested.status_code == 200
    assert nested.data == b"png"
    assert traversal.status_code == 404


def test_history_download_rejects_run_path_outside_output_root(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "experiment_results.csv").write_text("scenario\noutside\n")

    conn = routes._get_db()
    conn.execute(
        "INSERT INTO experiments (id, run_at, results_path, status) VALUES (?, ?, ?, ?)",
        (11, "2026-08-03T12:00:00", str(outside_dir / "experiment_results.csv"), "completed"),
    )
    conn.commit()
    conn.close()

    response = create_app().test_client().get(
        "/history/run/11/download/experiment_results.csv"
    )
    assert response.status_code == 404


def test_write_por_timeseries_to_run_output_uses_current_rows(tmp_path):
    run_dir = tmp_path / "output" / "run_3"
    rows = [{
        "scenario": "high_demand",
        "strategy": "greedy",
        "replication": 2,
        "tick": 3,
        "por": 0.8,
    }]

    routes._write_por_timeseries(str(run_dir), rows)
    assert (run_dir / "por_timeseries.csv").read_text() == (
        "scenario,strategy,replication,tick,por\n"
        "high_demand,greedy,2,3,0.8\n"
    )


def test_snapshot_run_rows_copies_rows_under_experiment_lock(monkeypatch):
    rows = [{"scenario": "current"}]
    monkeypatch.setattr(routes, "experiment_state", {"run_rows": rows})

    snapshot = routes._snapshot_run_rows()
    rows.append({"scenario": "later"})

    assert snapshot == [{"scenario": "current"}]


def test_current_results_keep_global_download_links(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))

    body = create_app().test_client().get("/results").get_data(as_text=True)

    assert 'href="/download/experiment_results.csv"' in body


def test_new_async_run_discards_rows_from_previous_run(tmp_path, monkeypatch):
    result = {
        "scenario": "low_demand",
        "strategy": "auction",
        "replication": 0,
        "mean_pst": 1.0,
        "rsr": 2.0,
    }

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        def run_batch(self, **kwargs):
            kwargs["progress_callback"](1, 1, "low_demand", "auction", 0, result)

    class FakeAnalyzer:
        def __init__(self, **kwargs):
            pass

        def load_results(self, csv_file=None):
            pass

        def generate_all(self):
            pass

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "ExperimentRunner", FakeRunner)
    monkeypatch.setattr(routes, "_create_experiment_record", lambda *args: 1)
    monkeypatch.setattr(
        routes,
        "_load_current_outputs",
        lambda: ("results.csv", [result], [], []),
    )
    import analysis
    monkeypatch.setattr(analysis, "SimulationAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(
        routes,
        "experiment_state",
        {"status": "idle", "run_rows": [{"scenario": "old"}], "progress_log": []},
    )

    routes._run_experiment_async("", "", 1)

    assert routes.experiment_state["run_rows"] == [result]


@pytest.mark.parametrize("status", ["completed", "running"])
def test_results_polling_markup_reflects_experiment_status(tmp_path, monkeypatch, status):
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(
        routes,
        "experiment_state",
        {"status": status, "progress_log": [], "run_rows": []},
    )

    body = create_app().test_client().get("/results").get_data(as_text=True)

    poll_script = "setTimeout(function checkCompletion()"
    if status == "completed":
        assert poll_script not in body
    else:
        assert poll_script in body


def test_visualization_discovers_recorded_run_metadata(tmp_path, monkeypatch):
    frames_dir = tmp_path / "output" / "frames"
    frames_dir.mkdir(parents=True)
    metadata = {
        "scenario": "high_demand",
        "strategy": "auction",
        "total_frames": 12,
    }
    (frames_dir / "run_17_meta.json").write_text(json.dumps(metadata))
    (frames_dir / "run_17_frames.json").write_text(json.dumps([{"tick": 0}]))
    monkeypatch.setattr(routes, "VIZ_FRAMES_DIR", str(frames_dir))

    client = create_app().test_client()
    visualize_body = client.get("/visualize").get_data(as_text=True)
    discovered_runs = client.get("/api/viz/runs").get_json()

    assert "run_17" in visualize_body
    assert "12 frames" in visualize_body
    assert discovered_runs == [{"run_id": "run_17", "meta": metadata}]


def test_record_dashboard_experiment_saves_real_metadata_and_route_files(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(routes, "VIZ_FRAMES_DIR", str(tmp_path / "output" / "frames"))

    run_id = routes._record_dashboard_experiment(
        scenario="low_demand",
        strategy="greedy",
        simulation_type="mesa",
        city=None,
        experiment_run_id=23,
        config={
            "grid": {"width": 20, "height": 20, "cell_size_meters": 10},
            "parking": {"num_spots": 20, "num_zones": 4, "price_range": [1, 10]},
            "demand": {
                "arrival_rate_lambda": 0,
                "parking_duration_mean_ticks": 8,
                "parking_duration_std_ticks": 2,
                "search_radius_cells": 30,
                "max_search_duration_ticks": 6,
            },
            "simulation": {"total_ticks": 2, "warmup_ticks": 0, "random_seed": 42},
            "strategy": "auction",
        },
    )

    metadata_path = tmp_path / "output" / "frames" / f"{run_id}_meta.json"
    frames_path = tmp_path / "output" / "frames" / f"{run_id}_frames.json"
    assert run_id.startswith("run_dashboard_23")
    assert metadata_path.is_file()
    assert frames_path.is_file()
    metadata = json.loads(metadata_path.read_text())
    assert metadata["scenario"] == "low_demand"
    assert metadata["strategy"] == "greedy"
    assert metadata["dashboard_experiment_id"] == 23
    assert metadata["visualization_run_id"] == run_id
    assert json.loads(frames_path.read_text())
    client = create_app().test_client()
    assert run_id in client.get("/visualize").get_data(as_text=True)
    assert client.get("/api/viz/runs").get_json()[0]["meta"] == metadata


def test_frame_recorder_ids_do_not_collide_in_same_second(tmp_path, monkeypatch):
    from model import ParkingModel
    from recorder import FrameRecorder

    config = {
        "grid": {"width": 20, "height": 20, "cell_size_meters": 10},
        "parking": {"num_spots": 20, "num_zones": 4, "price_range": [1, 10]},
        "demand": {
            "arrival_rate_lambda": 0,
            "parking_duration_mean_ticks": 8,
            "parking_duration_std_ticks": 2,
            "search_radius_cells": 30,
            "max_search_duration_ticks": 6,
        },
        "simulation": {"total_ticks": 1, "warmup_ticks": 0, "random_seed": 42},
        "strategy": "auction",
    }
    monkeypatch.setattr("recorder.time.time", lambda: 1234)
    first = FrameRecorder(ParkingModel(config_dict=config, strategy="auction"))
    second = FrameRecorder(ParkingModel(config_dict=config, strategy="auction"))

    first_id, _, _ = first.save(str(tmp_path))
    second_id, _, _ = second.save(str(tmp_path))

    assert first_id != second_id
    assert (tmp_path / f"{first_id}_meta.json").is_file()
    assert (tmp_path / f"{second_id}_meta.json").is_file()


def test_frame_recorder_ids_are_unique_when_saves_race(tmp_path, monkeypatch):
    from model import ParkingModel
    from recorder import FrameRecorder

    config = {
        "grid": {"width": 8, "height": 8, "cell_size_meters": 10},
        "parking": {"num_spots": 4, "num_zones": 2, "price_range": [1, 10]},
        "demand": {"arrival_rate_lambda": 0, "parking_duration_mean_ticks": 8,
                   "parking_duration_std_ticks": 2, "search_radius_cells": 30,
                   "max_search_duration_ticks": 6},
        "simulation": {"total_ticks": 1, "warmup_ticks": 0, "random_seed": 42},
        "strategy": "auction",
    }
    monkeypatch.setattr("recorder.time.time", lambda: 1234)

    def save_one():
        recorder = FrameRecorder(ParkingModel(config_dict=config, strategy="auction"))
        return recorder.save(str(tmp_path))[0]

    with ThreadPoolExecutor(max_workers=2) as executor:
        run_ids = list(executor.map(lambda _: save_one(), range(2)))

    assert len(set(run_ids)) == 2
    assert all((tmp_path / f"{run_id}_meta.json").is_file() for run_id in run_ids)
    assert all((tmp_path / f"{run_id}_frames.json").is_file() for run_id in run_ids)


def test_viz_record_saves_and_returns_discoverable_run(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "VIZ_FRAMES_DIR", str(tmp_path / "frames"))
    response = create_app().test_client().post(
        "/api/viz/record",
        json={
            "strategy": "greedy",
            "total_ticks": 2,
            "arrival_rate": 0,
            "grid_width": 8,
            "grid_height": 8,
            "num_spots": 4,
            "num_zones": 2,
            "warmup_ticks": 0,
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["run_id"] != "unknown"
    run_id = payload["run_id"]
    metadata = create_app().test_client().get(f"/api/viz/meta/{run_id}").get_json()
    frames = create_app().test_client().get(f"/api/viz/frames/{run_id}").get_json()
    runs = create_app().test_client().get("/api/viz/runs").get_json()
    assert metadata["visualization_run_id"] == run_id
    assert metadata["strategy"] == "greedy"
    assert frames
    assert any(run["run_id"] == run_id for run in runs)


def test_viz_record_uses_run_id_from_simulation_save(tmp_path, monkeypatch):
    import model
    import recorder

    save_calls = []

    class FakeRecorder:
        def __init__(self, model, city_config=None, record_interval=1):
            self.frames = [{"t": 1}]

        def save(self, output_dir="output/frames"):
            save_calls.append(output_dir)
            return "run_from_simulation", "meta.json", "frames.json"

    class FakeModel:
        def __init__(self, config_dict, strategy):
            self.recorder = None

        def run_simulation(self, output_dir="output/frames"):
            self._frame_run_id, _, _ = self.recorder.save(output_dir)
            return {"frame_run_id": self._frame_run_id}

    monkeypatch.setattr(routes, "VIZ_FRAMES_DIR", str(tmp_path / "frames"))
    monkeypatch.setattr(model, "ParkingModel", FakeModel)
    monkeypatch.setattr(recorder, "FrameRecorder", FakeRecorder)

    response = create_app().test_client().post(
        "/api/viz/record",
        json={"total_ticks": 1},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "completed",
        "frames": 1,
        "run_id": "run_from_simulation",
    }
    assert save_calls == [str(tmp_path / "frames")]


def test_results_error_state_does_not_emit_polling_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(
        routes,
        "experiment_state",
        {"status": "error", "error_message": "simulation failed", "progress_log": []},
    )

    body = create_app().test_client().get("/results").get_data(as_text=True)

    assert "setTimeout(function checkCompletion()" not in body


def test_reset_clears_run_identifiers_with_consistent_state(monkeypatch):
    monkeypatch.setattr(routes, "experiment_state", {"status": "completed", "run_id": 8})

    response = create_app().test_client().post("/reset")

    assert response.status_code == 302
    assert routes.experiment_state["run_id"] is None
    assert routes.experiment_state["visualization_run_id"] is None


def test_recording_failure_keeps_completed_experiment_results(tmp_path, monkeypatch):
    result = {
        "scenario": "low_demand", "strategy": "auction", "replication": 0,
        "total_arrivals": 1, "total_successful": 1, "total_failed": 0,
        "mean_pst": 1.0, "std_por": 0.1, "rsr": 100.0,
        "mean_utility": 0.5, "tfi": 0.0, "sumo_connected": False, "_timeseries": [],
    }

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        def run_batch(self, **kwargs):
            kwargs["progress_callback"](1, 1, "low_demand", "auction", 0, result)

        def compute_summary(self, rows):
            return [{"scenario": "low_demand", "strategy": "auction", "n_replications": 1}]

    class FakeAnalyzer:
        def __init__(self, **kwargs):
            pass

        def load_results(self, csv_file=None):
            pass

        def generate_all(self):
            pass

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "ExperimentRunner", FakeRunner)
    monkeypatch.setattr(routes, "_record_dashboard_experiment", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("recorder unavailable")))
    import analysis
    monkeypatch.setattr(analysis, "SimulationAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(routes, "experiment_state", {
        "status": "idle", "run_rows": [], "progress_log": [],
        "visualization_run_id": "run_from_previous_experiment",
    })

    routes._run_experiment_async("", "", 1)

    conn = routes._get_db()
    stored = conn.execute("SELECT status, results_path, progress_json FROM experiments WHERE id=1").fetchone()
    conn.close()
    assert stored["status"] == "completed"
    assert os.path.isfile(stored["results_path"])
    assert "Visualization recording failed: recorder unavailable" in stored["progress_json"]
    assert json.loads(stored["progress_json"])["visualization_run_id"] is None
    assert routes.experiment_state["visualization_run_id"] is None


def test_async_success_persists_visualization_run_and_route_discovery(tmp_path, monkeypatch):
    result = {
        "scenario": "low_demand", "strategy": "auction", "replication": 0,
        "total_arrivals": 0, "total_successful": 0, "total_failed": 0,
        "mean_pst": 0, "std_por": 0, "rsr": 0,
        "mean_utility": 0, "tfi": 0, "sumo_connected": False, "_timeseries": [],
    }

    class FakeRunner:
        base_config = {
            "grid": {"width": 20, "height": 20, "cell_size_meters": 10},
            "parking": {"num_spots": 20, "num_zones": 4, "price_range": [1, 10]},
            "demand": {
                "arrival_rate_lambda": 0,
                "parking_duration_mean_ticks": 8,
                "parking_duration_std_ticks": 2,
                "search_radius_cells": 30,
                "max_search_duration_ticks": 6,
            },
            "simulation": {"total_ticks": 1, "warmup_ticks": 0, "random_seed": 42},
            "strategy": "auction",
        }
        scenarios_config = {"scenarios": {}}

        def __init__(self, **kwargs):
            pass

        def run_batch(self, **kwargs):
            kwargs["progress_callback"](1, 1, "low_demand", "auction", 0, result)

        def compute_summary(self, rows):
            return [{"scenario": "low_demand", "strategy": "auction", "n_replications": 1}]

    class FakeAnalyzer:
        def __init__(self, **kwargs):
            pass

        def load_results(self, csv_file=None):
            pass

        def generate_all(self):
            pass

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "ExperimentRunner", FakeRunner)
    monkeypatch.setattr(routes, "experiment_state", {"status": "idle", "run_rows": [], "progress_log": []})
    import analysis
    monkeypatch.setattr(analysis, "SimulationAnalyzer", FakeAnalyzer)

    monkeypatch.setattr(routes, "VIZ_FRAMES_DIR", str(tmp_path / "output" / "frames"))
    routes._run_experiment_async("low_demand", "auction", 1)

    conn = routes._get_db()
    stored = conn.execute("SELECT progress_json FROM experiments WHERE id=1").fetchone()
    conn.close()
    progress = json.loads(stored["progress_json"])
    visualization_run_id = progress["visualization_run_id"]
    assert visualization_run_id
    assert routes.experiment_state["visualization_run_id"] == visualization_run_id
    assert create_app().test_client().get("/api/viz/runs").get_json()[0]["run_id"] == visualization_run_id


def test_app_startup_recovers_persisted_running_runs_as_stopped(tmp_path, monkeypatch):
    db_path = tmp_path / "experiments.sqlite"
    monkeypatch.setattr(routes, "DB_PATH", str(db_path))
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))

    conn = routes._get_db()
    conn.execute(
        "INSERT INTO experiments (id, run_at, scenario, strategy, status) VALUES (?, ?, ?, ?, ?)",
        (41, "2026-08-04T08:00:00", "high_demand", "auction", "running"),
    )
    conn.commit()
    conn.close()

    create_app()

    conn = routes._get_db()
    stored = conn.execute("SELECT status, error FROM experiments WHERE id=41").fetchone()
    conn.close()
    assert stored["status"] == "stopped"
    assert stored["error"]
    recovery_message = stored["error"].lower()
    assert "stopped" in recovery_message or "interrupted" in recovery_message


def test_history_delete_removes_only_run_local_artifacts_and_record(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    output_dir = tmp_path / "output"
    run_dir = output_dir / "run_7"
    figure_dir = output_dir / "figures" / "run_7"
    unrelated_dir = output_dir / "run_8"
    run_dir.mkdir(parents=True)
    figure_dir.mkdir(parents=True)
    unrelated_dir.mkdir(parents=True)
    (run_dir / "experiment_results.csv").write_text("scenario\nrun-7\n")
    (figure_dir / "pst_comparison.png").write_bytes(b"run-7")
    (unrelated_dir / "experiment_results.csv").write_text("scenario\nrun-8\n")

    conn = routes._get_db()
    conn.execute(
        "INSERT INTO experiments (id, run_at, results_path, figures_json, status) VALUES (?, ?, ?, ?, ?)",
        (7, "2026-08-04T08:00:00", str(run_dir / "experiment_results.csv"), json.dumps(["run_7/pst_comparison.png"]), "completed"),
    )
    conn.commit()
    conn.close()

    response = create_app().test_client().post("/history/run/7/delete")

    assert response.status_code == 302
    assert not run_dir.exists()
    assert not figure_dir.exists()
    assert unrelated_dir.exists()
    conn = routes._get_db()
    assert not conn.execute("SELECT 1 FROM experiments WHERE id=7").fetchone()
    conn.close()


def test_history_delete_rejects_outside_results_path_without_deleting_it(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "experiment_results.csv"
    outside_file.write_text("scenario\noutside\n")

    conn = routes._get_db()
    conn.execute(
        "INSERT INTO experiments (id, run_at, results_path, status) VALUES (?, ?, ?, ?)",
        (8, "2026-08-04T08:00:00", str(outside_file), "completed"),
    )
    conn.commit()
    conn.close()

    response = create_app().test_client().post("/history/run/8/delete")

    assert response.status_code == 404
    assert outside_file.read_text() == "scenario\noutside\n"
    conn = routes._get_db()
    assert conn.execute("SELECT 1 FROM experiments WHERE id=8").fetchone()
    conn.close()


@pytest.mark.parametrize("unsafe_path", [
    "output/csv/experiment_results.csv",
    "output/figures/run_9/pst_comparison.png",
    "output/run_8/experiment_results.csv",
])
def test_history_delete_rejects_noncanonical_run_directory(tmp_path, monkeypatch, unsafe_path):
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    unsafe_file = tmp_path / unsafe_path
    unsafe_file.parent.mkdir(parents=True)
    unsafe_file.write_text("must remain\n")

    conn = routes._get_db()
    conn.execute(
        "INSERT INTO experiments (id, run_at, results_path, status) VALUES (?, ?, ?, ?)",
        (9, "2026-08-04T08:00:00", str(unsafe_file), "completed"),
    )
    conn.commit()
    conn.close()

    response = create_app().test_client().post("/history/run/9/delete")

    assert response.status_code == 404
    assert unsafe_file.read_text() == "must remain\n"
    conn = routes._get_db()
    assert conn.execute("SELECT 1 FROM experiments WHERE id=9").fetchone()
    conn.close()


def _make_directory_link(link, target):
    """Point `link` at directory `target`; fall back to a junction where creating
    a symlink needs elevation (Windows without Developer Mode). Returns the kind
    of link created, since junctions are not reported by is_symlink()."""
    try:
        link.symlink_to(target, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        if os.name != "nt":
            raise
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
        return "junction"


def test_history_delete_rejects_symlinked_run_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    output_dir = tmp_path / "output"
    target_dir = output_dir / "real_run_12"
    run_path = output_dir / "run_12"
    target_dir.mkdir(parents=True)
    (target_dir / "experiment_results.csv").write_text("scenario\ntarget\n")
    link_kind = _make_directory_link(run_path, target_dir)

    conn = routes._get_db()
    conn.execute(
        "INSERT INTO experiments (id, run_at, results_path, status) VALUES (?, ?, ?, ?)",
        (12, "2026-08-04T08:00:00", str(run_path / "experiment_results.csv"), "completed"),
    )
    conn.commit()
    conn.close()

    response = create_app().test_client().post("/history/run/12/delete")

    assert response.status_code == 404
    assert run_path.exists()
    if link_kind == "symlink":
        assert run_path.is_symlink()
    assert (target_dir / "experiment_results.csv").read_text() == "scenario\ntarget\n"
    conn = routes._get_db()
    assert conn.execute("SELECT 1 FROM experiments WHERE id=12").fetchone()
    conn.close()


def test_history_deletes_stopped_run_that_never_wrote_artifacts(tmp_path, monkeypatch):
    """A run interrupted before it wrote anything must still be clearable."""
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    conn = routes._get_db()
    conn.execute(
        "INSERT INTO experiments (id, run_at, status, results_path) VALUES (?, ?, 'stopped', NULL)",
        (12, "2026-08-30T08:00:00"),
    )
    conn.commit()
    conn.close()

    response = create_app().test_client().post("/history/run/12/delete")

    assert response.status_code == 302
    conn = routes._get_db()
    assert conn.execute("SELECT 1 FROM experiments WHERE id=12").fetchone() is None
    conn.close()


def test_history_deletes_error_run_together_with_its_leftover_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    run_dir = tmp_path / "output" / "run_13"
    run_dir.mkdir(parents=True)
    (run_dir / "partial.txt").write_text("written before the failure\n")
    conn = routes._get_db()
    conn.execute(
        "INSERT INTO experiments (id, run_at, status, results_path, error) VALUES (?, ?, 'error', NULL, ?)",
        (13, "2026-08-30T08:00:00", "Could not prepare the SUMO network"),
    )
    conn.commit()
    conn.close()

    response = create_app().test_client().post("/history/run/13/delete")

    assert response.status_code == 302
    assert not run_dir.exists()
    conn = routes._get_db()
    assert conn.execute("SELECT 1 FROM experiments WHERE id=13").fetchone() is None
    conn.close()


def test_history_deletes_record_when_run_directory_was_removed_outside_the_app(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    stored_path = tmp_path / "output" / "run_14" / "experiment_results.csv"
    conn = routes._get_db()
    conn.execute(
        "INSERT INTO experiments (id, run_at, status, results_path) VALUES (?, ?, 'completed', ?)",
        (14, "2026-08-30T08:00:00", str(stored_path)),
    )
    conn.commit()
    conn.close()

    response = create_app().test_client().post("/history/run/14/delete")

    assert response.status_code == 302
    conn = routes._get_db()
    assert conn.execute("SELECT 1 FROM experiments WHERE id=14").fetchone() is None
    conn.close()


def test_history_delete_returns_404_for_unknown_run(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))

    response = create_app().test_client().post("/history/run/999/delete")

    assert response.status_code == 404


def test_history_delete_removes_visualization_frames_of_that_run_only(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    frames_dir = tmp_path / "output" / "frames"
    frames_dir.mkdir(parents=True)
    kept = [
        "run_dashboard_70_meta.json",   # id prefix collision
        "run_dashboard_8_meta.json",
        "run_dashboard_7_notes.txt",
    ]
    for name in ["run_dashboard_7_meta.json", "run_dashboard_7_frames.json",
                 "run_dashboard_7_2_meta.json"] + kept:
        (frames_dir / name).write_text("{}")
    conn = routes._get_db()
    conn.execute(
        "INSERT INTO experiments (id, run_at, status) VALUES (?, ?, 'stopped')",
        (7, "2026-08-30T08:00:00"),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(routes, "VIZ_FRAMES_DIR", str(frames_dir))

    response = create_app().test_client().post("/history/run/7/delete")

    assert response.status_code == 302
    remaining = sorted(name for name in os.listdir(frames_dir))
    assert remaining == sorted(kept)


@pytest.mark.parametrize(
    "status",
    [
        "running",
        "completed",
        "error",
        "stopped",
    ],
)
def test_run_renders_state_specific_content(tmp_path, monkeypatch, status):
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(
        routes,
        "_load_run_config",
        lambda: {"simulation_types": {}, "osm_cities": {}},
    )
    monkeypatch.setattr(
        routes,
        "experiment_state",
        {
            "status": status,
            "scenario": "high_demand",
            "strategy": "auction",
            "replications": 1,
            "total_runs": 4,
            "completed_runs": 2,
            "progress_log": ["replication complete"],
            "error_message": "simulation failed" if status == "error" else None,
        },
    )

    response = create_app().test_client().get("/run")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    if status == "running":
        assert "RUNNING" in body
        assert "replication complete" in body
        assert 'name="scenario"' not in body
    elif status == "error":
        assert "simulation failed" in body
        assert 'name="scenario"' in body
        assert 'class="btn btn-primary">Launch Experiment</button>' in body
    elif status == "completed":
        assert "Previous Results Available" in body
        assert 'href="/results"' in body
        assert 'name="scenario"' in body
        assert 'class="btn btn-primary">Launch Experiment</button>' in body
    else:
        assert "STOPPED" in body
        assert 'name="scenario"' in body
        assert 'class="btn btn-primary">Launch Experiment</button>' in body

    assert 'id="progress-fill" style="width: 100%"' in body if status == "completed" else 'id="progress-fill" style="width: 50%"' in body
    assert 'id="run-summary"' in body
    assert 'id="status-badge"' in body
    if status != "running":
        assert "setTimeout(pollProgress" not in body


@pytest.mark.parametrize("status", ["completed", "error", "stopped"])
def test_progress_sse_terminates_after_terminal_status(monkeypatch, status):
    monkeypatch.setattr(
        routes,
        "experiment_state",
        {"status": status, "completed_runs": 2, "total_runs": 4, "progress_log": []},
    )

    stream = create_app().test_client().get("/progress").response

    assert next(stream).startswith(b"data: ")
    with pytest.raises(StopIteration):
        next(stream)


def test_run_progress_panel_has_stable_ids_and_state_aware_polling(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(
        routes,
        "_load_run_config",
        lambda: {"simulation_types": {}, "osm_cities": {}},
    )
    monkeypatch.setattr(
        routes,
        "experiment_state",
        {
            "status": "running",
            "scenario": "high_demand",
            "strategy": "auction",
            "replications": 1,
            "total_runs": 4,
            "completed_runs": 2,
            "progress_log": ["replication complete"],
            "error_message": None,
        },
    )

    body = create_app().test_client().get("/run").get_data(as_text=True)

    for element_id in ("status-badge", "run-summary", "progress-fill", "progress-text", "progress-log"):
        assert f'id="{element_id}"' in body
    assert "fetch('/progress.json')" in body
    assert "state.status === 'completed'" in body
    assert "state.status === 'error'" in body
    assert "state.status === 'stopped'" in body
    assert "window.location.href = '/results'" not in body


def test_near_sequential_launch_posts_create_only_one_worker(monkeypatch):
    started = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started.append(self)

    monkeypatch.setattr(routes.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        routes,
        "experiment_state",
        {"status": "idle", "run_rows": [], "progress_log": []},
    )
    client = create_app().test_client()

    first = client.post("/run", data={"replications": "1"})
    second = client.post("/run", data={"replications": "1"})

    assert first.status_code == 302
    assert second.status_code == 302
    assert len(started) == 1
    assert routes.experiment_state["status"] == "running"


@pytest.mark.parametrize("status", ["completed", "error", "stopped"])
def test_terminal_run_progress_uses_completed_runs_ratio(tmp_path, monkeypatch, status):
    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(
        routes,
        "_load_run_config",
        lambda: {"simulation_types": {}, "osm_cities": {}},
    )
    monkeypatch.setattr(
        routes,
        "experiment_state",
        {
            "status": status,
            "scenario": "high_demand",
            "strategy": "auction",
            "replications": 1,
            "total_runs": 4,
            "completed_runs": 1,
            "progress_log": [],
            "error_message": "simulation failed" if status == "error" else None,
        },
    )

    body = create_app().test_client().get("/run").get_data(as_text=True)

    expected_width = 100 if status == "completed" else 25
    assert f'id="progress-fill" style="width: {expected_width}%"' in body

    routes.experiment_state["status"] = "running"
    body = create_app().test_client().get("/run").get_data(as_text=True)
    assert "fill.style.width = terminalProgressPercent(state) + '%';" in body


def test_run_csv_writes_exactly_the_result_columns(tmp_path, monkeypatch):
    from experiments import RESULT_COLUMNS

    row = {key: 1 for key in RESULT_COLUMNS}
    row.update({"scenario": "low_demand", "strategy": "auction", "_timeseries": []})

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        def run_batch(self, **kwargs):
            kwargs["progress_callback"](1, 1, "low_demand", "auction", 0, dict(row))

        def compute_summary(self, rows):
            return []

    class FakeAnalyzer:
        def __init__(self, figures_dir, **kwargs):
            pass

        def load_results(self, csv_file=None):
            pass

        def generate_all(self):
            pass

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "ExperimentRunner", FakeRunner)
    monkeypatch.setattr(routes, "_load_current_outputs", lambda: ("global.csv", [], [], []))
    monkeypatch.setattr(
        routes, "experiment_state", {"status": "idle", "run_rows": [], "progress_log": []}
    )
    import analysis
    monkeypatch.setattr(analysis, "SimulationAnalyzer", FakeAnalyzer)

    routes._run_experiment_async("low_demand", "auction", 1)

    written = (tmp_path / "output" / "run_1" / "experiment_results.csv").read_text()
    header = written.splitlines()[0].split(",")
    assert header == RESULT_COLUMNS


def test_every_result_column_has_a_tooltip():
    from experiments import RESULT_COLUMNS

    missing = [key for key in RESULT_COLUMNS if key not in routes.RESULTS_TOOLTIPS]
    assert missing == []


def test_run_form_forwards_refresh_osm_only_for_city_runs(tmp_path, monkeypatch):
    started = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            self.args = args

        def start(self):
            started.append(self.args)

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(routes.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        routes,
        "experiment_state",
        {"status": "idle", "run_rows": [], "progress_log": []},
    )
    client = create_app().test_client()

    client.post(
        "/run",
        data={
            "replications": "1",
            "simulation_type": "osm_city",
            "city": "penang",
            "refresh_osm": "1",
        },
    )
    assert started[0] == ("", "auction", 1, "osm_city", "penang", True)

    started.clear()
    routes.experiment_state["status"] = "idle"
    client.post(
        "/run",
        data={"replications": "1", "simulation_type": "mesa", "refresh_osm": "1"},
    )
    assert started[0] == ("", "auction", 1, "mesa", None, False)


def test_async_run_passes_refresh_osm_to_runner_batch(tmp_path, monkeypatch):
    result = {
        "scenario": "low_demand",
        "strategy": "auction",
        "replication": 0,
        "total_arrivals": 1,
        "total_successful": 1,
        "total_failed": 0,
        "mean_pst": 1.0,
        "std_por": 0.1,
        "rsr": 100.0,
        "mean_utility": 0.5,
        "tfi": 0.0,
        "sumo_connected": True,
        "_timeseries": [],
    }
    batches = []

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        def run_batch(self, **kwargs):
            batches.append(kwargs)
            kwargs["progress_callback"](1, 1, "low_demand", "auction", 0, result)

        def compute_summary(self, rows):
            return [{"scenario": "low_demand", "strategy": "auction", "n_replications": 1}]

    class FakeAnalyzer:
        def __init__(self, figures_dir, **kwargs):
            self.figures_dir = figures_dir

        def load_results(self, csv_file=None):
            pass

        def generate_all(self):
            pass

    monkeypatch.setattr(routes, "SIMULATION_DIR", str(tmp_path))
    monkeypatch.setattr(routes, "DB_PATH", str(tmp_path / "experiments.sqlite"))
    monkeypatch.setattr(routes, "ExperimentRunner", FakeRunner)
    monkeypatch.setattr(
        routes,
        "_load_current_outputs",
        lambda: ("global.csv", [], [], []),
    )
    monkeypatch.setattr(
        routes,
        "experiment_state",
        {"status": "idle", "run_rows": [], "progress_log": []},
    )
    import analysis
    monkeypatch.setattr(analysis, "SimulationAnalyzer", FakeAnalyzer)

    routes._run_experiment_async(
        "low_demand", "auction", 1, simulation_type="osm_city", city="penang", refresh_osm=True
    )
    routes._run_experiment_async(
        "low_demand", "auction", 1, simulation_type="mesa", refresh_osm=True
    )

    assert [batch["refresh_osm"] for batch in batches] == [True, False]
    assert [batch["city"] for batch in batches] == ["penang", None]
