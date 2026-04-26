from collections import deque
from datetime import datetime


class EventStore:
    def __init__(self, max_events=50):
        self.events = deque(maxlen=max_events)

    def add_event(self, kind, detail):
        event = {
            "kind": kind,
            "detail": detail,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self.events.appendleft(event)
        return event

    def get_events(self, limit=None):
        if limit is None:
            return list(self.events)
        return list(self.events)[:limit]
