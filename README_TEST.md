# Test Scripts for Conveyor System

These test scripts simulate barcode scanning and photo eye triggers without requiring actual hardware or manual intervention.

## Test Scripts

### 1. `test_barcode_scanner.py`
Simulates barcode scanning events.

**Usage:**
```bash
# Interactive mode
python test_barcode_scanner.py

# Command line mode (scan multiple barcodes)
python test_barcode_scanner.py 9781234567890 9780987654321 9781122334455
```

**Interactive Commands:**
- Enter a barcode to simulate scanning
- Enter `auto` for automatic test sequence
- Enter `quit` to exit

### 2. `test_photo_eye.py`
Simulates photo eye trigger events.

**Usage:**
```bash
# Interactive mode
python test_photo_eye.py

# Command line mode (trigger multiple positionIds)
python test_photo_eye.py 101 102 103 104
```

**Interactive Commands:**
- Enter a positionId (integer) to simulate trigger
- Enter `auto` for automatic test sequence
- Enter `quit` to exit
- Press Enter for default positionId (101)

### 3. `test_full_flow.py`
Simulates the complete flow: barcode scanning → wait for PalletIQ → photo eye trigger.

**Usage:**
```bash
# Interactive mode
python test_full_flow.py

# Command line mode (multiple flows)
python test_full_flow.py 9781234567890 101 9780987654321 102

# Or with default positionIds
python test_full_flow.py 9781234567890 9780987654321 9781122334455
```

**Interactive Commands:**
- Enter a barcode to simulate full flow (default positionId=101)
- Enter `barcode,positionId` for custom positionId (e.g., `9781234567890,105`)
- Enter `auto` for automatic test sequence
- Enter `quit` to exit

## How It Works

These test scripts directly call the callback functions registered in `app.py`:
- `on_barcode_scanned(barcode)` - Simulates barcode scanning
- `on_photo_eye_triggered(positionId)` - Simulates photo eye trigger

The scripts bypass the actual hardware (barcode scanner and PLC photo eye) and directly invoke the application logic, allowing you to test the system without physical hardware or manual intervention.

## Testing Scenarios

### Scenario 1: Single Item Flow
```bash
python test_full_flow.py
# Enter: 9781234567890
```

### Scenario 2: Multiple Items (Sequential)
```bash
python test_full_flow.py 9781234567890 9780987654321 9781122334455
```

### Scenario 3: Rapid Scanning
```bash
python test_barcode_scanner.py 9781234567890 9780987654321 9781122334455 9785544332211
# Then manually trigger photo eye for each:
python test_photo_eye.py 101 102 103 104
```

### Scenario 4: Photo Eye Only (for existing items)
```bash
# First ensure items exist in book_dict (via scanning or manual entry)
python test_photo_eye.py 101 102 103
```

## Notes

- These scripts require the Flask app to be running (or at least the app module to be importable)
- The scripts use the same callback functions as the real hardware, so the behavior is identical
- All timing and delays are configurable in the scripts
- The scripts are safe to run while the main application is running

## Integration with Real System

When the real PLC and barcode scanner are connected:
- The real hardware will work alongside these test scripts
- Test scripts can be used to add test items while real items are being processed
- Useful for debugging and development without disrupting production

