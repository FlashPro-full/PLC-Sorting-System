from flask import Flask
from flask_socketio import SocketIO  # type: ignore[import-untyped]
from dotenv import load_dotenv
import os
import sys
import time
import threading
import webbrowser
from datetime import datetime
from typing import Dict
from collections import deque

from routes.scan import scan_bp
from routes.settings import settings_bp

from barcode_scanner import connect_barcode_signal
from plc import connect_photo_eye_signal, connect_plc, write_bucket, read_photo_eye
from palletiq_api import request_palletiq_async, init_session, init_token

load_dotenv()

barcode_queue: deque = deque()
queue_lock = threading.Lock()
queue_items: Dict[str, dict] = {}

book_dict: Dict[str, dict] = {}
book_dict_lock = threading.Lock()

belt_speed = 32.1
max_distance = 972
_test_signals_started = False

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

_pending_requests = set()
_pending_lock = threading.Lock()

def on_barcode_scanned(barcode):
    scan_time = time.time()
    
    with _pending_lock:
        if barcode in _pending_requests:
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
        queue_items[barcode] = item
    
    socketio.emit('add_book', item)
    
    sys.stdout.flush()

_processed_responses = set()
_response_lock = threading.Lock()

def on_palletiq_response(barcode, response):
    if not response:
        return
    
    with _response_lock:
        response_key = f"{barcode}_{response.get('pusher')}_{response.get('label')}"
        if response_key in _processed_responses:
            return
        _processed_responses.add(response_key)
        if len(_processed_responses) > 1000:
            _processed_responses.clear()
    
    pusher = response.get("pusher")
    label = response.get("label")
    distance = response.get("distance", max_distance)
    
    item = None
    
    with book_dict_lock:
        if barcode in book_dict:
            if book_dict[barcode].get("pusher") is not None:
                return
            item = book_dict[barcode]
            item["pusher"] = pusher
            item["label"] = label
            item["distance"] = distance
            item["status"] = "progress"
    
    if not item:
        return
    
    positionId = item.get("positionId")

    socketio.emit('update_book', item)
    
    print(f"✅ PalletIQ Response - Barcode: {barcode}, Photo: {positionId}, Label: {label}, Pusher: {pusher}, Distance: {distance}", flush=True)

    write_bucket(positionId, pusher)

def _handle_palletiq_error(barcode, error):
    with queue_lock:
        if barcode in queue_items:
            item = queue_items[barcode]
            item["status"] = "error"
            item["error"] = str(error) if error else "Unknown error"
            
            with book_dict_lock:
                if barcode in book_dict:
                    book_dict[barcode]["status"] = "error"
                    book_dict[barcode]["error"] = str(error) if error else "Unknown error"
    
    with _pending_lock:
        _pending_requests.discard(barcode)

def on_photo_eye_triggered(positionId):
    photo_eye_trigger_time = time.time()
    
    item = None
    barcode = None
    
    with queue_lock:
        if len(barcode_queue) > 0:
            item = barcode_queue.popleft()
            if item:
                barcode = item.get("barcode")
                if barcode and barcode in queue_items:
                    del queue_items[barcode]
        else:
            print(f"⚠️ Photo eye triggered at position {positionId} but barcode_queue is empty", flush=True)
    
    if item:
        item["positionId"] = positionId
        item["status"] = "starting"
        item["start_time"] = photo_eye_trigger_time
        
        with book_dict_lock:
            book_dict[item["barcode"]] = item

        socketio.emit('update_book', item)

        print(f"✅ Photo eye processed - Barcode: {item.get('barcode')}, Position: {positionId}", flush=True)
    else:
        print(f"❌ Photo eye signal lost - Position: {positionId}, Queue empty", flush=True)
    
    def on_success(response):
        with _pending_lock:
            _pending_requests.discard(barcode)
        if response:
            on_palletiq_response(barcode, response)
        else:
            _handle_palletiq_error(barcode, None)
    
    def on_error(error):
        with _pending_lock:
            _pending_requests.discard(barcode)
        _handle_palletiq_error(barcode, error)
    
    promise = request_palletiq_async(barcode)
    promise.then(on_success).catch(on_error)
    
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

def broadcast_system_status():
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

@socketio.on('connect')
def handle_connect():
    global _test_signals_started
    broadcast_system_status()
    
    if not _test_signals_started:
        _test_signals_started = True
        import test_signals
        def delayed_test():
            time.sleep(10)
            test_signals.generate_test_signals(25, 1, 1, 101, "BOOK")
        test_thread = threading.Thread(target=delayed_test, daemon=True)
        test_thread.start()

@socketio.on('disconnect')
def handle_disconnect():
    pass

def main():
    print("=" * 60, flush=True)
    print("🚀 Starting Conveyor System Application", flush=True)
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
        webbrowser.open(f"http://localhost:{port}")
    
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    socketio.run(app, debug=debug_mode, host=host, port=port, use_reloader=False)
