document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("settingsForm");

    // Load existing settings from server and update each pusher's inputs
    fetch("/get-settings")
        .then(response => response.json())
        .then(settings => {
            // For each fieldset in the pusher settings
            document.querySelectorAll("#pusherSettings fieldset").forEach(fieldset => {
                // The pusher name is assumed to be the text in the legend element
                const pusherName = fieldset.querySelector("legend").innerText;
                const pusherSettings = settings[pusherName];
                if (pusherSettings) {
                    // Set the dropdown to the saved label
                    const labelSelect = fieldset.querySelector(`select[id="${pusherName}_label"]`);
                    if (labelSelect) {
                        labelSelect.value = pusherSettings.label;
                    }
                    // Set the input field to the saved distance
                    const distanceInput = fieldset.querySelector(`input[id="${pusherName}_distance"]`);
                    if (distanceInput) {
                        distanceInput.value = pusherSettings.distance;
                    }
                }
            });
        })
        .catch(error => {});

    // Handle form submission
    form.addEventListener("submit", function (event) {
        event.preventDefault();

        let updatedSettings = {};
        // Iterate through each pusher's fieldset
        document.querySelectorAll("#pusherSettings fieldset").forEach(fieldset => {
            const pusherName = fieldset.querySelector("legend").innerText;
            const labelSelect = fieldset.querySelector(`select[id="${pusherName}_label"]`);
            const distanceInput = fieldset.querySelector(`input[id="${pusherName}_distance"]`);

            if (labelSelect && distanceInput) {
                const label = labelSelect.value;
                const distance = parseFloat(distanceInput.value) || 0;
                updatedSettings[pusherName] = { label, distance };
            }
        });

        fetch("/update-settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ settings: updatedSettings })
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            // Trigger settings update event for 3D visualization
            document.dispatchEvent(new CustomEvent('settingsUpdated'));
        })
        .catch(error => {});
    });
});
