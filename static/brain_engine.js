/**
 * BrainEngine.js - NEURAL ENGINE 2.0
 * A high-performance 3D point-cloud brain animation for UrlForge.
 * Features: Morphologically accurate morphology, depth-based palette, and cinematic focus.
 */

class BrainAnimation {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.meshPoints = [];
        this.auraPoints = [];
        this.uSteps = 70; // Grid resolution
        this.vSteps = 80;
        
        this.rotation = { x: 0, y: 0 };
        this.targetRotation = { x: 0, y: 0 };
        this.mouse = { x: 0, y: 0 };
        
        this.scale = 0;
        this.targetScale = 0;
        this.isEnlarged = false;
        
        this.glowColor = null;
        this.glowIntensity = 0;
        
        this.particles = [];
        this.labels = [];

        this.init();
        this.animate();
        this.addEventListeners();
    }

    init() {
        this.resize();
        this.generateAnatomicalMesh();
        this.generateAura();
    }

    resize() {
        // Reset scale before measuring to avoid recursive growth
        this.canvas.width = window.innerWidth * window.devicePixelRatio;
        this.canvas.height = window.innerHeight * window.devicePixelRatio;
        this.ctx.setTransform(1, 0, 0, 1, 0, 0); 
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        
        this.canvas.style.width = window.innerWidth + 'px';
        this.canvas.style.height = window.innerHeight + 'px';
        
        // Dynamic base scale based on screen width
        const base = Math.min(window.innerWidth, window.innerHeight);
        this.idleScale = base * 0.12; 
        this.analyticalScale = base * 0.28; 
        
        this.targetScale = this.isEnlarged ? this.analyticalScale : this.idleScale;
        if (this.scale === 0) this.scale = this.targetScale;
    }

    generateAnatomicalMesh() {
        this.meshPoints = [];
        const length = 1.35;
        const width = 1.0;
        const height = 0.9;
        const fissureWidth = 0.12;

        for (let s = 0; s < 2; s++) { // Two hemispheres
            const side = s === 0 ? 1 : -1;
            const hemisphere = [];
            
            for (let i = 0; i <= this.uSteps; i++) {
                const u = (i / this.uSteps) * Math.PI;
                const row = [];
                for (let j = 0; j <= this.vSteps; j++) {
                    const v = (j / this.vSteps) * Math.PI - (Math.PI / 2);

                    const foldFrequency = 12;
                    const foldDepth = 0.12;
                    const folds = Math.sin(u * foldFrequency) * Math.cos(v * foldFrequency) * Math.sin(u * 2) * foldDepth;
                    
                    let r = 1.0 + folds;
                    let x = r * width * Math.sin(u) * Math.cos(v);
                    let y = r * height * Math.sin(u) * Math.sin(v);
                    let z = r * length * Math.cos(u);

                    // Central Fissure
                    x = (Math.abs(x) + fissureWidth) * side;

                    row.push({ x, y, z, baseX: x, baseY: y, baseZ: z });
                }
                hemisphere.push(row);
            }
            this.meshPoints.push(hemisphere);
        }
    }

    generateAura() {
        this.auraPoints = [];
        for (let i = 0; i < 2500; i++) {
            const r = 2.0 + Math.random() * 2.5; 
            const u = Math.acos(2 * Math.random() - 1);
            const v = Math.random() * Math.PI * 2;
            
            this.auraPoints.push({
                x: r * Math.sin(u) * Math.cos(v),
                y: r * Math.sin(u) * Math.sin(v),
                z: r * Math.cos(u),
                brightness: Math.random() * 0.4 + 0.2
            });
        }
    }

    addEventListeners() {
        window.addEventListener('resize', () => this.resize());
        
        const handleMove = (e) => {
            const x = e.touches ? e.touches[0].clientX : e.clientX;
            const y = e.touches ? e.touches[0].clientY : e.clientY;
            this.mouse.x = (x - window.innerWidth / 2) / (window.innerWidth / 2);
            this.mouse.y = (y - window.innerHeight / 2) / (window.innerHeight / 2);
        };

        window.addEventListener('mousemove', handleMove);
        window.addEventListener('touchmove', (e) => {
            handleMove(e);
            if (this.targetScale > 200) e.preventDefault(); // Prevent scroll in analytical mode
        }, { passive: false });
    }

    startThinking() {
        this.isEnlarged = true;
        this.targetScale = this.analyticalScale;
    }

    stopThinking() {
        this.isEnlarged = false;
        this.targetScale = this.idleScale;
    }

    glow(isSuccess) {
        this.glowColor = isSuccess ? '#10b981' : '#ef4444';
        this.glowIntensity = 1.0;
        this.emitBurst(this.glowColor);
    }

    emitBurst(color) {
        const count = this.targetScale > 150 ? 40 : 20; 
        for (let i = 0; i < count; i++) {
            this.particles.push({
                x: 0, y: 0, z: 0,
                vx: (Math.random() - 0.5) * 25,
                vy: (Math.random() - 0.5) * 25,
                vz: (Math.random() - 0.5) * 25,
                life: 1.0,
                color
            });
        }
    }

    project(px_in, py_in, pz_in, centerX, centerY) {
        // 3D Rotation
        let x = px_in * Math.cos(this.rotation.y) - pz_in * Math.sin(this.rotation.y);
        let z = px_in * Math.sin(this.rotation.y) + pz_in * Math.cos(this.rotation.y);
        let y = py_in * Math.cos(this.rotation.x) - z * Math.sin(this.rotation.x);
        z = py_in * Math.sin(this.rotation.x) + z * Math.cos(this.rotation.x);

        // Perspective Stability Guard: prevent z-perspective inversion
        const fov = 600;
        const perspective = fov / Math.max(10, (fov + z * this.scale));
        const drawX = centerX + x * this.scale * perspective;
        const drawY = centerY + y * this.scale * perspective;
        
        return { drawX, drawY, perspective, z, x, y };
    }

    showCategory(text) {
        const isBad = text.toLowerCase().includes('error') || text.toLowerCase().includes('fail') || text.toLowerCase().includes('issue');
        this.glow(!isBad);
        
        this.labels.push({
            text: text.toUpperCase(),
            x: 0,
            y: 0,
            z: 0,
            vx: (Math.random() - 0.5) * 2, // Slower lateral drift
            vy: (Math.random() - 0.5) * 0.5,
            vz: 0.8, // Slow-motion fly for readability
            opacity: 0,
            life: 4.0 // Longer life for readability
        });
    }

    animate() {
        const time = Date.now() * 0.001;
        this.ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

        // Rotation & Scaling Logic (Strict Kinetic Cursor Tracking)
        // Auto-drift and constant rotation removed per user request
        this.targetRotation.x = (this.mouse.y * 0.4); 
        this.targetRotation.y = (this.mouse.x * 0.6); 
        
        this.rotation.x += (this.targetRotation.x - this.rotation.x) * 0.05;
        this.rotation.y += (this.targetRotation.y - this.rotation.y) * 0.05;
        this.scale += (this.targetScale - this.scale) * 0.05;

        const centerX = window.innerWidth / 2;
        const centerY = window.innerHeight / 2;

        // 1. Draw Digital Aura (Dots scattered around)
        this.ctx.fillStyle = '#fff';
        this.auraPoints.forEach(p => {
            const rotated = this.project(p.x, p.y, p.z, centerX, centerY);
            if (!rotated) return;
            
            this.ctx.globalAlpha = p.brightness * rotated.perspective * 0.4;
            this.ctx.beginPath();
            this.ctx.arc(rotated.drawX, rotated.drawY, 1.2 * rotated.perspective, 0, Math.PI * 2);
            this.ctx.fill();
        });

        // 2. Draw Solid Brain Mesh
        this.ctx.lineWidth = 0.5;
        this.meshPoints.forEach(hemisphere => {
            for (let i = 0; i < this.uSteps; i++) {
                for (let j = 0; j < this.vSteps; j++) {
                    const p1 = hemisphere[i][j];
                    const p2 = hemisphere[i][j + 1]; // Only connect along v-contour

                    const r1 = this.project(p1.x, p1.y, p1.z, centerX, centerY);
                    const r2 = this.project(p2.x, p2.y, p2.z, centerX, centerY);

                    if (!r1 || !r2) continue;

                    // Solid occlusion: strictly cull back-facing contour segments
                    if (r1.z > 0.4) continue; 

                    const depthRatio = (r1.z + 1.5) / 3;
                    const r = Math.floor(79 + (6 - 79) * depthRatio);
                    const g = Math.floor(70 + (182 - 70) * depthRatio);
                    const b = Math.floor(229 + (212 - 229) * depthRatio);
                    const color = `rgb(${r}, ${g}, ${b})`;

                    this.ctx.strokeStyle = color;
                    this.ctx.globalAlpha = (1 - depthRatio) * 0.8;
                    if (this.glowIntensity > 0) {
                        this.ctx.strokeStyle = this.glowColor;
                        this.ctx.globalAlpha = this.glowIntensity;
                    }

                    this.ctx.beginPath();
                    this.ctx.moveTo(r1.drawX, r1.drawY);
                    this.ctx.lineTo(r2.drawX, r2.drawY);
                    this.ctx.stroke();
                }
            }
        });

        // Decay Glow
        if (this.glowIntensity > 0) this.glowIntensity -= 0.015;

        // 3. Draw Burst Particles
        for (let i = this.particles.length - 1; i >= 0; i--) {
            const p = this.particles[i];
            p.x += p.vx; p.y += p.vy; p.z += p.vz;
            p.life -= 0.02;
            
            if (p.life <= 0 || p.z < -450) {
                this.particles.splice(i, 1);
                continue;
            }
            
            const r = this.project(p.x, p.y, p.z, centerX, centerY);
            if (!r) continue;

            this.ctx.globalAlpha = p.life * r.perspective;
            this.ctx.fillStyle = p.color;
            this.ctx.beginPath();
            this.ctx.arc(r.drawX, r.drawY, 4 * r.perspective, 0, Math.PI * 2);
            this.ctx.fill();
        }

        // Draw Drifting Labels - Robust Backwards Loop
        this.ctx.textAlign = 'center';
        for (let i = this.labels.length - 1; i >= 0; i--) {
            const l = this.labels[i];
            l.x += l.vx;
            l.y += l.vy;
            l.z -= l.vz; // Move toward camera
            l.life -= 0.015;
            
            if (l.life <= 0 || l.z < -450) {
                this.labels.splice(i, 1);
                continue;
            }
            
            
            const t_perspective = 600 / Math.max(10, (600 + l.z));
            const t_size = Math.floor(22 * t_perspective); 
            const drawX = centerX + l.x * t_perspective;
            const drawY = centerY + (l.y - 40) * t_perspective; 

            this.ctx.font = `800 ${t_size}px "Outfit"`;
            // Improved Fade Logic: Faster fade-in, slower fade-out
            const lifeAlpha = Math.min(l.life * 1.5, 1.0); 
            const distAlpha = Math.min(1.0, (580 + l.z) / 100);
            this.ctx.globalAlpha = Math.max(0, lifeAlpha * distAlpha);
            
            // Add cinematic text shadow for readability
            this.ctx.shadowBlur = 15;
            this.ctx.shadowColor = 'rgba(255, 255, 255, 0.5)';
            this.ctx.fillStyle = '#fff';
            this.ctx.fillText(l.text, drawX, drawY);
            this.ctx.shadowBlur = 0; // Reset
        }

        this.ctx.globalAlpha = 1.0;
        requestAnimationFrame(() => this.animate());
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.brain = new BrainAnimation('bg-canvas');
});
