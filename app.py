from flask import Flask, jsonify #type: ignore
from flask_socketio import SocketIO  # type: ignore[import-untyped]
from dotenv import load_dotenv #type: ignore
import os
import sys
import time
import threading
import webbrowser
import json

from routes.scan import scan_bp
from routes.settings import settings_bp

from barcode_scanner import connect_barcode_signal
from plc import connect_photo_eye_signal, connect_plc, read_photo_eye
from purescan_api import init_session, init_token
from timer import start_interval_timer, configure_runtime
from state import enqueue_event

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

belt_speed = 32.1

def set_belt_speed():
    global belt_speed
    with open("settings.json", "r") as f:
        belt_speed = json.load(f)['belt_speed']


def on_barcode_scanned(barcode):
    enqueue_event("barcode", barcode, time.time())
    return

def on_photo_eye_triggered(positionId):
    enqueue_event("photo_eye", positionId, time.time())
    return


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

    # global _test_signals_started
    # if not _test_signals_started:
    #     _test_signals_started = True
    #     import test_signals
    #     def delayed_test():
    #         time.sleep(10)
    #         test_signals.generate_test_signals(100, 3, 0.5)
    #     test_thread = threading.Thread(target=delayed_test, daemon=True)
    #     test_thread.start()

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

    set_belt_speed()
    configure_runtime(socketio, lambda: belt_speed)
    from plc import set_pushers_plc
    set_pushers_plc()
    from purescan_api import set_pushers_purescan
    set_pushers_purescan()

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
