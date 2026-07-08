// stream3d.js - 3D Scroll Glass Pipe & Smooth Sliding Boy Animation using Three.js
// ponytail: light, clean, optimized Three.js scroll link implementation

(function() {
    // 1. Check if Three.js is loaded
    if (typeof THREE === 'undefined') {
        console.warn("Three.js not loaded. Falling back to CSS static effects.");
        return;
    }

    const canvas = document.getElementById('stream-canvas');
    if (!canvas) return;

    const scene = new THREE.Scene();
    
    // Camera
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(0, 12, 10);

    // Renderer
    const renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        alpha: true, // Transparent background
        antialias: true
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);

    // Add Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.55);
    scene.add(ambientLight);

    const pointLight1 = new THREE.PointLight(0x818CF8, 4, 50);
    pointLight1.position.set(5, 10, 5);
    scene.add(pointLight1);

    const pointLight2 = new THREE.PointLight(0x22D3EE, 4, 50);
    pointLight2.position.set(-5, -5, 5);
    scene.add(pointLight2);

    // Helper: Create a glowing circular canvas texture for particles
    const createParticleTexture = (colorStop0 = 'rgba(255, 255, 255, 1)', colorStop1 = 'rgba(34, 211, 238, 0.7)') => {
        const c = document.createElement('canvas');
        c.width = 16;
        c.height = 16;
        const ctx = c.getContext('2d');
        const grad = ctx.createRadialGradient(8, 8, 0, 8, 8, 8);
        grad.addColorStop(0, colorStop0);
        grad.addColorStop(0.3, colorStop1);
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, 16, 16);
        return new THREE.CanvasTexture(c);
    };

    // 2. Define the Stream Path (CatmullRomCurve3)
    const points = [
        new THREE.Vector3(0, 15, 0),        // Top, start of stream
        new THREE.Vector3(2.5, 7.5, -2),    // Curve right in Hero section
        new THREE.Vector3(-3.5, 0, 2),      // Curve left between Hero and App
        new THREE.Vector3(3.5, -7.5, -2),   // Curve right in App section
        new THREE.Vector3(-2, -14, 1),      // Curve left
        new THREE.Vector3(0, -18, 0)        // End of stream, directly into whirlpool center
    ];

    const curve = new THREE.CatmullRomCurve3(points);
    
    // 3. Inner Flowing Liquid Mesh (Ống lỏng phát sáng bên trong)
    const liquidGeometry = new THREE.TubeGeometry(curve, 100, 0.32, 12, false);

    const waterMaterial = new THREE.ShaderMaterial({
        uniforms: {
            time: { value: 0.0 },
            scrollProgress: { value: 0.0 },
            color1: { value: new THREE.Color(0x818CF8) }, // Indigo
            color2: { value: new THREE.Color(0x22D3EE) }  // Cyan
        },
        vertexShader: `
            uniform float time;
            varying vec2 vUv;
            varying float vElevation;
            
            void main() {
                vUv = uv;
                
                // Add wave ripples inside the pipe
                vec3 newPosition = position;
                float wave = sin(position.x * 3.0 + time * 4.0) * 0.035 
                           + cos(position.y * 3.0 + time * 3.0) * 0.035;
                newPosition.z += wave;
                vElevation = wave;
                
                gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
            }
        `,
        fragmentShader: `
            uniform float time;
            uniform float scrollProgress;
            uniform vec3 color1;
            uniform vec3 color2;
            varying vec2 vUv;
            varying float vElevation;
            
            void main() {
                // Flow animation along UV coordinates
                float flow = vUv.x - time * 0.55;
                float pattern = sin(flow * 40.0) * 0.5 + 0.5;
                
                // Mix colors based on UV and wave elevation
                vec3 baseColor = mix(color1, color2, vUv.x);
                
                // Add highlights based on flow pattern and elevation
                vec3 highlight = vec3(1.0) * pattern * 0.3;
                vec3 finalColor = baseColor + highlight + vec3(vElevation * 0.5);
                
                // Reveal the stream progressively based on scrollProgress
                float alpha = 0.65;
                
                // Fade out at the bottom and top boundaries
                float borderFade = sin(vUv.x * 3.14159);
                alpha *= borderFade;
                
                // Smoothly reveal along scroll
                float revealThreshold = scrollProgress * 1.3 - 0.15;
                if (vUv.x > revealThreshold) {
                    alpha = 0.0;
                } else {
                    // Soft edge at the tip of the stream
                    float edge = (revealThreshold - vUv.x) * 12.0;
                    alpha *= clamp(edge, 0.0, 1.0);
                }
                
                gl_FragColor = vec4(finalColor, alpha);
            }
        `,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending
    });

    const liquidMesh = new THREE.Mesh(liquidGeometry, waterMaterial);
    scene.add(liquidMesh);

    // 4. Outer Glass Pipe Mesh (Vỏ ống thủy tinh vật lý)
    const glassPipeGeometry = new THREE.TubeGeometry(curve, 100, 0.44, 16, false);
    const glassPipeMaterial = new THREE.MeshPhysicalMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.22,
        roughness: 0.05,
        metalness: 0.1,
        transmission: 0.92, // Glass refraction
        ior: 1.52,          // Index of refraction of glass
        thickness: 0.4,     // Glass wall thickness
        depthWrite: true,
        side: THREE.DoubleSide
    });
    const glassPipeMesh = new THREE.Mesh(glassPipeGeometry, glassPipeMaterial);
    scene.add(glassPipeMesh);

    // 5. Sci-Fi Glowing Emitter Bulb at the Top
    const bulbGeometry = new THREE.SphereGeometry(0.65, 32, 16);
    const bulbMaterial = new THREE.MeshPhysicalMaterial({
        color: 0x818CF8,
        transparent: true,
        opacity: 0.35,
        emissive: 0x818CF8,
        emissiveIntensity: 0.8,
        roughness: 0.1,
        metalness: 0.8
    });
    const energyBulb = new THREE.Mesh(bulbGeometry, bulbMaterial);
    energyBulb.position.set(0, 15, 0);
    scene.add(energyBulb);

    // 6. Sci-Fi Metallic Joints / Collars along the curve
    const numBrackets = 8;
    const brackets = [];
    const bracketGeometry = new THREE.CylinderGeometry(0.47, 0.47, 0.18, 24, 1, false);
    const bracketMaterial = new THREE.MeshStandardMaterial({
        color: 0x8b9bb4, // Steel metal color
        roughness: 0.25,
        metalness: 0.95,
        emissive: 0x22D3EE,
        emissiveIntensity: 0.15,
        side: THREE.DoubleSide
    });

    for (let i = 1; i < numBrackets; i++) {
        const t = i / numBrackets;
        const pt = curve.getPointAt(t);
        const tangent = curve.getTangentAt(t);
        
        const bracket = new THREE.Mesh(bracketGeometry, bracketMaterial);
        bracket.position.copy(pt);
        
        const up = new THREE.Vector3(0, 1, 0);
        const quaternion = new THREE.Quaternion().setFromUnitVectors(up, tangent);
        bracket.quaternion.copy(quaternion);
        
        scene.add(bracket);
        brackets.push(bracket);
    }

    // 7. 🧒 UPGRADE: Create Larger Animated Boy Character with Expressions!
    const boyGroup = new THREE.Group();
    
    // skin material
    const skinMaterial = new THREE.MeshStandardMaterial({ color: 0xffdbac, roughness: 0.6 });
    // hair material (brown)
    const hairMaterial = new THREE.MeshStandardMaterial({ color: 0x4a2e1b, roughness: 0.8 });
    // shirt material (red)
    const shirtMaterial = new THREE.MeshStandardMaterial({ color: 0xef4444, roughness: 0.5 });
    // pants material (denim blue)
    const pantsMaterial = new THREE.MeshStandardMaterial({ color: 0x2563eb, roughness: 0.5 });
    
    // Head (Sphere) - Upgraded to Radius 0.16 (fills tube width)
    const headGeom = new THREE.SphereGeometry(0.16, 16, 16);
    const head = new THREE.Mesh(headGeom, skinMaterial);
    head.position.y = 0.20;
    boyGroup.add(head);

    // Hair Cap
    const hairGeom = new THREE.SphereGeometry(0.165, 16, 16, 0, Math.PI * 2, 0, Math.PI / 1.7);
    const hair = new THREE.Mesh(hairGeom, hairMaterial);
    hair.position.y = 0.21;
    hair.rotation.x = -0.25;
    boyGroup.add(hair);

    // Eyes (Excited wide open!)
    const eyeGeom = new THREE.SphereGeometry(0.024, 8, 8);
    const eyeMat = new THREE.MeshBasicMaterial({ color: 0x000000 });
    const leftEye = new THREE.Mesh(eyeGeom, eyeMat);
    leftEye.position.set(0.05, 0.20, 0.14);
    const rightEye = new THREE.Mesh(eyeGeom, eyeMat);
    rightEye.position.set(-0.05, 0.20, 0.14);
    boyGroup.add(leftEye, rightEye);

    // Rosy Cheeks (Excitement glow!)
    const cheekGeom = new THREE.SphereGeometry(0.024, 8, 8);
    const cheekMat = new THREE.MeshBasicMaterial({ color: 0xff8ba7 });
    const leftCheek = new THREE.Mesh(cheekGeom, cheekMat);
    leftCheek.position.set(0.08, 0.14, 0.13);
    const rightCheek = new THREE.Mesh(cheekGeom, cheekMat);
    rightCheek.position.set(-0.08, 0.14, 0.13);
    boyGroup.add(leftCheek, rightCheek);

    // Eyebrows tilted in surprise/excitement
    const browGeom = new THREE.BoxGeometry(0.045, 0.01, 0.01);
    const browMat = new THREE.MeshBasicMaterial({ color: 0x4a2e1b });
    const leftBrow = new THREE.Mesh(browGeom, browMat);
    leftBrow.position.set(0.05, 0.225, 0.14);
    leftBrow.rotation.z = 0.18; // tilt up
    const rightBrow = new THREE.Mesh(browGeom, browMat);
    rightBrow.position.set(-0.05, 0.225, 0.14);
    rightBrow.rotation.z = -0.18; // tilt up
    boyGroup.add(leftBrow, rightBrow);

    // Screaming Open Mouth (Excited mouth!)
    const mouthGeom = new THREE.SphereGeometry(0.034, 8, 8);
    const mouthMat = new THREE.MeshBasicMaterial({ color: 0x400505 }); // dark red inside
    const mouth = new THREE.Mesh(mouthGeom, mouthMat);
    mouth.position.set(0, 0.13, 0.145);
    mouth.scale.set(1.4, 0.7, 0.8); // oval shape
    boyGroup.add(mouth);

    // Torso (Cylinder)
    const torsoGeom = new THREE.CylinderGeometry(0.11, 0.09, 0.24, 16);
    const torso = new THREE.Mesh(torsoGeom, shirtMaterial);
    torso.position.y = -0.02;
    boyGroup.add(torso);

    // Pants (Cylinder)
    const pantsGeom = new THREE.CylinderGeometry(0.09, 0.09, 0.1, 16);
    const pants = new THREE.Mesh(pantsGeom, pantsMaterial);
    pants.position.y = -0.15;
    boyGroup.add(pants);

    // Legs sitting/extended forward
    const legGeom = new THREE.CylinderGeometry(0.04, 0.03, 0.18, 8);
    const leftLeg = new THREE.Mesh(legGeom, pantsMaterial);
    leftLeg.position.set(0.05, -0.19, 0.08);
    leftLeg.rotation.x = Math.PI / 2.3; // sliding forward
    const rightLeg = new THREE.Mesh(legGeom, pantsMaterial);
    rightLeg.position.set(-0.05, -0.19, 0.08);
    rightLeg.rotation.x = Math.PI / 2.15; // slightly offset for realism
    boyGroup.add(leftLeg, rightLeg);

    // Arms waving in excitement!
    const armGeom = new THREE.CylinderGeometry(0.035, 0.026, 0.18, 8);
    const leftArm = new THREE.Mesh(armGeom, skinMaterial);
    leftArm.position.set(0.15, 0.07, 0.03);
    leftArm.rotation.z = -Math.PI / 3; // Wave out
    leftArm.rotation.x = Math.PI / 6;
    const rightArm = new THREE.Mesh(armGeom, skinMaterial);
    rightArm.position.set(-0.15, 0.07, 0.03);
    rightArm.rotation.z = Math.PI / 3;  // Wave out
    rightArm.rotation.x = -Math.PI / 6;
    boyGroup.add(leftArm, rightArm);

    // Add Boy to the Scene
    boyGroup.position.set(0, 15, 0); // start at the top
    scene.add(boyGroup);

    // 8. Create floating bubble particles inside the glass pipe
    const particleCount = 50;
    const particleGeometry = new THREE.BufferGeometry();
    const particlePositions = new Float32Array(particleCount * 3);
    const particleProgress = []; // store 't' parameter along curve (0 to 1)
    const particleOffsets = []; // offset to keep them swirling inside the pipe

    for (let i = 0; i < particleCount; i++) {
        const t = Math.random();
        particleProgress.push(t);
        
        const angle = Math.random() * Math.PI * 2;
        const radius = 0.1 + Math.random() * 0.2;
        particleOffsets.push({ angle, radius, speed: 0.4 + Math.random() * 0.6 });
        
        const pt = curve.getPointAt(t);
        particlePositions[i * 3] = pt.x + Math.cos(angle) * radius;
        particlePositions[i * 3 + 1] = pt.y + Math.sin(angle) * radius;
        particlePositions[i * 3 + 2] = pt.z;
    }

    particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
    const particleMaterial = new THREE.PointsMaterial({
        size: 0.28,
        map: createParticleTexture(),
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    });

    const particleSystem = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particleSystem);

    // 9. Water Splashes at Bends / Curves (Va đập)
    const splashCount = 40;
    const splashGeometry = new THREE.BufferGeometry();
    const splashPositions = new Float32Array(splashCount * 3);
    const splashVelocities = [];
    const splashLifes = new Float32Array(splashCount);

    for (let i = 0; i < splashCount; i++) {
        splashPositions[i * 3] = 0;
        splashPositions[i * 3 + 1] = -100; // hide initially
        splashPositions[i * 3 + 2] = 0;
        splashVelocities.push(new THREE.Vector3());
        splashLifes[i] = 0;
    }

    splashGeometry.setAttribute('position', new THREE.BufferAttribute(splashPositions, 3));
    const splashMaterial = new THREE.PointsMaterial({
        size: 0.32, // larger splashes
        map: createParticleTexture('rgba(255, 255, 255, 1)', 'rgba(34, 211, 238, 0.9)'),
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    });
    const splashSystem = new THREE.Points(splashGeometry, splashMaterial);
    scene.add(splashSystem);

    let lastActiveSplashIdx = 0;
    function emitWaterSplashes(position, intensity) {
        const countToEmit = Math.floor(4 + intensity * 6);
        const posArr = splashSystem.geometry.attributes.position.array;
        
        for (let k = 0; k < countToEmit; k++) {
            const idx = lastActiveSplashIdx;
            lastActiveSplashIdx = (lastActiveSplashIdx + 1) % splashCount;
            
            // Set spawn position to boy's coordinates
            posArr[idx * 3] = position.x + (Math.random() - 0.5) * 0.2;
            posArr[idx * 3 + 1] = position.y + (Math.random() - 0.5) * 0.2;
            posArr[idx * 3 + 2] = position.z + (Math.random() - 0.5) * 0.2;
            
            // Random outwards velocity
            splashVelocities[idx].set(
                (Math.random() - 0.5) * 2.2,
                (Math.random() - 0.2) * 2.8 + 1.0, // eject upwards
                (Math.random() - 0.5) * 2.2
            ).multiplyScalar(intensity * 1.5);
            
            splashLifes[idx] = 1.0;
        }
        splashSystem.geometry.attributes.position.needsUpdate = true;
    }

    // 10. 🌊 3D Funnel Whirlpool Mesh at the Bottom
    const whirlpoolGeometry = new THREE.RingGeometry(0.1, 4.5, 64, 32);
    wharpVertexToFunnel(whirlpoolGeometry);

    function wharpVertexToFunnel(geometry) {
        geometry.rotateX(-Math.PI / 2);
        
        const pos = geometry.attributes.position.array;
        for (let i = 0; i < pos.length; i += 3) {
            const x = pos[i];
            const z = pos[i+2];
            const dist = Math.sqrt(x*x + z*z);
            pos[i+1] = -1.8 / (0.35 + dist * dist) + 0.3; // Y coordinate deformation
        }
        geometry.computeVertexNormals();
    }

    // Custom Shader for Whirlpool Vortex effect
    const whirlpoolMaterial = new THREE.ShaderMaterial({
        uniforms: {
            time: { value: 0.0 },
            scrollProgress: { value: 0.0 },
            color1: { value: new THREE.Color(0x818CF8) },
            color2: { value: new THREE.Color(0x22D3EE) }
        },
        vertexShader: `
            varying vec2 vUv;
            varying vec3 vPosition;
            void main() {
                vUv = uv;
                vPosition = position;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform float time;
            uniform float scrollProgress;
            uniform vec3 color1;
            uniform vec3 color2;
            varying vec2 vUv;
            varying vec3 vPosition;
            
            void main() {
                float r = length(vPosition.xz);
                float theta = atan(vPosition.z, vPosition.x);
                
                float spiral = theta + time * 3.5 - 5.0 / (r + 0.2);
                float wave = sin(spiral * 8.0) * 0.5 + 0.5;
                float foam = smoothstep(0.72, 1.0, sin(spiral * 16.0 + r * 5.0) * 0.5 + 0.5);
                
                vec3 baseColor = mix(color1, color2, r / 4.5);
                vec3 finalColor = baseColor + vec3(wave * 0.22) + vec3(foam * 0.35);
                
                float edgeFade = smoothstep(0.0, 0.4, r) * smoothstep(4.5, 3.2, r);
                float reveal = smoothstep(0.4, 0.8, scrollProgress);
                float alpha = 0.85 * edgeFade * reveal;
                
                gl_FragColor = vec4(finalColor, alpha);
            }
        `,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide
    });

    const whirlpoolMesh = new THREE.Mesh(whirlpoolGeometry, whirlpoolMaterial);
    whirlpoolMesh.position.set(0, -18, 0); // Positioned at the bottom downstream
    scene.add(whirlpoolMesh);

    // Sci-Fi Metallic Drain Ring around the Whirlpool
    const drainRingGeometry = new THREE.TorusGeometry(4.55, 0.12, 8, 48);
    const drainRingMaterial = new THREE.MeshStandardMaterial({
        color: 0x8b9bb4,
        roughness: 0.25,
        metalness: 0.95,
        emissive: 0x22D3EE,
        emissiveIntensity: 0.1
    });
    const drainRing = new THREE.Mesh(drainRingGeometry, drainRingMaterial);
    drainRing.position.set(0, -18, 0);
    drainRing.rotateX(-Math.PI / 2);
    scene.add(drainRing);

    // Swirling Whirlpool Particles (Hạt hút vào xoáy nước)
    const vParticleCount = 90;
    const vParticleGeometry = new THREE.BufferGeometry();
    const vParticlePositions = new Float32Array(vParticleCount * 3);
    const vParticleData = []; // Custom array to track polar state of particles
    
    for (let i = 0; i < vParticleCount; i++) {
        const radius = 0.5 + Math.random() * 3.8;
        const angle = Math.random() * Math.PI * 2;
        const speed = 1.0 + Math.random() * 1.8;
        vParticleData.push({ radius, angle, speed });
        
        const x = Math.cos(angle) * radius;
        const z = Math.sin(angle) * radius;
        const y = -1.8 / (0.35 + radius * radius) + 0.3 - 18;
        
        vParticlePositions[i * 3] = x;
        vParticlePositions[i * 3 + 1] = y;
        vParticlePositions[i * 3 + 2] = z;
    }
    
    vParticleGeometry.setAttribute('position', new THREE.BufferAttribute(vParticlePositions, 3));
    const vParticleMaterial = new THREE.PointsMaterial({
        size: 0.28,
        map: createParticleTexture(),
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    });
    
    const vortexParticleSystem = new THREE.Points(vParticleGeometry, vParticleMaterial);
    scene.add(vortexParticleSystem);

    // ✨ Ambient Droplets "Vướng Vấn Bụi Trần" (Hạt sương lơ lửng ngẫu nhiên)
    const aParticleCount = 140;
    const aParticleGeometry = new THREE.BufferGeometry();
    const aParticlePositions = new Float32Array(aParticleCount * 3);
    const aParticleSpeeds = []; // store speed factor for gentle drift
    
    for (let i = 0; i < aParticleCount; i++) {
        aParticlePositions[i * 3] = (Math.random() - 0.5) * 16;     // X: -8 to 8
        aParticlePositions[i * 3 + 1] = (Math.random() - 0.5) * 44; // Y: -24 to 20
        aParticlePositions[i * 3 + 2] = (Math.random() - 0.5) * 12; // Z: -6 to 6
        aParticleSpeeds.push({
            x: 0.2 + Math.random() * 0.8,
            y: 0.1 + Math.random() * 0.5,
            z: 0.2 + Math.random() * 0.8
        });
    }
    
    aParticleGeometry.setAttribute('position', new THREE.BufferAttribute(aParticlePositions, 3));
    
    // Create a special custom texture with soft glowing core and double-layered color highlights
    const createAmbientTexture = () => {
        const c = document.createElement('canvas');
        c.width = 16;
        c.height = 16;
        const ctx = c.getContext('2d');
        const grad = ctx.createRadialGradient(8, 8, 0, 8, 8, 8);
        grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
        grad.addColorStop(0.2, 'rgba(224, 242, 254, 0.7)'); // Sky blue inner halo
        grad.addColorStop(0.5, 'rgba(129, 140, 248, 0.25)'); // Indigo outer blur
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, 16, 16);
        return new THREE.CanvasTexture(c);
    };

    const aParticleMaterial = new THREE.PointsMaterial({
        size: 0.22,
        map: createAmbientTexture(),
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    });
    
    const ambientParticleSystem = new THREE.Points(aParticleGeometry, aParticleMaterial);
    scene.add(ambientParticleSystem);

    // 13. 🔄 UPGRADE: Smooth Interpolation State Variables (Vật lý chuyển động mượt mà)
    let scrollPercent = 0;
    let currentBoyT = 0;       // Smoothly lerped slide progress
    let targetBoyT = 0;        // Raw scroll slide progress
    
    const cameraLookTarget = new THREE.Vector3(0, 15, 0); // Smooth camera tracking point
    const currentDisplacement = new THREE.Vector3(0, 0, 0); // Smooth collision offset
    
    // DOM elements for reveal
    const heroOverlay = document.getElementById('hero-overlay');
    const appSection = document.getElementById('app-section');
    
    function updateScroll() {
        const scrollY = window.scrollY;
        const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
        scrollPercent = maxScroll <= 0 ? 0 : scrollY / maxScroll;
        
        // Update shader scroll progress
        waterMaterial.uniforms.scrollProgress.value = scrollPercent;
        whirlpoolMaterial.uniforms.scrollProgress.value = scrollPercent;
        
        // Camera parallax position interpolation
        const targetY = 12 - scrollPercent * 25;
        const targetX = Math.sin(scrollPercent * Math.PI) * 2.2;
        const targetZ = 9 + Math.cos(scrollPercent * Math.PI) * 2.2;
        
        camera.position.y += (targetY - camera.position.y) * 0.08;
        camera.position.x += (targetX - camera.position.x) * 0.08;
        camera.position.z += (targetZ - camera.position.z) * 0.08;
        
        // Raw boy progress target along the curve (t from 0 to 0.96)
        targetBoyT = scrollPercent * 0.96;
        
        // ─── Scroll Reveal Dynamics ───
        // 1. Hero Overlay Fading
        if (heroOverlay) {
            const heroOpacity = Math.max(0, 1 - scrollPercent * 2.5); // Fades completely by 40% scroll
            const heroTranslateY = -scrollPercent * 60; // Smooth float-up
            heroOverlay.style.opacity = heroOpacity;
            heroOverlay.style.transform = `translateY(${heroTranslateY}px)`;
            
            if (heroOpacity <= 0) {
                heroOverlay.style.display = 'none';
            } else {
                heroOverlay.style.display = 'flex';
            }
        }
        
        // 2. App Section Revealing & Lighting Up
        if (appSection) {
            const revealProgress = Math.min(1, Math.max(0, (scrollPercent - 0.15) / 0.45));
            
            const appOpacity = revealProgress;
            const appScale = 0.95 + revealProgress * 0.05;
            const appBrightness = 0.2 + revealProgress * 0.8;
            const appBlur = 12 * (1 - revealProgress);
            
            appSection.style.opacity = appOpacity;
            appSection.style.transform = `scale(${appScale})`;
            appSection.style.filter = `brightness(${appBrightness}) blur(${appBlur}px)`;
            
            if (revealProgress > 0.5) {
                appSection.style.pointerEvents = 'all';
            } else {
                appSection.style.pointerEvents = 'none';
            }
        }
    }
    
    window.addEventListener('scroll', updateScroll);
    updateScroll();

    // 14. Window Resize Handler
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    // 15. Animation Loop
    const clock = new THREE.Clock();
    
    function animate() {
        requestAnimationFrame(animate);
        
        const delta = clock.getDelta();
        const time = clock.getElapsedTime();
        
        // Update water shader uniforms
        waterMaterial.uniforms.time.value = time;
        whirlpoolMaterial.uniforms.time.value = time;
        
        // Rotate the upper energy bulb slightly
        energyBulb.rotation.y = time * 0.2;
        energyBulb.rotation.x = time * 0.15;
        
        // 🧒 SMOOTH BOYT INTERPOLATION (Silky smooth sliding slide!)
        currentBoyT += (targetBoyT - currentBoyT) * 0.085; // Lerp progress
        
        // Fetch boy's basic curve point
        const boyPos = curve.getPointAt(currentBoyT);
        
        // Calculate curvature dynamically to trigger collision impacts (va đập)
        const tangent = curve.getTangentAt(currentBoyT);
        const prevTangent = curve.getTangentAt(Math.max(0, currentBoyT - 0.03));
        const angleChange = prevTangent.angleTo(tangent);
        
        const curveFactor = Math.min(1.0, angleChange * 6.5);
        const isBending = curveFactor > 0.35;
        
        // Calculate binormal vector for centrifugal displacement (lực ly tâm)
        const binormal = new THREE.Vector3().crossVectors(tangent, new THREE.Vector3(0, 0, 1)).normalize();
        
        let targetDisplacement = new THREE.Vector3(0, 0, 0);
        if (isBending) {
            // Push outwards against glass wall + rattling vibration
            const pushOut = curveFactor * 0.09;
            const rattle = Math.sin(time * 38.0) * 0.016;
            targetDisplacement = binormal.clone().multiplyScalar(pushOut + rattle);
            
            // Randomly trigger splash particles
            if (Math.random() < 0.25) {
                emitWaterSplashes(boyPos, curveFactor);
            }
        }
        
        // Lerp displacement for ultra-smooth collision transitions
        currentDisplacement.lerp(targetDisplacement, 0.085);
        
        // Apply position to boy
        boyGroup.position.copy(boyPos).add(currentDisplacement);
        
        // Orient the boy along slide direction
        const targetLookPos = curve.getPointAt(Math.min(0.99, currentBoyT + 0.01));
        boyGroup.lookAt(targetLookPos);
        
        // Lean into curve and add roll wiggles
        if (isBending) {
            boyGroup.rotateZ(curveFactor * 0.38 * Math.sin(time * 26.0));
            boyGroup.rotateX((Math.random() - 0.5) * 0.08); // pitch rattling
        }
        
        // Screaming mouth opens/closes (screaming "Ahhh!")
        mouth.scale.y = 0.65 + Math.sin(time * 16.0) * 0.35;
        
        // Waving arms
        leftArm.rotation.x = Math.PI / 5 + Math.sin(time * 14.0) * 0.25;
        rightArm.rotation.x = -Math.PI / 5 + Math.cos(time * 14.0) * 0.25;
        
        // 🧒 SMOOTH WHIRLPOOL SUCK-IN / REVELATION (Reversible)
        if (currentBoyT > 0.91) {
            const sinkProgress = Math.min(1.0, (currentBoyT - 0.91) / 0.05);
            const scaleFactor = 1.0 - sinkProgress;
            
            boyGroup.scale.set(scaleFactor, scaleFactor, scaleFactor);
            boyGroup.position.y -= sinkProgress * 1.4; // sink Y down
            
            if (scaleFactor <= 0.03) {
                boyGroup.visible = false;
            } else {
                boyGroup.visible = true;
            }
        } else {
            boyGroup.visible = true;
            boyGroup.scale.set(1.0, 1.0, 1.0);
        }
        
        // ─── 🔄 SMOOTH CAMERA TARGET TRACKING ───
        // Make camera look directly at the boy's position, offset slightly downwards
        // to keep the boy at the upper portion of the viewport.
        const targetLook = new THREE.Vector3(boyGroup.position.x, boyGroup.position.y - 0.45, boyGroup.position.z);
        cameraLookTarget.lerp(targetLook, 0.085); // lerping camera focal point!
        camera.lookAt(cameraLookTarget);
        
        // A. Animate bubble particles inside the glass pipe
        const positions = particleSystem.geometry.attributes.position.array;
        for (let i = 0; i < particleCount; i++) {
            particleProgress[i] += delta * 0.06 * particleOffsets[i].speed;
            
            const revealLimit = scrollPercent * 1.3;
            if (particleProgress[i] > revealLimit || particleProgress[i] > 1) {
                particleProgress[i] = 0;
            }
            
            const t = particleProgress[i];
            const pt = curve.getPointAt(t);
            
            const angle = particleOffsets[i].angle + time * particleOffsets[i].speed * 1.8;
            const radius = particleOffsets[i].radius * (1.0 + Math.sin(time * 1.5 + i) * 0.1);
            
            positions[i * 3] = pt.x + Math.cos(angle) * radius;
            positions[i * 3 + 1] = pt.y + Math.sin(angle) * radius;
            positions[i * 3 + 2] = pt.z + Math.sin(time * 0.6 + i) * 0.08;
        }
        particleSystem.geometry.attributes.position.needsUpdate = true;

        // B. Animate water splash particles at curves (va đập)
        const sPos = splashSystem.geometry.attributes.position.array;
        for (let i = 0; i < splashCount; i++) {
            if (splashLifes[i] > 0) {
                sPos[i * 3] += splashVelocities[i].x * delta;
                sPos[i * 3 + 1] += splashVelocities[i].y * delta;
                sPos[i * 3 + 2] += splashVelocities[i].z * delta;
                
                // Gravity
                splashVelocities[i].y -= 4.2 * delta;
                
                // Age particle
                splashLifes[i] -= delta * 2.2;
                
                if (splashLifes[i] <= 0) {
                    splashLifes[i] = 0;
                    sPos[i * 3 + 1] = -100;
                }
            }
        }
        splashSystem.geometry.attributes.position.needsUpdate = true;

        // C. Animate whirlpool particles swirling and sinking into funnel
        const vPositions = vortexParticleSystem.geometry.attributes.position.array;
        const vReveal = smoothstep(0.3, 0.7, scrollPercent);
        
        for (let i = 0; i < vParticleCount; i++) {
            const data = vParticleData[i];
            
            const angularVelocity = (0.048 * data.speed) / (data.radius + 0.12);
            data.angle += angularVelocity;
            data.radius -= delta * 0.45 * data.speed;
            
            if (data.radius < 0.22 || vReveal <= 0.0) {
                data.radius = 3.2 + Math.random() * 1.3;
                data.angle = Math.random() * Math.PI * 2;
            }
            
            const x = Math.cos(data.angle) * data.radius;
            const z = Math.sin(data.angle) * data.radius;
            const y = -1.8 / (0.35 + data.radius * data.radius) + 0.3 - 18;
            
            vPositions[i * 3] = x;
            vPositions[i * 3 + 1] = y;
            vPositions[i * 3 + 2] = z;
        }
        vortexParticleSystem.geometry.attributes.position.needsUpdate = true;
        vParticleMaterial.size = 0.28 * vReveal;

        // D. Animate Ambient Droplets "Vướng Vấn Bụi Trần"
        const aPositions = ambientParticleSystem.geometry.attributes.position.array;
        for (let i = 0; i < aParticleCount; i++) {
            const speed = aParticleSpeeds[i];
            aPositions[i * 3] += Math.sin(time * 0.4 * speed.x + i) * 0.003;
            aPositions[i * 3 + 1] += Math.cos(time * 0.3 * speed.y + i) * 0.004;
            aPositions[i * 3 + 2] += Math.sin(time * 0.5 * speed.z + i) * 0.003;
            
            if (Math.abs(aPositions[i * 3]) > 10) aPositions[i * 3] *= -0.9;
            if (aPositions[i * 3 + 1] > 20) aPositions[i * 3 + 1] = -24;
            if (aPositions[i * 3 + 1] < -24) aPositions[i * 3 + 1] = 20;
            if (Math.abs(aPositions[i * 3 + 2]) > 8) aPositions[i * 3 + 2] *= -0.9;
        }
        ambientParticleSystem.geometry.attributes.position.needsUpdate = true;
        
        // Smoothly interpolate scroll updates
        updateScroll();
        
        renderer.render(scene, camera);
    }
    
    // Helper function for smooth interpolation
    function smoothstep(min, max, value) {
        const x = Math.max(0, Math.min(1, (value - min) / (max - min)));
        return x * x * (3 - 2 * x);
    }

    animate();
})();
