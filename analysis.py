#!/usr/bin/env python3
"""Analysis and visualization for experiment outputs."""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import t


SCENARIO_ORDER = ["low_demand", "medium_demand", "high_demand", "peak_demand"]
STRATEGY_ORDER = ["auction", "fcfs", "random", "greedy"]


def _ordered_available(known_order, values):
    available = list(dict.fromkeys(values))
    return [value for value in known_order if value in available] + [
        value for value in available if value not in known_order
    ]


class SimulationAnalyzer:
    """Generates figures and tables from experiment CSV files."""

    def __init__(
        self,
        results_dir="output/csv",
        figures_dir="output/figures",
        tables_dir="output/tables",
    ):
        self.results_dir = results_dir
        self.figures_dir = figures_dir
        self.tables_dir = tables_dir
        os.makedirs(figures_dir, exist_ok=True)
        os.makedirs(tables_dir, exist_ok=True)
        self.results_df = None

    def load_results(self, csv_file=None):
        path = csv_file or os.path.join(self.results_dir, "experiment_results.csv")
        self.results_df = pd.read_csv(path)
        print(f"Loaded {len(self.results_df)} rows from {path}")
        return self.results_df

    def generate_all(self):
        if self.results_df is None:
            self.load_results()
        self._set_style()
        self.plot_pst_comparison()
        self.plot_rsr_comparison()
        self.plot_utility_comparison()
        self.plot_tfi_comparison()
        self.plot_pst_boxplot()
        self.plot_por_timeseries()
        self.generate_results_table()
        print(f"Saved figures to {self.figures_dir} and tables to {self.tables_dir}")

    def _set_style(self):
        try:
            import seaborn as sns
            sns.set_theme(style="whitegrid")
        except Exception:
            plt.style.use("seaborn-v0_8-whitegrid")

    def _ordered_values(self, column):
        scenarios = _ordered_available(SCENARIO_ORDER, self.results_df["scenario"].dropna())
        strategies = _ordered_available(STRATEGY_ORDER, self.results_df["strategy"].dropna())
        values_df = self.results_df.copy()
        values_df[column] = pd.to_numeric(values_df[column], errors="coerce")
        grouped = values_df.groupby(["scenario", "strategy"])[column].mean()
        values = {
            strategy: [grouped.get((scenario, strategy), np.nan) for scenario in scenarios]
            for strategy in strategies
        }
        return scenarios, strategies, values

    def _grouped_stats(self, column):
        values_df = self.results_df[["scenario", "strategy", column]].copy()
        values_df[column] = pd.to_numeric(values_df[column], errors="coerce")
        values_df = values_df.dropna(subset=[column])
        stats = (
            values_df.groupby(["scenario", "strategy"])[column]
            .agg(mean="mean", std="std", count="count")
            .reset_index()
        )
        stats["ci95"] = stats.apply(
            lambda row: (
                0.0
                if row["count"] <= 1
                else t.ppf(0.975, row["count"] - 1) * row["std"] / np.sqrt(row["count"])
            ),
            axis=1,
        )
        return stats[["scenario", "strategy", "mean", "ci95", "count"]]

    def _bar_chart(self, column, ylabel, title, filename, error_column=None):
        scenarios, strategies, values = self._ordered_values(column)
        errors = {strategy: [0.0] * len(scenarios) for strategy in strategies}
        if error_column is not None:
            stats = self._grouped_stats(error_column).set_index(["scenario", "strategy"])
            values = {
                strategy: [
                    stats.loc[(scenario, strategy), "mean"]
                    if (scenario, strategy) in stats.index
                    else np.nan
                    for scenario in scenarios
                ]
                for strategy in strategies
            }
            errors = {
                strategy: [
                    stats.loc[(scenario, strategy), "ci95"]
                    if (scenario, strategy) in stats.index
                    else 0.0
                    for scenario in scenarios
                ]
                for strategy in strategies
            }
        x = np.arange(len(scenarios))
        width = 0.18
        offsets = (np.arange(len(strategies)) - (len(strategies) - 1) / 2) * width

        fig, ax = plt.subplots(figsize=(11, 6))
        for offset, strategy in zip(offsets, strategies):
            kwargs = {"yerr": errors[strategy]} if error_column is not None else {}
            ax.bar(x + offset, values[strategy], width=width, label=strategy, **kwargs)

        ax.set_xlabel("Scenario")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels([s.replace("_", " ").title() for s in scenarios], rotation=15)
        ax.legend(title="Strategy")
        fig.tight_layout()
        path = os.path.join(self.figures_dir, filename)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"Saved {path}")

    def plot_pst_comparison(self):
        self._bar_chart(
            "mean_pst",
            "Mean Parking Search Time (ticks)",
            "Mean Parking Search Time by Scenario and Strategy",
            "pst_comparison.png",
            error_column="mean_pst",
        )

    def plot_rsr_comparison(self):
        self._bar_chart(
            "rsr",
            "Reservation Success Rate (%)",
            "Reservation Success Rate by Scenario and Strategy",
            "rsr_comparison.png",
            error_column="rsr",
        )

    def plot_utility_comparison(self):
        self._bar_chart(
            "mean_utility",
            "Mean Utility",
            "Mean Utility by Scenario and Strategy",
            "utility_comparison.png",
            error_column="mean_utility",
        )

    def plot_tfi_comparison(self):
        self._bar_chart(
            "tfi",
            "Traffic Flow Impact",
            "Traffic Flow Impact by Scenario and Strategy",
            "tfi_comparison.png",
            error_column="tfi",
        )

    def plot_pst_boxplot(self):
        scenarios = _ordered_available(SCENARIO_ORDER, self.results_df["scenario"].dropna())
        strategies = _ordered_available(STRATEGY_ORDER, self.results_df["strategy"].dropna())
        values_df = self.results_df.copy()
        values_df["mean_pst"] = pd.to_numeric(values_df["mean_pst"], errors="coerce")

        box_values = []
        labels = []
        for scenario in scenarios:
            for strategy in strategies:
                values = values_df.loc[
                    (values_df["scenario"] == scenario)
                    & (values_df["strategy"] == strategy),
                    "mean_pst",
                ].dropna().tolist()
                if values:
                    box_values.append(values)
                    labels.append(
                        f"{scenario.replace('_', ' ').title()}\n{strategy.title()}"
                    )

        fig, ax = plt.subplots(figsize=(11, 6))
        if box_values:
            ax.boxplot(box_values, tick_labels=labels)
        ax.set_xlabel("Scenario and Strategy")
        ax.set_ylabel("Mean Parking Search Time (ticks)")
        ax.set_title("Parking Search Time Distribution by Scenario and Strategy")
        ax.tick_params(axis="x", labelrotation=25)
        fig.tight_layout()
        path = os.path.join(self.figures_dir, "pst_boxplot.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"Saved {path}")

    def plot_por_timeseries(self):
        path = os.path.join(self.results_dir, "por_timeseries.csv")
        if not os.path.exists(path):
            print(f"Skipping POR time series; missing {path}")
            return

        df = pd.read_csv(path)
        scenarios = _ordered_available(SCENARIO_ORDER, df["scenario"].dropna())
        strategies = _ordered_available(STRATEGY_ORDER, df["strategy"].dropna())
        rows = max(1, (len(scenarios) + 1) // 2)
        fig, axes = plt.subplots(rows, 2, figsize=(11, 3.5 * rows), sharey=True)
        axes = np.atleast_1d(axes).ravel()

        for axis, scenario in zip(axes, scenarios):
            scenario_df = df[df["scenario"] == scenario]
            for strategy in strategies:
                strategy_df = scenario_df[scenario_df["strategy"] == strategy]
                mean_por = strategy_df.groupby("tick")["por"].mean()
                if not mean_por.empty:
                    axis.plot(mean_por.index, mean_por.values, label=strategy)

            axis.set_xlabel("Simulation Tick")
            axis.set_ylabel("Parking Occupancy Rate")
            axis.set_title(
                f"{scenario.replace('_', ' ').title()} Parking Occupancy Rate Over Time"
            )
            axis.set_ylim(0, 1)

        for axis in axes[len(scenarios):]:
            axis.set_visible(False)

        handles, labels = [], []
        for axis in axes[:len(scenarios)]:
            handles, labels = axis.get_legend_handles_labels()
            if handles:
                break
        if handles:
            fig.legend(handles, labels, title="Strategy")
        fig.tight_layout()
        output = os.path.join(self.figures_dir, "por_timeseries.png")
        fig.savefig(output, dpi=150)
        plt.close(fig)
        print(f"Saved {output}")

    def generate_results_table(self):
        summary = self.results_df.groupby(["scenario", "strategy"]).agg(
            mean_pst=("mean_pst", "mean"),
            std_pst=("mean_pst", "std"),
            mean_rsr=("rsr", "mean"),
            std_rsr=("rsr", "std"),
            mean_utility=("mean_utility", "mean"),
            mean_tfi=("tfi", "mean"),
        ).reset_index()

        scenario_order = _ordered_available(SCENARIO_ORDER, summary["scenario"])
        strategy_order = _ordered_available(STRATEGY_ORDER, summary["strategy"])
        summary["_scenario_order"] = summary["scenario"].map(
            {name: idx for idx, name in enumerate(scenario_order)}
        )
        summary["_strategy_order"] = summary["strategy"].map(
            {name: idx for idx, name in enumerate(strategy_order)}
        )
        summary = summary.sort_values(by=["_scenario_order", "_strategy_order"])
        summary = summary.drop(columns=["_scenario_order", "_strategy_order"])
        path = os.path.join(self.tables_dir, "results_table.tex")
        with open(path, "w") as f:
            f.write(summary.to_latex(index=False, float_format="%.3f"))
        print(f"Saved {path}")
        return summary


def main():
    parser = argparse.ArgumentParser(description="Generate parking experiment analysis outputs")
    parser.add_argument("--results", default=None, help="Path to experiment_results.csv")
    args = parser.parse_args()
    analyzer = SimulationAnalyzer()
    analyzer.load_results(args.results)
    analyzer.generate_all()


if __name__ == "__main__":
    main()
