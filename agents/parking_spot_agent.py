"""
Parking Spot Agent — Mesa 3 compatible with FIPA-ACL messaging.
Compliant with MS Thesis Section 3.3.3.
"""
import mesa
from agents.message import FIPAMessage, Performative


class ParkingSpotAgent(mesa.Agent):
    """Parking spot agent that manages availability, state, and message updates."""

    def __init__(self, model, unique_id, pos, zone_id, price):
        super().__init__(model)
        self.unique_id = unique_id
        self.pos = pos
        self.zone_id = zone_id
        self.price = price
        self.is_occupied = False
        self.occupied_by = None
        self.reservation_holder = None
        self.total_occupied_ticks = 0
        self.inbox = []

    def receive_message(self, message: FIPAMessage):
        self.inbox.append(message)

    def occupy(self, driver):
        self.is_occupied = True
        self.occupied_by = driver

    def vacate(self):
        self.is_occupied = False
        self.occupied_by = None
        self.reservation_holder = None

    def is_available(self):
        return not self.is_occupied

    def step(self):
        if self.is_occupied:
            self.total_occupied_ticks += 1

        # Process incoming messages
        while self.inbox:
            msg = self.inbox.pop(0)
            if msg.performative == Performative.ALLOCATION_RESULT:
                # Reserved for driver
                self.reservation_holder = msg.content.get("driver_id")