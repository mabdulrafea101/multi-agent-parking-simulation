"""
SUMO Integration Module for Parking Simulation.
Uses TraCI (Traffic Control Interface) to connect Mesa agents with SUMO traffic simulation.
"""
import os
import subprocess
import urllib.parse
import urllib.request
try:
    import traci
    import sumolib
except ImportError:
    traci = None
    sumolib = None

from engine.cities import get_city_config

SUMO_HOME_DEFAULT = "/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo"


def _sumo_bin(name):
    """Return full path to a SUMO binary, ensuring env is set."""
    sumo_home = os.environ.get("SUMO_HOME", SUMO_HOME_DEFAULT)
    bin_dir = os.path.join(sumo_home, "bin")
    # Make sure subprocesses can find SUMO tools
    os.environ["SUMO_HOME"] = sumo_home
    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
    _ensure_proj_lib()
    return os.path.join(bin_dir, name)


def _ensure_proj_lib():
    """Set PROJ_DATA and PROJ_LIB so SUMO can find proj.db on any platform."""
    if "PROJ_LIB" in os.environ or "PROJ_DATA" in os.environ:
        return
    try:
        import pyproj
        data_dir = pyproj.datadir.get_data_dir()
        os.environ["PROJ_DATA"] = data_dir
        os.environ["PROJ_LIB"] = os.path.dirname(data_dir)
    except Exception:
        pass


class SUMOIntegration:
    """Manages SUMO simulation and connection to Mesa model via TraCI."""

    def __init__(self, config):
        self.config = config
        self.connected = False
        self.network = None

    def setup_network_from_osm(self, osm_file, output_dir="output/sumo"):
        """Convert OpenStreetMap data to SUMO network via netconvert."""
        os.makedirs(output_dir, exist_ok=True)
        net_file = os.path.join(output_dir, "parking_network.net.xml")
        nc_bin = _sumo_bin("netconvert")
        cmd = [
            nc_bin,
            "--osm-files", osm_file,
            "--output-file", net_file,
            "--geometry.remove",
            "--roundabouts.guess",
            "--ramps.guess",
            "--junctions.join",
            "--tls.guess-signals",
            "--tls.join",
            "--no-turnarounds",
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.network = sumolib.net.readNet(net_file)
            return net_file
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  SUMO: netconvert failed ({e})")
            return None

    def create_synthetic_network(self, output_dir="output/sumo"):
        """Create a synthetic grid network matching the Mesa simulation grid."""
        os.makedirs(output_dir, exist_ok=True)
        grid_cfg = self.config.get("grid", {})
        raw_w = grid_cfg.get("width", 20)
        raw_h = grid_cfg.get("height", 20)
        cell_size = grid_cfg.get("cell_size_meters", 10)
        # Match the simulation grid exactly so driver positions map to network coords
        n = min(max(raw_w, raw_h), 20)
        net_file = os.path.join(output_dir, "synthetic_network.net.xml")
        ng_bin = _sumo_bin("netgenerate")

        result = subprocess.run(
            [
                ng_bin,
                "--grid", "--grid.number", str(n),
                "--grid.length", str(cell_size),
                "--default.lanenumber", "1",
                "--default.speed", "13.89",
                "--no-internal-links",
                "--output-file", net_file,
            ],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  SUMO: netgenerate failed: {result.stderr[:200]}")
            return None

        if os.path.exists(net_file):
            try:
                self.network = sumolib.net.readNet(net_file)
            except Exception:
                self.network = None
            return net_file
        return None

    def start_sumo(self, net_file, gui=False, port=8813):
        """Start SUMO via traci.start() (launches process + connects)."""
        # Close any stale TraCI connection first to free the port
        try:
            traci.close()
        except Exception:
            pass

        # Kill any stale SUMO processes that may be holding the port
        try:
            import subprocess, signal
            result = subprocess.run(
                ["pgrep", "-f", f"sumo.*-c.*traci_config"],
                capture_output=True, text=True, timeout=5,
            )
            for pid_str in result.stdout.strip().split("\n"):
                if pid_str.strip():
                    try:
                        os.kill(int(pid_str), signal.SIGTERM)
                    except (ProcessLookupError, ValueError):
                        pass
            # Also check for sumo processes on the specific port
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5,
            )
            for pid_str in result.stdout.strip().split("\n"):
                if pid_str.strip():
                    try:
                        os.kill(int(pid_str), signal.SIGTERM)
                    except (ProcessLookupError, ValueError):
                        pass
            import time as _t
            _t.sleep(0.5)  # Give processes time to die
        except Exception:
            pass

        sumo_binary = _sumo_bin("sumo-gui" if gui else "sumo")

        if not os.path.isfile(sumo_binary):
            print(f"  SUMO: Binary not found at {sumo_binary}")
            self.connected = False
            return False

        sim_ticks = self.config.get("simulation", {}).get("total_ticks", 500)
        cfg_path = os.path.join(os.path.dirname(net_file), "traci_config.sumocfg")
        cfg_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<configuration>\n"
            f'  <input><net-file value="{os.path.abspath(net_file)}"/></input>\n'
            f'  <time><begin value="0"/><end value="{sim_ticks}"/></time>\n'
            '  <processing><ignore-route-errors value="true"/></processing>\n'
            "</configuration>"
        )
        with open(cfg_path, "w") as f:
            f.write(cfg_content)

        cmd = [sumo_binary, "-c", cfg_path, "--no-step-log", "true"]

        try:
            traci.start(cmd, port=port)
            self.connected = True
            return True
        except Exception as e:
            print(f"  SUMO: Could not start ({e}), running in Mesa-only mode")
            self.connected = False
            # Attempt to clean up the failed connection so next run can retry
            try:
                traci.close()
            except Exception:
                pass
            return False

    def step(self):
        if self.connected:
            traci.simulationStep()

    def get_vehicle_position(self, veh_id):
        if self.connected:
            try:
                return traci.vehicle.getPosition(veh_id)
            except Exception:
                return None
        return None

    def add_vehicle(self, veh_id, edge_id, depart=0):
        if self.connected:
            try:
                route_id = f"route_{veh_id}"
                traci.route.add(route_id, [edge_id])
                traci.vehicle.add(veh_id, route_id, depart=depart)
                return True
            except Exception:
                return False
        return False

    def close(self):
        """Close TraCI connection and reset global state."""
        try:
            traci.close()
        except Exception:
            pass
        # Reset the TraCI module-level connection slot so the next
        # traci.start() does not see a stale "already active" handle.
        try:
            from traci import connection as _tc
            if _tc.has("default"):
                _tc._connections["default"] = None  # type: ignore[index]
        except Exception:
            pass
        self.connected = False


