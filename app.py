from flask import Flask
from dotenv import load_dotenv
import os
import time
import threading
from typing import Dict

from routes.scan import scan_bp
from routes.settings import settings_bp

from barcode_scanner import connect_barcode_signal, is_barcode_scanner_connected
from plc import connect_photo_eye_signal, is_plc_connected, connect_plc
from palletiq_api import request_palletiq

load_dotenv()

book_dict: Dict[str, dict] = {}
book_dict_lock = threading.Lock()
last_barcode = ""
last_barcode_lock = threading.Lock()
last_palletiq_response = None

app = Flask(__name__)

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
    
    response = request_palletiq(current_barcode)
    
    if not response:
        return

    with book_dict_lock:
        book_dict[current_barcode]["location"] = 0
        book_dict[current_barcode]["pusher"] = response["pusher_number"]
        book_dict[current_barcode]["distance"] = response["distance"]
        book_dict[current_barcode]["status"] = "In Progress"
        book_dict[current_barcode]["timestamp"] = time.time()
        print(f"✅ Book array updated: {book_dict[current_barcode]}")

def check_connections():
    from barcode_scanner import is_barcode_scanner_connected as check_barcode
    from plc import is_plc_connected as check_plc
    plc_status = check_plc()
    barcode_status = check_barcode()
    return {"plc": plc_status, "barcode_scanner": barcode_status}

def main():
    connect_plc()
    status = check_connections()
    print(f"✅ plc: {status['plc']}, barcode_scanner: {status['barcode_scanner']}")
    connect_barcode_signal(on_barcode_scanned)
    connect_photo_eye_signal(on_photo_eye_triggered)

app.register_blueprint(scan_bp)
app.register_blueprint(settings_bp)

if __name__ == '__main__':
    main()
    app.run(debug=True, host='0.0.0.0', port=5000)