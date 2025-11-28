function updateActiveItemsTableFromFrontendItems() {
    const items = Array.from(frontendItems.values());
    const data = {
        items: items,
        count: items.length,
        timestamp: new Date().toLocaleString()
    };
    updateActiveItemsTableFromData(data);
}

function calculateCurrentPosition(startTime, beltSpeed = 32.1) {
    if (!startTime) return null;
    const now = Date.now() / 1000;
    const elapsed = now - startTime;
    return elapsed * beltSpeed;
}

function updateActiveItemsTableFromData(data) {
    console.log("📊 updateActiveItemsTableFromData() called");
    
    let items = [];
    if (data.items) {
        if (Array.isArray(data.items)) {
            items = data.items;
        } else if (typeof data.items === 'object') {
            items = Object.entries(data.items).map(([barcode, itemData]) => ({
                barcode: barcode,
                ...itemData
            }));
        }
    }
    
    const itemCount = items.length;
    console.log("📊 Data received:", {
        itemCount: itemCount,
        items: items,
        timestamp: data.timestamp
    });
    
    const tbody = document.getElementById("active-items-tbody");
    const countSpan = document.getElementById("items-count");
    
    console.log("📊 Table elements found:", {
        tbody: tbody ? "✅" : "❌",
        countSpan: countSpan ? "✅" : "❌"
    });
    
    if (!tbody) return;
    
    if (items && items.length > 0) {
        Array.from(tbody.children).forEach(row => {
            if (!row.dataset.barcode) {
                row.remove();
            }
        });
        
        const existingRows = {};
        Array.from(tbody.children).forEach(row => {
            const barcode = row.dataset.barcode;
            if (barcode) {
                existingRows[barcode] = row;
            }
        });
        
        const activeBarcodes = new Set(items.map(item => item.barcode));
        
        Object.keys(existingRows).forEach(barcode => {
            if (!activeBarcodes.has(barcode)) {
                const row = existingRows[barcode];
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
        
        console.log(`📊 Processing ${items.length} items for table`);
        items.forEach((item, index) => {
            try {
                const barcode = item.barcode;
                if (!barcode) {
                    console.warn(`⚠️ Item ${index} has no barcode, skipping`);
                    return;
                }
                
                console.log(`📊 Item ${index + 1}/${items.length}:`, {
                    barcode: barcode,
                    positionId: item.positionId,
                    label: item.label,
                    pusher: item.pusher
                });
                let row = existingRows[barcode];
                
                if (!row) {
                    row = document.createElement("tr");
                    row.dataset.barcode = barcode;
                    row.style.borderBottom = "1px solid var(--border)";
                    row.style.transition = "background 0.2s, opacity 0.3s";
                    row.onmouseenter = () => row.style.background = "rgba(58, 122, 254, 0.05)";
                    row.onmouseleave = () => row.style.background = "";
                    tbody.appendChild(row);
                    existingRows[barcode] = row;
                }
                
                const timeStr = item.created_at || new Date().toLocaleTimeString();
                
                let positionCm = "0.0 cm";
                if (item.start_time) {
                    const position = calculateCurrentPosition(item.start_time, BELT_SPEED);
                    if (position !== null) {
                        positionCm = position.toFixed(1) + " cm";
                    }
                }
        
                const status = item.status || "pending";
                const statusColor = status === "progress" ? "#27ae60" : "#f39c12";
                const statusBg = status === "progress" ? "rgba(39, 174, 96, 0.1)" : "rgba(243, 156, 18, 0.1)";
                
                const distance = item.distance !== undefined && item.distance !== null ? item.distance.toFixed(1) + " cm" : "N/A";
                
                row.innerHTML = `
                    <td style="padding: 10px; font-family: monospace; font-weight: 600; font-size: 1.1em;">${barcode}</td>
                    <td style="padding: 10px;">
                        <span style="padding: 4px 8px; background: rgba(58, 122, 254, 0.1); border-radius: 4px; font-weight: 600; color: var(--accent); font-size: 1.1em;">
                            ${item.label || "N/A"}
                        </span>
                    </td>
                    <td style="padding: 10px;">
                        <span style="padding: 4px 8px; background: ${statusBg}; border-radius: 4px; font-weight: 600; color: ${statusColor}; font-size: 1.1em;">
                            ${status}
                        </span>
                    </td>
                    <td style="padding: 10px; font-family: monospace; font-weight: 600; color: var(--accent); font-size: 1.1em;">
                        ${positionId !== undefined && positionId !== null ? positionId : "N/A"}
                    </td>
                    <td style="padding: 10px; font-family: monospace; font-weight: 600; color: var(--accent); font-size: 1.1em;" data-position-id="${positionId || ''}">
                        <span class="position-cm-display">${positionCm}</span>
                    </td>
                    <td style="padding: 10px; font-family: monospace; font-weight: 600; color: var(--accent); font-size: 1.1em;">
                        ${distance}
                    </td>
                    <td style="padding: 10px;">
                        <span style="padding: 4px 8px; background: rgba(255, 193, 7, 0.2); border-radius: 4px; font-weight: 600; font-size: 1.1em;">
                            ${item.pusher || "N/A"}
                        </span>
                    </td>
                    <td style="padding: 10px; font-size: 1.1em; color: var(--muted); font-family: monospace;">
                        ${timeStr}
                    </td>
                `;
            } catch (error) {
                console.error(`❌ Error processing item ${index}:`, error, item);
            }
        });
        
        if (countSpan) {
            countSpan.textContent = itemCount;
        }
        
        document.dispatchEvent(new CustomEvent('activeItemsUpdated', {
            detail: { items: items }
        }));
    } else {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="padding: 12px; text-align: center; color: var(--muted); font-style: italic; font-size: 1.1em;">
                    Waiting for items...
                </td>
            </tr>
        `;
        if (countSpan) {
            countSpan.textContent = "0";
        }
        
        document.dispatchEvent(new CustomEvent('activeItemsUpdated', {
            detail: { items: [] }
        }));
    }
}

async function updateActiveItemsTable() {
    if (socket && socket.connected) {
        console.log('📡 WebSocket connected - waiting for book_dict_update event');
        return;
    }
    
    if (!socket) {
        console.warn('⚠️ Socket not initialized, attempting to initialize...');
        try {
            socket = io();
        } catch (error) {
            console.error('❌ Failed to initialize socket:', error);
        }
    }
    
    console.warn('⚠️ WebSocket not connected - using HTTP fallback');
    try {
        const response = await fetch("/book-dict");
        const data = await response.json();
        if (data.items) {
            const items = Object.entries(data.items).map(([barcode, itemData]) => ({
                barcode: barcode,
                ...itemData
            }));
            updateActiveItemsTableFromData({ items: items, count: items.length, timestamp: data.timestamp });
        }
    } catch (error) {
        console.error("Error updating active items table:", error);
    }
}

function updateSystemStatusFromData(status) {
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
    
    const photoEyeStatus = document.getElementById("photo-eye-status");
    if (photoEyeStatus) {
        if (status.photo_eye.connected) {
            photoEyeStatus.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #fff; margin-right: 6px; opacity: 1; box-shadow: 0 0 6px rgba(255,255,255,0.8);"></span>${status.photo_eye.message}`;
            photoEyeStatus.style.background = "#27ae60";
        } else {
            photoEyeStatus.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #fff; margin-right: 6px; opacity: 0.5;"></span>${status.photo_eye.message}`;
            photoEyeStatus.style.background = "#666";
        }
    }
}

let socket = null;
let frontendItems = new Map();
let positionUpdateAnimationId = null;
const BELT_SPEED = 32.1;

function updateTablePositions() {
    const tbody = document.getElementById("active-items-tbody");
    if (!tbody) {
        positionUpdateAnimationId = requestAnimationFrame(updateTablePositions);
        return;
    }
    
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const currentTime = Date.now() / 1000;
    
    rows.forEach(row => {
        const barcode = row.dataset.barcode;
        if (!barcode) return;
        
        const item = frontendItems.get(barcode);
        if (!item || !item.start_time) return;
        
        const elapsed = currentTime - item.start_time;
        if (elapsed < 0) return;
        
        const currentPosition = elapsed * BELT_SPEED;
        
        const positionCell = row.querySelector('td[data-position-id]');
        if (positionCell) {
            const displaySpan = positionCell.querySelector('.position-cm-display');
            if (displaySpan) {
                displaySpan.textContent = currentPosition.toFixed(1) + " cm";
            }
        }
    });
    
    positionUpdateAnimationId = requestAnimationFrame(updateTablePositions);
}

function startPositionUpdateLoop() {
    if (positionUpdateAnimationId === null) {
        console.log("✅ Starting real-time position update loop (synchronized with 3D)");
        positionUpdateAnimationId = requestAnimationFrame(updateTablePositions);
    }
}

function stopPositionUpdateLoop() {
    if (positionUpdateAnimationId !== null) {
        cancelAnimationFrame(positionUpdateAnimationId);
        positionUpdateAnimationId = null;
        console.log("⏹️ Stopped real-time position update loop");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 Frontend initializing...");
    
    try {
        socket = io();
        console.log("✅ Socket.IO initialized");
        
        if (socket) {
            socket.on('connect', () => {
                console.log('✅ WebSocket connected - real-time updates enabled');
                console.log('📡 All data will be received via WebSocket (no HTTP polling)');
            });
            
            socket.on('disconnect', () => {
                console.log('⚠️ WebSocket disconnected - will reconnect automatically');
            });
            
            socket.on('book_dict_update', (bookDict) => {
                console.log("📡 WebSocket 'book_dict_update' event received");
                frontendItems.clear();
                if (bookDict && typeof bookDict === 'object') {
                    for (const [barcode, itemData] of Object.entries(bookDict)) {
                        if (barcode && itemData) {
                            const item = {
                                barcode: barcode,
                                ...itemData
                            };
                            if (itemData.start_time) {
                                item.start_time = itemData.start_time;
                            }
                            frontendItems.set(barcode, item);
                        }
                    }
                }
                updateActiveItemsTableFromFrontendItems();
                
                document.dispatchEvent(new CustomEvent('activeItemsUpdated', {
                    detail: { items: Array.from(frontendItems.values()) }
                }));
            });
            
            socket.on('system_status', (status) => {
                console.log('📊 Received system status (checked once at startup)');
                updateSystemStatusFromData(status);
            });
            
            console.log('✅ WebSocket communication enabled - no HTTP polling needed');
        } else {
            console.error("❌ Socket.IO failed to initialize - frontend will have limited functionality");
        }
    } catch (error) {
        console.error("❌ Failed to initialize Socket.IO:", error);
        console.error("   Frontend will work but real-time updates may not function");
    }

    const testBtn = document.getElementById("test-integration-btn");
    if (testBtn) {
        testBtn.addEventListener("click", runIntegrationTest);
    }
    
    startPositionUpdateLoop();
    
    console.log("✅ Frontend initialization complete");
});

async function runIntegrationTest() {
    const testBtn = document.getElementById("test-integration-btn");
    const testResultsCard = document.getElementById("test-results-card");
    const testResultsDiv = document.getElementById("test-results");
    
    if (!testBtn || !testResultsDiv) return;
    
    testBtn.disabled = true;
    testBtn.textContent = "Running Tests...";
    testResultsCard.style.display = "block";
    testResultsDiv.innerHTML = "<div style='text-align: center; padding: 20px;'>Running integration tests... Please wait.</div>";
    
    try {
        const response = await fetch("/test-integration");
        const results = await response.json();
        
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

