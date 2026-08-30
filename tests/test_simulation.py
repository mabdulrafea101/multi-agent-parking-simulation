"""
Unit tests for the parking simulation.
"""
import pytest
import json
import os
import sys
import numpy as np
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.driver_agent import DriverAgent
from agents.parking_spot_agent import ParkingSpotAgent
from agents.coordinator_agent import CoordinatorAgent
from model import ParkingModel
from experiments import ExperimentRunner


def test_refresh_osm_clears_city_cache_once_per_batch(tmp_path, monkeypatch):
    cleared = []
    single_run_kwargs = []

    monkeypatch.setattr(
        "engine.sumo_integration.clear_city_cache",
        lambda city, **kwargs: cleared.append(city),
    )
    monkeypatch.setattr(
        "engine.sumo_integration.ensure_city_network",
        lambda city, **kwargs: str(tmp_path / f"{city}.net.xml"),
    )

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.scenarios_config = {
        "scenarios": {"low_demand": {}, "high_demand": {}},
        "strategies": {"auction": {}},
    }
    runner.results_dir = str(tmp_path)
    runner.figures_dir = str(tmp_path)
    runner.tables_dir = str(tmp_path)

    def fake_run_single(scenario, strategy, rep, **kwargs):
        single_run_kwargs.append(kwargs)
        return {
            "scenario": scenario,
            "strategy": strategy,
            "replication": rep,
            "total_arrivals": 1,
            "total_successful": 1,
            "total_failed": 0,
            "mean_pst": 1.0,
            "std_por": 0.1,
            "rsr": 100.0,
            "mean_utility": 1.0,
            "tfi": 0.0,
            "sumo_connected": True,
            "_timeseries": [],
        }

    runner.run_single = fake_run_single
    runner.save_summary = lambda results: None

    runner.run_batch(
        replication_end=2,
        simulation_type="osm_city",
        city="penang",
        refresh_osm=True,
    )

    assert cleared == ["penang"]
    assert len(single_run_kwargs) == 4
    assert all("refresh_osm" not in kwargs for kwargs in single_run_kwargs)
    assert all(kwargs["net_file"].endswith("penang.net.xml") for kwargs in single_run_kwargs)


def test_city_network_is_prepared_once_before_any_replication(tmp_path, monkeypatch):
    events = []

    monkeypatch.setattr(
        "engine.sumo_integration.ensure_city_network",
        lambda city, **kwargs: events.append(("prepare", city)) or "penang.net.xml",
    )

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.scenarios_config = {
        "scenarios": {"low_demand": {}},
        "strategies": {"auction": {}},
    }
    runner.results_dir = str(tmp_path)
    runner.save_summary = lambda results: None

    def fake_run_single(scenario, strategy, rep, **kwargs):
        events.append(("run", rep))
        return {
            "scenario": scenario,
            "strategy": strategy,
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
            "_timeseries": [],
        }

    runner.run_single = fake_run_single
    runner.run_batch(replication_end=3, simulation_type="osm_city", city="penang")

    assert events == [
        ("prepare", "penang"),
        ("run", 0),
        ("run", 1),
        ("run", 2),
    ]


def test_run_single_row_carries_sumo_instrumentation_columns():
    from experiments import RESULT_COLUMNS

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.base_config = {
        "grid": {"width": 20, "height": 20, "cell_size_meters": 10},
        "parking": {"num_spots": 20, "num_zones": 4, "price_range": [1, 10]},
        "demand": {
            "arrival_rate_lambda": 2,
            "parking_duration_mean_ticks": 8,
            "parking_duration_std_ticks": 2,
            "search_radius_cells": 30,
            "max_search_duration_ticks": 6,
        },
        "simulation": {"total_ticks": 5, "warmup_ticks": 1, "random_seed": 42},
        "strategy": "auction",
    }
    runner.scenarios_config = {"scenarios": {"low_demand": {"arrival_rate_lambda": 2}}}
    runner.base_seed = 42

    row = runner.run_single("low_demand", "auction", 0)

    assert set(RESULT_COLUMNS) <= set(row), set(RESULT_COLUMNS) - set(row)
    assert row["sumo_spawn_edges"] == 0
    assert row["sumo_vehicles_completed"] == 0


