// frontend/components/ThreeDViewer.tsx
// Interactive 3D GLB viewer powered by Three.js + @react-three/fiber

"use client";

import React, { Suspense, useRef, useEffect, useState } from "react";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { OrbitControls, Environment, ContactShadows } from "@react-three/drei";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";

// ── Types ──────────────────────────────────────────────────────────────────────

interface ThreeDViewerProps {
  glbBase64: string;
  sizeKb?: number;
}

// ── GLB Model Component ────────────────────────────────────────────────────────

function GLBModel({ url }: { url: string }) {
  const gltf = useLoader(GLTFLoader, url);
  const groupRef = useRef<THREE.Group>(null!);

  // Auto-rotate slowly
  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.4;
    }
  });

  // Center and scale the model to fit the viewport
  useEffect(() => {
    if (!gltf.scene) return;
    const box = new THREE.Box3().setFromObject(gltf.scene);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const scale = 2 / maxDim;
    gltf.scene.scale.setScalar(scale);
    gltf.scene.position.sub(center.multiplyScalar(scale));
  }, [gltf]);

  return (
    <group ref={groupRef}>
      <primitive object={gltf.scene} />
    </group>
  );
}

// ── Loading fallback ───────────────────────────────────────────────────────────

function ModelFallback() {
  return (
    <mesh>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#6366f1" wireframe />
    </mesh>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function ThreeDViewer({ glbBase64, sizeKb }: ThreeDViewerProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  // Convert base64 GLB → Blob URL so Three.js can load it
  useEffect(() => {
    if (!glbBase64) return;

    const binaryStr = atob(glbBase64);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: "model/gltf-binary" });
    const url = URL.createObjectURL(blob);
    setObjectUrl(url);

    return () => URL.revokeObjectURL(url);
  }, [glbBase64]);

  if (!objectUrl) {
    return (
      <div className="threed-viewer-card glass-card">
        <div className="threed-loading">
          <div className="spinner" />
          <p>Preparing 3D viewer…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="threed-viewer-card glass-card">

      {/* Header bar */}
      <div className="threed-viewer-header">
        <span className="enhanced-badge">🧊 3D Model — Hunyuan3D-2</span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {sizeKb && (
            <span className="enhanced-model-tag">{sizeKb} KB GLB</span>
          )}
          <span className="enhanced-model-tag">Drag · Scroll · Auto-rotate</span>
          <a
            href={objectUrl}
            download="model.glb"
            className="threed-download-btn"
            title="Download GLB"
          >
            ⬇ Download
          </a>
        </div>
      </div>

      {/* Three.js Canvas */}
      <div className="threed-canvas-wrap" id="threed-canvas">
        <Canvas
          camera={{ position: [0, 1.5, 4], fov: 45 }}
          shadows
          style={{ width: "100%", height: "100%" }}
        >
          {/* Lighting */}
          <ambientLight intensity={0.6} />
          <directionalLight
            position={[5, 8, 5]}
            intensity={1.2}
            castShadow
            shadow-mapSize={[1024, 1024]}
          />
          <directionalLight position={[-4, 4, -4]} intensity={0.4} />

          {/* Model */}
          <Suspense fallback={<ModelFallback />}>
            <GLBModel url={objectUrl} />
          </Suspense>

          {/* Contact shadow on "floor" */}
          <ContactShadows
            position={[0, -1.4, 0]}
            opacity={0.4}
            scale={6}
            blur={2}
            far={4}
          />

          {/* Environment lighting (HDRI preset) */}
          <Environment preset="city" />

          {/* User controls: drag to rotate, scroll to zoom */}
          <OrbitControls
            enablePan={false}
            minDistance={1.5}
            maxDistance={8}
            autoRotate={false}
          />
        </Canvas>
      </div>

      {/* Hint */}
      <p className="threed-hint">
        Drag to orbit &middot; Scroll to zoom &middot; Model auto-rotates
      </p>
    </div>
  );
}
