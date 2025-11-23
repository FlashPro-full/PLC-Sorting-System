from flask import Flask, render_template
from flask_socketio import SocketIO #type: ignore
from dotenv import load_dotenv
import os
import time
import threading
from typing import Dict

from routes.scan import scan_bp
from routes.settings import settings_bp

from barcode_scanner import connect_barcode_signal
from plc import connect_photo_eye_signal, connect_plc, read_belt_speed, write_bucket, read_photo_eye
from palletiq_api import request_palletiq

load_dotenv()

book_dict: Dict[str, dict] = {}
book_dict_lock = threading.Lock()
last_barcode = ""
last_barcode_lock = threading.Lock()
belt_speed = 0
photo_eye = 101
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
    on_photo_eye_triggered()
    
def on_photo_eye_triggered():
    global last_barcode
    global photo_eye
    with last_barcode_lock:
        current_barcode = last_barcode
        last_barcode = ""
    
    if not current_barcode:
        return
    
    current_time = time.time()
    
    with book_dict_lock:
        if current_barcode not in book_dict:
            book_dict[current_barcode] = {}
        
        previous_timestamp = time.time()
        
        response = request_palletiq(current_barcode)
        print(response)
        after_timestamp = time.time()
        time_taken = after_timestamp - previous_timestamp
        print(f"🕒 Time taken: {time_taken} seconds")
        
        if not response:
            return
        
        location = belt_speed * time_taken
        distance = response["distance"]
        pusher = response["pusher_number"]
        label = response["label"]
        
        book_dict[current_barcode]["location"] = location
        book_dict[current_barcode]["pusher"] = pusher
        book_dict[current_barcode]["distance"] = distance
        book_dict[current_barcode]["label"] = label
        book_dict[current_barcode]["last_update"] = current_time
        book_dict[current_barcode]["photo_eye"] = photo_eye
        
        if "created_at" not in book_dict[current_barcode]:
            book_dict[current_barcode]["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"✅ Book array updated: {book_dict[current_barcode]}")

        photo_eye = photo_eye + 1
        if photo_eye > 150:
            photo_eye = 101

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


def broadcast_active_items():
    import math
    try:
        with book_dict_lock:
            items = []
            for barcode, item_data in book_dict.items():
                items.append({
                    "barcode": barcode,
                    "position": math.floor(item_data.get("position", 0)),
                    "pusher": item_data.get("pusher"),
                    "distance": item_data.get("distance", 0),
                    "label": item_data.get("label", "Unknown"),
                    "photo_eye": item_data.get("photo_eye"),
                    "created_at": item_data.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
                })
            
            payload = {
                'items': items,
                'count': len(items),
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            socketio.emit('active_items_update', payload)
    except Exception:
        pass

def _tracking_loop():
    global belt_speed, _tracking_running
    
    while _tracking_running:
        try:
            current_time = time.time()
            items_to_remove = []
            
            with book_dict_lock:
                for barcode, item_data in list(book_dict.items()):
                    if "last_update" not in item_data:
                        continue
                    
                    elapsed_time = current_time - item_data.get("last_update", current_time)
                    location_increment = belt_speed * elapsed_time
                    new_location = item_data.get("position", 0) + location_increment
                    
                    distance = item_data.get("distance", 0)
                    pusher = item_data.get("pusher")
                    pusher_activated = item_data.get("pusher_activated", False)
                    
                    item_data["position"] = new_location
                    item_data["last_update"] = current_time
                    
                    if distance > 0 and pusher and not pusher_activated:
                        if new_location >= distance:
                            item_data["pusher_activated"] = True
                            items_to_remove.append(barcode)
                    
                    if pusher_activated:
                        items_to_remove.append(barcode)
                
                for barcode in items_to_remove:
                    if barcode in book_dict:
                        del book_dict[barcode]
                        print(f"✅ Item {barcode} removed from tracking")
            
            if items_to_remove:
                broadcast_active_items()
            
            broadcast_active_items()
            
        except Exception as e:
            print(f"❌ Error in tracking loop: {e}")
        
        time.sleep(1.0)

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
    if belt_speed == 0:
        belt_speed = 10
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