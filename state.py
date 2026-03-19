from typing import Dict
from collections import deque
import threading

book_dict: Dict[str, dict] = {}
barcode_queue: deque = deque()
event_queue: deque = deque()
state_lock = threading.Lock()

def enqueue_event(event_type: str, payload, ts=None):
    event_queue.append({
        "type": event_type,
        "payload": payload,
        "ts": ts
    })