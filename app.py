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
from plc import connect_photo_eye_signal, is_plc_connected, connect_plc, read_belt_speed, write_bucket, read_photo_eye
from palletiq_api import request_palletiq

load_dotenv()

book_dict: Dict[str, dict] = {}
book_dict_lock = threading.Lock()
last_barcode = ""
last_barcode_lock = threading.Lock()
belt_speed = 0

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def on_barcode_scanned(barcode):
    global last_barcode
    with last_barcode_lock:
        last_barcode = barcode
    print(f"✅ Barcode scanned: {barcode}")
    
def on_photo_eye_triggered(photo_eye_number):
    global last_barcode, belt_speed
    
    current_belt_speed = read_belt_speed()
    if current_belt_speed is not None:
        belt_speed = current_belt_speed
    
    current_time = time.time()
    items_to_remove = []
    
    with book_dict_lock:
        for barcode, item_data in list(book_dict.items()):
            if "last_update" not in item_data:
                continue
            
            elapsed_time = current_time - item_data.get("last_update", current_time)
            location_increment = belt_speed * elapsed_time
            new_location = item_data.get("location", 0) + location_increment
            
            distance = item_data.get("distance", 0)
            pusher = item_data.get("pusher")
            pusher_activated = item_data.get("pusher_activated", False)
            
            item_data["location"] = new_location
            item_data["last_update"] = current_time
            
            if distance > 0:
                new_position_id = 101 + int((new_location / max(distance, 1)) * 49)
                new_position_id = min(max(new_position_id, 101), 150)
                item_data["position_id"] = new_position_id
            else:
                new_position_id = item_data.get("position_id", 101)
            
            if distance > 0 and pusher and not pusher_activated:
                if new_location >= distance:
                    result = write_bucket(new_position_id, pusher)
                    if result == 1:
                        print(f"✅ Pusher {pusher} activated for barcode {barcode} at location {new_location:.2f} cm")
                        item_data["pusher_activated"] = True
                        items_to_remove.append(barcode)
            
            if pusher_activated:
                items_to_remove.append(barcode)
        
        for barcode in items_to_remove:
            if barcode in book_dict:
                del book_dict[barcode]
                print(f"✅ Item {barcode} removed from tracking")
    
    with last_barcode_lock:
        current_barcode = last_barcode
        last_barcode = ""
    
    if not current_barcode:
        if items_to_remove:
            broadcast_active_items()
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
            if items_to_remove:
                broadcast_active_items()
            return
        
        location = belt_speed * time_taken
        distance = response["distance"]
        pusher = response["pusher_number"]
        label = response["label"]
        
        existing_location = book_dict[current_barcode].get("location", 0)
        if existing_location > 0:
            elapsed_time = current_time - book_dict[current_barcode].get("last_update", current_time)
            location_increment = belt_speed * elapsed_time
            location = existing_location + location_increment
        
        book_dict[current_barcode]["location"] = location
        book_dict[current_barcode]["pusher"] = pusher
        book_dict[current_barcode]["distance"] = distance
        book_dict[current_barcode]["label"] = label
        book_dict[current_barcode]["last_update"] = current_time
        book_dict[current_barcode]["photo_eye_number"] = photo_eye_number
        
        if "created_at" not in book_dict[current_barcode]:
            book_dict[current_barcode]["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        position_id = 101 + int((location / max(distance, 1)) * 49)
        position_id = min(max(position_id, 101), 150)
        book_dict[current_barcode]["position_id"] = position_id
        
        pusher_activated = book_dict[current_barcode].get("pusher_activated", False)
        
        if distance > 0 and pusher and not pusher_activated:
            if location >= distance:
                result = write_bucket(position_id, pusher)
                if result == 1:
                    print(f"✅ Pusher {pusher} activated for barcode {current_barcode} at location {location:.2f} cm")
                    book_dict[current_barcode]["pusher_activated"] = True
                    del book_dict[current_barcode]
                    print(f"✅ Item {current_barcode} removed from tracking")
                    broadcast_active_items()
                    return
        
        print(f"✅ Book array updated: {book_dict[current_barcode]}")
    
    broadcast_active_items()

def check_connections():
    from barcode_scanner import is_barcode_scanner_connected as check_barcode
    from plc import is_plc_connected as check_plc
    plc_status = check_plc()
    barcode_status = check_barcode()
    
    photo_eye_status = False
    photo_eye_value = 0
    if plc_status:
        try:
            photo_eye_value = read_photo_eye()
            photo_eye_status = photo_eye_value != 0
        except Exception:
            photo_eye_status = False
    
    return {
        "plc": plc_status, 
        "barcode_scanner": barcode_status,
        "photo_eye": {
            "connected": photo_eye_status,
            "message": "Not Ready" if photo_eye_value == 0 else "Photo Eye Ready"
        }
    }


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
                    "position_id": item_data.get("position_id", 101 + int((item_data.get("location", 0) / max(item_data.get("distance", 1), 1)) * 49)),
                    "label": item_data.get("label", "Unknown"),
                    "pusher_distance": item_data.get("distance", 0),
                    "distance_traveled": item_data.get("location", 0),
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
    if belt_speed is None:
        belt_speed = 10
    print(f"✅ Belt speed: {belt_speed} cm/s")
    connect_barcode_signal(on_barcode_scanned)
    connect_photo_eye_signal(on_photo_eye_triggered)

app.register_blueprint(scan_bp)
app.register_blueprint(settings_bp)

if __name__ == '__main__':
    main()
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    socketio.run(app, debug=debug_mode, host=host, port=port, use_reloader=False)