def test_summary_min_spawn_edges_ignores_mesa_only_runs():
    runner = ExperimentRunner.__new__(ExperimentRunner)

    def row(connected, spawn_edges):
        return {
            "scenario": "low_demand",
            "strategy": "auction",
            "replication": 0,
            "total_arrivals": 10,
            "total_successful": 10,
            "total_failed": 0,
            "mean_pst": 1.0,
            "std_por": 0.1,
            "rsr": 100.0,
            "mean_utility": 1.0,
            "tfi": 0.1,
            "sumo_connected": connected,
            "sumo_vehicles_completed": 5 if connected else 0,
            "sumo_spawn_edges": spawn_edges,
        }

    summary = runner.compute_summary([row(True, 240), row(True, 239), row(False, 0)])[0]

    assert summary["min_sumo_spawn_edges"] == 239
    assert summary["sumo_connected_runs"] == 2
    # Instrumentation must not leak into aggregate KPI statistics.
    assert "mean_sumo_spawn_edges" not in summary
    assert "mean_sumo_vehicles_completed" not in summary


def test_batch_aborts_when_city_network_cannot_be_prepared(tmp_path, monkeypatch):
    def refuse(city, **kwargs):
        raise RuntimeError(f"Could not prepare the SUMO network for '{city}'")

    monkeypatch.setattr("engine.sumo_integration.ensure_city_network", refuse)

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.scenarios_config = {
        "scenarios": {"low_demand": {}},
        "strategies": {"auction": {}},
    }
    runner.results_dir = str(tmp_path)
    ran = []
    runner.run_single = lambda *args, **kwargs: ran.append(args)

    with pytest.raises(RuntimeError, match="Could not prepare"):
        runner.run_batch(replication_end=3, simulation_type="osm_city", city="penang")

    assert ran == []


def test_batch_keeps_city_cache_when_refresh_not_requested(tmp_path, monkeypatch):
    cleared = []
    monkeypatch.setattr(
        "engine.sumo_integration.clear_city_cache",
        lambda city, **kwargs: cleared.append(city),
    )
    monkeypatch.setattr(
        "engine.sumo_integration.ensure_city_network",
        lambda city, **kwargs: "penang.net.xml",
    )

    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.scenarios_config = {
        "scenarios": {"low_demand": {}},
        "strategies": {"auction": {}},
    }
    runner.results_dir = str(tmp_path)
    runner.save_summary = lambda results: None
    runner.run_single = lambda scenario, strategy, rep, **kwargs: {
        "scenario": scenario,
        "strategy": strategy,
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
        "_timeseries": [],
    }

    runner.run_batch(replication_end=1, simulation_type="osm_city", city="penang")

    assert cleared == []


def test_batch_persists_por_timeseries_for_every_scenario(tmp_path):
    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.scenarios_config = {
        "scenarios": {"low_demand": {}, "high_demand": {}},
        "strategies": {"auction": {}},
    }
    runner.results_dir = str(tmp_path)
    runner.run_single = lambda scenario, strategy, rep, **kwargs: {
        "scenario": scenario,
        "strategy": strategy,
        "replication": rep,
        "total_arrivals": 1,
        "total_successful": 1,
        "total_failed": 0,
        "mean_pst": 1.0,
        "std_por": 0.1,
        "rsr": 100.0,
        "mean_utility": 1.0,
        "tfi": 0.0,
        "sumo_connected": False,
        "_timeseries": [{"scenario": scenario, "strategy": strategy, "replication": rep, "tick": 1, "por": 0.5}],
    }

    callback_rows = []
    runner.run_batch(replication_end=1, progress_callback=lambda **kwargs: callback_rows.append(kwargs["result"]))

    with (tmp_path / "por_timeseries.csv").open(newline="") as file:
        rows = list(csv.DictReader(file))
    assert {row["scenario"] for row in rows} == {"low_demand", "high_demand"}
    assert all(result["_timeseries"] for result in callback_rows)


class TestParkingSpotAgent:
    """Tests for ParkingSpotAgent."""
    
    def test_initialization(self):
        """Test spot agent initializes correctly."""
        from model import ParkingModel
        config = {
            "grid": {"width": 10, "height": 10, "cell_size_meters": 10},
            "parking": {"num_spots": 10, "num_zones": 2, "min_spots_per_zone": 2,
                       "max_spots_per_zone": 8, "price_range": [1, 10]},
            "demand": {"arrival_rate_lambda": 2, "parking_duration_mean_ticks": 20,
                      "parking_duration_std_ticks": 5, "search_radius_cells": 5,
                      "max_search_duration_ticks": 10},
            "simulation": {"total_ticks": 10, "warmup_ticks": 2, "random_seed": 42},
            "strategy": "auction"
        }
        model = ParkingModel(config_dict=config, strategy="auction")
        spot = model.spots[0]
        
        assert spot.is_available() == True
        assert spot.occupied_by is None
        assert spot.price > 0
    
    def test_occupy_vacate(self):
        """Test spot occupation and vacation."""
        config = {
            "grid": {"width": 10, "height": 10, "cell_size_meters": 10},
            "parking": {"num_spots": 10, "num_zones": 2, "min_spots_per_zone": 2,
                       "max_spots_per_zone": 8, "price_range": [1, 10]},
            "demand": {"arrival_rate_lambda": 2, "parking_duration_mean_ticks": 20,
                      "parking_duration_std_ticks": 5, "search_radius_cells": 5,
                      "max_search_duration_ticks": 10},
            "simulation": {"total_ticks": 10, "warmup_ticks": 2, "random_seed": 42},
            "strategy": "auction"
        }
        model = ParkingModel(config_dict=config, strategy="auction")
        spot = model.spots[0]
        
        # Create a mock driver
        class MockDriver:
            unique_id = 9999
        
        driver = MockDriver()
        spot.occupy(driver)
        
        assert spot.is_available() == False
        assert spot.occupied_by == driver
        
        spot.vacate()
        assert spot.is_available() == True
        assert spot.occupied_by is None


