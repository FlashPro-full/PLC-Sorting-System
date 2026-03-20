import threading
import time
import logging
from plc import write_bucket
from purescan_api import request_purescan_async
from state import book_dict, barcode_queue, event_queue, state_lock, enqueue_event

INTERVAL_100MS = 0.1
MAX_EVENTS_PER_TICK = 300
_timer_thread = None
_timer_running = False
_timer_lock = threading.Lock()
_last_error_log = 0.0
_logger = logging.getLogger(__name__)

_socketio = None
_get_belt_speed = lambda: 32.1

def configure_runtime(socketio, get_belt_speed):
    global _socketio, _get_belt_speed
    _socketio = socketio
    _get_belt_speed = get_belt_speed

def on_interval_100ms():
    current_time = time.time()
    _drain_events(current_time)

    push_list = []
    with state_lock:
        for barcode in list(book_dict):
            item = book_dict.get(barcode)
            if not item:
                continue

            start = item.get("start_time")
            if start is not None and current_time - start >= 1 and item.get("status") == "pending":
                if barcode_queue and barcode_queue[0].get("barcode") == barcode:
                    barcode_queue.popleft()
                del book_dict[barcode]
                continue

            if (item.get("status") == "progress"
                    and item.get("push_time") is not None
                    and current_time >= item.get("push_time")
                    and item.get("positionId") is not None
                    and item.get("pusher") is not None
                    and not (isinstance(item.get("label"), str) and item.get("label").strip().lower() == "none")):
                push_list.append((barcode, item.get("pusher")))

    done = []
    for barcode, pusher in push_list:
        result = write_bucket(pusher)
        if result == 1:
            done.append(barcode)
    if done:
        with state_lock:
            for barcode in done:
                if barcode in book_dict:
                    del book_dict[barcode]

def _drain_events(now):
    processed = 0
    while processed < MAX_EVENTS_PER_TICK:
        with state_lock:
            if not event_queue:
                return
            event = event_queue.popleft()
        _handle_event(event, now)
        processed += 1

def _emit(event_name, data):
    if _socketio is not None:
        _socketio.emit(event_name, data)

def _handle_event(event, now):
    event_type = event.get("type")
    payload = event.get("payload")
    ts = event.get("ts") or now
    belt_speed = _get_belt_speed()

    if event_type == "barcode":
        barcode = payload
        item = {
            "barcode": barcode,
            "start_time": ts,
            "positionId": None,
            "positionCm": None,
            "pusher": None,
            "label": None,
            "distance": None,
            "status": "pending",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with state_lock:
            barcode_queue.append(item)
            book_dict[barcode] = item
        _emit("add_book", item)
        promise = request_purescan_async(barcode)
        promise.then(lambda response, b=barcode: enqueue_event("purescan_ok", {"barcode": b, "response": response}, time.time())).catch(
            lambda error, b=barcode: enqueue_event("purescan_err", {"barcode": b, "error": str(error)}, time.time())
        )
        return

    if event_type == "photo_eye":
        position_id = payload
        barcode = None
        emit_data = None
        remove_barcode = None
        with state_lock:
            if barcode_queue:
                item = barcode_queue.popleft()
                barcode = item.get("barcode") if item else None
            if barcode and barcode in book_dict:
                distance = book_dict[barcode].get("distance")
                book_dict[barcode]["positionId"] = position_id
                book_dict[barcode]["start_time"] = ts
                if distance is None:
                    book_dict[barcode]["status"] = "fetching"
                else:
                    book_dict[barcode]["status"] = "progress"
                    book_dict[barcode]["push_time"] = ts + (distance / belt_speed)
                    emit_data = dict(book_dict[barcode])
        if emit_data is not None:
            _emit("update_book", emit_data)
        return

    if event_type == "purescan_ok":
        barcode = payload.get("barcode")
        response = payload.get("response")

        emit_data = None

        if response is None:
            with state_lock:
                if barcode in book_dict:
                    book_dict[barcode]["status"] = "No response"
                    book_dict[barcode]["label"] = "Fall Down"
                    emit_data = dict(book_dict[barcode])
                    del book_dict[barcode]
            return
        
        with state_lock:
            if barcode in book_dict and book_dict[barcode].get("pusher") is None:
                label = response.get("label")
                distance = response.get("distance")
                pusher = response.get("pusher")
                book_dict[barcode]["pusher"] = pusher
                book_dict[barcode]["label"] = label
                book_dict[barcode]["distance"] = distance
                if book_dict[barcode].get("status") == "fetching":
                    book_dict[barcode]["status"] = "progress"
                    book_dict[barcode]["push_time"] = book_dict[barcode]["start_time"] + (distance / belt_speed)
                emit_data = dict(book_dict[barcode])
                del book_dict[barcode]
        if emit_data is not None:
            _emit("update_book", emit_data)
        return

    if event_type == "purescan_err":
        barcode = payload.get("barcode")
        emit_data = None
        with state_lock:
            if barcode in book_dict:
                book_dict[barcode]["status"] = "No response"
                book_dict[barcode]["label"] = "Fall Down"
                emit_data = dict(book_dict[barcode])
                del book_dict[barcode]
        if emit_data is not None:
            _emit("update_book", emit_data)
        return

        
def _timer_loop():
    global _last_error_log
    while _timer_running:
        tick_start = time.perf_counter()
        try:
            on_interval_100ms()
        except Exception as e:
            now = time.time()
            if now - _last_error_log >= 1.0:
                _last_error_log = now
                _logger.exception("timer loop error: %s", e)
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