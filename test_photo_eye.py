"""
Test script to simulate photo eye triggers without a real photo eye.
This script directly calls the photo eye callback to simulate triggers.
"""
import time
import sys
from app import on_photo_eye_triggered

def simulate_photo_eye_trigger(positionId: int = 101):
    """Simulate a photo eye trigger by directly calling the callback."""
    print(f"👁️ Simulating photo eye trigger: positionId={positionId}")
    on_photo_eye_triggered(positionId)
    print(f"✅ Photo eye trigger simulated: positionId={positionId}")

def simulate_multiple_triggers(positionIds: list, delay: float = 2.0):
    """Simulate multiple photo eye triggers with delay between them."""
    print(f"👁️ Simulating {len(positionIds)} photo eye triggers with {delay}s delay...")
    for i, positionId in enumerate(positionIds, 1):
        print(f"\n[{i}/{len(positionIds)}] Triggering photo eye: positionId={positionId}")
        simulate_photo_eye_trigger(positionId)
        if i < len(positionIds):
            print(f"⏳ Waiting {delay} seconds before next trigger...")
            time.sleep(delay)
    print(f"\n✅ Completed {len(positionIds)} simulated triggers")

def interactive_mode():
    """Interactive mode to manually trigger photo eye."""
    print("=" * 60)
    print("🧪 Photo Eye Test Mode (Interactive)")
    print("=" * 60)
    print("Enter positionId to simulate photo eye trigger (or 'quit' to exit)")
    print("Enter 'auto' for automatic test sequence")
    print("Default positionId: 101")
    print("-" * 60)
    
    while True:
        try:
            user_input = input("\n👁️ Enter positionId (or 'quit'/'auto'): ").strip()
            
            if user_input.lower() == 'quit':
                print("👋 Exiting test mode...")
                break
            elif user_input.lower() == 'auto':
                # Automatic test sequence
                test_position_ids = [101, 102, 103, 104]
                simulate_multiple_triggers(test_position_ids, delay=2.0)
            elif user_input:
                try:
                    positionId = int(user_input)
                    simulate_photo_eye_trigger(positionId)
                except ValueError:
                    print("⚠️ Please enter a valid positionId (integer)")
            else:
                # Default positionId
                simulate_photo_eye_trigger(101)
        except KeyboardInterrupt:
            print("\n👋 Exiting test mode...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Command line mode: test_photo_eye.py <positionId1> <positionId2> ...
        try:
            position_ids = [int(arg) for arg in sys.argv[1:]]
            simulate_multiple_triggers(position_ids, delay=2.0)
        except ValueError:
            print("❌ Error: All arguments must be integers (positionId)")
            sys.exit(1)
    else:
        # Interactive mode
        interactive_mode()

