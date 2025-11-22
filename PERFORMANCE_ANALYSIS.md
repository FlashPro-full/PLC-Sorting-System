# Performance Analysis: `on_photo_eye_triggered()`

## Function Execution Flow

### 1. Initial Setup (Lines 35-42)
- **`read_belt_speed()`** - Modbus TCP read operation
  - **Time**: 10-50ms (typical), up to 5s (timeout)
  - **Blocking**: Yes (waits for PLC response)
  - **Lock**: Uses `modbus_lock` (may wait if PLC is busy)
  - **Network**: TCP/IP to PLC device

- **Lock acquisition**: `book_dict_lock`
  - **Time**: <0.1ms (microseconds)
  - **Blocking**: Yes (waits if another thread holds lock)

### 2. Update Existing Items Loop (Lines 44-81)
- **Loop through all items in `book_dict`**
  - **Time per item**: ~0.1-0.5ms (depends on item count)
  - **Operations per item**:
    - Dictionary lookups: ~0.01ms
    - Math calculations: ~0.01ms
    - Dictionary updates: ~0.01ms
    - `write_bucket()` if pusher activation needed: 10-50ms (Modbus write)

- **`write_bucket()`** (if triggered, lines 69)
  - **Time**: 10-50ms per write (typical), up to 5s (timeout)
  - **Blocking**: Yes (waits for PLC response)
  - **Operations**: 2-3 Modbus register writes
  - **Lock**: Uses `modbus_lock` (may wait if PLC is busy)

- **Item removal loop** (lines 78-81)
  - **Time**: ~0.1ms per item removed
  - **Blocking**: No (just dictionary operations)

### 3. Get Current Barcode (Lines 83-90)
- **Lock acquisition**: `last_barcode_lock`
  - **Time**: <0.1ms
  - **Blocking**: Yes (waits if barcode scanner thread holds lock)

- **Early return if no barcode**
  - **Time**: <0.1ms
  - **`broadcast_active_items()`** if items removed
    - **Time**: 1-5ms (WebSocket emit, non-blocking)

### 4. PalletIQ API Call (Lines 92-107)
- **`request_palletiq(current_barcode)`** - HTTP API call
  - **Time**: 100-500ms (typical), can be 1-5s (slow network/timeout)
  - **Blocking**: Yes (waits for HTTP response)
  - **Operations**:
    - Token validation/refresh: 50-200ms (if needed)
    - HTTP GET request: 50-300ms
    - JSON parsing: <1ms
    - Settings lookup: <1ms
  - **Network**: Internet connection to PalletIQ API
  - **This is the LONGEST operation**

### 5. Update Current Item (Lines 109-147)
- **Dictionary operations**: ~0.1ms
- **Math calculations**: ~0.01ms
- **`write_bucket()`** (if pusher activation needed, line 138)
  - **Time**: 10-50ms (same as above)
  - **Blocking**: Yes

### 6. Broadcast to Clients (Line 149)
- **`broadcast_active_items()`** - WebSocket emit
  - **Time**: 1-5ms (non-blocking, async)
  - **Operations**:
    - Lock acquisition: <0.1ms
    - Build items array: ~0.1-1ms (depends on item count)
    - `socketio.emit()`: 1-5ms (queued, non-blocking)
  - **Network**: WebSocket to connected clients

## Total Execution Time Breakdown

### Best Case Scenario (Fast Network, No Pusher Activation)
1. `read_belt_speed()`: 10ms
2. Update existing items (10 items): 1ms
3. Get barcode: 0.1ms
4. `request_palletiq()`: 100ms ⭐ **LONGEST**
5. Update current item: 0.1ms
6. `broadcast_active_items()`: 2ms
**Total: ~113ms**

### Typical Case Scenario
1. `read_belt_speed()`: 20ms
2. Update existing items (20 items, 1 pusher activation): 35ms
3. Get barcode: 0.1ms
4. `request_palletiq()`: 200ms ⭐ **LONGEST**
5. Update current item: 0.1ms
6. `broadcast_active_items()`: 3ms
**Total: ~258ms**

### Worst Case Scenario (Slow Network, Multiple Pusher Activations)
1. `read_belt_speed()`: 50ms (or timeout 5000ms)
2. Update existing items (50 items, 5 pusher activations): 250ms
3. Get barcode: 0.1ms
4. `request_palletiq()`: 2000ms ⭐ **LONGEST** (slow API)
5. Update current item + pusher activation: 50ms
6. `broadcast_active_items()`: 5ms
**Total: ~2355ms (2.4 seconds)**

### Worst Case with Timeouts
1. `read_belt_speed()`: 5000ms (timeout)
2. Update existing items: 250ms
3. `request_palletiq()`: 5000ms (timeout)
4. Other operations: 10ms
**Total: ~10260ms (10+ seconds)**

## Bottlenecks

### 1. **PalletIQ API Call** (Primary Bottleneck)
- **Impact**: 100-2000ms (typically 200-500ms)
- **Blocking**: Yes
- **Solution**: Could be made async, but current implementation is synchronous

### 2. **Modbus Operations** (Secondary Bottleneck)
- **Impact**: 10-50ms per operation (can be 5000ms on timeout)
- **Blocking**: Yes
- **Operations**: 
  - `read_belt_speed()`: 1 call
  - `write_bucket()`: 0-N calls (depends on items needing pusher activation)

### 3. **Lock Contention**
- **Impact**: Variable (depends on concurrent operations)
- **Locks**:
  - `book_dict_lock`: Held during entire item update loop
  - `modbus_lock`: Held during PLC operations
  - `last_barcode_lock`: Brief acquisition

## Recommendations

1. **Make PalletIQ API call async** - Use threading or async/await
2. **Cache belt speed** - Read once per second instead of every trigger
3. **Batch Modbus writes** - If multiple pushers need activation
4. **Reduce lock hold time** - Release `book_dict_lock` before API call
5. **Add timeout handling** - Prevent function from hanging on slow operations

## Current System Impact

- **Signal/Slot**: Photo eye monitor runs in separate thread, triggers callback
- **WebSocket**: Broadcast is non-blocking, doesn't delay function
- **HTTP**: Only used for `/active-items` endpoint (not in this function)
- **Thread Safety**: All operations are properly locked

## Real-World Performance

In a production environment with:
- 10-20 active items
- Good network connection (50-100ms API latency)
- Responsive PLC (10-20ms Modbus operations)

**Expected execution time: 200-300ms per photo eye trigger**

This is acceptable for a conveyor system where photo eye triggers are typically 1-5 seconds apart.

