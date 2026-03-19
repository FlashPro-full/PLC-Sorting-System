from typing import Dict
from collections import deque
import threading

MAX_EVENT_QUEUE = 5000
book_dict: Dict[str, dict] = {}
barcode_queue: deque = deque()
event_queue: deque = deque(maxlen=MAX_EVENT_QUEUE)
state_lock = threading.Lock()

def enqueue_event(event_type: str, payload, ts=None):
    with state_lock:
        event_queue.append({
            "type": event_type,
            "payload": payload,
            "ts": ts
        })