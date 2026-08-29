import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, PanResponder, Pressable, StyleSheet, Text, View } from "react-native";
import { Canvas, useFrame } from "@react-three/fiber/native";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";
import { decode } from "base64-arraybuffer";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { ColorPalette, makeSharedStyles, useAppTheme } from "../theme";
import Icon from "./Icon";
import ModelLighting from "./ModelLighting";
import { configureModelRenderer } from "./configureModelRenderer";

interface Props { glbBase64: string; sizeKb?: number }

function Model({ scene, yaw, pitch, zoom }: { scene: THREE.Group; yaw: React.RefObject<number>; pitch: React.RefObject<number>; zoom: React.RefObject<number> }) {
  const group = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (!group.current) return;
    yaw.current += delta * 0.18;
    group.current.rotation.set(pitch.current, yaw.current, 0);
    group.current.scale.setScalar(zoom.current);
  });
  return <group ref={group}><primitive object={scene} /></group>;
}

export default function ThreeDViewer({ glbBase64, sizeKb }: Props) {
  const { colors } = useAppTheme();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  const shared = React.useMemo(() => makeSharedStyles(colors), [colors]);
  const [scene, setScene] = useState<THREE.Group | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const yaw = useRef(0);
  const pitch = useRef(0);
  const zoom = useRef(1);
  const lastDrag = useRef({ x: 0, y: 0 });

  useEffect(() => {
    let active = true;
    setScene(null);
    setLoadError(null);
    new GLTFLoader().parse(
      decode(glbBase64),
      "",
      (gltf) => {
        if (!active) return;
        const loaded = gltf.scene;
        const box = new THREE.Box3().setFromObject(loaded);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const scale = 2 / Math.max(size.x, size.y, size.z, 0.001);
        loaded.scale.setScalar(scale);
        loaded.position.sub(center.multiplyScalar(scale));
        setScene(loaded);
      },
      (caught) => active && setLoadError(caught instanceof Error ? caught.message : "Unable to load GLB"),
    );
    return () => { active = false; };
  }, [glbBase64]);

  const panResponder = PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: (_, gesture) => { lastDrag.current = { x: gesture.x0, y: gesture.y0 }; },
    onPanResponderMove: (_, gesture) => {
      yaw.current += (gesture.moveX - lastDrag.current.x) * 0.012;
      pitch.current = Math.max(-1.2, Math.min(1.2, pitch.current + (gesture.moveY - lastDrag.current.y) * 0.012));
      lastDrag.current = { x: gesture.moveX, y: gesture.moveY };
    },
  });

  const download = async () => {
    try {
      const uri = `${FileSystem.cacheDirectory}eduvision-model.glb`;
      await FileSystem.writeAsStringAsync(uri, glbBase64, { encoding: FileSystem.EncodingType.Base64 });
      if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(uri, { mimeType: "model/gltf-binary", dialogTitle: "Save or share 3D model" });
    } catch (caught) {
      setLoadError(caught instanceof Error ? caught.message : "Unable to save GLB");
    }
  };

  return (
    <View style={[shared.card, styles.card]}>
      <View style={styles.header}>
        <View style={styles.inlineInfo}><Icon color={colors.primaryBright} name="cube" size={16} /><Text style={styles.badge}>3D Model - Hunyuan3D-2</Text></View>
        {!!sizeKb && <Text style={styles.tag}>{sizeKb} KB GLB</Text>}
      </View>
      <View {...panResponder.panHandlers} style={styles.canvas}>
        {!scene ? (
          <View style={styles.loading}><ActivityIndicator color={colors.primaryBright} size="large" /><Text style={styles.hint}>{loadError ?? "Preparing 3D viewer..."}</Text></View>
        ) : (
          <Canvas camera={{ position: [0, 1.5, 4], fov: 45 }} onCreated={({ gl }) => configureModelRenderer(gl)} style={styles.canvasFill}>
            <ModelLighting />
            <Model pitch={pitch} scene={scene} yaw={yaw} zoom={zoom} />
          </Canvas>
        )}
      </View>
      <View style={styles.controls}>
        <Pressable accessibilityLabel="Zoom out" onPress={() => { zoom.current = Math.max(0.45, zoom.current - 0.15); }} style={styles.controlButton}><Icon color={colors.text} name="minus" size={18} /></Pressable>
        <Text style={styles.hint}>Drag to orbit. Model auto-rotates.</Text>
        <Pressable accessibilityLabel="Zoom in" onPress={() => { zoom.current = Math.min(2.5, zoom.current + 0.15); }} style={styles.controlButton}><Icon color={colors.text} name="plus" size={18} /></Pressable>
      </View>
      <Pressable onPress={download} style={[shared.button, shared.primaryButton]}><Icon color="#ffffff" name="download" size={17} /><Text style={shared.buttonText}>Save or Share GLB</Text></Pressable>
      {!!loadError && <Text style={styles.error}>{loadError}</Text>}
    </View>
  );
}

const makeStyles = (colors: ColorPalette) => StyleSheet.create({
  card: { padding: 12, gap: 12 },
  header: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 8, paddingHorizontal: 5 },
  inlineInfo: { flexDirection: "row", alignItems: "center", gap: 7 },
  badge: { color: colors.primaryBright, fontSize: 12, fontWeight: "800" },
  tag: { color: colors.textDim, fontSize: 10 },
  canvas: { width: "100%", height: 420, borderRadius: 14, overflow: "hidden", backgroundColor: colors.canvas },
  canvasFill: { width: "100%", height: "100%" },
  loading: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12 },
  controls: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 16 },
  controlButton: { width: 38, height: 34, borderRadius: 10, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  hint: { color: colors.textDim, textAlign: "center", fontSize: 11 },
  error: { color: colors.danger, fontSize: 12, textAlign: "center" },
});
