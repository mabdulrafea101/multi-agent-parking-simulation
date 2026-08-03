"""
FIPA-ACL Message Protocol for Multi-Agent Parking Simulation.
Compliant with MS Thesis Section 3.3.5.
"""
from enum import Enum, auto
import time


class Performative(Enum):
    BID_REQUEST = auto()
    BID_SUBMIT = auto()
    ALLOCATION_RESULT = auto()
    DEPARTURE_NOTICE = auto()
    AVAILABILITY_UPDATE = auto()


class FIPAMessage:
    """Structured message adhering to FIPA-ACL specification."""

    def __init__(self, performative: Performative, sender_id, receiver_id, content: dict):
        self.performative = performative
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.content = content
        self.timestamp = time.time()

    def __repr__(self):
        return f"<FIPAMessage {self.performative.name} from={self.sender_id} to={self.receiver_id}>"
