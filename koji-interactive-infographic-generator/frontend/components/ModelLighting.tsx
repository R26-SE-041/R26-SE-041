import React from "react";

/**
 * Balanced studio lighting shared by the web and native GLB viewers.
 * Hemisphere light keeps upward and downward faces readable, while the four
 * directional lights preserve enough contrast to show the mesh's form.
 */
export default function ModelLighting() {
  return (
    <>
      <ambientLight intensity={0.65} />
      <hemisphereLight args={["#fffaf2", "#dbeafe", 1.35]} />
      <directionalLight color="#fff4df" position={[5, 7, 5]} intensity={1.65} />
      <directionalLight color="#e8f1ff" position={[-5, 2, 4]} intensity={1.2} />
      <directionalLight color="#ffffff" position={[0, -5, 3]} intensity={1.35} />
      <directionalLight color="#e9e5ff" position={[1, 2, -5]} intensity={1.0} />
    </>
  );
}
