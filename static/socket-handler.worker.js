const COMPLETION_OFFSET = 3.21;
const UPDATE_INTERVAL = 100;
const DEFAULT_BELT_SPEED = 32.1;
const DEFAULT_MAX_DISTANCE = 972;
const FETCH_TIMEOUT_SEC = 5;

let items = {};
let beltSpeed = DEFAULT_BELT_SPEED;
let maxDistance = DEFAULT_MAX_DISTANCE;
let tickTimerId = null;

function normalizeItemFromAdd(itemData) {
    return {
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
}

function normalizeItemFromUpdate(data) {
    return {
        barcode: data.barcode,
        start_time: data.start_time,
        positionId: data.positionId,
        positionCm: data.positionCm,
        pusher: data.pusher,
        label: data.label,
        distance: data.distance,
        status: data.status || "pending",
        created_at: data.created_at,
        pusherActivated: false
    };
}

function itemsToArray() {
    return Object.keys(items).map(function (barcode) {
        const item = items[barcode];
        return { barcode: barcode, ...item };
    });
}

function runPositionUpdate() {
    const currentTime = Date.now() / 1000;
    const itemsToRemove = [];
    const pusherActivates = [];

    Object.keys(items).forEach(function (barcode) {
        const item = items[barcode];
        if (item.status === "routing" || item.status === "completed") {
            if (item.start_time == null) {
                item.start_time = currentTime;
            }
            const routingDuration = currentTime - item.start_time;
            if (routingDuration >= 1.5) {
                itemsToRemove.push(barcode);
            }
            return;
        }

        if (item.status === "pending" || item.status === "No response") {
            if (item.start_time != null) {
                const startTime = typeof item.start_time === "string" ? parseFloat(item.start_time) : item.start_time;
                const elapsed = currentTime - startTime;
                if (elapsed >= 0) {
                    const speed = beltSpeed > 0 ? beltSpeed : DEFAULT_BELT_SPEED;
                    const locationCm = elapsed * speed;
                    if (locationCm >= maxDistance) {
                        itemsToRemove.push(barcode);
                    }
                }
            }
            return;
        }

        if (item.status === "fetching" && item.start_time != null) {
            const startTime = typeof item.start_time === "string" ? parseFloat(item.start_time) : item.start_time;
            const elapsed = currentTime - startTime;
            if (elapsed >= FETCH_TIMEOUT_SEC) {
                item.status = "No response";
                item.start_time = currentTime;
            }
            return;
        }

        if (item.status !== "progress" || !item.positionId || item.start_time == null) {
            return;
        }

        const startTime = typeof item.start_time === "string" ? parseFloat(item.start_time) : item.start_time;
        const elapsed = currentTime - startTime;
        if (elapsed < 0) return;

        const speed = beltSpeed > 0 ? beltSpeed : DEFAULT_BELT_SPEED;
        item.positionCm = elapsed * speed;
        const positionCm = item.positionCm;
        const distance = item.distance !== undefined && item.distance !== null ? parseFloat(item.distance) : null;
        const removalThresholdCm = distance !== null ? distance - COMPLETION_OFFSET : maxDistance - COMPLETION_OFFSET;
        const backendPushTimeElapsed = distance !== null && speed > 0 ? distance / speed : null;

        if (distance !== null && positionCm >= distance - COMPLETION_OFFSET && !item.pusherActivated) {
            item.pusherActivated = true;
            pusherActivates.push({ barcode: barcode, pusher: item.pusher, distance: distance });
        }
        if (backendPushTimeElapsed !== null && elapsed >= backendPushTimeElapsed) {
            itemsToRemove.push(barcode);
        } else if (distance === null && positionCm >= removalThresholdCm) {
            itemsToRemove.push(barcode);
        }
    });

    itemsToRemove.forEach(function (barcode) {
        delete items[barcode];
    });

    self.postMessage({ type: "items_updated", items: itemsToArray() });
    pusherActivates.forEach(function (ev) {
        self.postMessage({ type: "pusher_activate", detail: ev });
    });
}

function startTickLoop() {
    if (tickTimerId !== null) return;
    tickTimerId = setInterval(runPositionUpdate, UPDATE_INTERVAL);
}

function stopTickLoop() {
    if (tickTimerId !== null) {
        clearInterval(tickTimerId);
        tickTimerId = null;
    }
}

self.onmessage = function (e) {
    const msg = e.data;
    if (!msg || !msg.type) return;

    switch (msg.type) {
        case "config":
            if (msg.beltSpeed != null) beltSpeed = Number(msg.beltSpeed) || DEFAULT_BELT_SPEED;
            if (msg.maxDistance != null) maxDistance = Number(msg.maxDistance) || DEFAULT_MAX_DISTANCE;
            if (msg.startTick) startTickLoop();
            break;

        case "add_book": {
            const itemData = msg.item;
            if (itemData && itemData.barcode) {
                items[itemData.barcode] = normalizeItemFromAdd(itemData);
                self.postMessage({ type: "items_updated", items: itemsToArray() });
            }
            break;
        }

        case "update_book": {
            const data = msg.data;
            if (data && data.barcode) {
                let existing = items[data.barcode];
                if (!existing) {
                    items[data.barcode] = normalizeItemFromUpdate(data);
                } else {
                    if (data.positionId != null) existing.positionId = data.positionId;
                    if (data.status != null) existing.status = data.status;
                    if (data.start_time != null) existing.start_time = data.start_time;
                    if (data.pusher != null) existing.pusher = data.pusher;
                    if (data.label != null) existing.label = data.label;
                    if (data.distance != null) existing.distance = data.distance;
                }
                self.postMessage({ type: "items_updated", items: itemsToArray() });
            }
            break;
        }

        case "system_status":
            self.postMessage({ type: "system_status", status: msg.status });
            break;

        case "initial_items":
            items = {};
            const list = msg.items || [];
            list.forEach(function (item) {
                if (item && item.barcode) {
                    items[item.barcode] = {
                        barcode: item.barcode,
                        start_time: item.start_time,
                        positionId: item.positionId,
                        positionCm: item.positionCm,
                        pusher: item.pusher,
                        label: item.label,
                        distance: item.distance,
                        status: item.status || "pending",
                        created_at: item.created_at,
                        pusherActivated: item.pusherActivated === true
                    };
                }
            });
            self.postMessage({ type: "items_updated", items: itemsToArray() });
            break;

        case "start_tick":
            startTickLoop();
            break;

        case "stop_tick":
            stopTickLoop();
            break;
    }
};
