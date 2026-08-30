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


class FakeEdge:
    def __init__(self, edge_id, shape=(), lanes=1, passenger=True):
        self.edge_id = edge_id
        self.shape = list(shape)
        self.lanes = lanes
        self.passenger = passenger

    def getID(self):
        return self.edge_id

    def getShape(self):
        return self.shape

    def getLaneNumber(self):
        return self.lanes

    def allows(self, vehicle_class):
        return self.passenger and vehicle_class == "passenger"


class FakeNetwork:
    def __init__(self, edges, boundary=(0.0, 0.0, 100.0, 100.0)):
        self.edges = list(edges)
        self.boundary = boundary

    def getEdges(self):
        return self.edges

    def getBoundary(self):
        return self.boundary


def test_drivable_edges_keeps_only_car_legal_edges():
    integration = SUMOIntegration({})
    integration.network = FakeNetwork([
        FakeEdge("road", lanes=1, passenger=True),
        FakeEdge("footway", lanes=1, passenger=False),
        FakeEdge("no_lane", lanes=0, passenger=True),
    ])

    assert [edge.getID() for edge in integration.drivable_edges()] == ["road"]


def test_drivable_edges_is_cached_per_network():
    calls = []

    class CountingNetwork(FakeNetwork):
        def getEdges(self):
            calls.append(1)
            return self.edges

    integration = SUMOIntegration({})
    integration.network = CountingNetwork([FakeEdge("road")])

    integration.drivable_edges()
    integration.drivable_edges()

    assert len(calls) == 1


def test_pos_to_edge_id_prefers_car_legal_edge_over_nearer_footway():
    footway = FakeEdge("footway", shape=[(1, 1)], passenger=False)
    road = FakeEdge("road", shape=[(9, 9)])
    integration = SUMOIntegration({})
    integration.network = FakeNetwork([footway, road])

    model = ParkingModel(config_dict=small_config(arrival_rate=0), strategy="auction")
    model.sumo = integration
    model.use_sumo = True

    assert model._pos_to_edge_id((1, 1)) == "road"
    assert model._edge_by_pos[(1, 1)] == "road"


def test_nearest_edge_id_ignores_pedestrian_edges():
    from engine.sumo_integration import OSMCityIntegration

    class LonLatNetwork(FakeNetwork):
        def convertLonLat2XY(self, lon, lat):
            return lon, lat

    integration = OSMCityIntegration(city_name="penang")
    integration.network = LonLatNetwork([
        FakeEdge("footway", shape=[(0.1, 0.1)], passenger=False),
        FakeEdge("road", shape=[(0.9, 0.9)]),
    ])

    assert integration._nearest_edge_id(0.0, 0.0) == "road"


def test_network_file_is_parsed_once_across_replications(monkeypatch, tmp_path):
    reads = []

    class CountingNet:
        @staticmethod
        def readNet(path):
            reads.append(path)
            return {"path": path}

    net_file = tmp_path / "city.net.xml"
    net_file.write_text("<net></net>")
    monkeypatch.setattr("engine.sumo_integration.sumolib.net", CountingNet)

    first = SUMOIntegration({})
    second = SUMOIntegration({})
    first.load_network(str(net_file))
    second.load_network(str(net_file))

    assert reads == [os.path.abspath(str(net_file))]
    assert first.network is second.network


def test_ensure_city_network_returns_the_prepared_file(monkeypatch):
    from engine.sumo_integration import OSMCityIntegration, ensure_city_network

    monkeypatch.setattr(
        OSMCityIntegration,
        "prepare_city_network",
        lambda self, name, **kwargs: f"{name}.net.xml",
    )

    assert ensure_city_network("penang") == "penang.net.xml"


def test_ensure_city_network_retries_then_aborts_the_batch(monkeypatch):
    from engine.sumo_integration import OSMCityIntegration, ensure_city_network

    attempts = []
    slept = []

    def fail(self, name, **kwargs):
        attempts.append(name)
        return None

    monkeypatch.setattr(OSMCityIntegration, "prepare_city_network", fail)
    monkeypatch.setattr("engine.sumo_integration.time.sleep", lambda seconds: slept.append(seconds))

    with pytest.raises(RuntimeError, match="after 3 attempts"):
        ensure_city_network("penang")

    assert attempts == ["penang", "penang", "penang"]
    assert slept == [5, 10]


def test_wheel_site_packages_covers_posix_venv_layout(tmp_path):
    from engine.sumo_integration import _wheel_site_packages

    posix_packages = tmp_path / "venv" / "lib" / "python3.12" / "site-packages"
    posix_packages.mkdir(parents=True)

    candidates = _wheel_site_packages(str(tmp_path))

    assert os.path.join(str(posix_packages)) in candidates
    assert os.path.join(str(tmp_path), "venv", "Lib", "site-packages") in candidates


def test_init_sumo_with_prepared_net_file_never_fetches(monkeypatch, tmp_path):
    city_dir = tmp_path / "output" / "sumo" / CITY
    city_dir.mkdir(parents=True)
    net_file = city_dir / f"{CITY}.net.xml"
    net_file.write_text("<net></net>")

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("a batch-prepared network must never be re-downloaded")

    def fail_run(*args, **kwargs):
        raise AssertionError("a batch-prepared network must never be rebuilt")

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
    model.init_sumo(osm_place=model.city, net_file=str(net_file))

    assert started == [str(net_file)]
    assert model.sumo.network == {"path": os.path.abspath(str(net_file))}


