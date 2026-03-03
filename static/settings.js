document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("settingsForm");
    const beltSpeedForm = document.getElementById("beltSpeedForm");
    const beltSpeedInput = document.getElementById("beltSpeedInput");
    const beltSpeedSource = document.getElementById("beltSpeedSource");

    // Tab switching (fix navigation: aria-hidden, focus, single scroll container)
    document.querySelectorAll(".settings-tab").forEach(function (tab) {
        tab.addEventListener("click", function () {
            var targetId = "tab-" + tab.getAttribute("data-tab");
            document.querySelectorAll(".settings-tab").forEach(function (t) {
                t.classList.toggle("active", t === tab);
                t.setAttribute("aria-selected", t === tab ? "true" : "false");
            });
            document.querySelectorAll(".settings-tab-panel").forEach(function (panel) {
                var isActive = panel.id === targetId;
                panel.classList.toggle("hidden", !isActive);
                panel.setAttribute("aria-hidden", isActive ? "false" : "true");
            });
            tab.focus();
        });
    });

    // Bucket distance: load
    fetch("/get-settings")
        .then(response => response.json())
        .then(settings => {
            document.querySelectorAll("#pusherSettings fieldset").forEach(fieldset => {
                const pusherName = fieldset.querySelector("legend").innerText;
                const pusherSettings = settings[pusherName];
                if (pusherSettings) {
                    const labelSelect = fieldset.querySelector("select[id=\"" + pusherName + "_label\"]");
                    if (labelSelect) labelSelect.value = pusherSettings.label;
                    const distanceInput = fieldset.querySelector("input[id=\"" + pusherName + "_distance\"]");
                    if (distanceInput) distanceInput.value = pusherSettings.distance;
                }
            });
        })
        .catch(function () {});

    // Bucket distance: save
    form.addEventListener("submit", function (event) {
        event.preventDefault();
        let updatedSettings = {};
        document.querySelectorAll("#pusherSettings fieldset").forEach(function (fieldset) {
            const pusherName = fieldset.querySelector("legend").innerText;
            const labelSelect = fieldset.querySelector("select[id=\"" + pusherName + "_label\"]");
            const distanceInput = fieldset.querySelector("input[id=\"" + pusherName + "_distance\"]");
            if (labelSelect && distanceInput) {
                updatedSettings[pusherName] = {
                    label: labelSelect.value,
                    distance: parseFloat(distanceInput.value) || 0
                };
            }
        });
        fetch("/update-settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ settings: updatedSettings })
        })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.error) alert(data.error);
            else {
                alert(data.message);
                document.dispatchEvent(new CustomEvent("settingsUpdated"));
            }
        })
        .catch(function () {});
    });

    // Belt speed: load (DF20 from PLC)
    fetch("/get-belt-speed")
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (beltSpeedInput) beltSpeedInput.value = data.speed;
            if (beltSpeedSource) {
                beltSpeedSource.textContent = data.source === "plc"
                    ? "Current value from PLC (DF20)."
                    : "Using default (PLC not connected or read failed).";
            }
        })
        .catch(function () {});

    // Belt speed: save
    if (beltSpeedForm) {
        beltSpeedForm.addEventListener("submit", function (event) {
            event.preventDefault();
            var speed = parseFloat(beltSpeedInput.value);
            if (isNaN(speed) || speed <= 0) {
                alert("Please enter a valid positive speed.");
                return;
            }
            fetch("/update-belt-speed", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ speed: speed })
            })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.error) alert(data.error);
                else {
                    alert(data.message);
                    if (beltSpeedSource) beltSpeedSource.textContent = "Saved to PLC (DF20).";
                }
            })
            .catch(function () { alert("Failed to update belt speed."); });
        });
    }
});
