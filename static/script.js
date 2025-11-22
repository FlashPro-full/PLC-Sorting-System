
// Update active items table from WebSocket data (no HTTP request needed)
function updateActiveItemsTableFromData(data) {
    console.log("📊 updateActiveItemsTableFromData() called");
    console.log("📊 Data received:", {
        itemCount: data.count,
        items: data.items,
        timestamp: data.timestamp
    });
    
    const tbody = document.getElementById("active-items-tbody");
    const countSpan = document.getElementById("items-count");
    
    console.log("📊 Table elements found:", {
        tbody: tbody ? "✅" : "❌",
        countSpan: countSpan ? "✅" : "❌"
    });
    
    if (!tbody) return;
    
    if (data.items && data.items.length > 0) {
        // Track existing rows by barcode to update/remove them
        const existingRows = {};
        Array.from(tbody.children).forEach(row => {
            const barcode = row.dataset.barcode;
            if (barcode) {
                existingRows[barcode] = row;
            }
        });
        
        // Track which items are still active
        const activeBarcodes = new Set(data.items.map(item => item.barcode));
        
        // Remove rows for items that are no longer in the list (routed/removed)
        Object.keys(existingRows).forEach(barcode => {
            if (!activeBarcodes.has(barcode)) {
                const row = existingRows[barcode];
                // Add fade-out animation
                row.style.transition = "opacity 0.3s ease-out";
                row.style.opacity = "0";
                setTimeout(() => {
                    if (row.parentNode) {
                        row.remove();
                    }
                }, 300);
                delete existingRows[barcode];
            }
        });
        
        // Add or update rows for each item
        console.log(`📊 Processing ${data.items.length} items for table`);
        data.items.forEach((item, index) => {
            const barcode = item.barcode;
            console.log(`📊 Item ${index + 1}/${data.items.length}:`, {
                barcode: barcode,
                position_id: item.position_id,
                label: item.label,
                pusher: item.pusher
            });
            let row = existingRows[barcode];
            
            if (!row) {
                // Create new row
                row = document.createElement("tr");
                row.dataset.barcode = barcode;
                row.style.borderBottom = "1px solid var(--border)";
                row.style.transition = "background 0.2s, opacity 0.3s";
                row.onmouseenter = () => row.style.background = "rgba(58, 122, 254, 0.05)";
                row.onmouseleave = () => row.style.background = "";
                tbody.appendChild(row);
                existingRows[barcode] = row;
            }
            
            // Format time
            const timeStr = item.created_at || new Date().toLocaleTimeString();
            
            // Calculate distance traveled based on position ID (changable distance)
            const distanceTraveled = item.distance_traveled !== undefined 
                ? `${item.distance_traveled.toFixed(1)} cm`
                : "Calculating...";
            
            // Photo Eye detection info
            const photoEyeTime = item.photo_eye_detected_at || "N/A";
            const photoEyeBadge = photoEyeTime !== "N/A" 
                ? `<span style="padding: 4px 8px; background: rgba(39, 174, 96, 0.2); border-radius: 4px; font-weight: 600; font-size: 1.0em; color: #27ae60;">👁️ ${photoEyeTime}</span>`
                : `<span style="padding: 4px 8px; background: rgba(149, 165, 166, 0.2); border-radius: 4px; font-size: 1.0em; color: #95a5a6;">N/A</span>`;
            
                    row.innerHTML = `
                        <td style="padding: 10px; font-family: monospace; font-weight: 600; font-size: 1.1em;">${item.barcode}</td>
                        <td style="padding: 10px;">
                            <span style="padding: 4px 8px; background: rgba(58, 122, 254, 0.1); border-radius: 4px; font-weight: 600; color: var(--accent); font-size: 1.1em;">
                                ${item.label || "N/A"}
                            </span>
                        </td>
                        <td style="padding: 10px; font-family: monospace; font-weight: 600; color: var(--accent); font-size: 1.1em;">
                            ${item.position_id}
                        </td>
                        <td style="padding: 10px; font-size: 1.1em; color: var(--accent); font-weight: 600;">
                            ${distanceTraveled}
                        </td>
                        <td style="padding: 10px;">
                            <span style="padding: 4px 8px; background: rgba(255, 193, 7, 0.2); border-radius: 4px; font-weight: 600; font-size: 1.1em;">
                                ${item.pusher}
                            </span>
                        </td>
                        <td style="padding: 10px; font-size: 1.0em;">
                            ${photoEyeBadge}
                        </td>
                        <td style="padding: 10px; font-size: 1.1em; color: var(--muted); font-family: monospace;">
                            ${timeStr}
                        </td>
                    `;
        });
        
        if (countSpan) {
            countSpan.textContent = data.count;
        }
        
        // Dispatch event for 3D visualization update
        document.dispatchEvent(new CustomEvent('activeItemsUpdated', {
            detail: { items: data.items }
        }));
    } else {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="8" style="padding: 12px; text-align: center; color: var(--muted); font-style: italic; font-size: 1.1em;">
                            Waiting for items...
                        </td>
                    </tr>
                `;
        if (countSpan) {
            countSpan.textContent = "0";
        }
        
        // Dispatch empty event
        document.dispatchEvent(new CustomEvent('activeItemsUpdated', {
            detail: { items: [] }
        }));
    }
}

// Real-time active items table (WebSocket only - no HTTP polling)
// This function is kept as fallback only if WebSocket is not available
async function updateActiveItemsTable() {
    // Check if WebSocket is connected
    if (socket && socket.connected) {
        // WebSocket is connected - data will come via WebSocket events
        // No need to make HTTP request
        console.log('📡 WebSocket connected - waiting for active_items_update event');
        return;
    }
    
    // If socket is not initialized, try to initialize it
    if (!socket) {
        console.warn('⚠️ Socket not initialized, attempting to initialize...');
        try {
            socket = io();
        } catch (error) {
            console.error('❌ Failed to initialize socket:', error);
        }
    }
    
    // Fallback: Only use HTTP if WebSocket is not available
    console.warn('⚠️ WebSocket not connected - using HTTP fallback');
    try {
        const response = await fetch("/active-items");
        const data = await response.json();
        updateActiveItemsTableFromData(data);
    } catch (error) {
        console.error("Error updating active items table:", error);
    }
}


// Update system status from WebSocket data
function updateSystemStatusFromData(status) {
    // Update PLC status
    const plcStatus = document.getElementById("plc-status");
    if (plcStatus) {
        if (status.plc.connected) {
            plcStatus.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #fff; margin-right: 6px; opacity: 1; box-shadow: 0 0 6px rgba(255,255,255,0.8);"></span>PLC: ${status.plc.message}`;
            plcStatus.style.background = "#27ae60";
        } else {
            plcStatus.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #fff; margin-right: 6px; opacity: 0.5;"></span>PLC: ${status.plc.message}`;
            plcStatus.style.background = "#e74c3c";
        }
    }
    
    // Update scanner status
    const scannerStatus = document.getElementById("scanner-status");
    if (scannerStatus) {
        if (status.scanner.connected) {
            scannerStatus.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #fff; margin-right: 6px; opacity: 1; box-shadow: 0 0 6px rgba(255,255,255,0.8);"></span>Scanner: ${status.scanner.message}`;
            scannerStatus.style.background = "#27ae60";
        } else {
            scannerStatus.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #fff; margin-right: 6px; opacity: 0.5;"></span>Scanner: ${status.scanner.message}`;
            scannerStatus.style.background = "#e74c3c";
        }
    }
    
    // Update photo eye status
    const photoEyeStatus = document.getElementById("photo-eye-status");
    if (photoEyeStatus) {
        if (status.photo_eye.active) {
            photoEyeStatus.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #fff; margin-right: 6px; opacity: 1; box-shadow: 0 0 6px rgba(255,255,255,0.8);"></span>Photo Eye: ${status.photo_eye.message}`;
            photoEyeStatus.style.background = "#27ae60";
        } else {
            photoEyeStatus.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #fff; margin-right: 6px; opacity: 0.5;"></span>Photo Eye: ${status.photo_eye.message}`;
            photoEyeStatus.style.background = "#666";
        }
    }
}


