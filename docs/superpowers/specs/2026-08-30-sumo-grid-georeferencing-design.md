# Georeferencing the Mesa grid onto the SUMO network

Date: 2026-08-30
Status: approved design, pending implementation plan
Scope: Python-side coordinate correctness only. Metrics, database schema, CSV
columns, recorder payload and the 3D/map viewer are deliberately unchanged.

## Decisions this spec encodes

| Question | Decision |
|---|---|
| What should SUMO contribute to the results? | Real geography; headline metrics stay Mesa-defined. |
| Does the world itself move? | No. Correct coordinates, same world. The 480-run suite stays valid. |
| How far does correctness propagate? | Python call sites only. `recorder.py`, `app/routes.py`, `templates/visualize.html` untouched. |
| Transform source of truth | The network's own extent (`net.getBoundary()`), not `bounds` and not `cell_size_meters`. |

## Problem

`ParkingModel._pos_to_edge_id` (`model.py:209-235`) is the single point where the
Mesa world touches the SUMO world, and it places every vehicle in a corner of
the network.

```python
cell_size = self.config.get("grid", {}).get("cell_size_meters", 10)
scale = 20.0 / max(self.config.get("grid", {}).get("width", 100),
                   self.config.get("grid", {}).get("height", 100))
px, py = float(pos[0]) * cell_size * scale, float(pos[1]) * cell_size * scale
```

The comment above it states the assumption: "Network is 20x20 regardless of
simulation grid size". That holds for the synthetic grid and nowhere else. With
the shipped defaults (`grid.width = grid.height = 100`, `cell_size_meters = 10`)
the formula produces coordinates confined to a 0-200 m square, while the cached
Kuala Lumpur network spans 6138.4 m by 7762.5 m.

Measured against the real networks, sampling 400 grid cells and resolving each
to the nearest car-legal edge:

| Network | Boundary (net-local metres) | Edges | Car-legal | Distinct edges chosen today | Distinct edges under this design |
|---|---|---|---|---|---|
| `kuala_lumpur.net.xml` | 0, 0, 6138.4, 7762.5 | 30,319 | 7,615 | 2 | 239 |
| `synthetic_network.net.xml` | 0, 0, 190, 190 | 1,520 | 1,520 | 344 | 399 |

The synthetic row is why the bug survived: stretching a grid over a 190 m
network is what this formula accidentally does, so `--simulation-type sumo`
spreads vehicles over 344 of its 400 sampled cells while `osm_city` collapses to
two edges. The gain on the synthetic net (344 to 399) comes from mapping cell
centres onto the exact boundary instead of cell corners onto a guessed one.

### Why this and not the other two candidates

- **City `bounds` + `convertLonLat2XY`**: the network was fetched *from* those
  bounds, so they describe the same rectangle, but `netconvert` then clips to
  the largest connected component. Trusting `bounds` allows positions outside
  the usable network, which forces a clamp to the net boundary anyway - at
  which point the net boundary was the real source of truth. It also has no
  answer for the no-city `sumo` path.
- **`cell_size_meters` as physical truth**: a 100 x 100 grid of 10 m cells is a
  1000 m square. Placing a 1000 m square inside a 6138 x 7763 m network is the
  same corner defect, relocated.

### Consequences that are in scope

1. SUMO vehicles depart at a location that genuinely corresponds to the grid
   cell the driver wants, instead of all of them at one corner.
2. The y-axis must be inverted. Mesa row 0 is the top (north) edge of the world;
   SUMO northing grows northward. Without the inversion, the mapping is mirrored
   and every north/south relationship in figures and prose is wrong.
3. Cells stop being square in metres for city networks (KL becomes 61 m by
   78 m per cell). This is stated rather than hidden: the grid is an abstract
   lattice stretched onto a real street network.

## Goals

- One pure, unit-testable transform from a grid cell to net-local metres.
- Both network types handled by the same mechanism, no special cases at call
  sites.
- Headline metrics unchanged to the bit for a fixed seed, so no suite re-run is
  required.
- Mapping quality visible in the run log instead of in a column nobody reads.

## Non-goals

