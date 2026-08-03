"""Regression tests for the results dashboard figure metadata."""
import csv
import json
import os
import re
import sys

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
    assert "Running" in body
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
