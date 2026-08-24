import React, { Suspense, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";
import { ColorPalette, makeSharedStyles, useAppTheme } from "../theme";
import Icon from "./Icon";

interface Props { glbBase64: string; sizeKb?: number }

function Model({ url }: { url: string }) {
  const gltf = useLoader(GLTFLoader, url);
  const group = useRef<THREE.Group>(null);
  useEffect(() => {
    const box = new THREE.Box3().setFromObject(gltf.scene);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const scale = 2 / Math.max(size.x, size.y, size.z, 0.001);
    gltf.scene.scale.setScalar(scale);
    gltf.scene.position.sub(center.multiplyScalar(scale));
  }, [gltf]);
  useFrame((_, delta) => { if (group.current) group.current.rotation.y += delta * 0.25; });
  return <group ref={group}><primitive object={gltf.scene} /></group>;
}

function Fallback() {
  return <mesh><boxGeometry args={[1, 1, 1]} /><meshStandardMaterial color="#8b5cf6" wireframe /></mesh>;
}

export default function ThreeDViewer({ glbBase64, sizeKb }: Props) {
  const { colors } = useAppTheme();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  const shared = React.useMemo(() => makeSharedStyles(colors), [colors]);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  useEffect(() => {
    const binary = atob(glbBase64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const url = URL.createObjectURL(new Blob([bytes], { type: "model/gltf-binary" }));
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [glbBase64]);

  const download = () => {
    if (!objectUrl) return;
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = "model.glb";
    anchor.click();
  };

  return (
    <View style={[shared.card, styles.card]}>
      <View style={styles.header}>
        <View style={styles.inlineInfo}><Icon color={colors.primaryBright} name="cube" size={16} /><Text style={styles.badge}>3D Model - Hunyuan3D-2</Text></View>
        <View style={styles.headerActions}>
          {!!sizeKb && <Text style={styles.tag}>{sizeKb} KB GLB</Text>}
          <Pressable onPress={download} style={styles.download}><Icon color="#ffffff" name="download" size={15} /><Text style={styles.downloadText}>Download</Text></Pressable>
        </View>
      </View>
      <View style={styles.canvas}>
        {!objectUrl ? (
          <View style={styles.loading}><ActivityIndicator color={colors.primaryBright} /><Text style={styles.hint}>Preparing 3D viewer...</Text></View>
        ) : (
          <Canvas camera={{ position: [0, 1.5, 4], fov: 45 }} style={styles.canvasFill}>
            <ambientLight intensity={1.5} />
            <directionalLight position={[5, 8, 5]} intensity={1.8} />
            <directionalLight position={[-5, 3, 2]} intensity={1.2} />
            <directionalLight position={[0, -3, -4]} intensity={0.8} />
            <Suspense fallback={<Fallback />}><Model url={objectUrl} /></Suspense>
            <OrbitControls enablePan={false} minDistance={1.5} maxDistance={8} />
          </Canvas>
        )}
      </View>
      <Text style={styles.hint}>Drag to orbit. Scroll to zoom. Model auto-rotates.</Text>
    </View>
  );
}

const makeStyles = (colors: ColorPalette) => StyleSheet.create({
  card: { padding: 12, gap: 12 },
  header: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 10, paddingHorizontal: 5 },
  headerActions: { flexDirection: "row", alignItems: "center", gap: 8 },
  inlineInfo: { flexDirection: "row", alignItems: "center", gap: 7 },
  badge: { color: colors.primaryBright, fontSize: 12, fontWeight: "800" },
  tag: { color: colors.textDim, fontSize: 10 },
  download: { flexDirection: "row", alignItems: "center", gap: 7, backgroundColor: colors.primary, borderRadius: 9, paddingHorizontal: 11, paddingVertical: 8 },
  downloadText: { color: "white", fontSize: 11, fontWeight: "800" },
  canvas: { width: "100%", height: 480, borderRadius: 14, overflow: "hidden", backgroundColor: colors.canvas },
  canvasFill: { width: "100%", height: "100%" },
  loading: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12 },
  hint: { color: colors.textDim, textAlign: "center", fontSize: 11 },
});
