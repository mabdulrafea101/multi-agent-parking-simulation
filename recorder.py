"""
Frame Recorder for Parking Simulation.
Captures per-tick snapshots of all agents for Three.js visualization.
"""
import json
import os
import time


class FrameRecorder:
    """Records simulation state every tick for visualization replay."""

    def __init__(self, model, city_config=None, record_interval=1):
        """
        Args:
            model: ParkingModel instance
            city_config: Optional city config dict (for map overlay coordinates)
            record_interval: Record every N ticks (1 = every tick)
        """
        self.model = model
        self.city_config = city_config
        self.record_interval = record_interval
        self.frames = []
        self.spot_positions = []  # Static spot data (recorded once)
        self._spots_recorded = False

    def capture_tick(self):
        """Capture current state as a frame. Call after model.step()."""
        tick = self.model.steps

        # Record static spot data once (first tick)
        if not self._spots_recorded:
            self._record_spots()

        # Only record at specified intervals
        if tick % self.record_interval != 0:
            return

        frame = {
            "t": tick,
            "drivers": self._record_drivers(),
            "kpi": self._record_kpi(),
        }
        self.frames.append(frame)

    def _record_spots(self):
        """Record static parking spot positions and metadata."""
        self.spot_positions = []
        for s in self.model.spots:
            self.spot_positions.append({
                "id": s.unique_id,
                "x": s.pos[0],
                "y": s.pos[1],
                "zone": s.zone_id,
                "price": round(s.price, 2),
            })
        self._spots_recorded = True

    def _record_drivers(self):
        """Record current state of all active drivers."""
        drivers = []
        for d in self.model.drivers:
            if d.state == "departed":
                continue
            drivers.append({
                "id": d.unique_id,
                "x": d.pos[0],
                "y": d.pos[1],
                "dx": d.destination[0],
                "dy": d.destination[1],
                "s": self._state_code(d.state),
                "sid": d.assigned_spot.unique_id if d.assigned_spot else None,
            })
        return drivers

    def _record_kpi(self):
        """Record aggregate KPI snapshot."""
        searching = sum(1 for d in self.model.drivers if d.state == "searching")
        occupied = sum(1 for s in self.model.spots if s.is_occupied)
        return {
            "srch": searching,
            "occ": occupied,
            "tot": len(self.model.drivers),
            "succ": self.model.total_success,
            "fail": self.model.total_failed,
        }

    @staticmethod
    def _state_code(state):
        """Compact state encoding: 0=searching, 1=assigned, 2=parked, 3=departed."""
        return {"searching": 0, "assigned": 1, "parked": 2, "departed": 3}.get(state, 0)

    def get_metadata(self):
        """Return metadata about the simulation for the frontend."""
        meta = {
            "grid_width": self.model.width,
            "grid_height": self.model.height,
            "cell_size_meters": self.model.config.get("grid", {}).get("cell_size_meters", 10),
            "total_ticks": self.model.total_ticks,
            "warmup_ticks": self.model.warmup_ticks,
            "strategy": self.model.strategy,
            "num_spots": len(self.model.spots),
            "num_zones": len(set(s.zone_id for s in self.model.spots)),
            "spots": self.spot_positions,
            "total_frames": len(self.frames),
            "record_interval": self.record_interval,
            "simulation_type": self.model.simulation_type,
        }
        if self.city_config:
            meta["city"] = self.city_config
        return meta

    def save(self, output_dir="output/frames"):
        """Save frames and metadata to JSON files."""
        os.makedirs(output_dir, exist_ok=True)
        run_id = f"run_{int(time.time())}"

        # Save metadata + spots
        meta_path = os.path.join(output_dir, f"{run_id}_meta.json")
        with open(meta_path, "w") as f:
            json.dump(self.get_metadata(), f)

        # Save frames (compact format)
        frames_path = os.path.join(output_dir, f"{run_id}_frames.json")
        with open(frames_path, "w") as f:
            json.dump(self.frames, f)

        print(f"  Recorder: Saved {len(self.frames)} frames to {output_dir}/{run_id}_*")
        return run_id, meta_path, frames_path

    @staticmethod
    def load(run_id, output_dir="output/frames"):
        """Load previously saved frames."""
        meta_path = os.path.join(output_dir, f"{run_id}_meta.json")
        frames_path = os.path.join(output_dir, f"{run_id}_frames.json")

        with open(meta_path, "r") as f:
            meta = json.load(f)
        with open(frames_path, "r") as f:
            frames = json.load(f)

        return meta, frames
