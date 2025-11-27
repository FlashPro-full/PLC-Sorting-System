"""
Test script to simulate the complete flow: barcode scanning + photo eye trigger.
This automates the entire process for testing without manual intervention.
"""
import time
import sys
from app import on_barcode_scanned, on_photo_eye_triggered

def simulate_full_flow(barcode: str, positionId: int = 101, scan_to_photo_delay: float = 3.0):
    """
    Simulate the complete flow:
    1. Scan barcode
    2. Wait for PalletIQ response (simulated by delay)
    3. Trigger photo eye
    
    Args:
        barcode: Barcode to scan
        positionId: Position ID for photo eye trigger
        scan_to_photo_delay: Delay between scan and photo eye trigger (seconds)
    """
    print("=" * 60)
    print(f"🔄 Simulating Full Flow for Barcode: {barcode}")
    print("=" * 60)
    
    # Step 1: Scan barcode
    print(f"\n[Step 1/2] 📷 Scanning barcode: {barcode}")
    on_barcode_scanned(barcode)
    print(f"✅ Barcode scanned: {barcode}")
    print(f"   Status: Item added to book_dict with status 'pending'")
    print(f"   Waiting for PalletIQ response...")
    
    # Step 2: Wait for PalletIQ response (simulated delay)
    print(f"\n⏳ Waiting {scan_to_photo_delay} seconds (simulating PalletIQ response time)...")
    time.sleep(scan_to_photo_delay)
    
    # Step 3: Trigger photo eye
    print(f"\n[Step 2/2] 👁️ Triggering photo eye: positionId={positionId}")
    on_photo_eye_triggered(positionId)
    print(f"✅ Photo eye triggered: positionId={positionId}")
    print(f"   Status: Item matched and positionId assigned")
    
    print("\n" + "=" * 60)
    print("✅ Full flow simulation completed!")
    print("=" * 60)

def simulate_multiple_flows(barcodes: list, positionIds: list = None, 
                           scan_to_photo_delay: float = 3.0, 
                           flow_delay: float = 5.0):
    """
    Simulate multiple complete flows.
    
    Args:
        barcodes: List of barcodes to scan
        positionIds: List of position IDs (defaults to 101, 102, 103, ...)
        scan_to_photo_delay: Delay between scan and photo eye trigger
        flow_delay: Delay between complete flows
    """
    if positionIds is None:
        positionIds = [101 + i for i in range(len(barcodes))]
    
    if len(positionIds) != len(barcodes):
        print(f"⚠️ Warning: {len(barcodes)} barcodes but {len(positionIds)} positionIds")
        print(f"   Using first {min(len(barcodes), len(positionIds))} items")
        positionIds = positionIds[:len(barcodes)]
    
    print(f"🔄 Simulating {len(barcodes)} complete flows...")
    print(f"   Scan-to-photo delay: {scan_to_photo_delay}s")
    print(f"   Flow-to-flow delay: {flow_delay}s")
    print("=" * 60)
    
    for i, (barcode, positionId) in enumerate(zip(barcodes, positionIds), 1):
        print(f"\n\n[Flow {i}/{len(barcodes)}]")
        simulate_full_flow(barcode, positionId, scan_to_photo_delay)
        
        if i < len(barcodes):
            print(f"\n⏳ Waiting {flow_delay} seconds before next flow...")
            time.sleep(flow_delay)

def interactive_mode():
    """Interactive mode for manual testing."""
    print("=" * 60)
    print("🧪 Full Flow Test Mode (Interactive)")
    print("=" * 60)
    print("Options:")
    print("  1. Enter barcode to simulate full flow (default positionId=101)")
    print("  2. Enter 'barcode,positionId' for custom positionId")
    print("  3. Enter 'auto' for automatic test sequence")
    print("  4. Enter 'quit' to exit")
    print("-" * 60)
    
    while True:
        try:
            user_input = input("\n🔄 Enter barcode (or 'quit'/'auto'): ").strip()
            
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
                test_position_ids = [101, 102, 103, 104]
                simulate_multiple_flows(test_barcodes, test_position_ids, 
                                      scan_to_photo_delay=3.0, flow_delay=5.0)
            elif user_input:
                # Parse input: "barcode,positionId" or just "barcode"
                if ',' in user_input:
                    parts = user_input.split(',')
                    barcode = parts[0].strip()
                    try:
                        positionId = int(parts[1].strip())
                    except (ValueError, IndexError):
                        print("⚠️ Invalid format. Using default positionId=101")
                        positionId = 101
                else:
                    barcode = user_input
                    positionId = 101
                
                simulate_full_flow(barcode, positionId, scan_to_photo_delay=3.0)
            else:
                print("⚠️ Please enter a barcode or 'quit'/'auto'")
        except KeyboardInterrupt:
            print("\n👋 Exiting test mode...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Command line mode: test_full_flow.py <barcode1> [positionId1] <barcode2> [positionId2] ...
        # Or: test_full_flow.py <barcode1> <barcode2> ... (uses default positionIds)
        args = sys.argv[1:]
        barcodes = []
        position_ids = []
        
        i = 0
        while i < len(args):
            barcodes.append(args[i])
            if i + 1 < len(args):
                try:
                    position_ids.append(int(args[i + 1]))
                    i += 2
                except ValueError:
                    position_ids.append(101)  # Default
                    i += 1
            else:
                position_ids.append(101)  # Default
                i += 1
        
        if len(position_ids) == len(barcodes):
            simulate_multiple_flows(barcodes, position_ids, 
                                  scan_to_photo_delay=3.0, flow_delay=5.0)
        else:
            simulate_multiple_flows(barcodes, scan_to_photo_delay=3.0, flow_delay=5.0)
    else:
        # Interactive mode
        interactive_mode()

