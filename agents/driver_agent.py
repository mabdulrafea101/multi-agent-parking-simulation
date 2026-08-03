"""
Driver Agent for Multi-Agent Parking Simulation.
Mesa 3 compatible with FIPA-ACL message protocol.
Compliant with MS Thesis Section 3.3.2.
"""
import math
import random
import mesa
from agents.message import FIPAMessage, Performative


class DriverAgent(mesa.Agent):
    """Driver agent that searches for parking using FIPA-ACL messaging and auction allocation."""

    def __init__(self, model, unique_id, destination, parking_duration, weights, entry_tick):
        super().__init__(model)
        self.unique_id = unique_id
        self.state = "searching"
        self.pos = self._random_entry_position()
        self.destination = destination
        self.assigned_spot = None
        self.weights = weights
        self.entry_tick = entry_tick
        self.assignment_tick = None
        self.departure_tick = None
        self.parking_duration = parking_duration
        self.search_duration = 0
        self.current_bid = None
        self.won_auction = False
        self.counted = False
        self.failed = False
        self.inbox = []

    def _random_entry_position(self):
        edge = random.choice(['top', 'bottom', 'left', 'right'])
        if edge == 'top':
            return (random.randint(0, self.model.width - 1), 0)
        elif edge == 'bottom':
            return (random.randint(0, self.model.width - 1), self.model.height - 1)
        elif edge == 'left':
            return (0, random.randint(0, self.model.height - 1))
        else:
            return (self.model.width - 1, random.randint(0, self.model.height - 1))

    def receive_message(self, message: FIPAMessage):
        self.inbox.append(message)

    def compute_utility(self, spot):
        w_d, w_c, w_t = self.weights
        dx = abs(spot.pos[0] - self.destination[0])
        dy = abs(spot.pos[1] - self.destination[1])
        dist = math.sqrt(dx**2 + dy**2)
        max_dist = math.sqrt(self.model.width**2 + self.model.height**2)
        norm_dist = dist / max_dist if max_dist > 0 else 0
        max_price = 10
        norm_cost = spot.price / max_price if max_price > 0 else 0
        norm_time = norm_dist
        utility = w_d * (1 - norm_dist) + w_c * (1 - norm_cost) + w_t * (1 - norm_time)
        return max(0.001, utility)

    def compute_bid(self, spot, max_bid=100, alpha=1.0):
        utility = self.compute_utility(spot)
        return alpha * utility * max_bid

    def step(self):
        self._process_inbox()

        if self.state == "searching":
            self._step_searching()
        elif self.state == "assigned":
            self._step_assigned()
        elif self.state == "parked":
            self._step_parked()

    def _process_inbox(self):
        while self.inbox:
            msg = self.inbox.pop(0)
            if msg.performative == Performative.ALLOCATION_RESULT:
                win = msg.content.get("win", False)
                if win:
                    spot_id = msg.content.get("spot_id")
                    spot = next((s for s in self.model.spots if s.unique_id == spot_id), None)
                    if spot:
                        self.state = "assigned"
                        self.assigned_spot = spot
                        self.assignment_tick = self.model.steps
                        self.won_auction = True
                        self.current_bid = msg.content.get("bid_value", 0)

    def _step_searching(self):
        self.search_duration += 1
        if self.search_duration > self.model.max_search_duration:
            self.state = "departed"
            self.departure_tick = self.model.steps
            self.failed = True
            return

        # Query available spots using BID_REQUEST message
        if self.model.strategy == "auction":
            available_spots = [s for s in self.model.spots if s.is_available()]
        else:
            available_spots = self.model.coordinator.query_spots(self.pos, self.model.search_radius)

        if available_spots:
            bids_payload = []
            for spot in available_spots:
                bid_val = self.compute_bid(spot)
                bids_payload.append({
                    "spot_id": spot.unique_id,
                    "spot_obj": spot,
                    "bid_value": bid_val
                })
            
            # Send structured FIPA BID_SUBMIT message to coordinator
            msg = FIPAMessage(
                performative=Performative.BID_SUBMIT,
                sender_id=self.unique_id,
                receiver_id=self.model.coordinator.unique_id,
                content={"driver_obj": self, "bids": bids_payload}
            )
            self.model.coordinator.receive_message(msg)

    def _step_assigned(self):
        if self.assigned_spot:
            self.state = "parked"
            self.assigned_spot.occupy(self)

    def _step_parked(self):
        if self.model.steps >= self.assignment_tick + self.parking_duration:
            self.state = "departed"
            self.departure_tick = self.model.steps
            if self.assigned_spot:
                self.assigned_spot.vacate()