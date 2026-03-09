document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("settingsForm");
    const beltSpeedForm = document.getElementById("beltSpeedForm");
    const beltSpeedInput = document.getElementById("beltSpeedInput");
    const beltSpeedSource = document.getElementById("beltSpeedSource");

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

    fetch("/get-settings")
        .then(response => response.json())
        .then(function (settings) {
            var pushers = settings.pushers || settings;
            document.querySelectorAll("#pusherSettings fieldset").forEach(function (fieldset) {
                var pusherName = fieldset.querySelector("legend").innerText;
                var pusherSettings = pushers[pusherName];
                if (pusherSettings) {
                    var labelSelect = fieldset.querySelector("select[id=\"" + pusherName + "_label\"]");
                    if (labelSelect) labelSelect.value = pusherSettings.label;
                    var distanceInput = fieldset.querySelector("input[id=\"" + pusherName + "_distance\"]");
                    if (distanceInput) distanceInput.value = pusherSettings.distance;
                }
            });
            if (beltSpeedInput) {
                var speed = settings.belt_speed;
                beltSpeedInput.value = (speed != null && speed !== "") ? Number(speed) : "";
            }
            if (beltSpeedSource) {
                beltSpeedSource.textContent = "From settings.";
            }
        })
        .catch(function () {});

    document.querySelectorAll(".pusher-trigger-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var pusher = parseInt(btn.getAttribute("data-pusher"), 10);
            if (isNaN(pusher)) return;
            fetch("/trigger-pusher", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pusher: pusher })
            })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.error) alert(data.error);
                else if (data.message) alert(data.message);
            })
            .catch(function () { alert("Trigger failed."); });
        });
    });

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        var pushers = {};
        document.querySelectorAll("#pusherSettings fieldset").forEach(function (fieldset) {
            var pusherName = fieldset.querySelector("legend").innerText;
            var labelSelect = fieldset.querySelector("select[id=\"" + pusherName + "_label\"]");
            var distanceInput = fieldset.querySelector("input[id=\"" + pusherName + "_distance\"]");
            if (labelSelect && distanceInput) {
                pushers[pusherName] = {
                    label: labelSelect.value,
                    distance: parseFloat(distanceInput.value) || 0
                };
            }
        });
        fetch("/update-pushers", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pushers: pushers })
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
                    if (beltSpeedSource) beltSpeedSource.textContent = "Saved.";
                }
            })
            .catch(function () { alert("Failed to update belt speed."); });
        });
    }
});