class TestDriverAgent:
    """Tests for DriverAgent."""
    
    def test_initialization(self):
        """Test driver agent initializes correctly."""
        config = {
            "grid": {"width": 10, "height": 10, "cell_size_meters": 10},
            "parking": {"num_spots": 10, "num_zones": 2, "min_spots_per_zone": 2,
                       "max_spots_per_zone": 8, "price_range": [1, 10]},
            "demand": {"arrival_rate_lambda": 2, "parking_duration_mean_ticks": 20,
                      "parking_duration_std_ticks": 5, "search_radius_cells": 5,
                      "max_search_duration_ticks": 10},
            "simulation": {"total_ticks": 10, "warmup_ticks": 2, "random_seed": 42},
            "strategy": "auction"
        }
        model = ParkingModel(config_dict=config, strategy="auction")
        
        # Create a driver manually
        dest = (5, 5)
        duration = 20
        weights = [0.33, 0.33, 0.34]
        
        driver = DriverAgent(model, 9999, dest, duration, weights, 0)
        
        assert driver.state == "searching"
        assert driver.search_duration == 0
        assert driver.won_auction == False
    
    def test_utility_computation(self):
        """Test utility function computation."""
        config = {
            "grid": {"width": 10, "height": 10, "cell_size_meters": 10},
            "parking": {"num_spots": 10, "num_zones": 2, "min_spots_per_zone": 2,
                       "max_spots_per_zone": 8, "price_range": [1, 10]},
            "demand": {"arrival_rate_lambda": 2, "parking_duration_mean_ticks": 20,
                      "parking_duration_std_ticks": 5, "search_radius_cells": 5,
                      "max_search_duration_ticks": 10},
            "simulation": {"total_ticks": 10, "warmup_ticks": 2, "random_seed": 42},
            "strategy": "auction"
        }
        model = ParkingModel(config_dict=config, strategy="auction")
        model.config["max_price"] = 10
        
        driver = DriverAgent(model, 9999, (5, 5), 20, [0.33, 0.33, 0.34], 0)
        spot = model.spots[0]
        
        utility = driver.compute_utility(spot)
        assert 0 <= utility <= 1.0
    
    def test_bid_computation(self):
        """Test bid computation."""
        config = {
            "grid": {"width": 10, "height": 10, "cell_size_meters": 10},
            "parking": {"num_spots": 10, "num_zones": 2, "min_spots_per_zone": 2,
                       "max_spots_per_zone": 8, "price_range": [1, 10]},
            "demand": {"arrival_rate_lambda": 2, "parking_duration_mean_ticks": 20,
                      "parking_duration_std_ticks": 5, "search_radius_cells": 5,
                      "max_search_duration_ticks": 10},
            "simulation": {"total_ticks": 10, "warmup_ticks": 2, "random_seed": 42},
            "strategy": "auction"
        }
        model = ParkingModel(config_dict=config, strategy="auction")
        model.config["max_price"] = 10
        
        driver = DriverAgent(model, 9999, (5, 5), 20, [0.33, 0.33, 0.34], 0)
        spot = model.spots[0]
        
        bid = driver.compute_bid(spot)
        assert bid >= 0


