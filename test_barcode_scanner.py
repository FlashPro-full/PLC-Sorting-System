"""
Test script to simulate barcode scanning without a real scanner.
This script directly calls the barcode scanning callback to simulate scans.
"""
import time
import sys
from app import on_barcode_scanned

def simulate_barcode_scan(barcode: str):
    """Simulate a barcode scan by directly calling the callback."""
    print(f"📷 Simulating barcode scan: {barcode}")
    on_barcode_scanned(barcode)
    print(f"✅ Barcode scan simulated: {barcode}")

def simulate_multiple_scans(barcodes: list, delay: float = 2.0):
    """Simulate multiple barcode scans with delay between them."""
    print(f"📷 Simulating {len(barcodes)} barcode scans with {delay}s delay...")
    for i, barcode in enumerate(barcodes, 1):
        print(f"\n[{i}/{len(barcodes)}] Scanning barcode: {barcode}")
        simulate_barcode_scan(barcode)
        if i < len(barcodes):
            print(f"⏳ Waiting {delay} seconds before next scan...")
            time.sleep(delay)
    print(f"\n✅ Completed {len(barcodes)} simulated scans")

def interactive_mode():
    """Interactive mode to manually enter barcodes."""
    print("=" * 60)
    print("🧪 Barcode Scanner Test Mode (Interactive)")
    print("=" * 60)
    print("Enter barcodes to simulate scanning (or 'quit' to exit)")
    print("Enter 'auto' for automatic test sequence")
    print("-" * 60)
    
    while True:
        try:
            user_input = input("\n📷 Enter barcode (or 'quit'/'auto'): ").strip()
            
            if user_input.lower() == 'quit':
                print("👋 Exiting test mode...")
                break
            elif user_input.lower() == 'auto':
                # Automatic test sequence
                test_barcodes = [
                    "9781234567890",
                    "9780987654321",
                    "9781122334455",
                    "9785544332211"
                ]
                simulate_multiple_scans(test_barcodes, delay=3.0)
            elif user_input:
                simulate_barcode_scan(user_input)
            else:
                print("⚠️ Please enter a barcode or 'quit'/'auto'")
        except KeyboardInterrupt:
            print("\n👋 Exiting test mode...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Command line mode: test_barcode_scanner.py <barcode1> <barcode2> ...
        barcodes = sys.argv[1:]
        simulate_multiple_scans(barcodes, delay=2.0)
    else:
        # Interactive mode
        interactive_mode()

