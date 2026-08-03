"""
Coordinator Agent — Mesa 3 compatible with FIPA-ACL messaging and SciPy Hungarian Bipartite Matching.
Compliant with MS Thesis Section 3.3.4 & 3.4.
"""
import math
import mesa
import numpy as np
from scipy.optimize import linear_sum_assignment
from agents.message import FIPAMessage, Performative


class CoordinatorAgent(mesa.Agent):
    """Central auctioneer that resolves bipartite parking matching via SciPy linear sum assignment."""

    def __init__(self, model, unique_id):
        super().__init__(model)
        self.unique_id = unique_id
        self.registered_spots = []
        self.pending_bids = []
        self.allocation_results = {}
        self.tick_allocations = 0
        self.inbox = []

    def receive_message(self, message: FIPAMessage):
        self.inbox.append(message)

    def register_spot(self, spot):
        if spot not in self.registered_spots:
            self.registered_spots.append(spot)

    def query_spots(self, driver_pos, radius):
        available = []
        for spot in self.registered_spots:
            if spot.is_available():
                dx = abs(spot.pos[0] - driver_pos[0])
                dy = abs(spot.pos[1] - driver_pos[1])
                dist = math.sqrt(dx**2 + dy**2)
                if dist <= radius:
                    available.append(spot)
        return available

    def submit_bids(self, bids):
        self.pending_bids.extend(bids)

    def run_auction(self):
        # 1. Gather all bids from inbox messages + legacy direct submissions
        all_driver_bids = {}  # driver_obj -> {spot_id: (spot_obj, bid_val)}

        # Process inbox FIPA messages
        while self.inbox:
            msg = self.inbox.pop(0)
            if msg.performative == Performative.BID_SUBMIT:
                driver_obj = msg.content.get("driver_obj")
                bids = msg.content.get("bids", [])
                if driver_obj and bids:
                    if driver_obj not in all_driver_bids:
                        all_driver_bids[driver_obj] = {}
                    for b in bids:
                        all_driver_bids[driver_obj][b["spot_id"]] = (b["spot_obj"], b["bid_value"])

        # Process legacy direct pending bids
        for driver, spot, bid_value in self.pending_bids:
            if driver not in all_driver_bids:
                all_driver_bids[driver] = {}
            all_driver_bids[driver][spot.unique_id] = (spot, bid_value)

        self.pending_bids = []

        if not all_driver_bids:
            return

        drivers = list(all_driver_bids.keys())
        available_spots = [s for s in self.registered_spots if s.is_available()]

        if not drivers or not available_spots:
            return

        # 2. Build cost matrix for SciPy linear_sum_assignment (Hungarian Algorithm)
        # Cost = -Bid (since SciPy minimizes cost, which maximizes total utility/bids)
        num_drivers = len(drivers)
        num_spots = len(available_spots)
        cost_matrix = np.full((num_drivers, num_spots), fill_value=1e6)

        for i, driver in enumerate(drivers):
            driver_bids = all_driver_bids[driver]
            for j, spot in enumerate(available_spots):
                if spot.unique_id in driver_bids:
                    spot_obj, bid_val = driver_bids[spot.unique_id]
                    # Subtract search_duration bonus to break ties in favor of earlier waiting drivers
                    tie_breaker = driver.search_duration * 0.001
                    cost_matrix[i, j] = -(bid_val + tie_breaker)

        # 3. Solve Maximum Weight Bipartite Matching
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        # 4. Dispatch FIPA ALLOCATION_RESULT messages to winners
        for r, c in zip(row_ind, col_ind):
            cost = cost_matrix[r, c]
            if cost < 1e5:  # Valid assignment
                driver = drivers[r]
                spot = available_spots[c]
                bid_val = -cost

                # FIPA ALLOCATION_RESULT message to Driver
                alloc_msg_driver = FIPAMessage(
                    performative=Performative.ALLOCATION_RESULT,
                    sender_id=self.unique_id,
                    receiver_id=driver.unique_id,
                    content={"win": True, "spot_id": spot.unique_id, "bid_value": bid_val}
                )
                driver.receive_message(alloc_msg_driver)

                # FIPA ALLOCATION_RESULT message to Parking Spot
                alloc_msg_spot = FIPAMessage(
                    performative=Performative.ALLOCATION_RESULT,
                    sender_id=self.unique_id,
                    receiver_id=spot.unique_id,
                    content={"driver_id": driver.unique_id}
                )
                spot.receive_message(alloc_msg_spot)

                # Immediate fallback state update for synchronous model tick compatibility
                driver.state = "assigned"
                driver.assignment_tick = self.model.steps
                driver.assigned_spot = spot
                driver.won_auction = True
                driver.current_bid = bid_val
                self.allocation_results[spot.unique_id] = driver
                self.tick_allocations += 1

    def handle_departure(self, spot):
        if spot.unique_id in self.allocation_results:
            del self.allocation_results[spot.unique_id]