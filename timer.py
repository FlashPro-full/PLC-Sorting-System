import threading
import time
from plc import write_bucket
from state import book_dict

INTERVAL_100MS = 0.1
_timer_thread = None
_timer_running = False
_timer_lock = threading.Lock()

def on_interval_100ms():
    current_time = time.time()

    for barcode in list(book_dict):
        item = book_dict.get(barcode)
        if not item:
            continue
        
        start = item.get("start_time")
        if start is not None and current_time - start >= 1 and item.get("status") == "pending":
            del book_dict[barcode]
            continue

        if (item.get("status") == "progress"
                and item.get("push_time") is not None
                and current_time >= item.get("push_time")
                and item.get("positionId") is not None
                and item.get("pusher") is not None):
            result = write_bucket(item.get("pusher"))
            if result == 1:
                del book_dict[barcode]

        
def _timer_loop():
    while _timer_running:
        tick_start = time.perf_counter()
        try:
            on_interval_100ms()
        except Exception:
            pass
        elapsed = time.perf_counter() - tick_start
        sleep_time = max(0.0, INTERVAL_100MS - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)


def start_interval_timer():
    global _timer_thread, _timer_running
    with _timer_lock:
        if _timer_thread is not None and _timer_thread.is_alive():
            return
        _timer_running = True
    _timer_thread = threading.Thread(target=_timer_loop, daemon=True)
    _timer_thread.start()