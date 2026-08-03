#!/usr/bin/env python3
"""Chapter 4 Analysis: Statistical testing and figure generation."""
import os
import numpy as np
import pandas as pd
from scipy import stats
from itertools import combinations

# ============================================================
# Load Data
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_CSV = os.path.join(SCRIPT_DIR, "output", "csv", "experiment_results.csv")
SUMMARY_CSV = os.path.join(SCRIPT_DIR, "output", "csv", "summary_statistics.csv")
TIMESERIES_CSV = os.path.join(SCRIPT_DIR, "output", "csv", "por_timeseries.csv")

results = pd.read_csv(RESULTS_CSV)
summary = pd.read_csv(SUMMARY_CSV)

OUTPUT_DIR = "simulation/output"
FIGURES_DIR = os.path.join(OUTPUT_DIR, "figures")
TABLES_DIR = os.path.join(OUTPUT_DIR, "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

METRICS = ["mean_pst", "std_por", "rsr", "mean_utility", "tfi"]
METRIC_LABELS = {
    "mean_pst": "Parking Search Time (ticks)",
    "std_por": "Std Dev of Occupancy Rate",
    "rsr": "Reservation Success Rate (%)",
    "mean_utility": "Mean Agent Utility",
    "tfi": "Traffic Flow Impact",
}

SCENARIOS = ["low_demand", "medium_demand", "high_demand", "peak_demand"]
STRATEGIES = ["auction", "fcfs", "random", "greedy"]
STRATEGY_LABELS = {
    "auction": "Auction-Based",
    "fcfs": "FCFS",
    "random": "Random",
    "greedy": "Greedy",
}

# ============================================================
# Table 4.1: Overall Summary (all scenarios x strategies)
# ============================================================
def generate_summary_table():
    rows = []
    for scenario in SCENARIOS:
        for strategy in STRATEGIES:
            mask = (results["scenario"] == scenario) & (results["strategy"] == strategy)
            subset = results[mask]
            if len(subset) == 0:
                continue
            row = {
                "Scenario": scenario.replace("_", " ").title(),
                "Strategy": STRATEGY_LABELS[strategy],
                "N": len(subset),
                "Mean PST": f"{subset['mean_pst'].mean():.2f} ± {subset['mean_pst'].std():.2f}",
                "RSR (%)": f"{subset['rsr'].mean():.1f} ± {subset['rsr'].std():.1f}",
                "Mean Utility": f"{subset['mean_utility'].mean():.3f} ± {subset['mean_utility'].std():.3f}",
                "TFI": f"{subset['tfi'].mean():.3f} ± {subset['tfi'].std():.3f}",
            }
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(TABLES_DIR, "table4_1_summary.csv"), index=False)
    return df

# ============================================================
# Table 4.2: Per-metric detailed summary
# ============================================================
def generate_metric_table(metric):
    rows = []
    for scenario in SCENARIOS:
        for strategy in STRATEGIES:
            mask = (results["scenario"] == scenario) & (results["strategy"] == strategy)
            subset = results[mask]
            if len(subset) == 0:
                continue
            row = {
                "Scenario": scenario.replace("_", " ").title(),
                "Strategy": STRATEGY_LABELS[strategy],
                "Mean": round(subset[metric].mean(), 4),
                "Std": round(subset[metric].std(), 4),
                "Min": round(subset[metric].min(), 4),
                "Max": round(subset[metric].max(), 4),
                "95% CI Lower": round(subset[metric].mean() - 1.96 * subset[metric].std() / np.sqrt(len(subset)), 4),
                "95% CI Upper": round(subset[metric].mean() + 1.96 * subset[metric].std() / np.sqrt(len(subset)), 4),
            }
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(TABLES_DIR, f"table4_2_{metric}.csv"), index=False)
    return df

