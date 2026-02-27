import time
from plc import plc, reset_plc, connect_plc

def test_photo_eye():
    print("🔌 Connecting to PLC...")
    connect_plc()
    if plc is None:
        print("❌ Failed to connect to PLC. Please check your connection settings.")
        return
    
    print("✅ Connected to PLC")
    print("📖 Reading photo eye values (Press Ctrl+C to stop)...")
    print("-" * 50)
    
    try:
        for i in range(100):
            value = plc.read_input_registers(0x0015, count=1)
            print(f"Reading #{i+1}: Value = {value}")
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
    except Exception as e:
        print(f"\n❌ Error during reading: {e}")
    finally:
        print("\n🔌 Cleaning up...")
        reset_plc()
        print("✅ Done")

if __name__ == "__main__":
    test_photo_eye()

