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
