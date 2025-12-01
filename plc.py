import json
import struct
import time
import threading
import atexit
import os
from pymodbus.client import ModbusTcpClient

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
_photo_eye_last_value = 0

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
            is_real_plc = (hasattr(plc, "_socket") or 
                            hasattr(plc, "_socket") or 
                            type(plc).__name__ == "ModbusTcpClient")
            
            if is_real_plc:
                if hasattr(plc, 'connected'):
                    if plc.connected:
                        try:
                            test_result = plc.read_coils(PHOTO_EYE_ADDRESS, count=1)
                            if test_result and not test_result.isError():
                                return plc
                        except (OSError, AttributeError, Exception):
                            pass
                    try:
                        if hasattr(plc, 'close'):
                            plc.close()
                    except (OSError, AttributeError):
                        pass
                    plc = None
                else:
                    if hasattr(plc, '_socket') and plc._socket:
                        try:
                            test_result = plc.read_coils(PHOTO_EYE_ADDRESS, count=1)
                            if test_result and not test_result.isError():
                                return plc
                        except (OSError, AttributeError, Exception):
                            pass
                    try:
                        if hasattr(plc, 'close'):
                            plc.close()
                    except (OSError, AttributeError):
                        pass
                    plc = None
        try:
            plc = ModbusTcpClient(PLC_IP, port=PLC_PORT, timeout=PLC_TIMEOUT)
            connection_result = plc.connect()

            if connection_result:
                try:
                    test_result = plc.read_coils(PHOTO_EYE_ADDRESS, count=1)
                    if test_result and not test_result.isError():
                        return plc
                except Exception:
                    pass
                return plc
            else:
                plc = None
                return None

        except (ConnectionRefusedError, TimeoutError, OSError, Exception) as e:
            plc = None
            return None

def is_plc_connected():
    global plc
    with modbus_lock:
        if plc is not None:
            is_real_plc = (hasattr(plc, "_socket") or
                          hasattr(plc, "socket") or
                          type(plc).__name__ == 'ModbusTcpClient')

            if is_real_plc:
                if hasattr(plc, '_socket') and plc._socket is not None:
                    try:
                        if hasattr(plc._socket, 'fileno'):
                            plc._socket.fileno()
                            return True
                    except:
                        pass
                if hasattr(plc, 'connected') and plc.connected:
                    return True
                try:
                    result = plc.read_coils(PHOTO_EYE_ADDRESS, count=1)
                    if result and not result.isError():
                        return True
                except:
                    pass
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
    try:
        lock_acquired = False
        try:
            lock_acquired = modbus_lock.acquire(blocking = False)
        except (KeyboardInterrupt, SystemExit, RuntimeError):
            lock_acquired = False
        
        try:
            current_plc = plc
            if current_plc:
                try:
                    if hasattr(current_plc, 'close'):
                        try:
                            current_plc.close()
                        except (OSError, AttributeError, KeyboardInterrupt, SystemExit):
                            pass
                except (KeyboardInterrupt, SystemExit):
                    pass
                except Exception:
                    pass
                if lock_acquired:
                    plc = None
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception:
            pass
        finally:
            if lock_acquired:
                try:
                    modbus_lock.release()
                except:
                    pass
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception:
        pass

def float_to_registers(value):
    packed = struct.pack('>f', float(value))
    return struct.unpack('>HH', packed)

def write_settings(settings=None):
    global SETTINGS
    if not settings:
        with _settings_lock:
            try:
                with open("settings.json", "r") as f:
                    settings = json.load(f)
            except Exception:
                settings = SETTINGS.copy() if SETTINGS else {}

    MODBUS_REGISTERS = {
        "Pusher 1": 0x7000,
        "Pusher 2": 0x7002,
        "Pusher 3": 0x7004,
        "Pusher 4": 0x7006,
        "Pusher 5": 0x7008,
        "Pusher 6": 0x700A,
        "Pusher 7": 0x700C,
        "Pusher 8": 0x700E
    }
    with modbus_lock:
        for pusher, address in MODBUS_REGISTERS.items():
            if pusher not in settings:
                continue
            dist = settings[pusher].get("distance", 0)
            high, low = float_to_registers(dist)
            print(f"📝 Writing {pusher}: {dist} → [{high}, {low}] to 0x{address:X}")
            try:
                plc.write_registers(address + 1, [high, low], unit=UNIT_ID)
            except Exception as e:
                print(f"❌ Error writing {pusher}: {e}")
        plc.close()

    load_settings()

def write_bucket(value, pusher):
    global plc
    
    if not (101 <= value <= 150):
        print(f"❌ Invalid bucket value: {value}. Must be between 101 and 150.")
        return -1

    register_address = 0x0064 + (value - 101)
    register_ref = 0x0013

    pusher_key = f"Pusher {pusher}"
    if pusher_key not in SETTINGS:
        print(f"❌ Pusher {pusher} not found in settings.json")
        return -1

    with modbus_lock:
        if plc is None:
            print(f"❌ PLC not connected, attempting to reconnect...")
            connect_plc()
        
        if plc is None:
            print(f"❌ Modbus write error: PLC not connected")
            return -1
        
        try:
            if not is_plc_connected():
                print(f"❌ PLC connection lost, attempting to reconnect...")
                connect_plc()
                if plc is None:
                    print(f"❌ Modbus write error: Failed to reconnect PLC")
                    return -1
            
            plc.write_register(register_address, pusher, unit=UNIT_ID)
            plc.write_register(register_ref, value, unit=UNIT_ID)

            print(f"✅ Updated register 0x{register_ref:04X} with {value}")
            print(f"✅ Wrote pusher {pusher} to register 0x{register_address:04X}")
        except Exception as e:
            print(f"❌ Modbus write error: {e}")
            return -1

    return 1

def read_photo_eye():
    if plc is None:
        return None
    
    try:
        with modbus_lock:
            result = plc.read_coils(1, count=1)
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
    global _photo_eye_last_value, _photo_eye_monitor_running
    _photo_eye_last_value = 0
    
    positionId = 0
    
    while _photo_eye_monitor_running:
        try:
            current_value = read_photo_eye()

            if _photo_eye_last_value == 0 and current_value == 1:
                with _photo_eye_callbacks_lock:
                    callbacks = _photo_eye_callbacks.copy()
                
                positionId = 0
                with modbus_lock:
                    if plc is not None:
                        try:
                            result = plc.read_input_registers(0x0015, count=1)
                            if result and not result.isError() and result.registers:
                                positionId = result.registers[0]
                            else:
                                print(f"❌ Error reading position ID from 0x0015")
                                positionId = 0
                        except Exception as e:
                            print(f"❌ Exception reading position ID: {e}")
                            positionId = 0
                
                for callback in callbacks:
                    try:
                        threading.Thread(target=callback, args=(positionId,), daemon=True).start()
                    except:
                        pass
            
            _photo_eye_last_value = current_value
            
            time.sleep(0.01)
        except:
            time.sleep(0.1)

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

