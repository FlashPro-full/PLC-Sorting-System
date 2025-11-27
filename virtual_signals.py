"""
Virtual Signal Generator for Barcode Scanner and Photo Eye

This module provides functions to simulate barcode scanning and photo eye triggers
for testing purposes without physical hardware.
"""

import threading
import time
from typing import Optional


def simulate_barcode_scan(barcode: str):
    """
    Simulate a barcode scan event.
    
    Args:
        barcode: The barcode string to simulate
        
    Example:
        simulate_barcode_scan("1234567890")
    """
    try:
        from barcode_scanner import _barcode_callbacks, _barcode_callbacks_lock
        
        with _barcode_callbacks_lock:
            callbacks = _barcode_callbacks.copy()
        
        if not callbacks:
            print(f"⚠️ Barcode '{barcode}' simulated but no callbacks registered!")
            return
        
        print(f"📱 Simulating barcode scan: {barcode}")
        
        for callback in callbacks:
            try:
                threading.Thread(target=callback, args=(barcode,), daemon=True).start()
            except Exception as e:
                print(f"❌ Error calling barcode callback: {e}")
    except ImportError:
        print("❌ Could not import barcode_scanner module")
    except Exception as e:
        print(f"❌ Error simulating barcode scan: {e}")


def simulate_photo_eye_trigger(positionId: int):
    """
    Simulate a photo eye trigger event.
    
    Args:
        positionId: The position ID to simulate (typically 101-108)
        
    Example:
        simulate_photo_eye_trigger(101)
    """
    try:
        from plc import _photo_eye_callbacks, _photo_eye_callbacks_lock
        
        with _photo_eye_callbacks_lock:
            callbacks = _photo_eye_callbacks.copy()
        
        if not callbacks:
            print(f"⚠️ Photo eye trigger (positionId={positionId}) simulated but no callbacks registered!")
            return
        
        print(f"👁️ Simulating photo eye trigger: positionId={positionId}")
        
        for callback in callbacks:
            try:
                threading.Thread(target=callback, args=(positionId,), daemon=True).start()
            except Exception as e:
                print(f"❌ Error calling photo eye callback: {e}")
    except ImportError:
        print("❌ Could not import plc module")
    except Exception as e:
        print(f"❌ Error simulating photo eye trigger: {e}")


def simulate_full_flow(barcode: str, positionId: int, delay: float = 0.5):
    """
    Simulate a complete flow: barcode scan followed by photo eye trigger.
    
    Args:
        barcode: The barcode string to simulate
        positionId: The position ID to simulate
        delay: Delay in seconds between barcode scan and photo eye trigger (default: 0.5)
        
    Example:
        simulate_full_flow("1234567890", 101, delay=0.5)
    """
    print(f"🔄 Simulating full flow: barcode={barcode}, positionId={positionId}, delay={delay}s")
    simulate_barcode_scan(barcode)
    
    if delay > 0:
        time.sleep(delay)
    
    simulate_photo_eye_trigger(positionId)


def simulate_multiple_barcodes(barcodes: list, interval: float = 1.0):
    """
    Simulate multiple barcode scans with a time interval between them.
    
    Args:
        barcodes: List of barcode strings to simulate
        interval: Time interval in seconds between scans (default: 1.0)
        
    Example:
        simulate_multiple_barcodes(["123", "456", "789"], interval=2.0)
    """
    print(f"📚 Simulating {len(barcodes)} barcode scans with {interval}s interval")
    for i, barcode in enumerate(barcodes, 1):
        print(f"  [{i}/{len(barcodes)}] Scanning: {barcode}")
        simulate_barcode_scan(barcode)
        if i < len(barcodes):
            time.sleep(interval)


def simulate_sequence(sequence: list):
    """
    Simulate a sequence of events. Each event is a dict with 'type' and data.
    
    Args:
        sequence: List of event dicts. Each dict should have:
            - 'type': 'barcode' or 'photo_eye'
            - 'barcode': barcode string (for 'barcode' type)
            - 'positionId': position ID (for 'photo_eye' type)
            - 'delay': optional delay before next event (in seconds)
        
    Example:
        sequence = [
            {'type': 'barcode', 'barcode': '123', 'delay': 0.5},
            {'type': 'photo_eye', 'positionId': 101, 'delay': 1.0},
            {'type': 'barcode', 'barcode': '456', 'delay': 0.5},
            {'type': 'photo_eye', 'positionId': 102}
        ]
        simulate_sequence(sequence)
    """
    print(f"🎬 Simulating sequence of {len(sequence)} events")
    for i, event in enumerate(sequence, 1):
        event_type = event.get('type')
        delay = event.get('delay', 0)
        
        if event_type == 'barcode':
            barcode = event.get('barcode')
            if barcode:
                print(f"  [{i}/{len(sequence)}] Barcode: {barcode}")
                simulate_barcode_scan(barcode)
            else:
                print(f"  ⚠️ Event {i}: Missing 'barcode' field")
        
        elif event_type == 'photo_eye':
            positionId = event.get('positionId')
            if positionId is not None:
                print(f"  [{i}/{len(sequence)}] Photo Eye: positionId={positionId}")
                simulate_photo_eye_trigger(positionId)
            else:
                print(f"  ⚠️ Event {i}: Missing 'positionId' field")
        
        else:
            print(f"  ⚠️ Event {i}: Unknown type '{event_type}'")
        
        if delay > 0 and i < len(sequence):
            time.sleep(delay)


# Interactive mode functions for command-line testing
def interactive_mode():
    """
    Start an interactive mode for testing virtual signals.
    """
    print("\n" + "="*60)
    print("🎮 Virtual Signal Generator - Interactive Mode")
    print("="*60)
    print("Commands:")
    print("  b <barcode>        - Simulate barcode scan")
    print("  p <positionId>     - Simulate photo eye trigger")
    print("  f <barcode> <pos>   - Simulate full flow (barcode + photo eye)")
    print("  q                  - Quit")
    print("="*60 + "\n")
    
    while True:
        try:
            command = input("> ").strip().split()
            
            if not command:
                continue
            
            cmd = command[0].lower()
            
            if cmd == 'q':
                print("👋 Exiting interactive mode")
                break
            
            elif cmd == 'b' and len(command) >= 2:
                barcode = command[1]
                simulate_barcode_scan(barcode)
            
            elif cmd == 'p' and len(command) >= 2:
                try:
                    positionId = int(command[1])
                    simulate_photo_eye_trigger(positionId)
                except ValueError:
                    print("❌ Invalid positionId. Must be an integer.")
            
            elif cmd == 'f' and len(command) >= 3:
                barcode = command[1]
                try:
                    positionId = int(command[2])
                    delay = float(command[3]) if len(command) >= 4 else 0.5
                    simulate_full_flow(barcode, positionId, delay)
                except ValueError:
                    print("❌ Invalid positionId or delay. positionId must be integer, delay must be float.")
            
            else:
                print("❌ Invalid command. Type 'q' to quit or see commands above.")
        
        except KeyboardInterrupt:
            print("\n👋 Exiting interactive mode")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    # Example usage when run directly
    print("Virtual Signal Generator")
    print("Run interactive_mode() for interactive testing")
    print("\nExample usage:")
    print("  from virtual_signals import simulate_barcode_scan, simulate_photo_eye_trigger")
    print("  simulate_barcode_scan('1234567890')")
    print("  simulate_photo_eye_trigger(101)")
    print("\nStarting interactive mode...\n")
    interactive_mode()

