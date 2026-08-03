"""Tests for SUMO integration and Mesa-only fallback."""
import os

from engine.sumo_integration import SUMOIntegration
from model import ParkingModel
from tests.test_model import small_config


def test_sumo_integration_init():
    config = small_config(arrival_rate=0)
    integration = SUMOIntegration(config)

    assert integration.config is config
    assert integration.connected is False
    assert integration.network is None


def test_synthetic_network_creation(monkeypatch, tmp_path):
    def fake_run(cmd, capture_output=True, text=True):
        net_file = cmd[cmd.index("--output-file") + 1]
        with open(net_file, "w") as f:
            f.write("<net></net>")

        class Result:
            returncode = 0
            stderr = ""

        return Result()

    class FakeSumoLibNet:
        @staticmethod
        def readNet(path):
            return {"path": path}

    monkeypatch.setattr("engine.sumo_integration.subprocess.run", fake_run)
    monkeypatch.setattr("engine.sumo_integration.sumolib.net", FakeSumoLibNet)

    integration = SUMOIntegration(small_config(arrival_rate=0))
    net_file = integration.create_synthetic_network(output_dir=str(tmp_path))

    assert net_file is not None
    assert os.path.exists(net_file)
    assert integration.network == {"path": net_file}


def test_mesa_only_fallback(monkeypatch):
    def fake_create_network(self):
        return "output/sumo/fake.net.xml"

    def fake_start_sumo(self, net_file, gui=False):
        return False

    monkeypatch.setattr(SUMOIntegration, "create_synthetic_network", fake_create_network)
    monkeypatch.setattr(SUMOIntegration, "start_sumo", fake_start_sumo)

    model = ParkingModel(config_dict=small_config(arrival_rate=1, total_ticks=3), strategy="auction")
    model.init_sumo()
    results = model.run_simulation()

    assert model.use_sumo is False
    assert results["sumo_connected"] is False
    assert results["total_arrivals"] >= 0
