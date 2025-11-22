from flask import Flask, render_template
from flask_socketio import SocketIO #type: ignore
from dotenv import load_dotenv
import os
import time
import threading
from typing import Dict

from routes.scan import scan_bp
from routes.settings import settings_bp

from barcode_scanner import connect_barcode_signal, is_barcode_scanner_connected
from plc import connect_photo_eye_signal, is_plc_connected, connect_plc, read_belt_speed, write_bucket
from palletiq_api import request_palletiq

load_dotenv()

book_dict: Dict[str, dict] = {}
book_dict_lock = threading.Lock()
last_barcode = ""
last_barcode_lock = threading.Lock()
belt_speed = 0
_tracking_thread = None
_tracking_running = False

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def on_barcode_scanned(barcode):
    global last_barcode
    with last_barcode_lock:
        last_barcode = barcode
    print(f"✅ Barcode scanned: {barcode}")
    
def on_photo_eye_triggered():
    global last_barcode
    
    with last_barcode_lock:
        current_barcode = last_barcode
        last_barcode = ""
    
    if not current_barcode:
        return
    
    with book_dict_lock:
        if current_barcode not in book_dict:
            book_dict[current_barcode] = {}
    
    previous_timestamp = time.time()
    
    response = request_palletiq(current_barcode)

    after_timestamp = time.time()
    time_taken = after_timestamp - previous_timestamp
    print(f"🕒 Time taken: {time_taken} seconds")
    
    if not response:
        return

    with book_dict_lock:
        book_dict[current_barcode]["location"] = belt_speed * time_taken
        book_dict[current_barcode]["pusher"] = response["pusher_number"]
        book_dict[current_barcode]["distance"] = response["distance"]
        book_dict[current_barcode]["last_update"] = time.time()
        book_dict[current_barcode]["pusher_activated"] = False
        print(f"✅ Book array updated: {book_dict[current_barcode]}")
    
    broadcast_active_items()

def check_connections():
    from barcode_scanner import is_barcode_scanner_connected as check_barcode
    from plc import is_plc_connected as check_plc
    plc_status = check_plc()
    barcode_status = check_barcode()
    return {"plc": plc_status, "barcode_scanner": barcode_status}

def _tracking_loop():
    global belt_speed, _tracking_running
    last_broadcast_time = 0
    while _tracking_running:
        try:
            current_time = time.time()
            current_belt_speed = read_belt_speed()
            if current_belt_speed is not None:
                belt_speed = current_belt_speed
            
            with book_dict_lock:
                items_to_remove = []
                for barcode, item_data in list(book_dict.items()):
                    if "last_update" not in item_data:
                        item_data["last_update"] = current_time
                        continue
                    
                    elapsed_time = current_time - item_data["last_update"]
                    location_increment = belt_speed * elapsed_time
                    item_data["location"] = item_data.get("location", 0) + location_increment
                    item_data["last_update"] = current_time
                    
                    distance = item_data.get("distance", 0)
                    pusher = item_data.get("pusher")
                    pusher_activated = item_data.get("pusher_activated", False)
                    
                    if distance > 0 and pusher and not pusher_activated:
                        if item_data["location"] >= distance:
                            position_id = 101 + int((item_data["location"] / distance) * 49)
                            position_id = min(max(position_id, 101), 150)
                            result = write_bucket(position_id, pusher)
                            if result == 1:
                                print(f"✅ Pusher {pusher} activated for barcode {barcode} at location {item_data['location']:.2f} cm")
                                items_to_remove.append(barcode)
                
                for barcode in items_to_remove:
                    if barcode in book_dict:
                        del book_dict[barcode]
                
                if items_to_remove:
                    broadcast_active_items()
            
            if current_time - last_broadcast_time >= 2.0:
                broadcast_active_items()
                last_broadcast_time = current_time
            
            time.sleep(1.0)
        except Exception as e:
            print(f"❌ Error in tracking loop: {e}")
            time.sleep(1.0)

def start_tracking():
    global _tracking_thread, _tracking_running
    if not _tracking_running:
        _tracking_running = True
        _tracking_thread = threading.Thread(target=_tracking_loop, daemon=True)
        _tracking_thread.start()

def stop_tracking():
    global _tracking_running
    _tracking_running = False

def broadcast_active_items():
    try:
        with book_dict_lock:
            items = []
            for barcode, item_data in book_dict.items():
                items.append({
                    "barcode": barcode,
                    "location": item_data.get("location", 0),
                    "pusher": item_data.get("pusher"),
                    "distance": item_data.get("distance", 0),
                    "position_id": 101 + int((item_data.get("location", 0) / max(item_data.get("distance", 1), 1)) * 49),
                    "label": "Unknown",
                    "pusher_distance": item_data.get("distance", 0),
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })
            
            payload = {
                'items': items,
                'count': len(items),
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            socketio.emit('active_items_update', payload)
    except Exception:
        pass

def broadcast_system_status():
    try:
        status = check_connections()
        system_status = {
            "plc": {"connected": status.get("plc", False), "message": "Connected" if status.get("plc") else "Disconnected"},
            "scanner": {"connected": status.get("barcode_scanner", False), "message": "Connected" if status.get("barcode_scanner") else "Disconnected", "mode": os.getenv("SCAN_MODE", "KEYBOARD")},
            "photo_eye": {"active": False, "message": "Ready"}
        }
        socketio.emit('system_status', system_status)
    except Exception:
        pass

@socketio.on('connect')
def handle_connect():
    broadcast_system_status()
    broadcast_active_items()

@socketio.on('disconnect')
def handle_disconnect():
    pass

def main():
    global belt_speed
    connect_plc()
    status = check_connections()
    print(f"✅ plc: {status['plc']}, barcode_scanner: {status['barcode_scanner']}")
    belt_speed = read_belt_speed()
    if belt_speed is None:
        belt_speed = 0
    print(f"✅ Belt speed: {belt_speed} cm/s")
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