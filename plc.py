import json
import struct
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

# _photo_eye_callbacks = []
_photo_eye_callback = None
_photo_eye_callbacks_lock = threading.Lock()
_photo_eye_monitor_thread = None
_photo_eye_monitor_running = False

def float_to_regs(value: float) -> list[int]:
    hi, lo = struct.unpack(">HH", struct.pack(">f", float(value)))
    return [lo, hi]

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

def write_pushers(values: list[float]):
    global plc

    with modbus_lock:
        if plc is None:
            plc = connect_plc()
        try:
            regs = []
            for v in values:
                regs.extend(float_to_regs(v))
            result = plc.write_registers(0x7000, regs, slave=UNIT_ID)
            if result.isError():
                print(f"❌ Modbus write error: {result}")
        except Exception as e:
            print(f"❌ Modbus write error: {e}")

def write_belt_speed(speed: float):
    global plc

    belt_speed = speed / 10

    with modbus_lock:
        if plc is None:
            plc = connect_plc()
        try:
            result = plc.write_registers(0x7018, float_to_regs(belt_speed), slave=UNIT_ID)
            if result.isError():
                print(f"❌ Modbus write error: {result}")
        except Exception as e:
            print(f"❌ Modbus write error: {e}")

def write_trigger_pusher(pusher: int):
    global plc

    with modbus_lock:
        if plc is None:
            plc = connect_plc()
        try:
            result = plc.write_register(0x0004, pusher, slave=UNIT_ID)
            if result.isError():
                print(f"❌ Modbus write error: {result}")
                return 0
            return 1
        except Exception as e:
            print(f"❌ Modbus write error: {e}")
            return 0

def write_bucket(value, pusher):
    
    if not (101 <= value <= 150):
        print(f"❌ Invalid bucket value: {value}. Must be between 101 and 150.")
        return -1

    register_address = 0x0064 + (value - 101)

    pusher_key = f"Pusher {pusher}"
    if pusher_key not in SETTINGS:
        print(f"❌ Pusher {pusher} not found in settings.json")
        return -1

    with modbus_lock:
        try:
            plc.write_register(register_address, pusher, slave=UNIT_ID)

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
    last_positionId = 0
    last_error_log = 0.0
    reconnect_interval = 0.1

    while _photo_eye_monitor_running:
        try:
            if plc is None:
                connect_plc()

            positionId = read_photo_eye()
            if positionId != last_positionId:
                callback = _photo_eye_callback
                if callback is not None:
                    try:
                        threading.Thread(target=callback, args=(positionId,), daemon=True).start()
                    except Exception:
                        pass

            last_positionId = positionId
            time.sleep(reconnect_interval)
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