// Global socket variable for WebSocket communication
let socket = null;

document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 Frontend initializing...");
    
    // Initialize Socket.IO for real-time communication (replaces all HTTP polling)
    try {
        socket = io();
        console.log("✅ Socket.IO initialized");
        
        // Socket.IO connection handlers (only set up if socket was created successfully)
        if (socket) {
            socket.on('connect', () => {
                console.log('✅ WebSocket connected - real-time updates enabled');
                console.log('📡 All data will be received via WebSocket (no HTTP polling)');
                // System status will be sent automatically on connect (checked once at startup)
                // Active items will be broadcast every 1 second via WebSocket
                // No need to request initial data - it will come via WebSocket
            });
            
            socket.on('disconnect', () => {
                console.log('⚠️ WebSocket disconnected - will reconnect automatically');
                // WebSocket will reconnect automatically
                // No fallback polling needed - just wait for reconnection
            });
            
            // Listen for active items updates via WebSocket (replaces HTTP polling)
            socket.on('active_items_update', (data) => {
                console.log("📡 WebSocket 'active_items_update' event received");
                console.log("📡 Event data:", {
                    count: data.count,
                    itemCount: data.items ? data.items.length : 0,
                    timestamp: data.timestamp,
                    items: data.items
                });
                updateActiveItemsTableFromData(data);
                
                // Update scanned barcode display with the most recent item
                if (data.items && data.items.length > 0) {
                    // Sort by created_at timestamp (most recent first)
                    const sortedItems = [...data.items].sort((a, b) => {
                        const timeA = new Date(a.created_at || 0).getTime();
                        const timeB = new Date(b.created_at || 0).getTime();
                        return timeB - timeA;
                    });
                    const mostRecent = sortedItems[0];
                    const displayField = document.getElementById('scannedBarcodeDisplay');
                    if (displayField && mostRecent.barcode) {
                        displayField.value = mostRecent.barcode;
                        // Add visual feedback - briefly highlight
                        displayField.style.backgroundColor = "rgba(58, 122, 254, 0.2)";
                        displayField.style.borderColor = "#3a7afe";
                        setTimeout(() => {
                            displayField.style.backgroundColor = "#f8f9fa";
                            displayField.style.borderColor = "var(--border)";
                        }, 500);
                    }
                }
            });
            
            // Listen for system status updates (sent once on connect, not continuously)
            socket.on('system_status', (status) => {
                console.log('📊 Received system status (checked once at startup)');
                updateSystemStatusFromData(status);
            });
            
            // Note: No HTTP polling - all updates come via WebSocket
            // Backend broadcasts active items every 1 second via WebSocket
            // Initial data will be sent when WebSocket connects
            console.log('✅ WebSocket communication enabled - no HTTP polling needed');
        } else {
            console.error("❌ Socket.IO failed to initialize - frontend will have limited functionality");
        }
    } catch (error) {
        console.error("❌ Failed to initialize Socket.IO:", error);
        console.error("   Frontend will work but real-time updates may not function");
    }

    // Integration test button
    const testBtn = document.getElementById("test-integration-btn");
    if (testBtn) {
        testBtn.addEventListener("click", runIntegrationTest);
    }
    
    console.log("✅ Frontend initialization complete");
});


