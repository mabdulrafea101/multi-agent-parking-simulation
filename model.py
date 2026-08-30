"""
Main Parking Simulation Model — Mesa 3 Compatible.
Uses Mesa 3 for agent management but custom grid for spatial operations.
"""
import mesa
import random
import math
import json
import os
import numpy as np
from recorder import FrameRecorder
from agents.driver_agent import DriverAgent
from agents.parking_spot_agent import ParkingSpotAgent
from agents.coordinator_agent import CoordinatorAgent
try:
    from engine.sumo_integration import (
        SUMOIntegration,
        OSMIntegration,
        OSMCityIntegration,
    )
    from engine.cities import get_city_config
except ImportError:
    SUMOIntegration = None
    OSMIntegration = None
    OSMCityIntegration = None
    get_city_config = None


class ParkingModel(mesa.Model):
    """Multi-agent parking simulation model using Mesa 3."""
    
    def __init__(self, config_path="config/default_params.json",
                 config_dict=None, strategy="auction", replication_id=0,
                 simulation_type="mesa", city=None):
        super().__init__()
        
        # Load configuration
        if config_dict is not None:
            self.config = config_dict
        else:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        
        self.strategy = strategy
        self.replication_id = replication_id
        self.simulation_type = simulation_type or "mesa"
        self.city = city if self.simulation_type == "osm_city" else None
        
        # Set random seed
        seed = self.config["simulation"]["random_seed"] + replication_id
        random.seed(seed)
        np.random.seed(seed)
        
        # Setup parameters
        self.width = self.config["grid"]["width"]
        self.height = self.config["grid"]["height"]
        self.total_ticks = self.config["simulation"]["total_ticks"]
        self.warmup_ticks = self.config["simulation"]["warmup_ticks"]
        self.search_radius = self.config["demand"]["search_radius_cells"]
        self.max_search_duration = self.config["demand"]["max_search_duration_ticks"]
        self.arrival_rate = self.config["demand"]["arrival_rate_lambda"]
        self.duration_mean = self.config["demand"]["parking_duration_mean_ticks"]
        self.duration_std = self.config["demand"]["parking_duration_std_ticks"]
        
        # Create coordinator
        self.coordinator = CoordinatorAgent(self, 0)
        
        # Create parking spots
        self.spots = self._create_parking_spots()
        
        # Driver tracking
        self.drivers = []
        self.next_driver_id = 10000 * (replication_id + 1) + len(self.spots) + 1
        
        # SUMO/TraCI integration
        self.sumo = None
        self.use_sumo = False
        self.sumo_vehicles_completed = 0
        self._sumo_port = 8813 + (replication_id % 100)
        self._edge_by_pos = {}
        self.kpi_data = {
            "tick": [], "searching_drivers": [], "occupied_spots": [],
            "total_drivers": [], "successful_allocations": [], "failed_allocations": [],
        }
        self.total_arrivals = 0
        self.total_success = 0
        self.total_failed = 0
        self.all_pst = []
        self.all_utilities = []
        self.recorder = None
    
    def _create_parking_spots(self):
        """Create parking spots distributed across zones."""
        spots = []
        num_spots = self.config["parking"]["num_spots"]
        num_zones = self.config["parking"]["num_zones"]
        price_range = self.config["parking"]["price_range"]
        spots_per_zone = num_spots // num_zones
        
        spot_id = 1
        for zone in range(num_zones):
            zone_x = (self.width // (num_zones // 2 + 1)) * ((zone % (num_zones // 2)) + 1)
            zone_y = (self.height // 3) * (zone // (num_zones // 2) + 1)
            zone_x = min(max(zone_x, 5), self.width - 5)
            zone_y = min(max(zone_y, 5), self.height - 5)
            zone_price = random.uniform(price_range[0], price_range[1])
            
            for i in range(spots_per_zone):
                pos = (
                    max(0, min(self.width - 1, zone_x + random.randint(-5, 5))),
                    max(0, min(self.height - 1, zone_y + random.randint(-5, 5)))
                )
                while any(s.pos == pos for s in spots):
                    pos = (max(0, min(self.width - 1, zone_x + random.randint(-5, 5))),
                           max(0, min(self.height - 1, zone_y + random.randint(-5, 5))))
                
                spot = ParkingSpotAgent(self, spot_id, pos, zone, zone_price)
                spots.append(spot)
                self.coordinator.register_spot(spot)
                spot_id += 1
        
        return spots
    
    @staticmethod
    def _resolve_city_config(place):
        """Return a supported city's config, or None for a free-text place name."""
        if not place or get_city_config is None:
            return None
        try:
            return get_city_config(place)
        except ValueError:
            return None

    def init_sumo(self, gui=False, osm_place=None, net_file=None):
        """Initialize SUMO/TraCI integration. Falls back to Mesa-only mode on failure.

        Pass net_file to reuse a network built earlier by the batch: the model then
        uses that file as-is and never downloads or rebuilds anything itself, which
        keeps every replication in a batch on the same road network.
        """
        if self.use_sumo:
            return

        try:
            city_config = self._resolve_city_config(osm_place)
            use_city_network = city_config is not None and OSMCityIntegration is not None

            self.sumo = (
                OSMCityIntegration(self.config, city_name=city_config["name"])
                if use_city_network
                else SUMOIntegration(self.config)
            )

            if use_city_network:
                prepared = net_file or self.sumo.prepare_city_network(city_config["name"])
                if prepared:
                    self._sumo_net_file = prepared
                    if net_file:
                        self.sumo.load_network(prepared)
                    print(f"  SUMO: Using city network at {prepared}")
                else:
                    print("  SUMO: City network unavailable, using synthetic network")
                    self._sumo_net_file = self.sumo.create_synthetic_network()
            elif osm_place:
                print(f"  SUMO: Downloading OSM data for '{osm_place}'...")
                osm = OSMIntegration()
                graph = osm.download_area(osm_place)
                if graph:
                    os.makedirs("output/sumo", exist_ok=True)
                    osm_file = osm.export_to_sumo(
                        output_path=os.path.join(
                            "output", "sumo", f"{osm_place}.osm.xml"
                        )
                    )
                    if not osm_file:
                        print("  SUMO: OSM export failed, using synthetic network")
                        net_file = None
                    else:
                        net_file = self.sumo.setup_network_from_osm(
                            osm_file, output_dir="output/sumo"
                        )
                    if net_file:
                        self._sumo_net_file = net_file
                        print(f"  SUMO: OSM network created at {net_file}")
                    else:
                        print("  SUMO: OSM conversion failed, using synthetic network")
                        self._sumo_net_file = self.sumo.create_synthetic_network()
                else:
                    print("  SUMO: OSM download failed, using synthetic network")
                    self._sumo_net_file = self.sumo.create_synthetic_network()
            else:
                self._sumo_net_file = self.sumo.create_synthetic_network()

            if self._sumo_net_file:
                success = self.sumo.start_sumo(self._sumo_net_file, gui=gui, port=self._sumo_port)
                if success:
                    self.use_sumo = True
                    print(f"  SUMO: Connected via TraCI on port {self._sumo_port}")
                else:
                    print("  SUMO: Could not start, running in Mesa-only mode")
            else:
                print("  SUMO: No network file, running in Mesa-only mode")

        except Exception as e:
            print(f"  SUMO: Initialization failed ({e}), running in Mesa-only mode")
            self.sumo = None
            self.use_sumo = False

    def _pos_to_edge_id(self, pos):
        """Map a grid position (x, y) to the nearest SUMO edge that takes cars.
        The SUMO network is smaller than the simulation grid, so scale coords."""
        if self.sumo is None or self.sumo.network is None:
            return None
        if pos in self._edge_by_pos:
            return self._edge_by_pos[pos]
        cell_size = self.config.get("grid", {}).get("cell_size_meters", 10)
        # Network is 20x20 regardless of simulation grid size
        # Scale simulation grid coords to network coords
        scale = 20.0 / max(self.config.get("grid", {}).get("width", 100), 
                           self.config.get("grid", {}).get("height", 100))
        px, py = float(pos[0]) * cell_size * scale, float(pos[1]) * cell_size * scale
        best_edge = None
        best_dist = float("inf")
        # Restricting to car-legal edges is what keeps SUMO from rejecting the
        # departure: most OSM edges are footways, steps or pedestrian shortcuts.
        for edge in self.sumo.drivable_edges():
            shape = edge.getShape()
            for (sx, sy) in shape:
                d = (sx - px) ** 2 + (sy - py) ** 2
                if d < best_dist:
                    best_dist = d
                    best_edge = edge
        edge_id = best_edge.getID() if best_edge else None
        self._edge_by_pos[pos] = edge_id
        return edge_id

    def step(self):
        """Execute one simulation tick."""
        # Record frame before step
        if self.recorder:
            self.recorder.capture_tick()
        # Spawn new drivers (Poisson process)
        num_arrivals = np.random.poisson(self.arrival_rate)
        for _ in range(num_arrivals):
            self._spawn_driver()
        
        # Step all drivers
        for driver in self.drivers:
            if driver.state != "departed":
                driver.step()
        
        # Run auction/allocation
        if self.strategy == "auction":
            self.coordinator.run_auction()
        else:
            self._run_baseline_allocation()

        # Advance SUMO simulation step
        if self.use_sumo:
            try:
                self.sumo.step()
                # Count completed vehicles
                try:
                    import traci
                    arrived = traci.simulation.getArrivedIDList()
                    self.sumo_vehicles_completed += len(arrived)
                except Exception:
                    pass
            except (BrokenPipeError, ConnectionError, OSError) as exc:
                print(f"  SUMO: Connection lost ({exc}), continuing in Mesa-only mode")
                self.use_sumo = False
                if self.sumo is not None:
                    try:
                        self.sumo.close()
                    except Exception:
                        pass
            except Exception as exc:
                print(f"  SUMO: Step failed ({exc}), continuing in Mesa-only mode")
                self.use_sumo = False

        # Collect KPIs
        self._collect_kpis()
    
    def _spawn_driver(self):
        """Spawn a new driver agent."""
        dest_x = random.randint(0, self.width - 1)
        dest_y = random.randint(0, self.height - 1)
        destination = (dest_x, dest_y)
        
        duration = max(5, int(np.random.lognormal(
            np.log(self.duration_mean),
            np.log(1 + self.duration_std / self.duration_mean)
        )))
        
        weights = np.random.dirichlet([1, 1, 1]).tolist()
        
        driver = DriverAgent(self, self.next_driver_id, destination, duration, weights, self.steps)
        self.drivers.append(driver)
        self.total_arrivals += 1
        self.next_driver_id += 1

        # Register vehicle in SUMO if connected
        if self.use_sumo:
            try:
                edge_id = self._pos_to_edge_id(destination)
                if edge_id:
                    self.sumo.add_vehicle(f"veh_{driver.unique_id}", edge_id, depart=self.steps)
            except (BrokenPipeError, ConnectionError, OSError):
                self.use_sumo = False
            except Exception:
                pass
    
    def _run_baseline_allocation(self):
        """Run baseline allocation strategies."""
        searching = [d for d in self.drivers if d.state == "searching"]
        available = [s for s in self.spots if s.is_available()]
        
        if not searching or not available:
            return
        
        if self.strategy == "fcfs":
            for driver in searching:
                if available:
                    spot = available.pop(0)
                    self._allocate(driver, spot)
        elif self.strategy == "random":
            random.shuffle(available)
            for driver in searching:
                if available:
                    spot = available.pop(0)
                    self._allocate(driver, spot)
        elif self.strategy == "greedy":
            for driver in searching:
                if available:
                    best_spot = min(available,
                                  key=lambda s: abs(s.pos[0] - driver.destination[0]) +
                                               abs(s.pos[1] - driver.destination[1]))
                    available.remove(best_spot)
                    self._allocate(driver, best_spot)
    
    def _allocate(self, driver, spot):
        """Allocate a spot to a driver."""
        driver.state = "assigned"
        driver.assignment_tick = self.steps
        driver.assigned_spot = spot
    
    def _collect_kpis(self):
        """Collect KPIs for current tick."""
        searching = sum(1 for d in self.drivers if d.state == "searching")
        occupied = sum(1 for s in self.spots if s.is_occupied)
        
        self.kpi_data["tick"].append(self.steps)
        self.kpi_data["searching_drivers"].append(searching)
        self.kpi_data["occupied_spots"].append(occupied)
        self.kpi_data["total_drivers"].append(len(self.drivers))
        
        for d in self.drivers:
            if d.state == "parked" and not d.counted:
                self.all_pst.append(d.search_duration)
                self.total_success += 1
                if d.assigned_spot:
                    utility = d.compute_utility(d.assigned_spot)
                    self.all_utilities.append(utility)
                d.counted = True
        
        for d in self.drivers:
            if d.state == "departed" and d.departure_tick == self.steps and d.failed:
                self.total_failed += 1
    
    def run_simulation(self, output_dir="output/frames"):
        """Run the full simulation."""
        for _ in range(self.total_ticks):
            self.step()
        # Save recorded frames
        if self.recorder:
            self.recorder.capture_tick()  # Final frame
            run_id, meta_path, frames_path = self.recorder.save(output_dir)
            self._frame_run_id = run_id
            print(f"  Visualization: {self.recorder.frames} frames saved (run_id={run_id})")
        # Close SUMO connection
        if self.sumo:
            try:
                self.sumo.close()
            except Exception:
                pass
        return self.get_results()
    
    def get_results(self):
        """Return aggregated simulation results."""
        results = self._compute_results()
        if self.recorder:
            results["frame_run_id"] = getattr(self, '_frame_run_id', None)
        return results

    def _compute_results(self):
        post_warmup = [i for i, t in enumerate(self.kpi_data["tick"])
                      if t >= self.warmup_ticks]
        
        if not post_warmup:
            return {}
        
        occupied = [self.kpi_data["occupied_spots"][i] for i in post_warmup]
        total_spots = len(self.spots)
        
        results = {
            "strategy": self.strategy,
            "replication_id": self.replication_id,
            "total_arrivals": self.total_arrivals,
            "total_successful": self.total_success,
            "total_failed": self.total_failed,
            "mean_pst": float(np.mean(self.all_pst)) if self.all_pst else 0,
            "std_pst": float(np.std(self.all_pst)) if self.all_pst else 0,
            "mean_por": float(np.mean(occupied)) / total_spots if total_spots > 0 else 0,
            "rsr": len(self.all_pst) / self.total_arrivals * 100 if self.total_arrivals > 0 else 0,
            "mean_utility": float(np.mean(self.all_utilities)) if self.all_utilities else 0,
            "tfi": sum(self.all_pst) / self.total_arrivals if self.total_arrivals > 0 else 0,
            "sumo_connected": self.use_sumo,
            "sumo_vehicles_completed": self.sumo_vehicles_completed,
        }
        
        return results