- Rendering real streets in the Three.js or Leaflet viewer.
- Multi-edge routes; vehicles still depart on a single-edge route and nothing
  reads positions back from SUMO (`get_vehicle_position` has zero callers).
- Agent movement: Mesa drivers still never move, `pos` is written once at
  spawn (`agents/driver_agent.py:19`).
- Adding `sumo_vehicles_completed` to `RESULT_COLUMNS`. It stays computed at
  `model.py:418` and unused; the tooltip at `app/routes.py:34` remains unable to
  fire. A follow-up spec should retire or land that field deliberately.
- Placing zones at real district anchors (Bukit Bintang, KLCC). The 8 generated
  clusters stay as they are; `parking_zone_edges` remains unused by the model.

## Design

### New module: `engine/geometry.py`

```python
class GridProjection:
    """Maps a cell of the abstract simulation grid onto a SUMO network."""

    def __init__(self, xmin, ymin, xmax, ymax): ...

    @classmethod
    def from_net(cls, net):
        """Build a projection covering the network's own boundary."""

    def cell_to_xy(self, x, y, width, height):
        """Cell centre in net-local metres, y inverted (row 0 = north)."""

    @property
    def extent_m(self):
        """(width_m, height_m) of the mapped network."""

    @property
    def degenerate(self):
        """True when the boundary has zero or negative area."""
```

Properties:

- No SUMO, TraCI or file-system imports. `from_net` consumes any object with a
  `getBoundary()` returning `(xmin, ymin, xmax, ymax)`, so tests pass a tuple.
- `cell_to_xy` maps cell *centres* and takes the grid dimensions explicitly, so
  the projection stays a pure function of its inputs, the model owns its own
  geometry, and no sample lands exactly on the boundary:
  `px = xmin + ((x + 0.5) / width) * (xmax - xmin)`. `from_net` stores only the
  boundary.
- Y inversion: `py = ymax - ((y + 0.5) / height) * (ymax - ymin)`.
- `degenerate` is set when `xmax <= xmin` or `ymax <= ymin`. Callers treat a
  degenerate projection as "no mapping available".

### Call sites

`ParkingModel`:

- `__init__` gains `self._projection = None` beside `self._edge_by_pos = {}`.
- `_projection_or_build()` returns the cached projection, building it from
  `self.sumo.network` on first use and rebuilding if the network object
  identity changes. Returns `None` when there is no network or the projection is
  degenerate.
- `_pos_to_edge_id` replaces the `scale` / `cell_size` arithmetic with one call
  to `_projection_or_build().cell_to_xy(...)`, then keeps the existing
  `drivable_edges()` scan, the existing memo write, and the existing `None`
  return path.

Unchanged on purpose: `cell_size_meters` remains config truth for
`create_synthetic_network` (`sumo_integration.py:240`), which is where it
physically belongs; `OSMCityIntegration._nearest_edge_id` (`sumo_integration.py:540-553`)
already converts geodetically through the network's own `convertLonLat2XY`.

### Data flow

```
driver spawn (grid cell)                     model.py:305
   -> ParkingModel._projection_or_build()     built once from sumo.network
   -> GridProjection.cell_to_xy(x, y, w, h)   net-local metres, y inverted
   -> nearest edge among sumo.drivable_edges()
   -> SUMOIntegration.add_vehicle(edge_id)    sumo_integration.py
   -> TraCI departure on a car-legal edge at the true location

nothing returns; the Mesa state machine is not consulted by this path
```

### Why metrics cannot shift

The projection is reachable only from `_pos_to_edge_id`, whose sole caller is
`_spawn_driver` (`model.py:305-307`) feeding `sumo.add_vehicle`. Spot creation
(`model.py:92-122`), utility scoring (`agents/driver_agent.py:48-59`), greedy
tie-breaks (`model.py:335-337`), allocation and KPI accumulation never call it,
and none of them read anything SUMO returns. RNG order is untouched: no new
`random` or `np.random` call is introduced anywhere on this path, so a fixed
seed replays identically. This is asserted by a regression test, not just
argued.

### Failure behaviour

