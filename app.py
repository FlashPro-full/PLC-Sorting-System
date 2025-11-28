from flask import Flask
from flask_socketio import SocketIO  # type: ignore[import-untyped]
from dotenv import load_dotenv
import os
import sys
import time
import threading
from datetime import datetime
from typing import Dict, Optional

from routes.scan import scan_bp
from routes.settings import settings_bp

from barcode_scanner import connect_barcode_signal
from plc import connect_photo_eye_signal, connect_plc, write_bucket, read_photo_eye
from palletiq_api import request_palletiq_async, init_session, init_token

load_dotenv()

book_dict: Dict[str, dict] = {}
book_dict_lock = threading.Lock()

belt_speed = 32.1
_tracking_thread = None
_tracking_running = False

_virtual_signal_thread = None
_virtual_signal_running = False
_virtual_signal_counter = 0

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

_pending_requests = set()
_pending_lock = threading.Lock()

def on_barcode_scanned(barcode):
    scan_time = time.time()
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    with _pending_lock:
        if barcode in _pending_requests:
            return
        _pending_requests.add(barcode)
    
    with book_dict_lock:
        if barcode not in book_dict:
            book_dict[barcode] = {
                "start_time": scan_time,
                "positionId": None,
                "positionCm": None,
                "pusher": None,
                "label": None,
                "distance": None,
                "status": "pending",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
    
    def on_success(response):
        with _pending_lock:
            _pending_requests.discard(barcode)
        on_palletiq_response(barcode, response)
    
    def on_error(error):
        with _pending_lock:
            _pending_requests.discard(barcode)
        _handle_palletiq_error(barcode, error)
    
    promise = request_palletiq_async(barcode)
    promise.then(on_success).catch(on_error)
    
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
    distance = response.get("distance", 0)
    
    with book_dict_lock:
        if barcode not in book_dict:
            return
        
        if book_dict[barcode].get("pusher") is not None:
            return
        
        book_dict[barcode]["pusher"] = pusher
        book_dict[barcode]["label"] = label
        book_dict[barcode]["distance"] = distance
        book_dict[barcode]["status"] = "progress"
        
        positionId = book_dict[barcode].get("positionId", "N/A")
    
    print(f"✅ PalletIQ Response - Barcode: {barcode}, Photo: {positionId}, Label: {label}, Pusher: {pusher}, Distance: {distance}", flush=True)

    broadcast_book_dict()

def _handle_palletiq_error(barcode, error):
    return

def on_photo_eye_triggered(positionId):
    photo_eye_trigger_time = time.time()
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    with book_dict_lock:
        for book, data in book_dict.items():
            if data.get("status") == "pending" and data.get("positionId") is None:
                data["positionId"] = positionId
                data["status"] = "progress"
                data["start_time"] = photo_eye_trigger_time
                break
        
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

def broadcast_book_dict():
    try:
        items_to_remove = []
        
        with book_dict_lock:
            for barcode, item_data in book_dict.items():
                if item_data.get("status") == "progress" and item_data.get("positionId") is not None:
                    elapsed_seconds = time.time() - item_data.get("start_time", time.time())
                    item_data["positionCm"] = elapsed_seconds * belt_speed

                position_cm = item_data.get("positionCm")
                distance = item_data.get("distance")
                if position_cm is not None and distance is not None and position_cm >= distance:
                    item_data["status"] = "completed"

                if item_data.get("status") == "completed":
                    items_to_remove.append(barcode)

            for barcode in items_to_remove:
                if barcode in book_dict:
                    del book_dict[barcode]
            
            socketio.emit('book_dict_update', book_dict)
            
    except Exception as e:
        pass

def _tracking_loop():
    global _tracking_running
    
    while _tracking_running:
        try:
            broadcast_book_dict()
        except Exception:
            pass
        
        time.sleep(1.0)

def start_tracking():
    global _tracking_thread, _tracking_running
    
    if _tracking_thread is None or not _tracking_thread.is_alive():
        _tracking_running = True
        _tracking_thread = threading.Thread(target=_tracking_loop, daemon=True)
        _tracking_thread.start()

def stop_tracking():
    global _tracking_running
    _tracking_running = False

def _virtual_signal_loop():
    global _virtual_signal_running, _virtual_signal_counter
    
    interval = 0.5
    prefix = "BOOK"
    base_position = 101
    total_signals = 50
    
    signal_count = 0
    
    while _virtual_signal_running and signal_count < total_signals:
        try:
            signal_count += 1
            
            if signal_count % 2 == 1:
                _virtual_signal_counter += 1
                barcode = f"{prefix}{_virtual_signal_counter:03d}"
                positionId = base_position + ((_virtual_signal_counter - 1) % 10)
                
                on_barcode_scanned(barcode)
            else:
                on_photo_eye_triggered(positionId)
            
            if signal_count < total_signals:
                time.sleep(interval)
            
        except KeyboardInterrupt:
            _virtual_signal_running = False
            break
        except Exception:
            time.sleep(interval)
    
    _virtual_signal_running = False

def start_virtual_signals():
    global _virtual_signal_thread, _virtual_signal_running
    
    if _virtual_signal_thread is None or not _virtual_signal_thread.is_alive():
        _virtual_signal_running = True
        _virtual_signal_thread = threading.Thread(target=_virtual_signal_loop, daemon=True, name="VirtualSignalGenerator")
        _virtual_signal_thread.start()

        def monitor_virtual_signals():
            while True:
                time.sleep(5)
                if _virtual_signal_thread and not _virtual_signal_thread.is_alive() and _virtual_signal_running:
                    start_virtual_signals()
                    break
        
        monitor_thread = threading.Thread(target=monitor_virtual_signals, daemon=True, name="VirtualSignalMonitor")
        monitor_thread.start()

def stop_virtual_signals():
    global _virtual_signal_running
    _virtual_signal_running = False

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
    broadcast_system_status()
    broadcast_book_dict()

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
    
    start_tracking()

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
    
    socketio.run(app, debug=debug_mode, host=host, port=port, use_reloader=False)
