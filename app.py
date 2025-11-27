from flask import Flask, render_template
from flask_socketio import SocketIO #type: ignore
from dotenv import load_dotenv
import os
import time
import threading
import logging
from typing import Dict, Optional

from routes.scan import scan_bp
from routes.settings import settings_bp

from barcode_scanner import connect_barcode_signal
from plc import connect_photo_eye_signal, connect_plc, write_bucket, read_photo_eye
from palletiq_api import request_palletiq_async

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

book_dict: Dict[str, dict] = {}
book_dict_lock = threading.Lock()

_tracking_thread = None
_tracking_running = False

belt_speed = 32.1

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def on_barcode_scanned(barcode):
    scan_time = time.time()
    with book_dict_lock:
        if barcode not in book_dict:
            book_dict[barcode] = {
                "start_time": scan_time,
                "positionId": None,
                "position": None,
                "distance": None,
                "pusher": None,
                "status": "pending",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
    request_palletiq_async(barcode).then(lambda response: on_palletiq_response(barcode, response)).catch(lambda error: logger.error(f"❌ Error requesting PalletIQ: {error}"))
    logger.info(f"✅ Barcode scanned: {barcode}")

def on_palletiq_response(barcode: str, response):
    with book_dict_lock:
        if barcode not in book_dict:
            return
        book_dict[barcode]["pusher"] = response.get("pusher")
        book_dict[barcode]["label"] = response.get("label")
        book_dict[barcode]["distance"] = response.get("distance")
        book_dict[barcode]["status"] = "progress"

        print(f"🕒 API call duration for {barcode}: {time.time() - book_dict[barcode]["start_time"]:.2f} seconds")
        
        write_bucket(book_dict[barcode]["positionId"], book_dict[barcode]["pusher"])

def on_photo_eye_triggered(positionId):
    photo_eye_time = time.time()
    with book_dict_lock:
        for barcode, item in book_dict.items():
            if item.get("positionId") is None and item.get("status") == "pending":
                item["start_time"] = photo_eye_time
                item["positionId"] = positionId
                logger.info(f"🔗 Matched: barcode={barcode} ↔ positionId={positionId}")
                return
        logger.warning(f"⚠️ No barcode available for positionId: {positionId}")

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
        except Exception as e:
            logger.warning(f"⚠️ Error reading photo eye: {e}")
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
        with book_dict_lock:
            payload = {
                'items': book_dict,
                'count': len(book_dict),
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            socketio.emit('update_book_dict', payload)
    except Exception as e:
        logger.error(f"❌ Error broadcasting book_dict: {e}", exc_info=True)

def _tracking_loop():
    global _tracking_running
    
    while _tracking_running:
        try:
            with book_dict_lock:
                items_to_remove = []
                current_time = time.time()
                
                for barcode, book in list(book_dict.items()):
                    
                    position = (current_time - book.get("start_time")) * 32.1
                    distance = book.get("distance")
                    
                    if position >= distance:
                        items_to_remove.append(barcode)
                
                for barcode in items_to_remove:
                    if barcode in book_dict:
                        del book_dict[barcode]
                        logger.info(f"✅ Item {barcode} removed from tracking")
                
                broadcast_book_dict()
        except Exception as e:
            logger.error(f"❌ Error in tracking loop: {e}", exc_info=True)
        
        time.sleep(0.5)

def start_tracking():
    global _tracking_thread, _tracking_running
    
    if _tracking_thread is None or not _tracking_thread.is_alive():
        _tracking_running = True
        _tracking_thread = threading.Thread(target=_tracking_loop, daemon=True)
        _tracking_thread.start()
        print("✅ Tracking system started")

def stop_tracking():
    global _tracking_running
    _tracking_running = False
    if _tracking_thread is not None and _tracking_thread.is_alive():
        _tracking_thread.join()
        _tracking_thread = None
    print("❌ Tracking system stopped")

def broadcast_system_status():
    try:
        status = check_connections()
        system_status = {
            "plc": {"connected": status.get("plc", False), "message": "Connected" if status.get("plc") else "Disconnected"},
            "scanner": {"connected": status.get("barcode_scanner", False), "message": "Connected" if status.get("barcode_scanner") else "Disconnected", "mode": os.getenv("SCAN_MODE", "KEYBOARD")},
            "photo_eye": status.get("photo_eye", {"connected": False, "message": "Not Ready"})
        }
        socketio.emit('system_status', system_status)
    except Exception as e:
        logger.error(f"❌ Error broadcasting system status: {e}", exc_info=True)

@socketio.on('connect')
def handle_connect():
    broadcast_system_status()
    broadcast_book_dict()

@socketio.on('disconnect')
def handle_disconnect():
    pass

def main():
    connect_plc()
    status = check_connections()
    logger.info(f"✅ plc: {status['plc']}, barcode_scanner: {status['barcode_scanner']}")
    connect_barcode_signal(on_barcode_scanned)
    connect_photo_eye_signal(on_photo_eye_triggered)
    start_tracking()

app.register_blueprint(scan_bp)
app.register_blueprint(settings_bp)

if __name__ == '__main__':
    main()
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    socketio.run(app, debug=debug_mode, host=host, port=port, use_reloader=False)