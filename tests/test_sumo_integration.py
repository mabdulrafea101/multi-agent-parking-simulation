"""Tests for SUMO integration and Mesa-only fallback."""
import os
import subprocess
from pathlib import Path

import pytest

from engine.sumo_integration import SUMOIntegration, _sumo_bin
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


def test_mesa_only_fallback(monkeypatch, tmp_path):
    def fake_create_network(self):
        return str(tmp_path / "output" / "sumo" / "fake.net.xml")

    def fake_start_sumo(self, net_file, gui=False, port=8813):
        return False

    monkeypatch.setattr(SUMOIntegration, "create_synthetic_network", fake_create_network)
    monkeypatch.setattr(SUMOIntegration, "start_sumo", fake_start_sumo)
    monkeypatch.chdir(tmp_path)

    model = ParkingModel(config_dict=small_config(arrival_rate=1, total_ticks=3), strategy="auction")
    model.init_sumo()
    results = model.run_simulation()

    assert model.use_sumo is False
    assert model.simulation_type == "mesa"
    assert results["sumo_connected"] is False
    assert results["total_arrivals"] >= 0


def test_real_netconvert_converts_minimal_osm_fixture(tmp_path):
    osm_file = Path(__file__).parent / "fixtures" / "minimal.osm.xml"
    net_file = tmp_path / "minimal.net.xml"
    netconvert = _sumo_bin("netconvert")

    if not os.path.isfile(netconvert):
        pytest.skip(f"SUMO netconvert unavailable at {netconvert}")

    command = [
        netconvert,
        "--osm-files", str(osm_file),
        "--output-file", str(net_file),
        "--geometry.remove",
        "--roundabouts.guess",
        "--ramps.guess",
        "--junctions.join",
        "--tls.guess-signals",
        "--tls.join",
        "--no-turnarounds",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    print(f"REAL NETCONVERT COMMAND: {' '.join(command)}")
    print(f"REAL NETCONVERT STDOUT: {result.stdout}")
    print(f"REAL NETCONVERT STDERR: {result.stderr}")

    assert result.returncode == 0, result.stderr
    assert net_file.is_file()
    assert net_file.stat().st_size > 0

    try:
        import sumolib
    except ImportError:
        sumolib = None
    if sumolib is not None:
        network = sumolib.net.readNet(str(net_file))
        assert network.getEdges()


def test_city_initialization_passes_exported_osm_xml_to_netconvert(
    monkeypatch, tmp_path
):
    commands = []

    class FakeOSM:
        def download_area(self, place_name):
            return {"place": place_name}

        def export_to_sumo(self, output_path):
            with open(output_path, "w") as osm_file:
                osm_file.write("<osm version='0.6'></osm>")
            return output_path

    def fake_run(cmd, capture_output=True, text=True, check=False):
        commands.append(cmd)
        net_file = cmd[cmd.index("--output-file") + 1]
        with open(net_file, "w") as network_file:
            network_file.write("<net></net>")

        class Result:
            returncode = 0
            stderr = ""

        return Result()

    class FakeSumoLibNet:
        @staticmethod
        def readNet(path):
            return {"path": path}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("model.OSMIntegration", FakeOSM)
    monkeypatch.setattr("engine.sumo_integration.subprocess.run", fake_run)
    monkeypatch.setattr("engine.sumo_integration.sumolib.net", FakeSumoLibNet)
    monkeypatch.setattr(SUMOIntegration, "start_sumo", lambda *args, **kwargs: False)

    model = ParkingModel(
        config_dict=small_config(arrival_rate=0),
        strategy="auction",
        simulation_type="osm_city",
        city="johor_bahru",
    )
    model.init_sumo(osm_place=model.city)

    assert len(commands) == 1
    osm_file = commands[0][commands[0].index("--osm-files") + 1]
    assert osm_file.endswith(".osm.xml")
    assert osm_file != "johor_bahru"
    assert os.path.exists(osm_file)


def test_city_initialization_uses_synthetic_network_when_osm_export_fails(
    monkeypatch, capsys, tmp_path
):
    class FakeOSM:
        def download_area(self, place_name):
            return {"place": place_name}

        def export_to_sumo(self, output_path):
            return None

    synthetic_file = str(tmp_path / "output" / "sumo" / "synthetic.net.xml")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("model.OSMIntegration", FakeOSM)
    monkeypatch.setattr(SUMOIntegration, "create_synthetic_network", lambda self: synthetic_file)
    monkeypatch.setattr(SUMOIntegration, "start_sumo", lambda *args, **kwargs: False)

    model = ParkingModel(
        config_dict=small_config(arrival_rate=0),
        strategy="auction",
        simulation_type="osm_city",
        city="johor_bahru",
    )
    model.init_sumo(osm_place=model.city)

    assert model._sumo_net_file == synthetic_file
    assert "OSM export failed" in capsys.readouterr().out
