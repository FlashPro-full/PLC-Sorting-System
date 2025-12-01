import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from barcode_scanner import _barcode_callbacks
from plc import _photo_eye_callbacks

def generate_test_signals(count=25, interval=0.5, delay_after_barcode=0.2, start_position=101, prefix="BOOK"):
    print("=" * 70)
    print("Test Signal Generator - Barcode Scanner + PLC Photo Eye")
    print("=" * 70)
    print(f"Testing {count} items")
    print(f"Interval: {interval}s between items")
    print(f"Delay after barcode: {delay_after_barcode}s")
    print(f"Barcode format: {prefix}001, {prefix}002, ...")
    print(f"Photo eye position: {start_position}")
    print("Press Ctrl+C to stop")
    print("-" * 70)
    
    if not _barcode_callbacks:
        print("❌ No barcode callbacks registered. Make sure app.py is running and has called connect_barcode_signal()")
        return
    
    if not _photo_eye_callbacks:
        print("❌ No photo eye callbacks registered. Make sure app.py is running and has called connect_photo_eye_signal()")
        return
    
    print("✅ Callbacks registered. Starting test...\n")
    
    try:
        for i in range(1, count + 1):
            barcode = f"{prefix}{i:03d}"
            positionId = start_position + ((i - 1) % 10)
            
            print(f"[{i}/{count}] Sending barcode: {barcode}")
            for callback in _barcode_callbacks:
                try:
                    callback(barcode)
                except Exception as e:
                    print(f"❌ Error calling barcode callback: {e}")
            
            time.sleep(delay_after_barcode)
            
            print(f"[{i}/{count}] Sending photo eye at position: {positionId}")
            for callback in _photo_eye_callbacks:
                try:
                    callback(positionId)
                except Exception as e:
                    print(f"❌ Error calling photo eye callback: {e}")
            
            if i < count:
                time.sleep(interval)
        
        print(f"\n✅ Test completed: {count} items processed")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during test: {e}")

if __name__ == '__main__':
    import sys
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 0.2
    start_pos = int(sys.argv[3]) if len(sys.argv) > 3 else 101
    prefix = sys.argv[4] if len(sys.argv) > 4 else "BOOK"
    
    generate_test_signals(count, 0.5, delay, start_pos, prefix)

