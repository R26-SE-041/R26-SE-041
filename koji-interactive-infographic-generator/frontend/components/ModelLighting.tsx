import React from "react";

/**
 * Balanced studio lighting shared by the web and native GLB viewers.
 * Hemisphere light keeps upward and downward faces readable, while soft fill
 * lights prevent generated meshes from losing detail on their back and sides.
 */
export default function ModelLighting() {
  return (
    <>
      <ambientLight intensity={0.85} />
      <hemisphereLight args={["#fffaf2", "#dbeafe", 1.55]} />
      <directionalLight color="#fff4df" position={[5, 7, 5]} intensity={1.75} />
      <directionalLight color="#e8f1ff" position={[-5, 3, 4]} intensity={1.4} />
      <directionalLight color="#ffffff" position={[0, -5, 3]} intensity={1.45} />
      <directionalLight color="#f1edff" position={[1, 3, -5]} intensity={1.3} />
    </>
  );
}
