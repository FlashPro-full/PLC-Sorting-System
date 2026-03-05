import json
import struct
import time
import threading
import atexit
import dotenv
import os
from pymodbus.client import ModbusTcpClient

dotenv.load_dotenv()

PLC_IP = os.getenv('PLC_IP')
PLC_PORT = int(os.getenv('PLC_PORT', '502'))
PLC_TIMEOUT = float(os.getenv('PLC_TIMEOUT', '5.0'))
UNIT_ID = int(os.getenv('MODBUS_UNIT_ID', '1'))

plc = None
modbus_lock = threading.Lock()
_settings_lock = threading.Lock()

pushers = {}
belt_speed = 0.0

_photo_eye_callbacks = []
_photo_eye_callbacks_lock = threading.Lock()
_photo_eye_monitor_thread = None
_photo_eye_monitor_running = False

def load_settings():
    global pushers, belt_speed
    with _settings_lock:
        try:
            with open("settings.json", "r") as f:
                pushers = json.load(f)['pushers']
                belt_speed = json.load(f)['belt_speed']
        except FileNotFoundError:
            pushers = {}
            belt_speed = 0.0
        except json.JSONDecodeError:
            pushers = {}
            belt_speed = 0.0
        except Exception:
            pushers = {}
            belt_speed = 0.0
    return pushers, belt_speed

load_settings()

def connect_plc():
    global plc
    with modbus_lock:
        if plc is not None:
            return plc
        try:
            plc = ModbusTcpClient(PLC_IP, port=PLC_PORT, timeout=PLC_TIMEOUT)
            connection_result = plc.connect()

            if not connection_result:
                plc = None

        except (ConnectionRefusedError, TimeoutError, OSError, Exception) as e:
            plc = None

    return plc

def is_plc_connected():
    if plc is not None:
        return True
    return False

def reset_plc():
    global plc
    with modbus_lock:
        if plc is not None:
            try:
                if hasattr(plc, 'close'):
                    plc.close()
            except:
                pass
            plc = None

@atexit.register
def cleanup_modbus():
    global plc
    if plc and plc.connected:
        print("🔌 Closing Modbus connection...")
        plc.close()
    
    plc = None

def write_bucket(pusher):
    global plc

    pusher_key = f"Pusher {pusher}"

    if pusher_key not in SETTINGS:
        print(f"❌ Pusher {pusher} not found in settings.json")
        return -1

    with modbus_lock:
        if plc is None:
            plc = connect_plc()
        try:
            plc.write_register(0x0001, pusher, slave=UNIT_ID)
        except Exception as e:
            print(f"❌ Modbus write error: {e}")

    return 1

def read_photo_eye():
    global plc

    if plc is None:
        plc = connect_plc()
    
    try:
        with modbus_lock:
            result = plc.read_coils(1, count=1, slave=UNIT_ID)
            if result and not result.isError():
                return result.bits[0] if result.bits else 0 
            else:
                print(f"Photo eye blocked")
                return None
    except Exception:
        pass
    
    return 0

def connect_photo_eye_signal(callback):
    with _photo_eye_callbacks_lock:
        if callback not in _photo_eye_callbacks:
            _photo_eye_callbacks.append(callback)
            print(f"✅ Registered photo eye callback: {callback.__name__}", flush=True)

def disconnect_photo_eye_signal(callback):
    with _photo_eye_callbacks_lock:
        if callback in _photo_eye_callbacks:
            _photo_eye_callbacks.remove(callback)

def _photo_eye_monitor_loop():
    last_value = 0
    last_error_log = 0.0
    reconnect_interval = 2.0
    while _photo_eye_monitor_running:
        try:
            if plc is None:
                connect_plc()
                if plc is None:
                    time.sleep(reconnect_interval)
                    continue
            current_value = read_photo_eye()

            if current_value == 1 and last_value == 0:
                for callback in _photo_eye_callbacks:
                    try:
                        threading.Thread(target=callback, args=(), daemon=True).start()
                    except:
                        pass

            last_value = current_value
            time.sleep(0.01)
        except Exception:
            now = time.time()
            if now - last_error_log >= 30.0:
                last_error_log = now
                print("❌ Photo eye monitor loop error (PLC may be disconnected)")
            time.sleep(reconnect_interval)

def start_photo_eye_monitor():
    global _photo_eye_monitor_thread, _photo_eye_monitor_running
    
    if _photo_eye_monitor_thread is None or not _photo_eye_monitor_thread.is_alive():
        _photo_eye_monitor_running = True
        _photo_eye_monitor_thread = threading.Thread(target=_photo_eye_monitor_loop, daemon=True)
        _photo_eye_monitor_thread.start()

def stop_photo_eye_monitor():
    global _photo_eye_monitor_running
    _photo_eye_monitor_running = False

start_photo_eye_monitor()

