"""Tests for SUMO integration and Mesa-only fallback."""
import os
import subprocess
from pathlib import Path

import pytest

from engine.sumo_integration import SUMOIntegration, _sumo_bin, clear_city_cache
from model import ParkingModel
from tests.test_model import small_config


CITY = "johor_bahru"


class FakeOverpassResponse:
    """Stand-in for the urlopen() context manager used by download_osm()."""

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeNet:
    @staticmethod
    def readNet(path):
        return {"path": path}


def fake_netconvert(commands):
    def run(cmd, capture_output=True, text=True, check=False):
        commands.append(cmd)
        net_file = cmd[cmd.index("--output-file") + 1]
        with open(net_file, "w") as network_file:
            network_file.write("<net></net>")

        class Result:
            returncode = 0
            stderr = ""

        return Result()

    return run


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


def test_city_initialization_passes_cached_osm_xml_to_netconvert(
    monkeypatch, tmp_path
):
    requests = []
    commands = []

    def fake_urlopen(request, timeout=None):
        requests.append(request)
        return FakeOverpassResponse(b"<osm version='0.6'></osm>")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("engine.sumo_integration.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("engine.sumo_integration.subprocess.run", fake_netconvert(commands))
    monkeypatch.setattr("engine.sumo_integration.sumolib.net", FakeNet)
    monkeypatch.setattr(SUMOIntegration, "start_sumo", lambda *args, **kwargs: False)

    model = ParkingModel(
        config_dict=small_config(arrival_rate=0),
        strategy="auction",
        simulation_type="osm_city",
        city=CITY,
    )
    model.init_sumo(osm_place=model.city)

    assert len(requests) == 1
    assert len(commands) == 1
    city_dir = (tmp_path / "output" / "sumo" / CITY).resolve()
    osm_file = Path(commands[0][commands[0].index("--osm-files") + 1]).resolve()
    net_file = Path(commands[0][commands[0].index("--output-file") + 1]).resolve()
    assert osm_file == city_dir / f"{CITY}.osm.xml"
    assert net_file == city_dir / f"{CITY}.net.xml"
    assert os.path.exists(osm_file)


def test_city_initialization_reuses_cached_network_without_redownloading(
    monkeypatch, tmp_path
):
    city_dir = tmp_path / "output" / "sumo" / CITY
    city_dir.mkdir(parents=True)
    osm_file = city_dir / f"{CITY}.osm.xml"
    osm_file.write_text("<osm version='0.6'></osm>")
    net_file = city_dir / f"{CITY}.net.xml"
    net_file.write_text("<net></net>")
    fresher = os.path.getmtime(osm_file) + 60
    os.utime(net_file, (fresher, fresher))

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("Overpass must not be queried when the OSM cache is warm")

    def fail_run(*args, **kwargs):
        raise AssertionError("netconvert must not run when the cached network is fresh")

    started = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("engine.sumo_integration.urllib.request.urlopen", fail_urlopen)
    monkeypatch.setattr("engine.sumo_integration.subprocess.run", fail_run)
    monkeypatch.setattr("engine.sumo_integration.sumolib.net", FakeNet)
    monkeypatch.setattr(
        SUMOIntegration,
        "start_sumo",
        lambda self, net, gui=False, port=8813: started.append(net) or False,
    )

    model = ParkingModel(
        config_dict=small_config(arrival_rate=0),
        strategy="auction",
        simulation_type="osm_city",
        city=CITY,
    )
    model.init_sumo(osm_place=model.city)
    model.init_sumo(osm_place=model.city)

    cached_net = os.path.normpath(os.path.join("output", "sumo", CITY, f"{CITY}.net.xml"))
    assert [os.path.normpath(net) for net in started] == [cached_net] * 2
    assert os.path.normpath(model._sumo_net_file) == cached_net


def test_city_initialization_uses_synthetic_network_when_download_fails(
    monkeypatch, capsys, tmp_path
):
    import urllib.error

    def fail_urlopen(*args, **kwargs):
        raise urllib.error.URLError("Overpass unreachable")

    def fail_run(*args, **kwargs):
        raise AssertionError("netconvert must not run when there is no OSM file")

    synthetic_file = str(tmp_path / "output" / "sumo" / "synthetic.net.xml")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("engine.sumo_integration.urllib.request.urlopen", fail_urlopen)
    monkeypatch.setattr("engine.sumo_integration.subprocess.run", fail_run)
    monkeypatch.setattr(SUMOIntegration, "create_synthetic_network", lambda self: synthetic_file)
    monkeypatch.setattr(SUMOIntegration, "start_sumo", lambda *args, **kwargs: False)

    model = ParkingModel(
        config_dict=small_config(arrival_rate=0),
        strategy="auction",
        simulation_type="osm_city",
        city=CITY,
    )
    model.init_sumo(osm_place=model.city)

    assert model._sumo_net_file == synthetic_file
    assert "City network unavailable" in capsys.readouterr().out


def test_unsupported_place_falls_back_to_osmnx_place_download(monkeypatch, tmp_path):
    downloaded = []

    class FakeOSM:
        def download_area(self, place_name):
            downloaded.append(place_name)
            return {"place": place_name}

        def export_to_sumo(self, output_path):
            with open(output_path, "w") as osm_file:
                osm_file.write("<osm version='0.6'></osm>")
            return output_path

    commands = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("model.OSMIntegration", FakeOSM)
    monkeypatch.setattr("engine.sumo_integration.subprocess.run", fake_netconvert(commands))
    monkeypatch.setattr("engine.sumo_integration.sumolib.net", FakeNet)
    monkeypatch.setattr(SUMOIntegration, "start_sumo", lambda *args, **kwargs: False)

    model = ParkingModel(
        config_dict=small_config(arrival_rate=0),
        strategy="auction",
        simulation_type="osm_city",
        city="Melbourne, Australia",
    )
    model.init_sumo(osm_place=model.city)

    assert downloaded == ["Melbourne, Australia"]
    assert len(commands) == 1


def test_clear_city_cache_removes_only_cached_network_artifacts(tmp_path):
    output_dir = tmp_path / "output" / "sumo"
    city_dir = output_dir / "penang"
    city_dir.mkdir(parents=True)
    osm_file = city_dir / "penang.osm.xml"
    net_file = city_dir / "penang.net.xml"
    keep = city_dir / "traci_config.sumocfg"
    for path in (osm_file, net_file, keep):
        path.write_text("content")

    removed = clear_city_cache("penang", output_dir=str(output_dir))

    assert {Path(path).name for path in removed} == {"penang.osm.xml", "penang.net.xml"}
    assert not osm_file.exists()
    assert not net_file.exists()
    assert keep.exists()


def test_clear_city_cache_is_safe_when_nothing_is_cached(tmp_path):
    output_dir = tmp_path / "output" / "sumo"

    assert clear_city_cache("penang", output_dir=str(output_dir)) == []


def test_osm_download_uses_simplify_false(monkeypatch):
    class FakeGraph:
        def nodes(self, data=True):
            return []

    called_with = {}

    def fake_graph_from_place(place_name, network_type="drive", **kwargs):
        called_with["place_name"] = place_name
        called_with["network_type"] = network_type
        called_with["kwargs"] = kwargs
        return FakeGraph()

    monkeypatch.setattr("osmnx.graph_from_place", fake_graph_from_place)

    from engine.sumo_integration import OSMIntegration
    osm = OSMIntegration()
    osm.download_area("test_place")

    assert called_with["place_name"] == "test_place"
    assert called_with["kwargs"].get("simplify") is False
