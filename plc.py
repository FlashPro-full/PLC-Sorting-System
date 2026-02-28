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
PHOTO_EYE_ADDRESS = int(os.getenv('PHOTO_EYE_ADDRESS', '0x0015'), 16)
UNIT_ID = int(os.getenv('MODBUS_UNIT_ID', '1'))

plc = None
modbus_lock = threading.Lock()
_settings_lock = threading.Lock()
SETTINGS = {}

_photo_eye_callbacks = []
_photo_eye_callbacks_lock = threading.Lock()
_photo_eye_monitor_thread = None
_photo_eye_monitor_running = False

def load_settings():
    global SETTINGS
    with _settings_lock:
        try:
            with open("settings.json", "r") as f:
                SETTINGS = json.load(f)
        except FileNotFoundError:
            SETTINGS = {}
        except json.JSONDecodeError:
            SETTINGS = {}
        except Exception:
            SETTINGS = {}
    return SETTINGS

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

def float_to_registers(value):
    packed = struct.pack('>f', float(value))
    return struct.unpack('>HH', packed)

def write_settings(settings=None):
    if not settings:
        with open("settings.json", "r") as f:
            settings = json.load(f)

    # From .ckp: Distance Travel 1-8 = DF2-DF9. CLICK DF1=0x7001, DF2=0x7003, ... DF9=0x7011.
    # Base addresses chosen so (address+1) writes the float to DF2-DF9.
    MODBUS_REGISTERS = {
        "Pusher 1": 0x7002,   # DF2
        "Pusher 2": 0x7004,   # DF3
        "Pusher 3": 0x7006,   # DF4
        "Pusher 4": 0x7008,   # DF5
        "Pusher 5": 0x700A,   # DF6
        "Pusher 6": 0x700C,   # DF7
        "Pusher 7": 0x700E,   # DF8
        "Pusher 8": 0x7010,   # DF9
    }

    with modbus_lock:
        if plc is None:
            plc = connect_plc()

        for pusher, address in MODBUS_REGISTERS.items():
            if pusher not in settings:
                continue
            dist = settings[pusher].get("distance", 0)
            high, low = float_to_registers(dist)
            print(f"📝 Writing {pusher}: {dist} → [{high}, {low}] to 0x{address:X}")
            try:
                plc.write_registers(address + 1, [high, low], slave=UNIT_ID)
            except Exception as e:
                print(f"❌ Write failed for {pusher}: {e}")

    load_settings()

def write_bucket(value, pusher):
    global plc
    
    if not (101 <= value <= 150):
        print(f"❌ Invalid bucket value: {value}. Must be between 101 and 150.")
        return -1

    register_address = 0x0064 + (value - 101)
    register_ref = 0x0000

    pusher_key = f"Pusher {pusher}"
    if pusher_key not in SETTINGS:
        print(f"❌ Pusher {pusher} not found in settings.json")
        return -1

    with modbus_lock:
        if plc is None:
            print(f"❌ PLC not connected, attempting to reconnect...")
            plc = connect_plc()
        try:
            plc.write_register(register_address, pusher, slave=UNIT_ID)
            plc.write_register(register_ref, value, slave=UNIT_ID)

            print(f"✅ Updated register 0x{register_ref:04X} with {value}")
            print(f"✅ Wrote pusher {pusher} to register 0x{register_address:04X}")
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
    last_positionId = 0
    positionId = 0
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
                positionId = 0
                with modbus_lock:
                    if plc is not None:
                        try:
                            result = plc.read_input_registers(0x0015, count=1, slave=UNIT_ID)
                            if result and not result.isError() and result.registers:
                                positionId = result.registers[0]
                        except Exception:
                            positionId = 0

                        if positionId != last_positionId:
                            for callback in _photo_eye_callbacks:
                                try:
                                    threading.Thread(target=callback, args=(positionId,), daemon=True).start()
                                except:
                                    pass

            last_value = current_value
            last_positionId = positionId
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