class TestCoordinatorAgent:
    """Tests for CoordinatorAgent."""
    
    def test_spot_registration(self):
        """Test spot registration."""
        config = {
            "grid": {"width": 10, "height": 10, "cell_size_meters": 10},
            "parking": {"num_spots": 10, "num_zones": 2, "min_spots_per_zone": 2,
                       "max_spots_per_zone": 8, "price_range": [1, 10]},
            "demand": {"arrival_rate_lambda": 2, "parking_duration_mean_ticks": 20,
                      "parking_duration_std_ticks": 5, "search_radius_cells": 5,
                      "max_search_duration_ticks": 10},
            "simulation": {"total_ticks": 10, "warmup_ticks": 2, "random_seed": 42},
            "strategy": "auction"
        }
        model = ParkingModel(config_dict=config, strategy="auction")
        
        assert len(model.coordinator.registered_spots) == len(model.spots)
    
    def test_query_spots(self):
        """Test spot querying within radius."""
        config = {
            "grid": {"width": 10, "height": 10, "cell_size_meters": 10},
            "parking": {"num_spots": 10, "num_zones": 2, "min_spots_per_zone": 2,
                       "max_spots_per_zone": 8, "price_range": [1, 10]},
            "demand": {"arrival_rate_lambda": 2, "parking_duration_mean_ticks": 20,
                      "parking_duration_std_ticks": 5, "search_radius_cells": 5,
                      "max_search_duration_ticks": 10},
            "simulation": {"total_ticks": 10, "warmup_ticks": 2, "random_seed": 42},
            "strategy": "auction"
        }
        model = ParkingModel(config_dict=config, strategy="auction")
        
        # Query from center
        spots = model.coordinator.query_spots((5, 5), 10)
        assert len(spots) > 0


class TestParkingModel:
    """Tests for ParkingModel."""
    
    def test_model_initialization(self):
        """Test model initializes correctly."""
        config = {
            "grid": {"width": 20, "height": 20, "cell_size_meters": 10},
            "parking": {"num_spots": 20, "num_zones": 4, "min_spots_per_zone": 2,
                       "max_spots_per_zone": 8, "price_range": [1, 10]},
            "demand": {"arrival_rate_lambda": 2, "parking_duration_mean_ticks": 20,
                      "parking_duration_std_ticks": 5, "search_radius_cells": 5,
                      "max_search_duration_ticks": 10},
            "simulation": {"total_ticks": 50, "warmup_ticks": 5, "random_seed": 42},
            "strategy": "auction"
        }
        model = ParkingModel(config_dict=config, strategy="auction")
        
        assert len(model.spots) == 20
        assert model.coordinator is not None
        assert model.width == 20
        assert model.height == 20
    
    def test_single_step(self):
        """Test single simulation step."""
        config = {
            "grid": {"width": 20, "height": 20, "cell_size_meters": 10},
            "parking": {"num_spots": 20, "num_zones": 4, "min_spots_per_zone": 2,
                       "max_spots_per_zone": 8, "price_range": [1, 10]},
            "demand": {"arrival_rate_lambda": 2, "parking_duration_mean_ticks": 20,
                      "parking_duration_std_ticks": 5, "search_radius_cells": 5,
                      "max_search_duration_ticks": 10},
            "simulation": {"total_ticks": 50, "warmup_ticks": 5, "random_seed": 42},
            "strategy": "auction"
        }
        model = ParkingModel(config_dict=config, strategy="auction")
        model.step()
        
        assert model.steps == 1
        assert len(model.kpi_data["tick"]) == 1
    
    def test_full_simulation(self):
        """Test full simulation run."""
        config = {
            "grid": {"width": 20, "height": 20, "cell_size_meters": 10},
            "parking": {"num_spots": 20, "num_zones": 4, "min_spots_per_zone": 2,
                       "max_spots_per_zone": 8, "price_range": [1, 10]},
            "demand": {"arrival_rate_lambda": 2, "parking_duration_mean_ticks": 20,
                      "parking_duration_std_ticks": 5, "search_radius_cells": 5,
                      "max_search_duration_ticks": 10},
            "simulation": {"total_ticks": 50, "warmup_ticks": 5, "random_seed": 42},
            "strategy": "auction"
        }
        model = ParkingModel(config_dict=config, strategy="auction")
        results = model.run_simulation()
        
        assert "mean_pst" in results
        assert "rsr" in results
        assert "mean_por" in results
        assert results["total_arrivals"] > 0
    
    def test_all_strategies(self):
        """Test that all four strategies work."""
        config = {
            "grid": {"width": 20, "height": 20, "cell_size_meters": 10},
            "parking": {"num_spots": 20, "num_zones": 4, "min_spots_per_zone": 2,
                       "max_spots_per_zone": 8, "price_range": [1, 10]},
            "demand": {"arrival_rate_lambda": 2, "parking_duration_mean_ticks": 20,
                      "parking_duration_std_ticks": 5, "search_radius_cells": 5,
                      "max_search_duration_ticks": 10},
            "simulation": {"total_ticks": 30, "warmup_ticks": 5, "random_seed": 42},
            "strategy": "auction"
        }
        
        for strategy in ["auction", "fcfs", "random", "greedy"]:
            model = ParkingModel(config_dict=config, strategy=strategy)
            results = model.run_simulation()
            assert results["strategy"] == strategy
            assert results["total_arrivals"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
