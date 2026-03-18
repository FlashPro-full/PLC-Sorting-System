from flask import Flask, jsonify #type: ignore
from flask_socketio import SocketIO  # type: ignore[import-untyped]
from dotenv import load_dotenv #type: ignore
import os
import sys
import time
import threading
import webbrowser
from datetime import datetime
import json
from typing import Dict
from collections import deque

from routes.scan import scan_bp
from routes.settings import settings_bp

from barcode_scanner import connect_barcode_signal
from plc import connect_photo_eye_signal, connect_plc, write_bucket, read_photo_eye
from purescan_api import request_purescan_async, init_session, init_token
from timer import start_interval_timer
from state import book_dict

load_dotenv()

barcode_queue: deque = deque()
queue_lock = threading.Lock()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

_pending_requests = set()
_pending_lock = threading.Lock()
_request_start_times = {}
_request_times_lock = threading.Lock()


def on_barcode_scanned(barcode):
    scan_time = time.time()

    print(f"scanned: {barcode} on {scan_time}", flush=True)
    
    with _pending_lock:
        if barcode in _pending_requests:
            print(f"⚠️ Photo eye triggered for {barcode} but request already pending", flush=True)
            return
        _pending_requests.add(barcode)

    item = {
        "barcode": barcode,
        "start_time": scan_time,
        "positionId": None,
        "positionCm": None,
        "pusher": None,
        "label": None,
        "distance": None,
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    with queue_lock:
        barcode_queue.append(item)
        book_dict[barcode] = item
    
    socketio.emit('add_book', item)

    request_start_time = time.time()
    with _request_times_lock:
        _request_start_times[barcode] = request_start_time
    
    def on_success(response):
        with _pending_lock:
            _pending_requests.discard(barcode)
        with _request_times_lock:
            _request_start_times.pop(barcode, None)
        if response:
            on_purescan_response(barcode, response)
        else:
            _handle_purescan_error(barcode, None)
    
    def on_error(error):
        with _pending_lock:
            _pending_requests.discard(barcode)
        _handle_purescan_error(barcode, error)
    
    promise = request_purescan_async(barcode)
    promise.then(on_success).catch(on_error)
    
    sys.stdout.flush()

def on_purescan_response(barcode, response):
    if not response:
        return
    
    print(f"fetched: {response} on {time.time()}", flush=True)
    
    belt_speed = 32.1
    with open("settings.json", "r") as f:
        belt_speed = json.load(f)['belt_speed']

    pusher = response.get("pusher")
    label = response.get("label")
    distance = response.get("distance")
    
    if barcode in book_dict:
        if book_dict[barcode].get("pusher") is not None:
            return
        book_dict[barcode]["pusher"] = pusher
        book_dict[barcode]["label"] = label
        book_dict[barcode]["distance"] = distance
        
        if book_dict[barcode].get("status") == "fetching":
            book_dict[barcode]["status"] = "progress"
            book_dict[barcode]["push_time"] = book_dict[barcode]["start_time"] + (distance / belt_speed)

        socketio.emit('update_book', book_dict[barcode])

def _handle_purescan_error(barcode, error):
    if not barcode:
        return
    
    elapsed_time = None
    with _request_times_lock:
        if barcode in _request_start_times:
            elapsed_time = time.time() - _request_start_times[barcode]
            _request_start_times.pop(barcode, None)
    
    if elapsed_time is not None and elapsed_time < 30:
        with _pending_lock:
            if barcode not in _pending_requests:
                _pending_requests.add(barcode)
        
        retry_start_time = time.time()
        with _request_times_lock:
            _request_start_times[barcode] = retry_start_time
        
        def on_success_retry(response):
            with _pending_lock:
                _pending_requests.discard(barcode)
            with _request_times_lock:
                _request_start_times.pop(barcode, None)
            if response:
                on_purescan_response(barcode, response)
            else:
                if barcode in book_dict:
                    book_dict[barcode]["status"] = "No response"
                    from purescan_api import get_pusher_number
                    pusher_data = get_pusher_number("Extra")
                    book_dict[barcode]["label"] = pusher_data.get("label")
                    book_dict[barcode]["distance"] = pusher_data.get("distance")
                    book_dict[barcode]["pusher"] = pusher_data.get("pusher")
                        
                socketio.emit('update_book', book_dict[barcode])
                del book_dict[barcode]
        
        def on_error_retry(error):
            with _pending_lock:
                _pending_requests.discard(barcode)
            with _request_times_lock:
                _request_start_times.pop(barcode, None)

        promise = request_purescan_async(barcode)
        promise.then(on_success_retry).catch(on_error_retry)
        return

def on_photo_eye_triggered(positionId):

    print(f"beam break: {positionId} on {time.time()}", flush=True)
    
    photo_eye_trigger_time = time.time()
    barcode = None
    belt_speed = 32.1
    
    with queue_lock:
        if len(barcode_queue) > 0:
            item = barcode_queue.popleft()
            if item:
                barcode = item.get("barcode")
    
    with open("settings.json", "r") as f:
        belt_speed = json.load(f)['belt_speed']
    
    if barcode:
        distance = book_dict[barcode].get("distance")
        book_dict[barcode]["positionId"] = positionId
        book_dict[barcode]["start_time"] = photo_eye_trigger_time
        if distance is None:
            book_dict[barcode]["status"] = "fetching"
        else: 
            book_dict[barcode]["status"] = "progress"
            book_dict[barcode]["push_time"] = photo_eye_trigger_time + (distance / belt_speed)
    
        socketio.emit('update_book', book_dict[barcode])
        
    sys.stdout.flush()

def check_connections():
    from barcode_scanner import is_barcode_scanner_connected as check_barcode
    from plc import is_plc_connected as check_plc
    plc_status = check_plc()
    barcode_status = check_barcode()
    
    photo_eye_status = False
    photo_eye_value = None
    if plc_status:
        try:
            photo_eye_value = read_photo_eye()
            photo_eye_status = photo_eye_value is not None
        except Exception:
            photo_eye_status = False
    
    return {
        "plc": plc_status, 
        "barcode_scanner": barcode_status,
        "photo_eye": {
            "connected": photo_eye_status,
            "message": "Not Ready" if photo_eye_value == None else "Ready"
        }
    }   

_client_already_connected = False

@app.before_request
def _mark_client_connected():
    global _client_already_connected
    _client_already_connected = True

@socketio.on('connect')
def handle_connect():
    global _client_already_connected
    _client_already_connected = True
    try:
        status = check_connections()
        system_status = {
            "plc": {"connected": status.get("plc", False), "message": "Connected" if status.get("plc") else "Disconnected"},
            "scanner": {"connected": status.get("barcode_scanner", False), "message": "Connected" if status.get("barcode_scanner") else "Disconnected", "mode": os.getenv("SCAN_MODE", "KEYBOARD")},
            "photo_eye": status.get("photo_eye", {"connected": False, "message": "Not Ready"})
        }

        socketio.emit('system_status', system_status)
    except Exception:
        pass

@socketio.on('disconnect')
def handle_disconnect():
    pass

def main():
    print("=" * 60, flush=True)
    print("=" * 60, flush=True)
    sys.stdout.flush()

    connect_plc()
    status = check_connections()
    print(f"✅ plc: {status['plc']}, barcode_scanner: {status['barcode_scanner']}", flush=True)
    sys.stdout.flush()

    init_session()
    init_token()
    
    connect_barcode_signal(on_barcode_scanned)
    connect_photo_eye_signal(on_photo_eye_triggered)

    start_interval_timer()

@app.route('/api/system-status', methods=['GET'])
def api_system_status():
    try:
        status = check_connections()
        return jsonify({
            "plc": {"connected": status.get("plc", False), "message": "Connected" if status.get("plc") else "Disconnected"},
            "scanner": {"connected": status.get("barcode_scanner", False), "message": "Connected" if status.get("barcode_scanner") else "Disconnected", "mode": os.getenv("SCAN_MODE", "KEYBOARD")},
            "photo_eye": status.get("photo_eye", {"connected": False, "message": "Not Ready"})
        })
    except Exception:
        return jsonify({"plc": {"connected": False, "message": "Error"}, "scanner": {"connected": False, "message": "Error"}, "photo_eye": {"connected": False, "message": "Error"}}), 500


app.register_blueprint(scan_bp)
app.register_blueprint(settings_bp)

if __name__ == '__main__':
    import sys
    if sys.stdout.isatty():
        sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None
    
    main()
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    
    print(f"\n🌐 Starting Flask server on {host}:{port}", flush=True)
    print(f"Debug mode: {debug_mode}", flush=True)
    print(f"Open browser to: http://localhost:{port}", flush=True)
    print("=" * 60, flush=True)
    sys.stdout.flush()
    
    def open_browser():
        time.sleep(1.5)
        if _client_already_connected:
            return
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    time.sleep(1)
    
    socketio.run(app, debug=debug_mode, host=host, port=port, use_reloader=False)