# ============================================================
# Table 4.3: Statistical significance tests (t-test + Bonferroni)
# ============================================================
def generate_significance_tests():
    rows = []
    for scenario in SCENARIOS:
        auction_mask = (results["scenario"] == scenario) & (results["strategy"] == "auction")
        auction_data = results[auction_mask]
        
        for baseline in ["fcfs", "random", "greedy"]:
            baseline_mask = (results["scenario"] == scenario) & (results["strategy"] == baseline)
            baseline_data = results[baseline_mask]
            
            for metric in METRICS:
                a_vals = auction_data[metric].values
                b_vals = baseline_data[metric].values
                
                if len(a_vals) < 2 or len(b_vals) < 2:
                    continue
                
                # Welch's t-test (does not assume equal variances)
                t_stat, p_value = stats.ttest_ind(a_vals, b_vals, equal_var=False)
                
                # Effect size (Cohen's d)
                pooled_std = np.sqrt((np.std(a_vals, ddof=1)**2 + np.std(b_vals, ddof=1)**2) / 2)
                cohens_d = (np.mean(a_vals) - np.mean(b_vals)) / pooled_std if pooled_std > 0 else 0
                
                rows.append({
                    "Scenario": scenario.replace("_", " ").title(),
                    "Comparison": f"Auction vs {STRATEGY_LABELS[baseline]}",
                    "Metric": METRIC_LABELS[metric],
                    "Auction Mean": round(np.mean(a_vals), 4),
                    f"{STRATEGY_LABELS[baseline]} Mean": round(np.mean(b_vals), 4),
                    "Difference": round(np.mean(a_vals) - np.mean(b_vals), 4),
                    "t-statistic": round(t_stat, 4),
                    "p-value": f"{p_value:.6f}",
                    "Cohen's d": round(cohens_d, 4),
                    "Significant (p<0.05)": "Yes" if p_value < 0.05 else "No",
                })
    
    df = pd.DataFrame(rows)
    
    # Bonferroni correction: for each scenario-metric combo, adjust p-value
    n_comparisons = 3  # auction vs fcfs, random, greedy
    df["p-value (raw)"] = df["p-value"]
    df["p-value (Bonferroni)"] = (df["p-value"].astype(float) * n_comparisons).clip(upper=1.0)
    df["Significant (Bonferroni)"] = df["p-value (Bonferroni)"].apply(lambda p: "Yes" if p < 0.05 else "No")
    
    df.to_csv(os.path.join(TABLES_DIR, "table4_3_significance.csv"), index=False)
    return df

# ============================================================
# Figure 4.1: PST comparison bar chart
# ============================================================
def generate_pst_figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(SCENARIOS))
    width = 0.2
    colors = ["#2196F3", "#FF9800", "#4CAF50", "#F44336"]
    
    for i, strategy in enumerate(STRATEGIES):
        means = []
        stds = []
        for scenario in SCENARIOS:
            mask = (results["scenario"] == scenario) & (results["strategy"] == strategy)
            subset = results[mask]
            means.append(subset["mean_pst"].mean())
            stds.append(subset["mean_pst"].std())
        ax.bar(x + i * width, means, width, yerr=stds, label=STRATEGY_LABELS[strategy],
               color=colors[i], capsize=3, alpha=0.85)
    
    ax.set_xlabel("Demand Scenario")
    ax.set_ylabel("Mean Parking Search Time (ticks)")
    ax.set_title("Figure 4.1: Parking Search Time Across Demand Scenarios")
    ax.set_xticks(x + 1.5 * width)
    ax.set_xticklabels([s.replace("_", " ").title() for s in SCENARIOS])
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "figure4_1_pst.png"), dpi=150)
    plt.close()

# ============================================================
# Figure 4.2: RSR comparison
# ============================================================
def generate_rsr_figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(SCENARIOS))
    width = 0.2
    colors = ["#2196F3", "#FF9800", "#4CAF50", "#F44336"]
    
    for i, strategy in enumerate(STRATEGIES):
        means = []
        stds = []
        for scenario in SCENARIOS:
            mask = (results["scenario"] == scenario) & (results["strategy"] == strategy)
            subset = results[mask]
            means.append(subset["rsr"].mean())
            stds.append(subset["rsr"].std())
        ax.bar(x + i * width, means, width, yerr=stds, label=STRATEGY_LABELS[strategy],
               color=colors[i], capsize=3, alpha=0.85)
    
    ax.set_xlabel("Demand Scenario")
    ax.set_ylabel("Reservation Success Rate (%)")
    ax.set_title("Figure 4.1: Reservation Success Rate Across Demand Scenarios")
    ax.set_xticks(x + 1.5 * width)
    ax.set_xticklabels([s.replace("_", " ").title() for s in SCENARIOS])
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "figure4_2_rsr.png"), dpi=150)
    plt.close()

# ============================================================
# Figure 4.3: Utility comparison
# ============================================================
def generate_utility_figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(SCENARIOS))
    width = 0.2
    colors = ["#2196F3", "#FF9800", "#4CAF50", "#F44336"]
    
    for i, strategy in enumerate(STRATEGIES):
        means = []
        stds = []
        for scenario in SCENARIOS:
            mask = (results["scenario"] == scenario) & (results["strategy"] == strategy)
            subset = results[mask]
            means.append(subset["mean_utility"].mean())
            stds.append(subset["mean_utility"].std())
        ax.bar(x + i * width, means, width, yerr=stds, label=STRATEGY_LABELS[strategy],
               color=colors[i], capsize=3, alpha=0.85)
    
    ax.set_xlabel("Demand Scenario")
    ax.set_ylabel("Mean Agent Utility")
    ax.set_title("Figure 4.3: Mean Agent Utility Across Demand Scenarios")
    ax.set_xticks(x + 1.5 * width)
    ax.set_xticklabels([s.replace("_", " ").title() for s in SCENARIOS])
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "figure4_3_utility.png"), dpi=150)
    plt.close()

