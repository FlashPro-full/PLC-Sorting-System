import time
import os
import sys
import threading
import serial  # type: ignore
from dotenv import load_dotenv
from collections import deque
from typing import List, Callable

load_dotenv()

BARCODE_PORT = str(os.getenv('SCAN_PORT', os.getenv('SCANNER_PORT', 'COM36')))
BARCODE_BAUDRATE = int(os.getenv('SCAN_BAUD', os.getenv('SCANNER_BAUD', '19200')))
BARCODE_TIMEOUT = float(os.getenv('SCAN_TIMEOUT', '0.5'))
BARCODE_MODE = str(os.getenv('SCAN_MODE', 'KEYBOARD')).upper()

_barcode_callbacks: List[Callable[[str], None]] = []
_barcode_callbacks_lock = threading.Lock()
_barcode_scanner_thread = None
_barcode_scanner_running = False
_barcode_scanner = None
_barcode_scanner_lock = threading.Lock()
_barcode_buffer = b""
_last_barcode = ""

def get_input():
    import sys
    while True:
        try:
            sys.stdout.write('> ')
            sys.stdout.flush()
            user_input = sys.stdin.readline()
            if user_input:
                user_input = user_input.strip()
                if user_input:
                    with _barcode_callbacks_lock:
                        callbacks = _barcode_callbacks.copy()
                    
                    for callback in callbacks:
                        try:
                            threading.Thread(target=callback, args=(user_input,), daemon=True).start()
                        except:
                            pass
        except (EOFError, KeyboardInterrupt):
            break
        except:
            time.sleep(0.1) 

def connect_barcode_scanner():
    global _barcode_scanner
    
    if BARCODE_MODE != 'SERIAL':
        return None
    
    with _barcode_scanner_lock:
        if _barcode_scanner is not None:
            try:
                if _barcode_scanner.is_open:
                    return _barcode_scanner
                else:
                    _barcode_scanner.close()
                    _barcode_scanner = None
            except:
                _barcode_scanner = None
        
        try:
            _barcode_scanner = serial.Serial(
                port=BARCODE_PORT,
                baudrate=BARCODE_BAUDRATE,
                timeout=BARCODE_TIMEOUT,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            if _barcode_scanner.is_open:
                _barcode_scanner.reset_input_buffer()
                _barcode_scanner.reset_output_buffer()
                return _barcode_scanner
        except (serial.SerialException, OSError, ValueError) as e:
            _barcode_scanner = None
            return None
    
    return None

def is_barcode_scanner_connected():
    if BARCODE_MODE == 'KEYBOARD':
        return True
    
    global _barcode_scanner
    with _barcode_scanner_lock:
        if _barcode_scanner is not None:
            try:
                return _barcode_scanner.is_open
            except:
                return False
    return False

def read_barcode():
    if BARCODE_MODE == 'KEYBOARD':
        return None
    
    global _barcode_scanner, _barcode_buffer
    
    scanner = None
    
    with _barcode_scanner_lock:
        if _barcode_scanner is not None:
            try:
                if _barcode_scanner.is_open:
                    scanner = _barcode_scanner
            except:
                _barcode_scanner = None
    
    if scanner is None:
        scanner = connect_barcode_scanner()
        if scanner is None:
            return None
    
    try:
        if scanner.in_waiting > 0:
            new_data = scanner.read(scanner.in_waiting)
            _barcode_buffer += new_data
            
            while b"\n" in _barcode_buffer or b"\r" in _barcode_buffer:
                line_end = -1
                if b"\r\n" in _barcode_buffer:
                    line_end = _barcode_buffer.index(b"\r\n")
                    line = _barcode_buffer[:line_end]
                    _barcode_buffer = _barcode_buffer[line_end + 2:]
                elif b"\n" in _barcode_buffer:
                    line_end = _barcode_buffer.index(b"\n")
                    line = _barcode_buffer[:line_end]
                    _barcode_buffer = _barcode_buffer[line_end + 1:]
                elif b"\r" in _barcode_buffer:
                    line_end = _barcode_buffer.index(b"\r")
                    line = _barcode_buffer[:line_end]
                    _barcode_buffer = _barcode_buffer[line_end + 1:]
                else:
                    break
                
                try:
                    barcode = line.decode('utf-8', errors='ignore').strip()
                    if barcode:
                        return barcode
                except UnicodeDecodeError:
                    continue
        
        if len(_barcode_buffer) > 100:
            _barcode_buffer = b""
            
    except (serial.SerialException, UnicodeDecodeError, OSError):
        with _barcode_scanner_lock:
            if _barcode_scanner is not None:
                try:
                    _barcode_scanner.close()
                except:
                    pass
                _barcode_scanner = None
        _barcode_buffer = b""
        return None
    
    return None

def connect_barcode_signal(callback):
    with _barcode_callbacks_lock:
        if callback not in _barcode_callbacks:
            _barcode_callbacks.append(callback)

def disconnect_barcode_signal(callback):
    with _barcode_callbacks_lock:
        if callback in _barcode_callbacks:
            _barcode_callbacks.remove(callback)

def _barcode_scanner_loop():
    global _barcode_scanner_running, _last_barcode
    
    if BARCODE_MODE == 'KEYBOARD':
        return
    
    while _barcode_scanner_running:
        try:
            barcode = read_barcode()
            
            if barcode and barcode != _last_barcode:
                _last_barcode = barcode
                with _barcode_callbacks_lock:
                    callbacks = _barcode_callbacks.copy()
                
                for callback in callbacks:
                    try:
                        threading.Thread(target=callback, args=(barcode,), daemon=True).start()
                    except:
                        pass
            
            time.sleep(0.01)
        except:
            time.sleep(0.1)

def start_barcode_scanner():
    global _barcode_scanner_thread, _barcode_scanner_running
    
    if BARCODE_MODE == 'KEYBOARD':
        input_thread = threading.Thread(target=get_input, daemon=True)
        input_thread.start()
        return
    
    if _barcode_scanner_thread is None or not _barcode_scanner_thread.is_alive():
        _barcode_scanner_running = True
        _barcode_scanner_thread = threading.Thread(target=_barcode_scanner_loop, daemon=True)
        _barcode_scanner_thread.start()

def stop_barcode_scanner():
    global _barcode_scanner_running, _barcode_scanner
    _barcode_scanner_running = False
    
    with _barcode_scanner_lock:
        if _barcode_scanner is not None:
            try:
                _barcode_scanner.close()
            except:
                pass
            _barcode_scanner = None

start_barcode_scanner()