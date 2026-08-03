"""Regression tests for experiment analysis output and confidence intervals."""
import os
import sys

import numpy as np
import pandas as pd
import analysis

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import SimulationAnalyzer


def _write_analysis_inputs(tmp_path):
    results = pd.DataFrame([
        {"scenario": "low_demand", "strategy": "auction", "mean_pst": 4.0, "rsr": 90.0, "mean_utility": 0.7, "tfi": 1.2},
        {"scenario": "low_demand", "strategy": "auction", "mean_pst": 6.0, "rsr": 80.0, "mean_utility": 0.5, "tfi": 1.8},
        {"scenario": "high_demand", "strategy": "fcfs", "mean_pst": 10.0, "rsr": 60.0, "mean_utility": 0.2, "tfi": 3.0},
        {"scenario": "high_demand", "strategy": "fcfs", "mean_pst": 14.0, "rsr": 50.0, "mean_utility": 0.1, "tfi": 4.0},
    ])
    results.to_csv(tmp_path / "experiment_results.csv", index=False)

    por = pd.DataFrame([
        {"scenario": scenario, "strategy": strategy, "replication": rep, "tick": tick, "por": value}
        for scenario, strategy, rep, value in [
            ("low_demand", "auction", 0, 0.2),
            ("medium_demand", "fcfs", 0, 0.4),
            ("high_demand", "random", 0, 0.6),
            ("peak_demand", "greedy", 0, 0.8),
        ]
        for tick in (0, 1)
    ])
    por.to_csv(tmp_path / "por_timeseries.csv", index=False)


def test_grouped_stats_uses_positive_student_t_interval_for_two_observations(tmp_path):
    _write_analysis_inputs(tmp_path)
    analyzer = SimulationAnalyzer(results_dir=str(tmp_path))
    analyzer.load_results()

    stats = analyzer._grouped_stats("mean_pst")

    low_demand = stats[
        (stats["scenario"] == "low_demand")
        & (stats["strategy"] == "auction")
    ].iloc[0]
    assert low_demand["count"] == 2
    assert np.isfinite(low_demand["ci95"])
    assert low_demand["ci95"] > 0


def test_grouped_stats_uses_zero_interval_for_one_observation(tmp_path):
    _write_analysis_inputs(tmp_path)
    analyzer = SimulationAnalyzer(results_dir=str(tmp_path))
    analyzer.load_results()
    analyzer.results_df = analyzer.results_df.iloc[[0]]

    stats = analyzer._grouped_stats("mean_pst")

    assert stats.iloc[0]["count"] == 1
    assert stats.iloc[0]["ci95"] == 0


def test_utility_and_tfi_comparisons_use_student_t_error_bars(tmp_path, monkeypatch):
    _write_analysis_inputs(tmp_path)
    analyzer = SimulationAnalyzer(results_dir=str(tmp_path))
    analyzer.load_results()
    calls = []

    def record_bar_chart(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(analyzer, "_bar_chart", record_bar_chart)

    analyzer.plot_utility_comparison()
    analyzer.plot_tfi_comparison()

    assert [call[1]["error_column"] for call in calls] == ["mean_utility", "tfi"]


def test_tfi_comparison_uses_traffic_flow_impact_labels(tmp_path, monkeypatch):
    _write_analysis_inputs(tmp_path)
    analyzer = SimulationAnalyzer(
        results_dir=str(tmp_path),
        figures_dir=str(tmp_path / "figures"),
    )
    analyzer.load_results()
    monkeypatch.setattr(analysis.plt, "close", lambda figure: None)

    analyzer.plot_tfi_comparison()

    axis = analysis.plt.gcf().axes[0]
    assert axis.get_ylabel() == "Traffic Flow Impact"
    assert axis.get_title() == "Traffic Flow Impact by Scenario and Strategy"
    analysis.plt.close(analysis.plt.gcf())


def test_generate_all_writes_six_primary_figures(tmp_path):
    _write_analysis_inputs(tmp_path)
    analyzer = SimulationAnalyzer(
        results_dir=str(tmp_path),
        figures_dir=str(tmp_path / "figures"),
        tables_dir=str(tmp_path / "tables"),
    )
    analyzer.load_results()
    analyzer.generate_all()

    assert {path.name for path in (tmp_path / "figures").glob("*.png")} == {
        "pst_comparison.png",
        "rsr_comparison.png",
        "utility_comparison.png",
        "tfi_comparison.png",
        "pst_boxplot.png",
        "por_timeseries.png",
    }


def test_por_timeseries_uses_all_demand_scenario_panels(tmp_path, monkeypatch):
    _write_analysis_inputs(tmp_path)
    analyzer = SimulationAnalyzer(
        results_dir=str(tmp_path),
        figures_dir=str(tmp_path / "figures"),
    )
    analyzer.load_results()
    monkeypatch.setattr(analysis.plt, "close", lambda figure: None)

    analyzer.plot_por_timeseries()

    figure = analysis.plt.gcf()
    assert len(figure.axes) == 4
    assert {
        axis.get_title()
        for axis in figure.axes
    } == {
        "Low Demand Parking Occupancy Rate Over Time",
        "Medium Demand Parking Occupancy Rate Over Time",
        "High Demand Parking Occupancy Rate Over Time",
        "Peak Demand Parking Occupancy Rate Over Time",
    }
    analysis.plt.close(figure)


def test_analysis_keeps_csv_scenarios_after_known_order(tmp_path):
    _write_analysis_inputs(tmp_path)
    extra = pd.DataFrame([
        {
            "scenario": "special_event",
            "strategy": "auction",
            "mean_pst": 8.0,
            "rsr": 70.0,
            "mean_utility": 0.3,
            "tfi": 2.0,
        },
    ])
    extra.to_csv(tmp_path / "experiment_results.csv", mode="a", header=False, index=False)
    analyzer = SimulationAnalyzer(results_dir=str(tmp_path))
    analyzer.load_results()

    scenarios, _, _ = analyzer._ordered_values("mean_pst")

    assert scenarios == ["low_demand", "high_demand", "special_event"]
