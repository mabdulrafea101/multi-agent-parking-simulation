"""Focused tests for ParkingModel behavior."""
import copy

from model import ParkingModel


def small_config(arrival_rate=3, total_ticks=12):
    return {
        "grid": {"width": 20, "height": 20, "cell_size_meters": 10},
        "parking": {
            "num_spots": 20,
            "num_zones": 4,
            "min_spots_per_zone": 2,
            "max_spots_per_zone": 8,
            "price_range": [1, 10],
        },
        "demand": {
            "arrival_rate_lambda": arrival_rate,
            "parking_duration_mean_ticks": 8,
            "parking_duration_std_ticks": 2,
            "search_radius_cells": 30,
            "max_search_duration_ticks": 6,
        },
        "simulation": {
            "total_ticks": total_ticks,
            "warmup_ticks": 1,
            "random_seed": 42,
        },
        "strategy": "auction",
    }


def test_parking_model_init():
    model = ParkingModel(config_dict=small_config(), strategy="auction")

    assert model.width == 20
    assert model.height == 20
    assert model.strategy == "auction"
    assert model.total_ticks == 12
    assert model.total_arrivals == 0


def test_spot_creation():
    model = ParkingModel(config_dict=small_config(), strategy="auction")

    assert len(model.spots) == 20
    assert len(model.coordinator.registered_spots) == 20
    assert all(0 <= spot.pos[0] < model.width for spot in model.spots)
    assert all(0 <= spot.pos[1] < model.height for spot in model.spots)


def test_driver_spawning():
    model = ParkingModel(config_dict=small_config(arrival_rate=0), strategy="auction")
    model._spawn_driver()

    assert model.total_arrivals == 1
    assert len(model.drivers) == 1
    assert model.drivers[0].state == "searching"


def test_single_step_collects_kpis():
    model = ParkingModel(config_dict=small_config(arrival_rate=2), strategy="auction")
    model.step()

    assert model.steps == 1
    assert len(model.kpi_data["tick"]) == 1
    assert model.total_arrivals >= 0


def test_full_simulation_all_strategies():
    for strategy in ["auction", "fcfs", "random", "greedy"]:
        config = copy.deepcopy(small_config(arrival_rate=2, total_ticks=15))
        model = ParkingModel(config_dict=config, strategy=strategy)
        results = model.run_simulation()

        assert results["strategy"] == strategy
        assert results["total_arrivals"] > 0
        assert "mean_pst" in results
        assert "rsr" in results


def test_results_computation():
    model = ParkingModel(config_dict=small_config(arrival_rate=2, total_ticks=15), strategy="greedy")
    results = model.run_simulation()

    assert results["total_arrivals"] == model.total_arrivals
    assert results["total_successful"] == model.total_success
    assert results["total_failed"] == model.total_failed
    assert 0 <= results["mean_por"] <= 1
    assert 0 <= results["rsr"] <= 100
    assert isinstance(results["sumo_connected"], bool)
