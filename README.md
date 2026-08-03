# Multi-Agent Parking Simulation

## Overview
Tier 2 simulation framework for intelligent urban parking allocation using:
- **Mesa 3.5.1** — Agent-based modeling
- **SUMO** — Microscopic traffic simulation (via TraCI)
- **OpenStreetMap** — Real road network data (via OSMnx)

## Project Structure
```
simulation/
├── config/
│   ├── default_params.json    # Default simulation parameters
│   └── scenarios.json         # Demand scenarios and strategies
├── agents/
│   ├── __init__.py
│   ├── driver_agent.py        # Driver agent with FSM
│   ├── parking_spot_agent.py  # Parking spot agent
│   └── coordinator_agent.py   # Auction coordinator
├── engine/
│   ├── sumo_integration.py    # SUMO + OSM integration
├── output/
│   ├── csv/                   # Raw simulation results
│   ├── figures/               # Generated plots
│   └── tables/                # Generated tables
├── tests/
│   ├── __init__.py
│   └── test_simulation.py     # Unit tests
├── model.py                   # Main ParkingModel class
├── experiments.py             # Batch experiment runner
├── analysis.py                # Results analysis and visualization
└── main.py                    # Entry point
```

## Quick Start

### Install Dependencies
```bash
pip install mesa osmnx traci sumolib numpy pandas matplotlib scipy pytest
```

### Run Single Simulation
```bash
cd simulation
python main.py --strategy auction --replications 1
```

### Run All Experiments (480 runs)
```bash
python main.py --all-scenarios --replications 30
```

### Run Tests
```bash
cd simulation
pytest tests/ -v
```

### Use OpenStreetMap Data
```bash
python main.py --osm "Kuala Lumpur, Malaysia" --strategy auction
```

## Configuration
Edit `config/default_params.json` to modify:
- Grid size, parking spots, zones
- Arrival rate, parking duration
- Simulation ticks, warmup period

Edit `config/scenarios.json` to modify:
- Demand scenarios (low/medium/high/peak)
- Allocation strategies (auction/fcfs/random/greedy)
- Number of replications

## Output
- **CSV files**: Per-replication and aggregated results
- **Figures**: KPI comparison plots, time series, box plots
- **Tables**: Summary statistics, statistical test results

## KPIs
1. Parking Search Time (PST)
2. Parking Occupancy Rate (POR)
3. Reservation Success Rate (RSR)
4. Average Agent Utility
5. Traffic Flow Impact (TFI)
