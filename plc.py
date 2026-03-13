import json
import time
import threading
import atexit
import dotenv #type: ignore
import os
from pymodbus.client import ModbusTcpClient #type: ignore

dotenv.load_dotenv()

PLC_IP = os.getenv('PLC_IP')
PLC_PORT = int(os.getenv('PLC_PORT', '502'))
PLC_TIMEOUT = float(os.getenv('PLC_TIMEOUT', '5.0'))
UNIT_ID = int(os.getenv('MODBUS_UNIT_ID', '1'))

plc = None
modbus_lock = threading.Lock()
plc_photo_eye = None
photo_eye_lock = threading.Lock()

# _photo_eye_callbacks = []
_photo_eye_callback = None
_photo_eye_callbacks_lock = threading.Lock()
_photo_eye_monitor_thread = None
_photo_eye_monitor_running = False

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

def _connect_photo_eye_plc():
    global plc_photo_eye
    with photo_eye_lock:
        if plc_photo_eye is not None and getattr(plc_photo_eye, 'connected', False):
            return plc_photo_eye
        try:
            if plc_photo_eye is not None:
                try:
                    plc_photo_eye.close()
                except Exception:
                    pass
                plc_photo_eye = None
            client = ModbusTcpClient(PLC_IP, port=PLC_PORT, timeout=PLC_TIMEOUT)
            if client.connect():
                plc_photo_eye = client
                return plc_photo_eye
            plc_photo_eye = None
        except Exception:
            plc_photo_eye = None
    return plc_photo_eye

def _read_photo_eye_dedicated():
    global plc_photo_eye
    if plc_photo_eye is None or not getattr(plc_photo_eye, 'connected', False):
        _connect_photo_eye_plc()
    if plc_photo_eye is None:
        return 0
    try:
        with photo_eye_lock:
            result = plc_photo_eye.read_holding_registers(0x0002, count=1, slave=UNIT_ID)
            if result and not result.isError() and result.registers:
                return result.registers[0]
            return None
    except Exception:
        pass
    return 0

def is_plc_connected():
    if plc is not None:
        return True
    return False

def reset_plc():
    global plc, plc_photo_eye
    with modbus_lock:
        if plc is not None:
            try:
                if hasattr(plc, 'close'):
                    plc.close()
            except:
                pass
            plc = None
    with photo_eye_lock:
        if plc_photo_eye is not None:
            try:
                if hasattr(plc_photo_eye, 'close'):
                    plc_photo_eye.close()
            except Exception:
                pass
            plc_photo_eye = None

@atexit.register
def cleanup_modbus():
    global plc, plc_photo_eye
    if plc and plc.connected:
        print("🔌 Closing Modbus connection...")
        plc.close()
    plc = None
    if plc_photo_eye and getattr(plc_photo_eye, 'connected', False):
        plc_photo_eye.close()
    plc_photo_eye = None

def write_bucket(pusher):
    global plc

    pusher_key = f"Pusher {pusher}"

    pushers = {}
    with open("settings.json", "r") as f:
        pushers = json.load(f)['pushers']

    if pusher_key not in pushers:
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
            result = plc.read_holding_registers(0x0002, count=1, slave=UNIT_ID)
            if result and not result.isError() and result.registers:
                return result.registers[0]
            return None
    except Exception:
        pass
    return 0

def connect_photo_eye_signal(callback):
    global _photo_eye_callback
    with _photo_eye_callbacks_lock:
        _photo_eye_callback = callback
        print(f"✅ Registered photo eye callback: {callback.__name__}", flush=True)

def disconnect_photo_eye_signal(callback):
    global _photo_eye_callback
    with _photo_eye_callbacks_lock:
        _photo_eye_callback = None

def _photo_eye_monitor_loop():
    last_value = 0
    last_error_log = 0.0
    reconnect_interval = 2.0
    while _photo_eye_monitor_running:
        try:
            # if plc is None:
            #     connect_plc()
            #     if plc is None:
            #         time.sleep(reconnect_interval)
            #         continue
            if _connect_photo_eye_plc() is None:
                time.sleep(reconnect_interval)
                continue
            # current_value = read_photo_eye()
            current_value = _read_photo_eye_dedicated()

            if current_value == 1 and last_value == 0:
                callback = _photo_eye_callback
                if callback is not None:
                    try:
                        threading.Thread(target=callback, args=(), daemon=True).start()
                    except Exception:
                        pass

            last_value = current_value
            time.sleep(0.1)
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

