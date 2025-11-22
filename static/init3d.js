// Initialize 3D Conveyor System
let conveyor3D = null;

function initialize3D() {
    console.log('🔄 initialize3D() called');
    const container = document.getElementById('conveyor3d');
    if (!container) {
        console.error('❌ Conveyor3D container not found');
        return;
    }
    console.log('✅ Container found:', container);

    // Check if already initialized
    if (window.conveyor3DInstance) {
        console.log('✅ 3D system already initialized, reusing instance');
        conveyor3D = window.conveyor3DInstance;
        return;
    }

    // Wait for module to load
    if (typeof ConveyorSystem3D !== 'undefined') {
        console.log('✅ ConveyorSystem3D class found, creating instance...');
        try {
            conveyor3D = new ConveyorSystem3D('conveyor3d');
            window.conveyor3DInstance = conveyor3D;
            console.log('✅ 3D Conveyor System initialized successfully');
        } catch (error) {
            console.error('❌ Error creating ConveyorSystem3D instance:', error);
        }
    } else {
        console.warn('⚠️ ConveyorSystem3D not found yet, retrying in 1 second...');
        // Retry after a short delay
        setTimeout(() => {
            if (typeof ConveyorSystem3D !== 'undefined') {
                if (!window.conveyor3DInstance) {
                    console.log('✅ ConveyorSystem3D found on retry, creating instance...');
                    try {
                        conveyor3D = new ConveyorSystem3D('conveyor3d');
                        window.conveyor3DInstance = conveyor3D;
                        console.log('✅ 3D Conveyor System initialized (delayed)');
                    } catch (error) {
                        console.error('❌ Error creating instance on retry:', error);
                    }
                } else {
                    conveyor3D = window.conveyor3DInstance;
                    console.log('✅ Instance already exists from auto-init');
                }
            } else {
                console.error('❌ ConveyorSystem3D still not found after retry');
                console.error('   Check Network tab for failed module imports');
                console.error('   Check if Three.js CDN is accessible');
            }
        }, 1000);
    }
}

// Listen for module load event
window.addEventListener('conveyor3d-loaded', () => {
    console.log('📦 Received conveyor3d-loaded event');
    setTimeout(initialize3D, 100);
});

document.addEventListener('DOMContentLoaded', () => {
    console.log('📄 DOM Content Loaded event fired');
    // Wait a bit for module to load
    setTimeout(initialize3D, 200);
});

// Also try immediately if DOM is already loaded
if (document.readyState !== 'loading') {
    console.log('📄 DOM already loaded, initializing after delay');
    setTimeout(initialize3D, 500);
}

// Listen for settings updates
document.addEventListener('settingsUpdated', () => {
    if (conveyor3D || window.conveyor3DInstance) {
        const instance = conveyor3D || window.conveyor3DInstance;
        instance.loadSettings();
    }
});