| Condition | Behaviour | Rationale |
|---|---|---|
| No network loaded | `cell_to_xy` never called; `_pos_to_edge_id` returns `None` | Existing degradation: no vehicle added, simulation proceeds |
| No car-legal edges | `drivable_edges()` yields an empty list, so `_pos_to_edge_id` returns `None` | Already the behaviour since the permission filter landed |
| Degenerate/zero-area boundary | projection reports `degenerate`, `_pos_to_edge_id` returns `None` | A 0-extent net cannot carry a meaningful mapping; guessing hides corruption |
| Network swapped after first use | cached projection rebuilt on identity change | Prevents stale coordinates if a batch ever changes networks |
| `net.getBoundary()` raises | propagate | A broken net file is a real failure, not a mapping detail |

### Diagnostics

Two additions, both stdout only:

1. At the end of `init_sumo` for a city run, one line with the mapped extent and
   edge counts:
   `SUMO: grid 100x100 -> network extent 6138x7763 m (7615 of 30319 edges take cars)`
2. Once per SUMO-connected replication, at the end of `run_simulation`, reporting
   what the mapping actually did during that run: the number of distinct edges
   used and the number of distinct cells mapped, both derived from
   `self._edge_by_pos`. Shape:
   `SUMO: spawn mapping used E distinct edges across C mapped cells`

The second line is the one that makes the current defect visible: on the KL
network today it would print 2 distinct edges, which is self-evidently wrong for
a city run, and nothing currently surfaces it.
No CSV, DB or JSON payload gains a field.

## Testing plan

**Unit - `tests/test_geometry.py` (new module, no SUMO needed)**

- Corners and cell centres map inside the boundary and never onto it.
- Y inversion: row 0 maps to the maximum northing, last row to the minimum.
- Non-square boundary stretches axes independently (KL-shaped 6138 x 7763).
- Degenerate boundary sets `degenerate` and yields no usable coordinates.
- `from_net` reads `getBoundary()` from a stub object.

**Unit - `tests/test_sumo_integration.py` (extend)**

- `_pos_to_edge_id` returns `None` when the projection is degenerate.
- Cached projection is rebuilt when `sumo.network` identity changes.
- Both diagnostic lines are emitted once per city run, captured with `capsys`.
- Existing permission and memoisation tests keep passing unchanged.

**Regression - metrics frozen**

- Fixed seed, short run: capture the `_compute_results()` dict; assert byte-equal
  `mean_pst`, `std_por`, `rsr`, `mean_utility`, `tfi`, `total_arrivals`,
  `total_successful`, `total_failed`.

**Integration - real network, skipped when absent**

- Against a cached city net: every sampled cell resolves inside the boundary;
  distinct edges used over 400 samples exceeds a floor (100) - the current code
  scores 2, so this test would have caught the defect.
- Skips cleanly when no cached network exists, matching the existing
  `test_real_netconvert_converts_minimal_osm_fixture` skip style.

**Manual verification**

1. `python experiments.py --scenario low_demand --strategy auction --replications 1 --simulation-type osm_city --city kuala_lumpur`
   - expect the two diagnostic lines, zero `has no valid route` / `not allowed to depart`, and `sumo_connected=True`.
2. `--simulation-type sumo` (synthetic): unchanged behaviour, extent line reads 190x190 m.
3. `pytest tests` fully green, no skips introduced on this machine.
4. A/B the fixed-seed KPI dict against the pre-change values.

## Rollout

Single commit. No data migration, no cache invalidation (the projection is
derived at runtime from files already cached), no configuration change, and no
re-run requirement. Existing `output/sumo/<city>/` caches stay valid.

## Follow-ups deliberately excluded

- Real-street rendering in the viewer (needs recorder payload and `visualize.html` work).
- Multi-edge routes so vehicles traverse the network.
- Geo-authored placement onto real district anchors - changes every
  distance-dependent KPI and requires regenerating the suite.
- Deciding the fate of the inert `sumo_vehicles_completed`.
- The grid-to-network aspect distortion, if square cells in metres ever become a
  requirement rather than an abstraction.
