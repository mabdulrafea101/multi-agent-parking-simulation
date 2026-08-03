#!/usr/bin/env python3
"""Batch experiment runner for the parking simulation."""
import argparse
import copy
import csv
import json
import os
import shutil
import time
from collections import defaultdict

import numpy as np

from model import ParkingModel


RESULT_COLUMNS = [
    "scenario",
    "strategy",
    "replication",
    "total_arrivals",
    "total_successful",
    "total_failed",
    "mean_pst",
    "std_por",
    "rsr",
    "mean_utility",
    "tfi",
    "sumo_connected",
]

SCENARIO_ORDER = ["low_demand", "medium_demand", "high_demand", "peak_demand"]
STRATEGY_ORDER = ["auction", "fcfs", "random", "greedy"]


def _ordered_available(known_order, values):
    available = list(dict.fromkeys(values))
    return [value for value in known_order if value in available] + [
        value for value in available if value not in known_order
    ]


class ExperimentRunner:
    """Runs scenario x strategy x replication experiment batches."""

    def __init__(self, config_dir="config", output_dir="output", base_seed=None):
        self.config_dir = config_dir
        self.output_dir = output_dir
        self.results_dir = os.path.join(output_dir, "csv")
        self.figures_dir = os.path.join(output_dir, "figures")
        self.tables_dir = os.path.join(output_dir, "tables")

        for directory in [self.results_dir, self.figures_dir, self.tables_dir]:
            os.makedirs(directory, exist_ok=True)

        with open(os.path.join(config_dir, "default_params.json"), "r") as f:
            self.base_config = json.load(f)
        with open(os.path.join(config_dir, "scenarios.json"), "r") as f:
            self.scenarios_config = json.load(f)

        configured_seed = self.base_config["simulation"].get("random_seed", 42)
        self.base_seed = configured_seed if base_seed is None else base_seed

    def run_all(self, replication_start=0, replication_end=30, parallel=False, progress_callback=None):
        """Run every configured scenario and strategy."""
        return self.run_selected(
            scenarios=None,
            strategies=None,
            replication_start=replication_start,
            replication_end=replication_end,
            parallel=parallel,
            progress_callback=progress_callback,
        )

    def run_batch(
        self,
        scenarios=None,
        strategies=None,
        replication_start=0,
        replication_end=30,
        parallel=False,
        simulation_type="mesa",
        city=None,
        progress_callback=None,
    ):
        """Run a batch with an explicit simulation backend selection."""
        return self.run_selected(
            scenarios=scenarios,
            strategies=strategies,
            replication_start=replication_start,
            replication_end=replication_end,
            parallel=parallel,
            simulation_type=simulation_type,
            city=city,
            progress_callback=progress_callback,
        )

    def run_selected(
        self,
        scenarios=None,
        strategies=None,
        replication_start=0,
        replication_end=30,
        parallel=False,
        simulation_type="mesa",
        city=None,
        progress_callback=None,
    ):
        """Run selected scenario x strategy x replication experiment batches."""
        del parallel
        simulation_type = simulation_type or "mesa"
        city = city if simulation_type == "osm_city" else None
        if scenarios is None:
            scenarios = _ordered_available(SCENARIO_ORDER, self.scenarios_config["scenarios"])
        else:
            scenarios = [s for s in scenarios if s in self.scenarios_config["scenarios"]]

        if strategies is None:
            strategies = [s for s in STRATEGY_ORDER if s in self.scenarios_config["strategies"]]
        else:
            strategies = [s for s in strategies if s in self.scenarios_config["strategies"]]

        if not scenarios:
            raise ValueError("No valid scenarios selected")
        if not strategies:
            raise ValueError("No valid strategies selected")

        total_reps = replication_end - replication_start
        total_runs = len(scenarios) * len(strategies) * total_reps
        completed = 0
        started_at = time.time()
        next_eta_at = started_at + 300
        all_results = []
        timeseries_rows = []

        for scenario_name in scenarios:
            for strategy_name in strategies:
                for rep in range(replication_start, replication_end):
                    try:
                        result = self.run_single(
                            scenario_name,
                            strategy_name,
                            rep,
                            simulation_type=simulation_type,
                            city=city,
                        )
                    except Exception as exc:
                        print(f"  [{scenario_name}] [{strategy_name}] rep {rep}: FAILED ({exc}), skipping")
                        # Create a placeholder result so the run is counted
                        result = {
                            "scenario": scenario_name,
                            "strategy": strategy_name,
                            "replication": rep,
                            "total_arrivals": 0,
                            "total_successful": 0,
                            "total_failed": 0,
                            "mean_pst": 0.0,
                            "std_por": 0.0,
                            "rsr": 0.0,
                            "mean_utility": 0.0,
                            "tfi": 0.0,
                            "sumo_connected": False,
                            "_error": str(exc),
                            "_timeseries": [],
                        }

                    all_results.append(result)
                    timeseries_rows.extend(result.get("_timeseries", []))
                    result.pop("_error", None)  # Remove error flag from result

                    completed += 1
                    if progress_callback:
                        progress_callback(
                            completed=completed,
                            total=total_runs,
                            scenario=scenario_name,
                            strategy=strategy_name,
                            replication=rep,
                            result=result,
                        )
                    print(
                        f"[{scenario_name}] [{strategy_name}] rep "
                        f"{rep - replication_start + 1}/{total_reps}: "
                        f"PST={result['mean_pst']:.2f} "
                        f"POR={result['std_por']:.3f} "
                        f"RSR={result['rsr']:.1f}%"
                    )

                    now = time.time()
                    if now >= next_eta_at and completed < total_runs:
                        elapsed = now - started_at
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining = (total_runs - completed) / rate if rate else 0
                        print(f"Estimated time remaining: {remaining / 60:.1f} minutes")
                        next_eta_at = now + 300

        self.save_results(all_results)
        self.save_summary(all_results)
        self.save_timeseries(timeseries_rows)
        return all_results

    def run_single(
        self,
        scenario_name,
        strategy_name,
        replication_id,
        simulation_type="mesa",
        city=None,
    ):
        """Run one scenario/strategy/replication combination."""
        config = copy.deepcopy(self.base_config)
        scenario = self.scenarios_config["scenarios"][scenario_name]
        config["demand"]["arrival_rate_lambda"] = scenario["arrival_rate_lambda"]
        config["simulation"]["random_seed"] = self.base_seed

        model = ParkingModel(
            config_dict=config,
            strategy=strategy_name,
            replication_id=replication_id,
            simulation_type=simulation_type,
            city=city,
        )

        if simulation_type != "mesa":
            # Keep experiments robust on machines without SUMO binaries or TraCI.
            from engine.sumo_integration import _sumo_bin
            if not os.path.isfile(_sumo_bin("netgenerate")):
                model.sumo = None
                model.use_sumo = False
            else:
                try:
                    model.init_sumo(gui=False, osm_place=city if simulation_type == "osm_city" else None)
                except Exception as exc:
                    print(f"  SUMO: Initialization failed ({exc}), running in Mesa-only mode")
                    model.sumo = None
                    model.use_sumo = False

        results = model.run_simulation()
        por_values = [
            occupied / len(model.spots)
            for occupied in model.kpi_data["occupied_spots"]
        ] if model.spots else []

        row = {
            "scenario": scenario_name,
            "strategy": strategy_name,
            "replication": replication_id,
            "total_arrivals": results.get("total_arrivals", 0),
            "total_successful": results.get("total_successful", 0),
            "total_failed": results.get("total_failed", 0),
            "mean_pst": results.get("mean_pst", 0.0),
            "std_por": float(np.std(por_values)) if por_values else 0.0,
            "rsr": results.get("rsr", 0.0),
            "mean_utility": results.get("mean_utility", 0.0),
            "tfi": results.get("tfi", 0.0),
            "sumo_connected": bool(results.get("sumo_connected", False)),
            "_timeseries": [
                {
                    "scenario": scenario_name,
                    "strategy": strategy_name,
                    "replication": replication_id,
                    "tick": tick,
                    "por": por,
                }
                for tick, por in zip(model.kpi_data["tick"], por_values)
            ],
        }
        return row

    def save_results(self, results):
        path = os.path.join(self.results_dir, "experiment_results.csv")
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=RESULT_COLUMNS)
            writer.writeheader()
            for row in results:
                writer.writerow({key: row.get(key, "") for key in RESULT_COLUMNS})
        print(f"Saved {len(results)} runs to {path}")

    def save_summary(self, results):
        summary = self.compute_summary(results)
        path = os.path.join(self.results_dir, "summary_statistics.csv")
        fieldnames = list(summary[0].keys()) if summary else [
            "scenario",
            "strategy",
            "n_replications",
        ]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summary)
        print(f"Saved summary statistics to {path}")

    def save_timeseries(self, rows):
        path = os.path.join(self.results_dir, "por_timeseries.csv")
        fieldnames = ["scenario", "strategy", "replication", "tick", "por"]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved POR time series to {path}")

    def compute_summary(self, results):
        grouped = defaultdict(list)
        for row in results:
            grouped[(row["scenario"], row["strategy"])].append(row)

        summary = []
        metric_columns = [
            "total_arrivals",
            "total_successful",
            "total_failed",
            "mean_pst",
            "std_por",
            "rsr",
            "mean_utility",
            "tfi",
        ]
        scenario_order = _ordered_available(SCENARIO_ORDER, [row["scenario"] for row in results])
        strategy_order = _ordered_available(STRATEGY_ORDER, [row["strategy"] for row in results])
        for scenario in scenario_order:
            for strategy in strategy_order:
                rows = grouped.get((scenario, strategy), [])
                if not rows:
                    continue
                output = {
                    "scenario": scenario,
                    "strategy": strategy,
                    "n_replications": len(rows),
                    "sumo_connected_runs": sum(1 for r in rows if r["sumo_connected"]),
                }
                for metric in metric_columns:
                    values = np.array([float(r[metric]) for r in rows], dtype=float)
                    output[f"mean_{metric}"] = float(np.mean(values))
                    output[f"std_{metric}"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
                summary.append(output)
        return summary


def parse_args():
    parser = argparse.ArgumentParser(description="Run parking simulation experiments")
    parser.add_argument("--all-scenarios", action="store_true", help="Run all scenarios and strategies")
    parser.add_argument("--scenario", action="append", help="Scenario to run; repeat for multiple scenarios")
    parser.add_argument("--strategy", action="append", help="Strategy to run; repeat for multiple strategies")
    parser.add_argument("--all-strategies", action="store_true", help="Run all strategies")
    parser.add_argument("--replications", type=int, default=30, help="Number of replications per cell")
    parser.add_argument("--base-seed", type=int, default=None, help="Base random seed")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    return parser.parse_args()


def main():
    args = parse_args()
    runner = ExperimentRunner(output_dir=args.output_dir, base_seed=args.base_seed)
    selected_scenarios = None if args.all_scenarios else args.scenario
    selected_strategies = None if args.all_strategies else args.strategy
    runner.run_selected(
        scenarios=selected_scenarios,
        strategies=selected_strategies,
        replication_end=args.replications,
    )


if __name__ == "__main__":
    main()
