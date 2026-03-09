let conveyor3D = null;
let initAttempts = 0;
const MAX_INIT_ATTEMPTS = 10;

function initialize3D() {
    initAttempts++;
    const container = document.getElementById('conveyor3d');
    if (!container) {
        return;
    }

    if (window.conveyor3DInstance) {
        conveyor3D = window.conveyor3DInstance;
        return;
    }

    if (typeof window.ConveyorSystem3D !== 'undefined') {
        try {
            conveyor3D = new window.ConveyorSystem3D('conveyor3d');
            window.conveyor3DInstance = conveyor3D;
            initAttempts = 0;
        } catch (error) {
            if (initAttempts < MAX_INIT_ATTEMPTS) {
                setTimeout(initialize3D, 1000);
            }
        }
    } else {
        if (initAttempts < MAX_INIT_ATTEMPTS) {
            setTimeout(initialize3D, 1000);
        }
    }
}

window.addEventListener('conveyor3d-loaded', () => {
    initAttempts = 0;
    setTimeout(initialize3D, 100);
});

function pollForModule() {
    if (typeof window.ConveyorSystem3D !== 'undefined') {
        initAttempts = 0;
        setTimeout(initialize3D, 100);
    } else if (initAttempts < MAX_INIT_ATTEMPTS) {
        setTimeout(pollForModule, 500);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(initialize3D, 500);
    setTimeout(pollForModule, 1000);
});

if (document.readyState !== 'loading') {
    setTimeout(initialize3D, 1000);
    setTimeout(pollForModule, 1500);
}

document.addEventListener('settingsUpdated', () => {
    if (conveyor3D || window.conveyor3DInstance) {
        const instance = conveyor3D || window.conveyor3DInstance;
        instance.loadSettings();
    }
});