class OSMCityIntegration(SUMOIntegration):
    """Build and cache SUMO networks from configured OSM city areas."""

    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self, config=None, city_name=None):
        super().__init__(config or {})
        self.city_name = city_name
        self.parking_zone_edges = []

    def _city_config(self, city_config):
        """Resolve a city config dictionary or supported city name."""
        if isinstance(city_config, str):
            return get_city_config(city_config)
        if city_config is None and self.city_name:
            return get_city_config(self.city_name)
        if not isinstance(city_config, dict):
            raise ValueError("city_config must be a city config dict or supported city name")
        return city_config

    def _city_output_dir(self, city_config, output_dir):
        city = self._city_config(city_config)
        city_name = city.get("name") or city.get("city_name") or self.city_name or "city"
        return os.path.join(output_dir, city_name)

    def download_osm(self, city_config, output_dir="output/sumo"):
        """Download OSM XML for a configured city's bounding box via Overpass."""
        city = self._city_config(city_config)
        bounds = city.get("bounds", {})
        required = ("lat_min", "lat_max", "lon_min", "lon_max")
        if not all(key in bounds for key in required):
            raise ValueError(f"City config for {city.get('name', 'city')} is missing bounds")

        cache_dir = self._city_output_dir(city, output_dir)
        os.makedirs(cache_dir, exist_ok=True)
        city_name = city.get("name") or city.get("city_name") or self.city_name or "city"
        osm_file = os.path.join(cache_dir, f"{city_name}.osm.xml")
        if os.path.exists(osm_file) and os.path.getsize(osm_file) > 0:
            return osm_file

        south = bounds["lat_min"]
        west = bounds["lon_min"]
        north = bounds["lat_max"]
        east = bounds["lon_max"]
        query = f"""
        [out:xml][timeout:180];
        (
          way["highway"]({south},{west},{north},{east});
          relation["highway"]({south},{west},{north},{east});
        );
        (._;>;);
        out body;
        """
        data = urllib.parse.urlencode({"data": query}).encode("utf-8")
        request = urllib.request.Request(
            self.OVERPASS_URL,
            data=data,
            headers={"User-Agent": "multi-agent-parking-simulation/1.0"},
        )

        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                osm_xml = response.read()
            with open(osm_file, "wb") as f:
                f.write(osm_xml)
            return osm_file
        except Exception as e:
            print(f"  OSM: Overpass download failed ({e})")
            return None

    def convert_to_sumo(self, osm_file, output_dir="output/sumo"):
        """Convert a downloaded OSM file to a cached SUMO network."""
        if not osm_file or not os.path.exists(osm_file):
            return None

        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.basename(osm_file)
        city_name = base_name.replace(".osm.xml", "").replace(".osm", "")
        if os.path.basename(output_dir) == city_name:
            cache_dir = output_dir
        else:
            cache_dir = os.path.join(output_dir, city_name)
        os.makedirs(cache_dir, exist_ok=True)

        net_file = os.path.join(cache_dir, f"{city_name}.net.xml")
        if os.path.exists(net_file) and os.path.getmtime(net_file) >= os.path.getmtime(osm_file):
            try:
                self.network = sumolib.net.readNet(net_file)
            except Exception:
                self.network = None
            return net_file

        nc_bin = _sumo_bin("netconvert")
        cmd = [
            nc_bin,
            "--osm-files", osm_file,
            "--output-file", net_file,
            "--geometry.remove",
            "--roundabouts.guess",
            "--ramps.guess",
            "--junctions.join",
            "--tls.guess-signals",
            "--tls.join",
            "--no-turnarounds",
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.network = sumolib.net.readNet(net_file)
            return net_file
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  SUMO: OSM netconvert failed ({e})")
            return None

    def get_parking_zones(self, city_config):
        """Return configured parking zones as (lat, lon, capacity) tuples."""
        city = self._city_config(city_config)
        zones = []
        self.parking_zone_edges = []

        for zone in city.get("parking_zones", []):
            lat = zone.get("lat")
            lon = zone.get("lon")
            capacity = zone.get("capacity", 0)
            if lat is None or lon is None:
                continue
            zones.append((lat, lon, capacity))

            edge_id = self._nearest_edge_id(lon, lat)
            if edge_id is not None:
                self.parking_zone_edges.append(
                    {
                        "name": zone.get("name"),
                        "lat": lat,
                        "lon": lon,
                        "capacity": capacity,
                        "edge_id": edge_id,
                    }
                )

        return zones

    def prepare_city_network(self, city_name, output_dir="output/sumo"):
        """Download, convert, and map parking zones for a supported city."""
        city = get_city_config(city_name)
        city_dir = self._city_output_dir(city, output_dir)
        osm_file = self.download_osm(city, output_dir)
        net_file = self.convert_to_sumo(osm_file, city_dir) if osm_file else None
        self.get_parking_zones(city)
        return net_file

    def _nearest_edge_id(self, lon, lat):
        if self.network is None:
            return None
        try:
            x, y = self.network.convertLonLat2XY(lon, lat)
            edge, _ = self.network.getNeighboringEdges(x, y, r=100)[0]
            return edge.getID()
        except Exception:
            return None


class OSMIntegration:
    """OpenStreetMap integration for realistic road networks."""

    def __init__(self):
        self.graph = None
        self.bounds = None

    def download_area(self, place_name, network_type="drive"):
        try:
            import osmnx as ox
            ox.settings.all_oneway = True
            self.graph = ox.graph_from_place(place_name, network_type=network_type, simplify=False)
            return self.graph
        except Exception as e:
            print(f"  OSM download failed: {e}")
            return None

    def export_to_sumo(self, output_path="output/sumo/osm_network.net.xml"):
        if self.graph is None:
            return None
        try:
            import osmnx as ox
            ox.save_graph_xml(self.graph, filepath=output_path)
            return output_path
        except Exception as e:
            print(f"  OSM to SUMO export failed: {e}")
            return None

    def get_parking_locations(self):
        if self.graph is None:
            return []
        parking_nodes = []
        for node, data in self.graph.nodes(data=True):
            tags = data.get("tags", {})
            if any("parking" in str(v).lower() for v in tags.values()):
                parking_nodes.append((node, data))
        return parking_nodes
