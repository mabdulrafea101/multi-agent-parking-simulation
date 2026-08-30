#!/usr/bin/env python3
"""
Main entry point for Multi-Agent Parking Simulation.
Usage:
    python main.py                          # Run default configuration
    python main.py --all-scenarios          # Run all 4 scenarios x 4 strategies x 30 reps
    python main.py --scenario low_demand --strategy auction --replications 5
    python main.py --gui                    # Run with SUMO GUI
    python main.py --osm "Kuala Lumpur, Malaysia"  # Use OSM data
"""
import argparse
import os
import sys
import json

# Add simulation directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model import ParkingModel
from recorder import FrameRecorder
from experiments import ExperimentRunner


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Parking Simulation")
    parser.add_argument("--config", default="config/default_params.json",
                       help="Path to configuration file")
    parser.add_argument("--scenario", default=None,
                       help="Scenario name (low_demand, medium_demand, high_demand, peak_demand)")
    parser.add_argument("--strategy", default="auction",
                       choices=["auction", "fcfs", "random", "greedy"],
                       help="Allocation strategy")
    parser.add_argument("--replications", type=int, default=1,
                       help="Number of replications")
    parser.add_argument("--all-scenarios", action="store_true",
                       help="Run all scenario x strategy combinations")
    parser.add_argument("--gui", action="store_true",
                       help="Run with SUMO GUI")
    parser.add_argument("--osm", type=str, default=None,
                       help="OSM road network source: a supported city key "
                            "(kuala_lumpur, penang, johor_bahru) uses the cached network built from that "
                            "city's bounds; any other value is treated as a free-text osmnx place name")
    parser.add_argument("--output-dir", default="output",
                       help="Output directory")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Multi-Agent Parking Simulation")
    print("=" * 60)
    
    # Setup output directories
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, "csv"), exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, "figures"), exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, "tables"), exist_ok=True)
    
    # OSM networks are resolved by ParkingModel.init_sumo below, which reuses
    # cached city data instead of re-querying Overpass for every replication.

    # Run experiments
    if args.all_scenarios:
        print("\nRunning all scenarios x strategies x replications...")
        runner = ExperimentRunner()
        results = runner.run_all(replication_end=args.replications)
        print(f"\nCompleted {len(results)} simulation runs")
    else:
        # Single run
        with open(args.config, 'r') as f:
            config = json.load(f)
        
        if args.scenario:
            with open("config/scenarios.json", 'r') as f:
                scenarios = json.load(f)
            if args.scenario in scenarios["scenarios"]:
                config["demand"]["arrival_rate_lambda"] = scenarios["scenarios"][args.scenario]["arrival_rate_lambda"]
        
        print(f"\nRunning: scenario={args.scenario or 'default'}, strategy={args.strategy}, reps={args.replications}")

        for rep in range(args.replications):
            model = ParkingModel(config_dict=config, strategy=args.strategy, replication_id=rep)
            model.init_sumo(gui=args.gui, osm_place=args.osm)
            model.recorder = FrameRecorder(model)
            results = model.run_simulation()
            
            print(f"  Rep {rep+1}/{args.replications}: "
                  f"PST={results.get('mean_pst', 0):.2f}, "
                  f"RSR={results.get('rsr', 0):.1f}%, "
                  f"POR={results.get('mean_por', 0):.3f}")
    
    print("\n" + "=" * 60)
    print("Simulation complete!")
    print(f"Results saved to: {args.output_dir}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
