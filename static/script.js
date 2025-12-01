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

    const tbody = document.getElementById("active-items-tbody");
    const countSpan = document.getElementById("items-count");

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

        items.forEach((item, index) => {
            try {
                const barcode = item.barcode;
                if (!barcode) {
                    return;
                }

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
                if (item.positionCm !== undefined && item.positionCm !== null) {
                    positionCm = parseFloat(item.positionCm).toFixed(1) + " cm";
                } else if (item.start_time && item.status === "progress" && item.positionId) {
                    const startTime = typeof item.start_time === 'string' ? parseFloat(item.start_time) : item.start_time;
                    const currentTime = Date.now() / 1000;
                    const elapsed = currentTime - startTime;
                    if (elapsed >= 0) {
                        const position = elapsed * BELT_SPEED;
                        positionCm = position.toFixed(1) + " cm";
                    }
                }

                const status = item.status || "pending";
                let statusColor = "#f39c12";
                let statusBg = "rgba(243, 156, 18, 0.1)";
                if (status === "progress") {
                    statusColor = "#27ae60";
                    statusBg = "rgba(39, 174, 96, 0.1)";
                } else if (status === "routing" || status === "completed") {
                    statusColor = "#3498db";
                    statusBg = "rgba(52, 152, 219, 0.1)";
                }

                const distance = item.distance !== undefined && item.distance !== null ? item.distance.toFixed(1) + " cm" : "N/A";
                const label = item.label !== undefined && item.label !== null ? item.label : "N/A";
                const pusher = item.pusher !== undefined && item.pusher !== null ? item.pusher : "N/A";

                row.innerHTML = `
                    <td style="padding: 10px; font-family: monospace; font-weight: 600; font-size: 1.1em;">${barcode}</td>
                    <td style="padding: 10px;">
                        <span style="padding: 4px 8px; background: rgba(58, 122, 254, 0.1); border-radius: 4px; font-weight: 600; color: var(--accent); font-size: 1.1em;">${label}</span>
                    </td>
                    <td style="padding: 10px;">
                        <span style="padding: 4px 8px; background: ${statusBg}; border-radius: 4px; font-weight: 600; color: ${statusColor}; font-size: 1.1em;">${status}</span>
                    </td>
                    <td style="padding: 10px; font-family: monospace; font-weight: 600; color: var(--accent); font-size: 1.1em;">${item.positionId !== undefined && item.positionId !== null ? item.positionId : "N/A"}</td>
                    <td style="padding: 10px; font-family: monospace; font-weight: 600; color: var(--accent); font-size: 1.1em;" data-position-id="${item.positionId || ''}">
                        <span class="position-cm-display">${positionCm}</span>
                    </td>
                    <td style="padding: 10px; font-family: monospace; font-weight: 600; color: var(--accent); font-size: 1.1em;">${distance}</td>
                    <td style="padding: 10px;">
                        <span style="padding: 4px 8px; background: rgba(255, 193, 7, 0.2); border-radius: 4px; font-weight: 600; font-size: 1.1em;">${pusher}</span>
                    </td>
                    <td style="padding: 10px; font-size: 1.1em; color: var(--muted); font-family: monospace;">${timeStr}</td>
                `;
            } catch (error) {
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
        return;
    }

    if (!socket) {
        try {
            socket = io();
        } catch (error) {
        }
    }

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
let positionUpdateIntervalId = null;
const BELT_SPEED = 32.1;
const MAX_DISTANCE = 972;
const COMPLETION_OFFSET = 3.21;
const UPDATE_INTERVAL = 100;

function updateTablePositions() {
    const tbody = document.getElementById("active-items-tbody");
    if (!tbody) {
        return;
    }

    const currentTime = Date.now() / 1000;
    const itemsToRemove = [];

    frontendItems.forEach((item, barcode) => {
        if (item.status === "routing" || item.status === "completed") {
            if (!item.routingStartTime) {
                item.routingStartTime = currentTime;
            }
            const routingDuration = currentTime - item.routingStartTime;
            if (routingDuration >= 1.5) {
                itemsToRemove.push(barcode);
            }
            return;
        }

        if (item.status !== "progress" || !item.positionId || !item.start_time) {
            return;
        }

        const startTime = typeof item.start_time === 'string' ? parseFloat(item.start_time) : item.start_time;
        const elapsed = currentTime - startTime;

        if (elapsed < 0) {
            return;
        }

        item.positionCm = elapsed * BELT_SPEED;

        const positionCm = item.positionCm;
        const distance = item.distance !== undefined && item.distance !== null ? parseFloat(item.distance) : null;
        const removalThreshold = distance !== null ? distance - COMPLETION_OFFSET : MAX_DISTANCE - COMPLETION_OFFSET;

        if (distance !== null && positionCm >= distance - COMPLETION_OFFSET && !item.pusherActivated) {
            item.pusherActivated = true;
            item.status = "routing";
            item.routingStartTime = currentTime;
            document.dispatchEvent(new CustomEvent('pusherActivate', {
                detail: { barcode: barcode, pusher: item.pusher, distance: distance }
            }));
            updateActiveItemsTableFromFrontendItems();
        } else if (positionCm >= removalThreshold) {
            itemsToRemove.push(barcode);
        }
    });

    itemsToRemove.forEach(barcode => {
        frontendItems.delete(barcode);
    });

    const rows = Array.from(tbody.querySelectorAll("tr"));
    rows.forEach(row => {
        const barcode = row.dataset.barcode;
        if (!barcode) return;

        const item = frontendItems.get(barcode);
        if (!item) {
            row.style.transition = "opacity 0.3s ease-out";
            row.style.opacity = "0";
            setTimeout(() => {
                if (row.parentNode) {
                    row.remove();
                }
            }, 300);
            return;
        }

        if (item.status === "progress" && item.positionId && item.positionCm !== undefined && item.positionCm !== null) {
            const positionCm = parseFloat(item.positionCm).toFixed(1) + " cm";
            const positionCell = row.querySelector('td[data-position-id]');
            if (positionCell) {
                const displaySpan = positionCell.querySelector('.position-cm-display');
                if (displaySpan) {
                    displaySpan.textContent = positionCm;
                }
            }
        }
    });

    if (itemsToRemove.length > 0) {
        updateActiveItemsTableFromFrontendItems();
    }

    document.dispatchEvent(new CustomEvent('activeItemsUpdated', {
        detail: { items: Array.from(frontendItems.values()) }
    }));
}

function startPositionUpdateLoop() {
    if (positionUpdateIntervalId === null) {
        updateTablePositions();
        positionUpdateIntervalId = setInterval(updateTablePositions, UPDATE_INTERVAL);
    }
}

function stopPositionUpdateLoop() {
    if (positionUpdateIntervalId !== null) {
        clearInterval(positionUpdateIntervalId);
        positionUpdateIntervalId = null;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    try {
        socket = io();

        if (socket) {
            socket.on('connect', () => {
            });

            socket.on('disconnect', () => {
            });

            socket.on('add_book', (itemData) => {
                try {
                    if (itemData && itemData.barcode) {
                        const item = {
                            barcode: itemData.barcode,
                            start_time: itemData.start_time,
                            positionId: itemData.positionId,
                            positionCm: itemData.positionCm,
                            pusher: itemData.pusher,
                            label: itemData.label,
                            distance: itemData.distance,
                            status: itemData.status,
                            created_at: itemData.created_at,
                            pusherActivated: false
                        };
                        frontendItems.set(itemData.barcode, item);
                        updateActiveItemsTableFromFrontendItems();
                        document.dispatchEvent(new CustomEvent('activeItemsUpdated', {
                            detail: { items: Array.from(frontendItems.values()) }
                        }));
                    }
                } catch (error) {
                }
            });

            socket.on('update_book', (data) => {
                try {
                    if (data && data.barcode) {
                        let existingItem = frontendItems.get(data.barcode);
                        if (existingItem) {
                            existingItem.positionId = data.positionId;
                            existingItem.status = data.status;
                            existingItem.start_time = data.start_time;
                            existingItem.pusher = data.pusher;
                            existingItem.label = data.label;
                            existingItem.distance = data.distance;
                        }

                    }

                    updateActiveItemsTableFromFrontendItems();
                    document.dispatchEvent(new CustomEvent('activeItemsUpdated', {
                        detail: { items: Array.from(frontendItems.values()) }
                    }));
                } catch (error) {
                }
            });

            socket.on('system_status', (status) => {
                try {
                    updateSystemStatusFromData(status);
                } catch (error) {
                }
            });

        }
    } catch (error) {
    }

    const testBtn = document.getElementById("test-integration-btn");
    if (testBtn) {
        testBtn.addEventListener("click", runIntegrationTest);
    }

    startPositionUpdateLoop();
});

async function loadInitialStatus() {
    try {
        const response = await fetch('/api/system-status');
        const status = await response.json();
        if (status) {
            updateSystemStatusFromData(status);
        }
    } catch (error) {
    }
}

// Load status as soon as script runs (before DOM ready if possible)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadInitialStatus);
} else {
    loadInitialStatus();
}

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

