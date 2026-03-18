from pynput import keyboard
import time
import threading

_scanner = None
_callback = None
_listener_thread = None
_lock = threading.Lock()

class BarcodeScannerPynput:
    def __init__(self):
        self.barcode = ""
        self.last_key_time = time.time()
        self.timeout = 0.05
        self._callback = None

    def set_callback(self, cb):
        self._callback = cb

    def on_press(self, key):
        current_time = time.time()
        if current_time - self.last_key_time > self.timeout:
            self.barcode = ""
        self.last_key_time = current_time
        try:
            if hasattr(key, 'char') and key.char is not None:
                self.barcode += key.char
            elif key == keyboard.Key.space:
                self.barcode += ' '
            elif key == keyboard.Key.enter:
                if self.barcode:
                    self.process_barcode(self.barcode.strip())
                self.barcode = ""
        except AttributeError:
            pass

    def process_barcode(self, barcode):
        if self._callback:
            try:
                threading.Thread(target=self._callback, args=(barcode,), daemon=True).start()
            except Exception:
                pass

    def _run_listener(self):
        with keyboard.Listener(on_press=self.on_press) as listener:
            listener.join()

def connect_barcode_signal(callback):
    global _scanner, _callback, _listener_thread
    with _lock:
        _callback = callback
        if _scanner is None:
            _scanner = BarcodeScannerPynput()
        _scanner.set_callback(callback)
        if _listener_thread is None or not _listener_thread.is_alive():
            _listener_thread = threading.Thread(target=_scanner._run_listener, daemon=True)
            _listener_thread.start()

def disconnect_barcode_signal(callback):
    global _callback
    with _lock:
        _callback = None
        if _scanner is not None:
            _scanner.set_callback(None)

def is_barcode_scanner_connected():
    return _listener_thread is not None and _listener_thread.is_alive()

if __name__ == "__main__":
    scanner = BarcodeScannerPynput()
    scanner.set_callback(lambda b: print(f"Scanned: {b}"))
    scanner._run_listener()