def model_with_network(edges, boundary):
    integration = SUMOIntegration({})
    integration.network = FakeNetwork(edges, boundary)
    model = ParkingModel(config_dict=small_config(arrival_rate=0), strategy="auction")
    model.sumo = integration
    model.use_sumo = True
    return model


def test_pos_to_edge_id_spans_the_whole_city_network():
    """The old hardcoded 20-cell assumption confined every spawn to 0-200 m."""
    south_west = FakeEdge("south_west", shape=[(10.0, 10.0)])
    north_east = FakeEdge("north_east", shape=[(4900.0, 4900.0)])
    model = model_with_network([south_west, north_east], (0.0, 0.0, 5000.0, 5000.0))

    assert model._pos_to_edge_id((19, 0)) == "north_east"
    assert model._pos_to_edge_id((0, 19)) == "south_west"


def test_pos_to_edge_id_respects_north_south_orientation():
    north = FakeEdge("north", shape=[(50.0, 4950.0)])
    south = FakeEdge("south", shape=[(50.0, 50.0)])
    model = model_with_network([north, south], (0.0, 0.0, 5000.0, 5000.0))

    assert model._pos_to_edge_id((9, 0)) == "north"
    assert model._pos_to_edge_id((9, 19)) == "south"


def test_pos_to_edge_id_returns_none_for_a_degenerate_network():
    model = model_with_network(
        [FakeEdge("road", shape=[(5.0, 5.0)])], (0.0, 0.0, 0.0, 0.0)
    )

    assert model._pos_to_edge_id((1, 1)) is None


def test_projection_rebuilds_when_the_network_changes():
    model = model_with_network(
        [FakeEdge("old", shape=[(90.0, 10.0)])], (0.0, 0.0, 100.0, 100.0)
    )
    assert model._pos_to_edge_id((9, 9)) == "old"

    model.sumo.network = FakeNetwork(
        [FakeEdge("new", shape=[(95.0, 95.0)])], (0.0, 0.0, 1000.0, 1000.0)
    )

    assert model._pos_to_edge_id((9, 9)) == "new"


def test_mapping_diagnostics_report_extent_and_car_legal_share(capsys):
    model = model_with_network(
        [
            FakeEdge("road", shape=[(10.0, 10.0)]),
            FakeEdge("walk", shape=[(20.0, 20.0)], passenger=False),
        ],
        (0.0, 0.0, 500.0, 400.0),
    )

    model._describe_network_mapping()

    printed = capsys.readouterr().out
    assert "network extent 500x400 m" in printed
    assert "1 of 2 edges take cars" in printed


def test_mapping_diagnostics_never_break_on_a_network_stub(capsys):
    model = ParkingModel(config_dict=small_config(arrival_rate=0), strategy="auction")
    model.sumo = SUMOIntegration({})
    model.sumo.network = {"path": "somewhere"}

    model._describe_network_mapping()

    assert capsys.readouterr().out == ""


def test_spawn_edge_spread_is_reported_after_a_sumo_run(capsys):
    model = model_with_network(
        [FakeEdge("a", shape=[(10.0, 10.0)]), FakeEdge("b", shape=[(90.0, 90.0)])],
        (0.0, 0.0, 100.0, 100.0),
    )
    model._pos_to_edge_id((0, 19))
    model._pos_to_edge_id((19, 0))
    capsys.readouterr()

    model.get_results()

    assert "spawn mapping used 2 distinct edges across 2 mapped cells" in (
        capsys.readouterr().out
    )


CACHED_CITY_NET = os.path.join("output", "sumo", "kuala_lumpur", "kuala_lumpur.net.xml")


def _random_stream(model, run_mapping):
    """Draw the same seeded numbers, optionally doing mapping work in between."""
    import random

    import numpy as np

    random.seed(1234)
    np.random.seed(1234)
    head = [random.random(), float(np.random.random())]
    if run_mapping:
        for gx in range(20):
            for gy in range(20):
                model._pos_to_edge_id((gx, gy))
    tail = [random.random(), float(np.random.random())]
    return head + tail


def test_spawn_mapping_consumes_no_randomness():
    """Headline KPIs stay bit-identical only because this path draws no numbers."""
    # The model is built before the seeded window: spot creation legitimately
    # consumes randomness in both cases.
    model = model_with_network(
        [FakeEdge("a", shape=[(10.0, 10.0)]), FakeEdge("b", shape=[(90.0, 90.0)])],
        (0.0, 0.0, 100.0, 100.0),
    )

    assert _random_stream(model, run_mapping=False) == _random_stream(
        model, run_mapping=True
    )


@pytest.mark.skipif(not os.path.isfile(CACHED_CITY_NET), reason="no cached city network")
def test_projection_reaches_the_whole_cached_city_network():
    import sumolib

    from engine.geometry import GridProjection

    net = sumolib.net.readNet(CACHED_CITY_NET)
    model = ParkingModel(config_dict=small_config(arrival_rate=0), strategy="auction")
    model.sumo = SUMOIntegration({})
    model.sumo.network = net
    model.use_sumo = True

    xmin, ymin, xmax, ymax = net.getBoundary()
    projection = GridProjection.from_net(net)
    used = set()
    for gx in range(0, model.width, 3):
        for gy in range(0, model.height, 3):
            px, py = projection.cell_to_xy(gx, gy, model.width, model.height)
            assert xmin <= px <= xmax and ymin <= py <= ymax
            edge_id = model._pos_to_edge_id((gx, gy))
            assert edge_id is not None
            used.add(edge_id)

    # The collapsed 0-200 m mapping reached 2 edges on this network.
    assert len(used) >= 20
