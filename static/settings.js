document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("settingsForm");

    fetch("/get-settings")
        .then(response => response.json())
        .then(settings => {
            document.querySelectorAll("#pusherSettings fieldset").forEach(fieldset => {
                const pusherName = fieldset.querySelector("legend").innerText;
                const pusherSettings = settings[pusherName];
                if (pusherSettings) {
                    const labelSelect = fieldset.querySelector(`select[id="${pusherName}_label"]`);
                    if (labelSelect) {
                        labelSelect.value = pusherSettings.label;
                    }
                    const distanceInput = fieldset.querySelector(`input[id="${pusherName}_distance"]`);
                    if (distanceInput) {
                        distanceInput.value = pusherSettings.distance;
                    }
                }
            });
        })
        .catch(error => {});

    form.addEventListener("submit", function (event) {
        event.preventDefault();

        let updatedSettings = {};
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
            document.dispatchEvent(new CustomEvent('settingsUpdated'));
        })
        .catch(error => {});
    });
});