// System status is now received via WebSocket (checkSystemStatus function removed)
// Status is sent once on WebSocket connect and cached on backend
// No HTTP polling needed - updateSystemStatusFromData() handles WebSocket updates

async function runIntegrationTest() {
    const testBtn = document.getElementById("test-integration-btn");
    const testResultsCard = document.getElementById("test-results-card");
    const testResultsDiv = document.getElementById("test-results");
    
    if (!testBtn || !testResultsDiv) return;
    
    // Disable button and show loading
    testBtn.disabled = true;
    testBtn.textContent = "Running Tests...";
    testResultsCard.style.display = "block";
    testResultsDiv.innerHTML = "<div style='text-align: center; padding: 20px;'>Running integration tests... Please wait.</div>";
    
    try {
        const response = await fetch("/test-integration");
        const results = await response.json();
        
        // Format test results
        let html = `<div style="margin-bottom: 20px;">
            <h3 style="margin: 0 0 10px 0; color: ${results.overall_status === 'pass' ? '#27ae60' : results.overall_status === 'warning' ? '#f39c12' : '#e74c3c'};">
                ${results.overall_status === 'pass' ? '✅' : results.overall_status === 'warning' ? '⚠️' : '❌'} 
                Overall Status: ${results.overall_status.toUpperCase()}
            </h3>
            <div style="font-size: 0.9em; color: #666;">
                Timestamp: ${results.timestamp}<br>
                Passed: ${results.summary.passed} | Failed: ${results.summary.failed} | Warnings: ${results.summary.warnings} | Skipped: ${results.summary.skipped}
            </div>
        </div>`;
        
        html += "<div style='display: grid; gap: 12px;'>";
        for (const [key, test] of Object.entries(results.tests)) {
            const statusColor = test.status === 'pass' ? '#27ae60' : test.status === 'fail' ? '#e74c3c' : test.status === 'warning' ? '#f39c12' : '#95a5a6';
            const statusIcon = test.status === 'pass' ? '✅' : test.status === 'fail' ? '❌' : test.status === 'warning' ? '⚠️' : '⏭️';
            
            html += `<div style="padding: 12px; border-radius: 8px; border: 1px solid ${statusColor}; background: ${statusColor}15;">
                <div style="font-weight: 600; margin-bottom: 4px;">
                    ${statusIcon} ${test.name}: <span style="color: ${statusColor};">${test.status.toUpperCase()}</span>
                </div>
                <div style="font-size: 0.9em; color: #666; margin-bottom: 4px;">${test.message}</div>`;
            
            if (test.details && Object.keys(test.details).length > 0) {
                html += `<details style="font-size: 0.85em; color: #888; margin-top: 4px;">
                    <summary style="cursor: pointer;">View Details</summary>
                    <pre style="margin-top: 8px; padding: 8px; background: #f5f5f5; border-radius: 4px; overflow-x: auto;">${JSON.stringify(test.details, null, 2)}</pre>
                </details>`;
            }
            
            html += "</div>";
        }
        html += "</div>";
        
        testResultsDiv.innerHTML = html;
        
        // Scroll to results
        testResultsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
    } catch (error) {
        testResultsDiv.innerHTML = `<div style="color: #e74c3c; padding: 20px;">
            ❌ Error running integration test: ${error.message}
        </div>`;
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = "Run Integration Test";
    }
}