# ============================================================
# Figure 4.4: POR time series (high demand)
# ============================================================
def generate_por_timeseries_figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    if not os.path.exists(TIMESERIES_CSV):
        return
    
    ts = pd.read_csv(TIMESERIES_CSV)
    if len(ts) == 0:
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = {"auction": "#2196F3", "fcfs": "#FF9800", "random": "#4CAF50", "greedy": "#F44336"}
    
    for strategy in STRATEGIES:
        mask = ts["strategy"] == strategy
        subset = ts[mask]
        if len(subset) == 0:
            continue
        # Average POR across replications
        avg_por = subset.groupby("tick")["por"].mean()
        ax.plot(avg_por.index, avg_por.values, label=STRATEGY_LABELS[strategy],
                color=colors[strategy], alpha=0.8, linewidth=1.5)
    
    ax.set_xlabel("Simulation Tick")
    ax.set_ylabel("Parking Occupancy Rate")
    ax.set_title("Figure 4.4: POR Time Series — High Demand Scenario")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_ylim(0, 1.1)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "figure4_4_por_timeseries.png"), dpi=150)
    plt.close()

# ============================================================
# Figure 4.5: TFI comparison
# ============================================================
def generate_tfi_figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(SCENARIOS))
    width = 0.2
    colors = ["#2196F3", "#FF9800", "#4CAF50", "#F44336"]
    
    for i, strategy in enumerate(STRATEGIES):
        means = []
        stds = []
        for scenario in SCENARIOS:
            mask = (results["scenario"] == scenario) & (results["strategy"] == strategy)
            subset = results[mask]
            means.append(subset["tfi"].mean())
            stds.append(subset["tfi"].std())
        ax.bar(x + i * width, means, width, yerr=stds, label=STRATEGY_LABELS[strategy],
               color=colors[i], capsize=3, alpha=0.85)
    
    ax.set_xlabel("Demand Scenario")
    ax.set_ylabel("Traffic Flow Impact")
    ax.set_title("Figure 4.5: Traffic Flow Impact Across Demand Scenarios")
    ax.set_xticks(x + 1.5 * width)
    ax.set_xticklabels([s.replace("_", " ").title() for s in SCENARIOS])
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "figure4_5_tfi.png"), dpi=150)
    plt.close()

# ============================================================
# LaTeX table generation
# ============================================================
def generate_latex_tables():
    """Generate LaTeX tables for the thesis."""
    
    # Table 1: Overall summary
    latex = []
    latex.append("\\begin{table}[htbp]")
    latex.append("\\centering")
    latex.append("\\caption{Summary of Simulation Results Across All Scenarios and Strategies}")
    latex.append("\\label{tab:summary}")
    latex.append("\\begin{tabular}{llcccc}")
    latex.append("\\hline")
    latex.append("Scenario & Strategy & PST$_{mean}$ & RSR (\\%) & Utility & TFI \\\\")
    latex.append("\\hline")
    
    for scenario in SCENARIOS:
        for strategy in STRATEGIES:
            mask = (results["scenario"] == scenario) & (results["strategy"] == strategy)
            subset = results[mask]
            if len(subset) == 0:
                continue
            latex.append(
                f"{scenario.replace('_', ' ').title()} & "
                f"{STRATEGY_LABELS[strategy]} & "
                f"{subset['mean_pst'].mean():.2f} $\\pm$ {subset['mean_pst'].std():.2f} & "
                f"{subset['rsr'].mean():.1f} $\\pm$ {subset['rsr'].std():.1f} & "
                f"{subset['mean_utility'].mean():.3f} $\\pm$ {subset['mean_utility'].std():.3f} & "
                f"{subset['tfi'].mean():.3f} $\\pm$ {subset['tfi'].std():.3f} \\\\"
            )
        latex.append("\\hline")
    
    latex.append("\\end{tabular}")
    latex.append("\\end{table}")
    
    with open(os.path.join(TABLES_DIR, "table4_1_summary.tex"), "w") as f:
        f.write("\n".join(latex))

# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Chapter 4: Analysis and Figure Generation")
    print("=" * 60)
    
    print("\n[1] Generating summary table...")
    t1 = generate_summary_table()
    print(f"    -> simulation/output/tables/table4_1_summary.csv ({len(t1)} rows)")
    
    print("\n[2] Generating per-metric tables...")
    for metric in METRICS:
        generate_metric_table(metric)
        print(f"    -> table4_2_{metric}.csv")
    
    print("\n[3] Running statistical significance tests...")
    sig = generate_significance_tests()
    print(f"    -> table4_3_significance.csv ({len(sig)} comparisons)")
    
    print("\n[4] Generating figures...")
    generate_pst_figure()
    print("    -> figure4_1_pst.png")
    generate_rsr_figure()
    print("    -> figure4_2_rsr.png")
    generate_utility_figure()
    print("    -> figure4_3_utility.png")
    generate_por_timeseries_figure()
    print("    -> figure4_4_por_timeseries.png")
    generate_tfi_figure()
    print("    -> figure4_5_tfi.png")
    
    print("\n[5] Generating LaTeX tables...")
    generate_latex_tables()
    print("    -> table4_1_summary.tex")
    
    print("\n" + "=" * 60)
    print("Analysis complete. All outputs saved to simulation/output/")
    print("=" * 60)
