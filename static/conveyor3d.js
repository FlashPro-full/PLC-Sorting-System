// Three.js 3D Conveyor System Visualization
console.log('📦 Loading conveyor3d.js module...');

import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js';

console.log('✅ Three.js imported:', typeof THREE);
console.log('✅ OrbitControls imported:', typeof OrbitControls);

class ConveyorSystem3D {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`❌ Container with id "${containerId}" not found`);
            return;
        }
        
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.conveyorBelt = null;
        this.pushers = [];
        this.buckets = []; // Track buckets separately
        this.items = [];
        this.itemsByBarcode = {}; // Track items by barcode for updates
        this.scanner = null;
        this.photoEye = null;
        this.photoEyeDetectionZone = null; // Track items in photo eye zone
        this.animationId = null;
        this.conveyorSpeed = 0.02;
        this.beltSpeedCmPerSec = 32.1; // Belt speed in cm/s
        this.settings = null;
        this.positionIdToZ = this.calculatePositionMapping(); // Cache position ID to Z mapping
        this.lastFrameTime = performance.now(); // For delta-time calculations
        this.frameCount = 0;
        this.positionIdToCm = {}; // Cache position ID to cm mapping
        this.calculatePositionIdToCm();
        
        try {
            this.init();
            // Start animation loop (will handle empty scene until settings load)
            this.animate();
            this.setupEventListeners();
            
            // Load settings asynchronously - this will update pusher positions and camera
            this.loadSettings();
            
            console.log('✅ ConveyorSystem3D initialized successfully');
        } catch (error) {
            console.error('❌ Error initializing ConveyorSystem3D:', error);
            console.error('Stack trace:', error.stack);
            // Show error message in container
            if (this.container) {
                this.container.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #fff; background: #ff4444; border-radius: 8px;">
                        <h3>❌ 3D Visualization Error</h3>
                        <p>${error.message}</p>
                        <p style="font-size: 0.8em; margin-top: 10px;">Check browser console (F12) for details</p>
                    </div>
                `;
            }
        }
    }

    init() {
        // Check WebGL support
        if (!this.isWebGLSupported()) {
            this.container.innerHTML = '<div style="padding: 20px; text-align: center; color: #fff;">❌ WebGL is not supported in your browser. Please use a modern browser like Chrome, Firefox, or Edge.</div>';
            console.error('❌ WebGL not supported');
            return;
        }
        console.log('✅ WebGL supported');

        // Scene setup - working room environment
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xe8e8e8); // Light gray room background
        // No fog - clear visibility
        console.log('✅ Scene created');

        // Camera - calculate position to see entire conveyor
        const width = this.container.clientWidth || 800;
        const height = this.container.clientHeight || 600;
        const aspect = width / height;
        
        // Calculate conveyor dimensions for camera positioning
        let maxPusherDistance = 972;
        if (this.settings) {
            const distances = Object.values(this.settings).map(p => p.distance || 0);
            maxPusherDistance = Math.max(...distances, 972);
        }
        const startBuffer = 200;
        const endBuffer = 200;
        const conveyorLength = startBuffer + maxPusherDistance + endBuffer;
        const conveyorWidth = 80;
        
        // Position camera to see entire conveyor from the SIDE (across), rotated 90 degrees
        // Use wider FOV (60 degrees) to see more of the scene
        this.camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 5000);
        
        // Calculate distance needed to fit conveyor in view
        const conveyorHalfLength = conveyorLength / 2;
        const conveyorHalfWidth = conveyorWidth / 2;
        
        // Position camera to view from the SIDE (across the conveyor)
        // Rotate 90 degrees: view from positive X side, looking along Z-axis (conveyor direction)
        // Camera should be at a good height to see the whole system
        const cameraHeight = Math.max(conveyorWidth * 2, 200); // High enough to see pushers and buckets
        const cameraDistance = Math.max(conveyorHalfWidth * 3, 150); // Distance from conveyor side
        
        // Position camera on the SIDE (positive X), looking along the conveyor (Z-axis)
        // This gives a side view rotated 90 degrees from top-down
        this.camera.position.set(
            cameraDistance, // On the side (positive X)
            cameraHeight, // High enough to see everything
            0 // Centered along conveyor length (Z = 0)
        );
        
        // Look at the center of the conveyor (0, 0, 0)
        // This creates a side view looking along the conveyor
        this.camera.lookAt(0, 0, 0);
        console.log('✅ Camera positioned to see entire conveyor from side:', {
            position: this.camera.position,
            conveyorLength: conveyorLength,
            fov: 60
        });

        // Remove loading indicator
        const loadingDiv = document.getElementById('conveyor3d-loading');
        if (loadingDiv) {
            loadingDiv.remove();
        }

        // Renderer
        try {
            // OPTIMIZED: Disable antialiasing for better performance (can enable if needed)
            this.renderer = new THREE.WebGLRenderer({ antialias: false });
            const width = this.container.clientWidth || 800;
            const height = this.container.clientHeight || 600;
            this.renderer.setSize(width, height);
            // OPTIMIZED: Use faster shadow map type for better performance
            this.renderer.shadowMap.enabled = true;
            this.renderer.shadowMap.type = THREE.BasicShadowMap; // Faster than PCFSoftShadowMap
            this.container.appendChild(this.renderer.domElement);
            console.log(`✅ Renderer created: ${width}x${height}`);
        } catch (error) {
            console.error('❌ Failed to create WebGL renderer:', error);
            this.container.innerHTML = '<div style="padding: 20px; text-align: center; color: #fff;">❌ Failed to initialize 3D renderer. Check browser console for details.</div>';
            return;
        }

        // Controls - allow viewing from different angles
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        
        // Calculate appropriate distance limits based on conveyor size (reuse conveyorHalfLength)
        this.controls.minDistance = Math.max(conveyorHalfLength * 0.5, 200); // Can zoom in closer
        this.controls.maxDistance = Math.max(conveyorHalfLength * 3, 2000); // Can zoom out further
        
        // Allow full rotation for side view (less restrictive angles)
        this.controls.minPolarAngle = Math.PI / 12; // Allow looking from below
        this.controls.maxPolarAngle = Math.PI - Math.PI / 12; // Allow looking from above
        
        this.controls.enablePan = true; // Allow panning to see different parts
        this.controls.panSpeed = 0.8;
        this.controls.rotateSpeed = 0.5;
        
        // Set initial target to center of conveyor
        this.controls.target.set(0, 0, 0);
        this.controls.update();

        // Lighting - adjusted for working room environment
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);

        // Main directional light (simulating overhead lighting)
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.7);
        directionalLight.position.set(0, 700, 0);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        directionalLight.shadow.camera.left = -800;
        directionalLight.shadow.camera.right = 800;
        directionalLight.shadow.camera.top = 800;
        directionalLight.shadow.camera.bottom = -800;
        directionalLight.shadow.camera.near = 0.1;
        directionalLight.shadow.camera.far = 2000;
        this.scene.add(directionalLight);

        // Fill light from side
        const fillLight = new THREE.DirectionalLight(0xffffff, 0.3);
        fillLight.position.set(-300, 400, 300);
        this.scene.add(fillLight);

        // Create working room environment
        this.createWorkingRoom();
        console.log('✅ Working room environment created');

        // Settings will be loaded asynchronously, create components after
        // Components will use default values initially, then update when settings load
        this.createConveyorBelt();
        this.createBarcodeScanner();
        this.createPhotoEye();
        this.createPushers();
        // Static book removed - no initial book model under scanner

        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize());
    }

    createWorkingRoom() {
        // Floor - concrete/industrial floor
        const floorGeometry = new THREE.PlaneGeometry(3000, 3000);
        const floorMaterial = new THREE.MeshStandardMaterial({ 
            color: 0x9e9e9e,
            roughness: 0.9,
            metalness: 0.1
        });
        const floor = new THREE.Mesh(floorGeometry, floorMaterial);
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = 0;
        floor.receiveShadow = true;
        this.scene.add(floor);

        // Back wall
        const backWallGeometry = new THREE.PlaneGeometry(3000, 800);
        const wallMaterial = new THREE.MeshStandardMaterial({ 
            color: 0xd0d0d0,
            roughness: 0.8
        });
        const backWall = new THREE.Mesh(backWallGeometry, wallMaterial);
        backWall.position.set(0, 400, -1500);
        backWall.receiveShadow = true;
        this.scene.add(backWall);

        // Left wall
        const leftWall = new THREE.Mesh(backWallGeometry, wallMaterial);
        leftWall.rotation.y = Math.PI / 2;
        leftWall.position.set(-1500, 400, 0);
        leftWall.receiveShadow = true;
        this.scene.add(leftWall);

        // Right wall
        const rightWall = new THREE.Mesh(backWallGeometry, wallMaterial);
        rightWall.rotation.y = -Math.PI / 2;
        rightWall.position.set(1500, 400, 0);
        rightWall.receiveShadow = true;
        this.scene.add(rightWall);

        // Ceiling
        const ceilingGeometry = new THREE.PlaneGeometry(3000, 3000);
        const ceilingMaterial = new THREE.MeshStandardMaterial({ 
            color: 0xf5f5f5,
            roughness: 0.7
        });
        const ceiling = new THREE.Mesh(ceilingGeometry, ceilingMaterial);
        ceiling.rotation.x = Math.PI / 2;
        ceiling.position.y = 800;
        ceiling.receiveShadow = false;
        this.scene.add(ceiling);

        // Add grid pattern to floor for industrial look
        const gridHelper = new THREE.GridHelper(3000, 30, 0x888888, 0xaaaaaa);
        gridHelper.position.y = 0.1;
        this.scene.add(gridHelper);

        // Add overhead lights (industrial lighting)
        for (let i = -1200; i <= 1200; i += 400) {
            for (let j = -1200; j <= 1200; j += 400) {
                const lightGeometry = new THREE.BoxGeometry(60, 10, 60);
                const lightMaterial = new THREE.MeshStandardMaterial({ 
                    color: 0xffffff,
                    emissive: 0xffffff,
                    emissiveIntensity: 0.3
                });
                const lightFixture = new THREE.Mesh(lightGeometry, lightMaterial);
                lightFixture.position.set(i, 750, j);
                this.scene.add(lightFixture);

                // Add point light for each fixture
                const pointLight = new THREE.PointLight(0xffffff, 0.5, 500);
                pointLight.position.set(i, 750, j);
                this.scene.add(pointLight);
            }
        }
    }

    createConveyorBelt() {
        const group = new THREE.Group();
        
        // Calculate conveyor length based on settings
        // Last pusher is at max distance, add buffers for start/end
        let maxPusherDistance = 972; // Default from Pusher 8
        if (this.settings) {
            const distances = Object.values(this.settings).map(p => p.distance || 0);
            maxPusherDistance = Math.max(...distances, 972);
        }
        
        // Conveyor length: start buffer (200cm) + max pusher distance + end buffer (200cm)
        const startBuffer = 200; // Space for scanner and photo eye
        const endBuffer = 200; // Space after last pusher
        const frameLength = startBuffer + maxPusherDistance + endBuffer;
        
        const frameWidth = 80;
        const frameHeight = 20;

        // Side rails
        const railGeometry = new THREE.BoxGeometry(10, frameHeight, frameLength);
        const railMaterial = new THREE.MeshStandardMaterial({ color: 0xcccccc });
        
        const leftRail = new THREE.Mesh(railGeometry, railMaterial);
        leftRail.position.set(-frameWidth/2, frameHeight/2, 0);
        leftRail.castShadow = true;
        group.add(leftRail);

        const rightRail = new THREE.Mesh(railGeometry, railMaterial);
        rightRail.position.set(frameWidth/2, frameHeight/2, 0);
        rightRail.castShadow = true;
        group.add(rightRail);
        
        // Position conveyor group on floor (floor is at y=0)
        group.position.y = 0;

        // Conveyor belt surface
        const beltGeometry = new THREE.PlaneGeometry(frameWidth - 20, frameLength);
        const beltMaterial = new THREE.MeshStandardMaterial({ 
            color: 0x333333,
            roughness: 0.8,
            metalness: 0.2
        });
        const belt = new THREE.Mesh(beltGeometry, beltMaterial);
        belt.rotation.x = -Math.PI / 2;
        belt.position.y = frameHeight;
        belt.receiveShadow = true;
        group.add(belt);

        // Add rollers
        const rollerCount = 40;
        const rollerSpacing = frameLength / rollerCount;
        const rollerGeometry = new THREE.CylinderGeometry(3, 3, frameWidth - 20, 16);
        const rollerMaterial = new THREE.MeshStandardMaterial({ color: 0x666666 });
        
        for (let i = 0; i < rollerCount; i++) {
            const roller = new THREE.Mesh(rollerGeometry, rollerMaterial);
            roller.rotation.z = Math.PI / 2;
            roller.position.set(0, frameHeight - 3, -frameLength/2 + i * rollerSpacing);
            roller.castShadow = true;
            group.add(roller);
        }

        this.conveyorBelt = group;
        this.scene.add(group);
        console.log('✅ Conveyor belt added to scene at position:', group.position);
    }

    createBarcodeScanner() {
        const group = new THREE.Group();
        group.userData.name = "Barcode Scanner";
        
        // Calculate scanner position based on conveyor length
        // Scanner should be at the start of the conveyor (near beginning)
        let maxPusherDistance = 972;
        if (this.settings) {
            const distances = Object.values(this.settings).map(p => p.distance || 0);
            maxPusherDistance = Math.max(...distances, 972);
        }
        const startBuffer = 200;
        const scannerZ = -(startBuffer + maxPusherDistance + 200) / 2 + startBuffer - 50;
        
        // Scanner body - make it larger and more visible
        const bodyGeometry = new THREE.BoxGeometry(40, 30, 35);
        const bodyMaterial = new THREE.MeshStandardMaterial({ 
            color: 0x1a5490,
            emissive: 0x1a5490,
            emissiveIntensity: 0.3
        });
        const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
        body.position.set(0, 60, scannerZ);
        body.castShadow = true;
        group.add(body);

        // Scanner window/lens - brighter and more visible
        const lensGeometry = new THREE.BoxGeometry(20, 12, 3);
        const lensMaterial = new THREE.MeshStandardMaterial({ 
            color: 0x00ff00,
            emissive: 0x00ff00,
            emissiveIntensity: 1.0
        });
        const lens = new THREE.Mesh(lensGeometry, lensMaterial);
        lens.position.set(0, 60, scannerZ + 18);
        group.add(lens);

        // Mounting bracket
        const bracketGeometry = new THREE.BoxGeometry(45, 8, 8);
        const bracketMaterial = new THREE.MeshStandardMaterial({ color: 0x7f8c8d });
        const bracket = new THREE.Mesh(bracketGeometry, bracketMaterial);
        bracket.position.set(0, 40, scannerZ);
        bracket.castShadow = true;
        group.add(bracket);

        // Add label "SCANNER"
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 128;
        const context = canvas.getContext('2d');
        context.fillStyle = '#ffff00';
        context.fillRect(0, 0, 512, 128);
        context.fillStyle = '#000000';
        context.font = 'Bold 48px Arial';
        context.textAlign = 'center';
        context.fillText('SCANNER', 256, 75);
        const texture = new THREE.CanvasTexture(canvas);
        const labelMaterial = new THREE.MeshStandardMaterial({ map: texture, transparent: true });
        const labelGeometry = new THREE.PlaneGeometry(40, 10);
        const label = new THREE.Mesh(labelGeometry, labelMaterial);
        label.position.set(0, 80, scannerZ);
        label.lookAt(this.camera.position);
        group.add(label);

        this.scanner = group;
        this.scene.add(group);
    }

    createPhotoEye() {
        // Remove existing photo eye if recreating
        if (this.photoEye) {
            this.scene.remove(this.photoEye);
        }
        
        const group = new THREE.Group();
        group.userData.name = "Photo Eye";
        group.userData.detectionActive = false; // Track if currently detecting
        group.userData.lastDetectionTime = 0; // Track last detection time
        
        // Calculate photo eye position based on position ID mapping
        // Photo eye is at position ID ~105 (shortly after scanner at 101)
        // Use the position mapping to get the correct Z coordinate
        const photoEyePositionId = 105; // Photo eye detects items at position ~105
        let photoEyeZ = -500; // Default fallback
        
        // Try to get position from mapping (recalculate if needed)
        if (!this.positionIdToZ || Object.keys(this.positionIdToZ).length === 0) {
            this.positionIdToZ = this.calculatePositionMapping();
        }
        
        if (this.positionIdToZ[photoEyePositionId] !== undefined) {
            photoEyeZ = this.positionIdToZ[photoEyePositionId];
        } else {
            // Calculate manually if mapping not ready
            let maxPusherDistance = 972;
            if (this.settings) {
                const distances = Object.values(this.settings).map(p => p.distance || 0);
                maxPusherDistance = Math.max(...distances, 972);
            }
            const startBuffer = 200;
            const totalLength = startBuffer + maxPusherDistance + 200;
            const conveyorStart = -totalLength / 2;
            const conveyorEnd = totalLength / 2;
            const normalized = (photoEyePositionId - 101) / (150 - 101);
            photoEyeZ = conveyorStart + (normalized * (conveyorEnd - conveyorStart));
        }
        
        // Photo eye sensor body - SMALLER size, VERTICAL orientation (rotated 90 degrees)
        // Photo eye should be vertical to detect items passing through horizontally
        const bodyGeometry = new THREE.CylinderGeometry(8, 8, 15, 16);
        const bodyMaterial = new THREE.MeshStandardMaterial({ 
            color: 0xff6b35,
            emissive: 0xff6b35,
            emissiveIntensity: 0.6
        });
        const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
        body.rotation.z = Math.PI / 2; // Rotate 90 degrees - now vertical
        body.position.set(-35, 25, photoEyeZ); // Lower height, left side
        body.castShadow = true;
        body.receiveShadow = true;
        group.add(body);
        group.userData.emitter = body; // Store reference for animation

        // Receiver on opposite side - SMALLER, VERTICAL
        const receiverGeometry = new THREE.CylinderGeometry(8, 8, 15, 16);
        const receiver = new THREE.Mesh(receiverGeometry, bodyMaterial);
        receiver.rotation.z = Math.PI / 2; // Rotate 90 degrees - now vertical
        receiver.position.set(35, 25, photoEyeZ); // Lower height, right side
        receiver.castShadow = true;
        receiver.receiveShadow = true;
        group.add(receiver);
        group.userData.receiver = receiver;

        // Beam indicator - SMALLER but still visible, ROTATED 90 degrees (vertical, along Z-axis)
        const beamGeometry = new THREE.CylinderGeometry(1.5, 1.5, 70, 8);
        const beamMaterial = new THREE.MeshStandardMaterial({ 
            color: 0xff6b35,
            transparent: true,
            opacity: 0.5,
            emissive: 0xff6b35,
            emissiveIntensity: 0.8
        });
        const beam = new THREE.Mesh(beamGeometry, beamMaterial);
        beam.rotation.z = Math.PI / 2; // Rotated 90 degrees - now vertical (along Z-axis)
        beam.position.set(0, 25, photoEyeZ);
        group.add(beam);
        group.userData.beam = beam; // Store for animation

        // Detection flash effect (invisible until triggered) - SMALLER, ROTATED 90 degrees
        const flashGeometry = new THREE.CylinderGeometry(2, 2, 70, 8);
        const flashMaterial = new THREE.MeshStandardMaterial({ 
            color: 0x00ff00,
            transparent: true,
            opacity: 0,
            emissive: 0x00ff00,
            emissiveIntensity: 2.0
        });
        const flash = new THREE.Mesh(flashGeometry, flashMaterial);
        flash.rotation.z = Math.PI / 2; // Rotated 90 degrees - now vertical (along Z-axis)
        flash.position.set(0, 25, photoEyeZ);
        group.add(flash);
        group.userData.flash = flash;

        // Add label "PHOTO EYE" - LARGER
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 128;
        const context = canvas.getContext('2d');
        context.fillStyle = '#ff6b35';
        context.fillRect(0, 0, 512, 128);
        context.fillStyle = '#ffffff';
        context.font = 'Bold 48px Arial';
        context.textAlign = 'center';
        context.fillText('PHOTO EYE', 256, 80);
        const texture = new THREE.CanvasTexture(canvas);
        const labelMaterial = new THREE.MeshStandardMaterial({ map: texture, transparent: true });
        const labelGeometry = new THREE.PlaneGeometry(40, 10);
        const label = new THREE.Mesh(labelGeometry, labelMaterial);
        label.position.set(0, 45, photoEyeZ);
        label.lookAt(this.camera.position);
        group.add(label);
        group.userData.label = label;

        // Store position ID for detection logic
        group.userData.positionId = photoEyePositionId;
        group.userData.zPosition = photoEyeZ;

        this.photoEye = group;
        this.scene.add(group);
        console.log('✅ Photo Eye created at Z:', photoEyeZ, 'Position ID:', photoEyePositionId);
    }

    createPushers() {
        // Pushers will be positioned based on settings
        // Convert distances to position IDs, then position at correct Z coordinates
        let pusherDistances = [222, 313, 464, 380, 607, 710, 850, 972];
        
        if (this.settings) {
            pusherDistances = [1, 2, 3, 4, 5, 6, 7, 8].map(num => {
                const pusherKey = `Pusher ${num}`;
                return this.settings[pusherKey]?.distance || pusherDistances[num - 1];
            });
        }
        
        // Use position IDs directly (not calculated from distance)
        pusherDistances.forEach((distance, index) => {
            const pusherNumber = index + 1;
            const positionId = this.getPusherPositionId(pusherNumber); // Use direct mapping
            const pusher = this.createPusher(pusherNumber, distance, positionId);
            this.pushers.push(pusher);
            this.scene.add(pusher);
            // Bucket is created inside createPusher and added to scene there
            if (pusher.userData.bucket) {
                this.buckets.push(pusher.userData.bucket);
            }
        });
    }
    
    getPusherPositionId(pusherNumber) {
        // FIXED MAPPING: Use position IDs directly (not calculated from distance)
        // This ensures pushers are positioned correctly based on position IDs, not distance calculations
        const pusherPositionIdMap = {
            1: 109,  // Pusher 1 → Position ID 109
            2: 113,  // Pusher 2 → Position ID 113
            3: 119,  // Pusher 3 → Position ID 119
            4: 116,  // Pusher 4 → Position ID 116
            5: 125,  // Pusher 5 → Position ID 125
            6: 129,  // Pusher 6 → Position ID 129
            7: 135,  // Pusher 7 → Position ID 135
            8: 140   // Pusher 8 → Position ID 140
        };
        
        return pusherPositionIdMap[pusherNumber] || 140; // Default to last pusher if not found
    }
    
    calculatePusherPositionId(pusherDistance) {
        // DEPRECATED: Use getPusherPositionId() instead for direct position ID mapping
        // This function is kept for backward compatibility but should not be used
        // Calculate position ID from distance (matching Python logic)
        const POSITION_ID_MIN = 101;
        const POSITION_ID_MAX = 150;
        
        // Get Pusher 8 distance (furthest pusher)
        let pusher8Distance = 972;
        if (this.settings) {
            const distances = Object.values(this.settings).map(p => p.distance || 0);
            pusher8Distance = Math.max(...distances, 972);
        }
        
        // Tracking range: 25% beyond Pusher 8 or 1200 cm minimum
        const trackingRangeCm = Math.max(pusher8Distance * 1.25, 1200);
        
        if (trackingRangeCm === 0) {
            return POSITION_ID_MIN;
        }
        
        // Normalize distance to 0-1 range
        const normalized = Math.min(pusherDistance / trackingRangeCm, 1.0);
        
        // Map to position ID range
        const positionRange = POSITION_ID_MAX - POSITION_ID_MIN;
        const positionId = POSITION_ID_MIN + Math.floor(normalized * positionRange);
        
        return Math.min(Math.max(positionId, POSITION_ID_MIN), POSITION_ID_MAX);
    }

    createPusher(number, distance, positionId) {
        const group = new THREE.Group();
        group.userData = { number, distance, positionId, activated: false };

        // Pusher arm - oriented to extend horizontally toward conveyor center
        // Arm extends along X-axis (from left side toward center at x=0)
        const armGeometry = new THREE.BoxGeometry(60, 8, 15);
        const armMaterial = new THREE.MeshStandardMaterial({ color: 0x3498db });
        const arm = new THREE.Mesh(armGeometry, armMaterial);
        arm.position.set(-30, 20, 0); // Start position (retracted, on left side)
        arm.castShadow = true;
        group.add(arm);

        // Pusher head - at the end of the arm
        const headGeometry = new THREE.BoxGeometry(10, 20, 20);
        const headMaterial = new THREE.MeshStandardMaterial({ color: 0x2980b9 });
        const head = new THREE.Mesh(headGeometry, headMaterial);
        head.position.set(0, 20, 0); // At the end of arm (will extend toward center)
        head.castShadow = true;
        group.add(head);

        // Base/mount
        const baseGeometry = new THREE.BoxGeometry(30, 15, 30);
        const baseMaterial = new THREE.MeshStandardMaterial({ color: 0x34495e });
        const base = new THREE.Mesh(baseGeometry, baseMaterial);
        base.position.set(0, 7.5, 0);
        base.castShadow = true;
        group.add(base);

        // Label - make larger and more visible
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 256;
        const context = canvas.getContext('2d');
        context.fillStyle = '#3498db';
        context.fillRect(0, 0, 512, 256);
        context.fillStyle = '#ffffff';
        context.font = 'Bold 120px Arial';
        context.textAlign = 'center';
        context.fillText(`P${number}`, 256, 160);
        const texture = new THREE.CanvasTexture(canvas);
        const labelMaterial = new THREE.MeshStandardMaterial({ map: texture, transparent: true });
        const labelGeometry = new THREE.PlaneGeometry(30, 15);
        const label = new THREE.Mesh(labelGeometry, labelMaterial);
        label.position.set(0, 45, 0);
        label.lookAt(this.camera.position);
        group.add(label);
        
        // Add distance label below
        const distCanvas = document.createElement('canvas');
        distCanvas.width = 256;
        distCanvas.height = 64;
        const distContext = distCanvas.getContext('2d');
        distContext.fillStyle = '#ffffff';
        distContext.font = 'Bold 24px Arial';
        distContext.textAlign = 'center';
        distContext.fillText(`${distance}cm`, 128, 40);
        const distTexture = new THREE.CanvasTexture(distCanvas);
        const distLabelMaterial = new THREE.MeshStandardMaterial({ map: distTexture, transparent: true });
        const distLabelGeometry = new THREE.PlaneGeometry(20, 5);
        const distLabel = new THREE.Mesh(distLabelGeometry, distLabelMaterial);
        distLabel.position.set(0, 25, 0);
        distLabel.lookAt(this.camera.position);
        group.add(distLabel);

        // Position pusher at the Z coordinate corresponding to its position ID
        // Use position ID mapping to get exact Z position (matches item tracking)
        const pusherZ = this.positionIdToZ[positionId];
        if (pusherZ !== undefined) {
            group.position.z = pusherZ;
        } else {
            // Fallback: calculate from distance if position ID mapping not available
            let maxPusherDistance = 972;
            if (this.settings) {
                const distances = Object.values(this.settings).map(p => p.distance || 0);
                maxPusherDistance = Math.max(...distances, 972);
            }
            const startBuffer = 200;
            const totalLength = startBuffer + maxPusherDistance + 200;
            const conveyorStart = -totalLength / 2;
            group.position.z = conveyorStart + startBuffer + distance;
        }
        
        // Pushers are installed on the LEFT side of conveyor (negative X)
        // They extend toward the center (positive X direction) to push items
        group.position.x = -40; // LEFT side of conveyor (negative X)
        group.position.y = 0; // On the floor/base level

        // Create bucket on the RIGHT side (where pusher pushes items)
        // Bucket should be positioned where items land after being pushed
        const bucket = this.createBucket(number, distance, positionId);
        if (bucket) {
            this.scene.add(bucket);
            group.userData.bucket = bucket; // Store reference
        }

        return group;
    }

    createBucket(pusherNumber, distance, positionId) {
        // Buckets are installed on the RIGHT side of conveyor (positive X)
        // They receive items pushed by the pusher from the left side
        const group = new THREE.Group();
        group.userData = { pusherNumber, distance, positionId, type: "bucket" };

        // Position bucket at the Z coordinate corresponding to its position ID (same as pusher)
        const bucketZ = this.positionIdToZ[positionId];
        if (bucketZ !== undefined) {
            group.position.z = bucketZ;
        } else {
            // Fallback: calculate from distance if position ID mapping not available
            let maxPusherDistance = 972;
            if (this.settings) {
                const distances = Object.values(this.settings).map(p => p.distance || 0);
                maxPusherDistance = Math.max(...distances, 972);
            }
            const startBuffer = 200;
            const totalLength = startBuffer + maxPusherDistance + 200;
            const conveyorStart = -totalLength / 2;
            group.position.z = conveyorStart + startBuffer + distance;
        }
        
        // Bucket container (open top box)
        const bucketGeometry = new THREE.BoxGeometry(40, 30, 40);
        const bucketMaterial = new THREE.MeshStandardMaterial({ 
            color: 0x95a5a6,
            roughness: 0.8,
            metalness: 0.2
        });
        const bucket = new THREE.Mesh(bucketGeometry, bucketMaterial);
        bucket.position.set(0, 15, 0); // Center of bucket
        bucket.castShadow = true;
        bucket.receiveShadow = true;
        group.add(bucket);

        // Bucket label (no cover/rim - open bucket)
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 128;
        const context = canvas.getContext('2d');
        context.fillStyle = '#95a5a6';
        context.fillRect(0, 0, 256, 128);
        context.fillStyle = '#ffffff';
        context.font = 'Bold 60px Arial';
        context.textAlign = 'center';
        context.fillText(`B${pusherNumber}`, 128, 80);
        const texture = new THREE.CanvasTexture(canvas);
        const labelMaterial = new THREE.MeshStandardMaterial({ map: texture, transparent: true });
        const labelGeometry = new THREE.PlaneGeometry(25, 12);
        const label = new THREE.Mesh(labelGeometry, labelMaterial);
        label.position.set(0, 32, 0);
        label.lookAt(this.camera.position);
        group.add(label);

        // Position bucket: same Z as pusher (already set above), but on RIGHT side (positive X)
        group.position.x = 50; // RIGHT side of conveyor (positive X) - where items land
        group.position.y = 0; // On the floor/base level

        return group;
    }

    createItem(barcode, positionZ = null) {
        // Calculate item start position (at scanner location)
        if (positionZ === null) {
            let maxPusherDistance = 972;
            if (this.settings) {
                const distances = Object.values(this.settings).map(p => p.distance || 0);
                maxPusherDistance = Math.max(...distances, 972);
            }
            const startBuffer = 200;
            const totalLength = startBuffer + maxPusherDistance + 200;
            const conveyorStart = -totalLength / 2;
            positionZ = conveyorStart + startBuffer - 50; // Near scanner
        }
        
        // ULTRA-OPTIMIZED: Single mesh book model - maximum performance
        const bookLength = 25; // Length along conveyor (Z-axis)
        const bookWidth = 18;  // Width across conveyor (X-axis)
        const bookThickness = 3; // Thickness (Y-axis - vertical)
        
        // Reuse shared materials and geometry (critical for performance)
        if (!this._sharedBookMaterial) {
            this._sharedBookMaterial = new THREE.MeshStandardMaterial({ 
                color: 0x8b4513,
                roughness: 0.7,
                metalness: 0.1
            });
        }
        
        if (!this._sharedBookGeometry) {
            this._sharedBookGeometry = new THREE.BoxGeometry(bookLength, bookThickness, bookWidth);
        }
        
        // Single mesh - no labels, no extra geometry for maximum performance
        const book = new THREE.Mesh(this._sharedBookGeometry, this._sharedBookMaterial);
        book.castShadow = true;
        book.receiveShadow = true;
        
        // Position book on conveyor belt (conveyor belt surface is at frameHeight = 20)
        const frameHeight = 20;
        book.position.z = positionZ;
        book.position.y = frameHeight + bookThickness / 2;
        book.position.x = 0;

        // Store barcode in userData for tracking
        book.userData.barcode = barcode;
        book.userData.routed = false;
        book.userData.pusher = null;
        
        this.items.push(book);
        this.scene.add(book);
        return book;
    }


    activatePusher(pusherNumber) {
        if (pusherNumber < 1 || pusherNumber > 8) return;
        
        const pusher = this.pushers[pusherNumber - 1];
        if (!pusher) return;

        // Prevent multiple activations
        if (pusher.userData.activated) {
            return; // Already activated
        }

        pusher.userData.activated = true;
        
        // Find arm and head - arm extends along X-axis, head is at the end
        const arm = pusher.children.find(child => 
            child.geometry && child.geometry.type === 'BoxGeometry' && 
            child.position.y === 20 && 
            child.position.x < 0 // Arm starts at negative X
        );
        const head = pusher.children.find(child => 
            child.geometry && child.geometry.type === 'BoxGeometry' && 
            child.position.y === 20 && 
            Math.abs(child.position.x) < 5 // Head is near x=0
        );
        
        if (arm && head) {
            const originalArmX = arm.position.x; // Should be around -30
            const originalHeadX = head.position.x; // Should be around 0
            
            // Add 0.5s delay before pusher starts moving forward
            setTimeout(() => {
                // Smooth extend animation with easing
                // Pusher extends from left (negative X) toward center (positive X)
                const extendDistance = 50; // Extend 50 units toward center
                const duration = 0.4; // 400ms for extension
                let startTime = performance.now();
                
                const extendAnimation = (currentTime) => {
                const elapsed = (currentTime - startTime) / 1000;
                const progress = Math.min(elapsed / duration, 1);
                
                // Smooth easing (ease-out cubic)
                const eased = 1 - Math.pow(1 - progress, 3);
                const currentArmX = originalArmX + (extendDistance * eased);
                const currentHeadX = originalHeadX + (extendDistance * eased);
                
                arm.position.x = currentArmX;
                head.position.x = currentHeadX;
                
                if (progress < 1) {
                    requestAnimationFrame(extendAnimation);
                } else {
                    // Retract after delay with smooth animation
                    setTimeout(() => {
                        startTime = performance.now();
                        const retractAnimation = (currentTime) => {
                            const elapsed = (currentTime - startTime) / 1000;
                            const progress = Math.min(elapsed / duration, 1);
                            
                            // Smooth easing (ease-in cubic)
                            const eased = Math.pow(progress, 3);
                            const currentArmX = originalArmX + extendDistance - (extendDistance * eased);
                            const currentHeadX = originalHeadX + extendDistance - (extendDistance * eased);
                            
                            arm.position.x = currentArmX;
                            head.position.x = currentHeadX;
                            
                            if (progress < 1) {
                                requestAnimationFrame(retractAnimation);
                            } else {
                                arm.position.x = originalArmX;
                                head.position.x = originalHeadX;
                                pusher.userData.activated = false;
                            }
                         };
                         requestAnimationFrame(retractAnimation);
                     }, 500); // Delay before retraction
                 }
             };
             requestAnimationFrame(extendAnimation);
            }, 500); // 0.5s delay before pusher forward movement starts
        } else {
            console.warn(`⚠️ Could not find arm/head for pusher ${pusherNumber}`);
            pusher.userData.activated = false;
        }
    }

    loadSettings() {
        fetch('/get-settings')
            .then(response => response.json())
            .then(settings => {
                this.settings = settings;
                this.updatePusherPositions();
                // Recalculate position mapping when settings load
                this.positionIdToZ = this.calculatePositionMapping();
                
                // Recreate photo eye with correct position after mapping is ready
                this.createPhotoEye();
                
                // Recalculate camera position to fit entire conveyor
                this.updateCameraForConveyor();
                
                console.log('✅ Settings loaded for 3D visualization');
            })
            .catch(error => {
                console.error('❌ Error loading settings:', error);
            });
    }

    updatePusherPositions() {
        if (!this.settings) return;

        // Recalculate position mapping when settings change
        this.positionIdToZ = this.calculatePositionMapping();
        this.calculatePositionIdToCm();

        this.pushers.forEach((pusher, index) => {
            const pusherNumber = index + 1;
            const pusherKey = `Pusher ${pusherNumber}`;
            if (this.settings[pusherKey]) {
                const distance = this.settings[pusherKey].distance;
                const positionId = this.getPusherPositionId(pusherNumber); // Use direct mapping
                
                // Update pusher position using position ID mapping
                const pusherZ = this.positionIdToZ[positionId];
                if (pusherZ !== undefined) {
                    pusher.position.z = pusherZ;
                }
                pusher.position.x = -40; // Ensure pushers stay on LEFT side
                pusher.userData.distance = distance;
                pusher.userData.positionId = positionId;
                
                // Update corresponding bucket position
                if (pusher.userData.bucket) {
                    pusher.userData.bucket.position.z = pusherZ || pusher.position.z;
                    pusher.userData.bucket.position.x = 50; // Ensure buckets stay on RIGHT side
                    pusher.userData.bucket.userData.positionId = positionId;
                }
            }
        });
    }

    animate() {
        // Check if essential components exist
        if (!this.renderer || !this.scene || !this.camera) {
            // Don't log error on every frame - only log once
            if (!this._animateErrorLogged) {
                console.warn('⚠️ Animation paused: renderer, scene, or camera not ready yet');
                this._animateErrorLogged = true;
            }
            // Still request next frame to retry when components are ready
            this.animationId = requestAnimationFrame(() => this.animate());
            return;
        }
        
        // Reset error flag if we're animating successfully
        if (this._animateErrorLogged) {
            this._animateErrorLogged = false;
            console.log('✅ Animation resumed - all components ready');
        }
        
        // Calculate delta time for frame-independent movement
        const currentTime = performance.now();
        const deltaTime = Math.min((currentTime - this.lastFrameTime) / 1000, 0.1); // Cap at 100ms to prevent jumps
        this.lastFrameTime = currentTime;
        this.frameCount++;
        
        this.animationId = requestAnimationFrame(() => this.animate());
        
        // Move items continuously at belt speed (32.1 cm/s) based on start_time
        const itemsLength = this.items.length;
        for (let i = 0; i < itemsLength; i++) {
            const item = this.items[i];
            
            // Skip items that are being pushed (they have their own animation)
            if (item.userData.beingPushed || item.userData.routed) continue;
            
            // Calculate current position from start_time using belt_speed
            if (item.userData.start_time) {
                const currentPosition = this.calculatePositionFromStartTime(item.userData.start_time);
                if (currentPosition !== null) {
                    // Calculate Z position from current position in cm
                    let maxPusherDistance = 972;
                    if (this.settings) {
                        const distances = Object.values(this.settings).map(p => p.distance || 0);
                        maxPusherDistance = Math.max(...distances, 972);
                    }
                    const startBuffer = 200;
                    const totalLength = startBuffer + maxPusherDistance + 200;
                    const conveyorStart = -totalLength / 2;
                    const targetZ = conveyorStart + startBuffer + currentPosition;
                    
                    // Smooth interpolation to target position
                    const currentZ = item.position.z;
                    const distanceToTarget = targetZ - currentZ;
                    const absDistance = Math.abs(distanceToTarget);
                    
                    if (absDistance > 0.01) {
                        // Smooth lerp for smooth movement
                        const lerpFactor = 0.15; // Adjust for smoothness
                        item.position.z = currentZ + (distanceToTarget * lerpFactor);
                    } else {
                        item.position.z = targetZ;
                    }
                    
                    // Update position in cm for display (table will update via its own animation loop)
                    item.userData.positionCm = currentPosition;
                    
                    // Check if item reached end of conveyor
                    if (currentPosition >= maxPusherDistance + 200 && !item.userData.routed) {
                        item.userData.routed = true;
                        setTimeout(() => this.removeItem(item), 200);
                    }
                }
            }
        }

        // Update controls
        if (this.controls) {
            this.controls.update();
        }

               // Always render for smooth 60 FPS animation
               if (this.renderer && this.scene && this.camera) {
                   try {
                       this.renderer.render(this.scene, this.camera);
                   } catch (renderError) {
                       // Log render error but don't spam console
                       if (!this._renderErrorLogged) {
                           console.error('❌ Render error:', renderError);
                           this._renderErrorLogged = true;
                       }
                   }
               }
    }

    onWindowResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    updateCameraForConveyor() {
        // Update camera position when settings change
        if (!this.camera) return;
        
        // Calculate conveyor dimensions
        let maxPusherDistance = 972;
        if (this.settings) {
            const distances = Object.values(this.settings).map(p => p.distance || 0);
            maxPusherDistance = Math.max(...distances, 972);
        }
        const startBuffer = 200;
        const endBuffer = 200;
        const conveyorLength = startBuffer + maxPusherDistance + endBuffer;
        const conveyorWidth = 80;
        const conveyorHalfLength = conveyorLength / 2;
        const conveyorHalfWidth = conveyorWidth / 2;
        
        // Position camera to view from the SIDE (across), rotated 90 degrees
        const cameraHeight = Math.max(conveyorWidth * 2, 200);
        const cameraDistance = Math.max(conveyorHalfWidth * 3, 150);
        
        // Position camera on the SIDE (positive X), looking along the conveyor (Z-axis)
        this.camera.position.set(
            cameraDistance, // On the side (positive X)
            cameraHeight, // High enough to see everything
            0 // Centered along conveyor length (Z = 0)
        );
        
        // Look at the center of the conveyor
        this.camera.lookAt(0, 0, 0);
        
        // Update controls target
        if (this.controls) {
            this.controls.target.set(0, 0, 0);
            this.controls.update();
        }
        
        console.log('✅ Camera updated for side view:', {
            position: this.camera.position,
            conveyorLength: conveyorLength,
            conveyorWidth: conveyorWidth
        });
    }

    calculatePositionMapping() {
        // Calculate Z position for each position ID (101-150)
        const mapping = {};
        const POSITION_ID_MIN = 101;
        const POSITION_ID_MAX = 150;
        
        // Get conveyor dimensions
        let maxPusherDistance = 972;
        if (this.settings) {
            const distances = Object.values(this.settings).map(p => p.distance || 0);
            maxPusherDistance = Math.max(...distances, 972);
        }
        const startBuffer = 200;
        const totalLength = startBuffer + maxPusherDistance + 200;
        const conveyorStart = -totalLength / 2;
        const conveyorEnd = totalLength / 2;
        
        // Map position IDs to Z coordinates
        for (let posId = POSITION_ID_MIN; posId <= POSITION_ID_MAX; posId++) {
            const normalized = (posId - POSITION_ID_MIN) / (POSITION_ID_MAX - POSITION_ID_MIN);
            const zPosition = conveyorStart + (normalized * (conveyorEnd - conveyorStart));
            mapping[posId] = zPosition;
        }
        
        return mapping;
    }

    calculatePositionFromStartTime(startTime) {
        // Calculate current position from start_time using belt_speed=32.1 cm/s
        // startTime is in seconds (Python time.time() format)
        if (!startTime) return null;
        const now = Date.now() / 1000; // Current time in seconds
        const elapsed = now - startTime;
        if (elapsed < 0) return 0; // Don't allow negative positions
        return elapsed * this.beltSpeedCmPerSec; // Position in cm
    }

    calculatePositionIdToCm() {
        // Calculate real position in cm for each position ID (101-150)
        // PositionId 101 = 0cm (start), PositionId 150 = end
        // Assuming positionId maps linearly to conveyor length
        const POSITION_ID_MIN = 101;
        const POSITION_ID_MAX = 150;
        
        // Get conveyor dimensions
        let maxPusherDistance = 972;
        if (this.settings) {
            const distances = Object.values(this.settings).map(p => p.distance || 0);
            maxPusherDistance = Math.max(...distances, 972);
        }
        
        // Map position IDs to cm (linear mapping)
        for (let posId = POSITION_ID_MIN; posId <= POSITION_ID_MAX; posId++) {
            const normalized = (posId - POSITION_ID_MIN) / (POSITION_ID_MAX - POSITION_ID_MIN);
            const positionCm = normalized * maxPusherDistance;
            this.positionIdToCm[posId] = positionCm;
        }
    }

    updateItemFromPositionId(item, positionId) {
        // Update item's Z position based on position ID with ultra-smooth interpolation
        // This is called when position ID changes, but animation loop handles continuous movement
        if (this.positionIdToZ[positionId] !== undefined) {
            const targetZ = this.positionIdToZ[positionId];
            const currentZ = item.position.z;
            const distance = Math.abs(targetZ - currentZ);
            
            // Maximum lerp for ultra-smooth, continuous response when position ID changes
            // The animation loop will handle smooth interpolation between frames
            const lerpFactor = 0.9; // Increased from 0.8 to 0.9 for smoother response
            
            if (distance < 0.005) {  // Reduced threshold for even smoother transitions
                // Snap when very close
                item.position.z = targetZ;
            } else {
                // Ultra-smooth interpolation to get close to target
                item.position.z = currentZ + (targetZ - currentZ) * lerpFactor;
            }
            
            return true;
        }
        return false;
    }

    // Position display is now handled by script.js animation loop for synchronization

    setupEventListeners() {
        // Listen for scan events
        document.addEventListener('itemScanned', (event) => {
            const { barcode, location, pusher } = event.detail;
            // Create item at calculated start position
            this.createItem(barcode);
            
            if (pusher) {
                setTimeout(() => {
                    this.activatePusher(pusher);
                }, 2000);
            }
        });

        // Listen for active items updates (real-time tracking)
        document.addEventListener('activeItemsUpdated', (event) => {
            const { items } = event.detail;
            this.updateItemsFromTracking(items);
        });

        // Listen for settings updates
        document.addEventListener('settingsUpdated', () => {
            this.loadSettings();
            // Recalculate position mapping when settings change
            this.positionIdToZ = this.calculatePositionMapping();
        });
    }

    updateItemsFromTracking(trackedItems) {
        // Update 3D items based on real-time tracking data
        // Optimized: batch updates and minimize DOM/3D operations
        const trackedBarcodes = new Set(trackedItems.map(item => item.barcode));
        
        // Process updates in batch
        trackedItems.forEach(trackedItem => {
            const barcode = trackedItem.barcode;
            trackedBarcodes.add(barcode);
            
            // Check if item already exists in 3D scene
            if (this.itemsByBarcode[barcode]) {
                // Update existing item position
                const item = this.itemsByBarcode[barcode];
                
                // CRITICAL: Skip items that are already routed or being pushed
                // These items are in the process of being removed and should not be updated
                if (item.userData.routed || item.userData.beingPushed) {
                    console.log(`⏭️ Skipping update for routed/being-pushed item: ${barcode}`);
                    return; // Skip this item
                }
                
                // Update item data from tracked item
                item.userData.start_time = trackedItem.start_time;
                item.userData.distance = trackedItem.distance;
                item.userData.status = trackedItem.status;
                item.userData.label = trackedItem.label;
                item.userData.pusher = trackedItem.pusher;
                item.userData.positionId = trackedItem.positionId;
                // Initialize pusherActivated if not already set
                if (item.userData.pusherActivated === undefined) {
                    item.userData.pusherActivated = false;
                }
                // Initialize beingPushed if not already set
                if (item.userData.beingPushed === undefined) {
                    item.userData.beingPushed = false;
                }
                
                // Check if item is passing through photo eye (position ID ~105)
                // Photo eye should detect when item REACHES the photo eye position (105), not before
                if (this.photoEye && !item.userData.photoEyeDetected) {
                    const photoEyePosId = this.photoEye.userData.positionId || 105;
                    const currentPosId = trackedItem.positionId;
                    // Trigger detection when item reaches or just passes photo eye position
                    // Use >= to ensure we detect when item reaches position 105
                    if (currentPosId >= photoEyePosId && currentPosId <= photoEyePosId + 1) {
                        // Item has reached photo eye position - trigger detection
                        this.triggerPhotoEyeDetection(item);
                        item.userData.photoEyeDetected = true;
                        console.log(`👁️ Photo eye detected item ${trackedItem.barcode} at position ${currentPosId} (photo eye at ${photoEyePosId})`);
                    }
                }
                
                // Handle bucket falling logic based on status
                if (trackedItem.status === "progress" && trackedItem.distance && trackedItem.pusher) {
                    // Status "progress": fall into corresponding bucket when position >= distance
                    const currentPosition = this.calculatePositionFromStartTime(trackedItem.start_time);
                    if (currentPosition !== null && currentPosition >= trackedItem.distance && !item.userData.beingPushed && !item.userData.routed) {
                        item.userData.beingPushed = true;
                        item.userData.routed = true;
                        
                        console.log(`📦 Pushing item ${barcode} into bucket ${trackedItem.pusher} (position: ${currentPosition.toFixed(1)}cm >= distance: ${trackedItem.distance}cm)`);
                        
                        // Activate pusher
                        this.activatePusher(trackedItem.pusher);
                        
                        // Mark item as routed in backend
                        fetch('/mark-item-routed', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ barcode: barcode })
                        }).catch(err => console.error('Failed to mark item as routed:', err));
                        
                        // Start pushing animation: move to side and fall into bucket
                        this.pushItemIntoBucket(item, trackedItem.pusher);
                    }
                } else if (trackedItem.status === "pending") {
                    // Status "pending": fall into latest bucket (pusher 8)
                    const latestPusher = 8;
                    if (!item.userData.beingPushed && !item.userData.routed) {
                        item.userData.beingPushed = true;
                        item.userData.routed = true;
                        
                        console.log(`📦 Pushing pending item ${barcode} into latest bucket (pusher ${latestPusher})`);
                        
                        // Activate pusher
                        this.activatePusher(latestPusher);
                        
                        // Mark item as routed in backend
                        fetch('/mark-item-routed', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ barcode: barcode })
                        }).catch(err => console.error('Failed to mark item as routed:', err));
                        
                        // Start pushing animation: move to side and fall into bucket
                        this.pushItemIntoBucket(item, latestPusher);
                    }
                }
            } else {
                // Create new item - calculate initial position from start_time
                const currentPosition = this.calculatePositionFromStartTime(trackedItem.start_time);
                if (currentPosition === null) {
                    console.log(`⏭️ Skipping creation of item without start_time: ${barcode}`);
                    return;
                }
                
                // Calculate Z position from current position in cm
                let maxPusherDistance = 972;
                if (this.settings) {
                    const distances = Object.values(this.settings).map(p => p.distance || 0);
                    maxPusherDistance = Math.max(...distances, 972);
                }
                const startBuffer = 200;
                const totalLength = startBuffer + maxPusherDistance + 200;
                const conveyorStart = -totalLength / 2;
                const zPosition = conveyorStart + startBuffer + currentPosition;
                
                const item = this.createItem(trackedItem.barcode, zPosition);
                console.log(`📦 Created item ${barcode} at position ${currentPosition.toFixed(1)}cm (Z: ${zPosition.toFixed(1)})`);
                
                // Store metadata
                item.userData.start_time = trackedItem.start_time;
                item.userData.distance = trackedItem.distance;
                item.userData.status = trackedItem.status;
                item.userData.label = trackedItem.label;
                item.userData.pusher = trackedItem.pusher;
                item.userData.positionId = trackedItem.positionId;
                item.userData.routed = false;
                item.userData.pusherActivated = false;
                item.userData.beingPushed = false;
                item.userData.photoEyeDetected = false;
                item.userData.positionCm = currentPosition;
                
                // Store reference
                this.itemsByBarcode[barcode] = item;
            }
        });
        
        // Batch remove items that are no longer tracked (optimized)
        const itemsToRemove = Object.keys(this.itemsByBarcode).filter(barcode => !trackedBarcodes.has(barcode));
        itemsToRemove.forEach(barcode => {
            const item = this.itemsByBarcode[barcode];
            if (item && this.scene) {
                this.scene.remove(item);
                const index = this.items.indexOf(item);
                if (index > -1) {
                    this.items.splice(index, 1);
                }
            }
            delete this.itemsByBarcode[barcode];
        });
    }

    triggerPhotoEyeDetection(item) {
        // Visual feedback when photo eye detects an item
        if (!this.photoEye) return;
        
        const now = performance.now();
        const timeSinceLastDetection = now - this.photoEye.userData.lastDetectionTime;
        
        // Prevent too frequent detections (debounce)
        if (timeSinceLastDetection < 200) return;
        
        this.photoEye.userData.lastDetectionTime = now;
        this.photoEye.userData.detectionActive = true;
        
        const flash = this.photoEye.userData.flash;
        const emitter = this.photoEye.userData.emitter;
        const receiver = this.photoEye.userData.receiver;
        const beam = this.photoEye.userData.beam;
        
        if (!flash || !emitter || !receiver || !beam) return;
        
        // Flash green detection beam
        flash.material.opacity = 0.9;
        flash.material.emissiveIntensity = 3.0;
        
        // Brighten emitter and receiver
        const originalEmissive = emitter.material.emissiveIntensity;
        emitter.material.emissiveIntensity = 1.5;
        receiver.material.emissiveIntensity = 1.5;
        beam.material.emissiveIntensity = 2.0;
        beam.material.opacity = 0.9;
        
        // Fade out after 300ms
        setTimeout(() => {
            const fadeOut = (progress) => {
                if (progress >= 1) {
                    flash.material.opacity = 0;
                    flash.material.emissiveIntensity = 2.0;
                    emitter.material.emissiveIntensity = originalEmissive;
                    receiver.material.emissiveIntensity = originalEmissive;
                    beam.material.emissiveIntensity = 1.0;
                    beam.material.opacity = 0.6;
                    this.photoEye.userData.detectionActive = false;
                } else {
                    flash.material.opacity = 0.9 * (1 - progress);
                    flash.material.emissiveIntensity = 2.0 + (1.0 * (1 - progress));
                    emitter.material.emissiveIntensity = originalEmissive + (1.5 - originalEmissive) * (1 - progress);
                    receiver.material.emissiveIntensity = originalEmissive + (1.5 - originalEmissive) * (1 - progress);
                    beam.material.emissiveIntensity = 1.0 + (1.0 * (1 - progress));
                    beam.material.opacity = 0.6 + (0.3 * (1 - progress));
                    requestAnimationFrame(() => fadeOut(progress + 0.1));
                }
            };
            fadeOut(0);
        }, 300);
        
        console.log('👁️ Photo Eye detected item:', item.userData.barcode);
    }

    pushItemIntoBucket(item, pusherNumber) {
        // Animate item being pushed off belt and falling into bucket
        if (!item || !this.scene) return;
        
        // Find the bucket for this pusher
        const pusher = this.pushers[pusherNumber - 1];
        if (!pusher || !pusher.userData.bucket) {
            // No bucket found, just remove item
            this.removeItem(item);
            return;
        }
        
        const bucket = pusher.userData.bucket;
        const bucketPosition = bucket.position;
        
        // Starting position (on belt)
        const startX = item.position.x;
        const startY = item.position.y;
        const startZ = item.position.z;
        const startRotationX = item.rotation.x;
        const startRotationZ = item.rotation.z;
        
        // Target position (in bucket)
        const targetX = bucketPosition.x; // Bucket is on right side
        const targetY = bucketPosition.y + 10; // Inside bucket (10 units from bottom)
        const targetZ = bucketPosition.z; // Same Z as bucket
        
        // Animation parameters
        const pushDuration = 0.6; // 600ms to push to side
        const fallDuration = 0.4; // 400ms to fall down
        const totalDuration = pushDuration + fallDuration;
        
        let startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = (currentTime - startTime) / 1000;
            const progress = Math.min(elapsed / totalDuration, 1);
            
            if (progress < 1) {
                if (elapsed < pushDuration) {
                    // Phase 1: Push to side (move X and Z toward bucket)
                    const pushProgress = elapsed / pushDuration;
                    const easedPush = 1 - Math.pow(1 - pushProgress, 3); // Ease-out
                    
                    // Move horizontally toward bucket
                    item.position.x = startX + (targetX - startX) * easedPush;
                    item.position.z = startZ + (targetZ - startZ) * easedPush * 0.3; // Slight forward movement
                    // Slight lift during push
                    item.position.y = startY + Math.sin(pushProgress * Math.PI) * 5;
                } else {
                    // Phase 2: Fall down into bucket
                    const fallProgress = (elapsed - pushDuration) / fallDuration;
                    const easedFall = Math.pow(fallProgress, 2); // Ease-in (gravity acceleration)
                    
                    // Complete horizontal movement
                    item.position.x = targetX;
                    item.position.z = targetZ;
                    // Fall down
                    item.position.y = startY + (targetY - startY) * easedFall;
                    
                    // Add rotation as it falls (tumbling effect) - based on progress
                    item.rotation.x = startRotationX + (fallProgress * Math.PI * 0.5); // Rotate 90 degrees as it falls
                    item.rotation.z = startRotationZ + (fallProgress * Math.PI * 0.3); // Slight Z rotation
                }
                
                requestAnimationFrame(animate);
            } else {
                // Animation complete - item is in bucket
                item.position.x = targetX;
                item.position.y = targetY;
                item.position.z = targetZ;
                
                // Remove item after a short delay (simulate it being in the bucket)
                setTimeout(() => {
                    this.removeItem(item);
                }, 500);
            }
        };
        
        requestAnimationFrame(animate);
        console.log(`📦 Pushing item ${item.userData.barcode} into bucket ${pusherNumber}`);
    }

    removeItem(item) {
        // Remove item from scene after pusher operation
        if (!item || !this.scene) return;
        
        // Remove from scene
        this.scene.remove(item);
        
        // Remove from items array
        const index = this.items.indexOf(item);
        if (index > -1) {
            this.items.splice(index, 1);
        }
        
        // Remove from itemsByBarcode map
        if (item.userData.barcode) {
            delete this.itemsByBarcode[item.userData.barcode];
        }
        
        console.log(`🗑️ Removed item ${item.userData.barcode} after pusher operation`);
    }

    isWebGLSupported() {
        try {
            const canvas = document.createElement('canvas');
            return !!(window.WebGLRenderingContext && 
                     (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
        } catch (e) {
            return false;
        }
    }

    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        window.removeEventListener('resize', this.onWindowResize);
        if (this.renderer) {
            this.renderer.dispose();
        }
    }
}

// Export for use - make available globally
window.ConveyorSystem3D = ConveyorSystem3D;
console.log('✅ ConveyorSystem3D class exported to window');
console.log('   Type check:', typeof window.ConveyorSystem3D);

// Dispatch event to notify that module is loaded
window.dispatchEvent(new CustomEvent('conveyor3d-loaded'));
console.log('✅ Dispatched conveyor3d-loaded event');

// Auto-initialization is handled by init3d.js to prevent duplicate instances

