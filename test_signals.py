import time
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from barcode_scanner import _barcode_callback
from plc import _photo_eye_callback

barcodes = [
    "735978486562",
    "786936188363",
    "786936281569",
    "738597122620",
    "786936798807",
    "602498626092",
    "074645885797",
    "027616919144",
    "786936180145",
    "012569585829",
    "097360734447",
    "097368794443",
    "786936303421",
    "786936816808",
    "767712810401",
    "786936708103",
    "043396007246",
    "786936735413",
    "796019791199",
]

def generate_test_signals(count=None, interval=0.5, delay_after_barcode=0.2):
    use_list = count is None
    n = len(barcodes) if use_list else count
    
    if not _barcode_callback:
        return
    
    if not _photo_eye_callback:
        return
    
    try:
        for i in range(0, n):
            barcode = barcodes[i%19]
            
            try:
                callback(barcode)
            except Exception as e:
                print(f"❌ Error calling barcode callback: {e}")
            
            time.sleep(delay_after_barcode)
            
            try:
                callback()
            except Exception as e:
                print(f"❌ Error calling photo eye callback: {e}")
            
            if i < n:
                time.sleep(interval)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during test: {e}")

if __name__ == '__main__':
    import sys
    count = int(sys.argv[1]) if len(sys.argv) > 1 else None  # None = use barcodes list
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 0.2
    start_pos = int(sys.argv[3]) if len(sys.argv) > 3 else 101
    
    generate_test_signals(count, 0.5, delay)