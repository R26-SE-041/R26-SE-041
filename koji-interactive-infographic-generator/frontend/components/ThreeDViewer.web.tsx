import React, { useRef } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { useAppTheme, makeSharedStyles } from "../theme";
import { ModelSource, useModel } from "./modelResources.web";
import ModelLighting from "./ModelLighting";
import { configureModelRenderer } from "./configureModelRenderer";

function Model({ scene, rotate }: { scene: THREE.Group; rotate: boolean }) {
  const group = useRef<THREE.Group>(null);
  useFrame((_, delta) => { if (rotate && group.current) group.current.rotation.y += delta * .2; });
  return <group ref={group}><primitive object={scene} dispose={null} /></group>;
}

export default function ThreeDViewer(props: ModelSource & { sizeKb?: number; active?: boolean }) {
  const { colors } = useAppTheme();
  const shared = makeSharedStyles(colors);
  const { scene, error, retry } = useModel(props);
  const [rotate, setRotate] = React.useState(false);
  const download = () => {
    const anchor = document.createElement("a");
    anchor.href = props.modelUrl || `data:model/gltf-binary;base64,${props.glbBase64}`;
    anchor.download = "model.glb";
    if (props.modelUrl) { anchor.target = "_blank"; anchor.rel = "noopener noreferrer"; }
    anchor.click();
  };
  return <View style={[shared.card, { padding: 12, gap: 12 }]}>
    <View style={{ flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
      <Text style={{ color: colors.text, fontWeight: "600" }}>3D Model{props.sizeKb ? ` · ${Math.round(props.sizeKb)} KB` : ""}</Text>
      <View style={{ flexDirection: "row", gap: 12 }}>
        <Pressable accessibilityRole="button" onPress={() => setRotate(value => !value)}><Text style={{ color: colors.text }}>{rotate ? "Pause rotation" : "Auto-rotate"}</Text></Pressable>
        <Pressable accessibilityRole="button" onPress={download}><Text style={{ color: colors.text }}>Download GLB</Text></Pressable>
      </View>
    </View>
    <div data-drag-surface="true" style={{ height: 480, borderRadius: 8, overflow: "hidden", backgroundColor: colors.canvas, touchAction: "none", userSelect: "none" }}>
      {error ? <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 12, padding: 24 }}><Text accessibilityRole="alert" style={{ color: colors.danger, textAlign: "center" }}>{error}</Text><Pressable accessibilityRole="button" onPress={retry}><Text style={{ color: colors.text }}>Retry model display</Text></Pressable></View>
        : scene ? <Canvas frameloop={props.active === false ? "never" : rotate ? "always" : "demand"} dpr={[1, 1.5]} camera={{ position: [0, .8, 4], fov: 45 }} onCreated={({ gl }) => configureModelRenderer(gl)}>
          <ModelLighting /><Model scene={scene} rotate={rotate} /><OrbitControls enablePan={false} minDistance={1.5} maxDistance={8} />
        </Canvas> : <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 12 }}><ActivityIndicator color={colors.primary} /><Text style={{ color: colors.textMuted }}>Opening your saved model…</Text></View>}
    </div>
    <Text style={{ color: colors.textMuted, textAlign: "center", fontSize: 12 }}>Drag or touch to rotate · Scroll or pinch to zoom</Text>
  </View>;
}
