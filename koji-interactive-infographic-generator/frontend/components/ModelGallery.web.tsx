import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, PerspectiveCamera, View as ModelView } from "@react-three/drei";
import { SavedModel } from "../studioClient";
import { useAppTheme } from "../theme";
import { useModel } from "./modelResources.web";
import { ModelGalleryProps, useSavedModels } from "./useSavedModels";
import ModelLighting from "./ModelLighting";
import { configureModelRenderer } from "./configureModelRenderer";

function ViewportUpdates({ active }: { active: boolean }) {
  const invalidate = useThree(state => state.invalidate);
  const size = useThree(state => state.size);
  useEffect(() => {
    let frame = 0, remaining = 0;
    const tick = () => {
      invalidate();
      if (--remaining > 0) frame = requestAnimationFrame(tick);
      else frame = 0;
    };
    // DOM layout and the shared canvas resize on separate frames. Redraw
    // after both have settled, then return to idle until another interaction.
    const update = () => { remaining = 4; if (!frame) frame = requestAnimationFrame(tick); };
    update();
    document.addEventListener("scroll", update, true); window.addEventListener("resize", update);
    const observer = new ResizeObserver(update); observer.observe(document.body);
    return () => { cancelAnimationFrame(frame); document.removeEventListener("scroll", update, true); window.removeEventListener("resize", update); observer.disconnect(); };
  }, [invalidate, size.width, size.height, active]);
  return null;
}

function ModelCard({ model, index, props }: { model: SavedModel; index: number; props: ModelGalleryProps }) {
  const { colors } = useAppTheme();
  const track = useRef<HTMLDivElement>(null);
  const [nearby, setNearby] = useState(false);
  useEffect(() => {
    const observer = new IntersectionObserver(entries => setNearby(entries[0].isIntersecting), { rootMargin: "300px" });
    if (track.current) observer.observe(track.current);
    return () => observer.disconnect();
  }, []);
  const { scene, error, retry } = useModel(model, !props.trashed && (index < 6 || (props.active && nearby)));
  const button = { minHeight: 40, paddingHorizontal: 12, justifyContent: "center" as const, borderRadius: 8, backgroundColor: colors.surfaceSoft };
  return <div ref={track} style={{ border: `1px solid ${colors.border}`, background: colors.surface, borderRadius: 12, padding: 12, minWidth: 0 }}>
    {scene ? <ModelView data-drag-surface="true" id={`model-preview-${index}`} visible={props.active && nearby} index={index + 1} style={{ height: 260, width: "100%", borderRadius: 8, touchAction: "none", userSelect: "none", cursor: "grab" }}>
      <PerspectiveCamera makeDefault position={[0, .7, 4]} fov={45} />
      <color attach="background" args={[colors.canvas]} /><ModelLighting />
      <primitive object={scene} dispose={null} />
      <OrbitControls makeDefault enablePan={false} minDistance={1.5} maxDistance={8} />
    </ModelView> : <View style={{ height: 260, alignItems: "center", justifyContent: "center", gap: 12, backgroundColor: colors.canvas, borderRadius: 8 }}>
      {error ? <><Text accessibilityRole="alert" style={{ color: colors.danger, textAlign: "center" }}>{error}</Text><Pressable accessibilityRole="button" onPress={retry}><Text style={{ color: colors.text }}>Retry display</Text></Pressable></> : <><ActivityIndicator color={colors.primary} /><Text style={{ color: colors.textMuted }}>{props.trashed ? "Model preserved in Recycle Bin" : "Preparing saved model…"}</Text></>}
    </View>}
    <View style={{ paddingTop: 12, gap: 10 }}>
      <Text numberOfLines={2} style={{ color: colors.text, fontSize: 17, fontWeight: "600", minHeight: 44 }}>{model.title}</Text>
      <Text style={{ color: colors.textMuted, fontSize: 12 }}>Drag or touch to rotate · Pinch to zoom</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {!props.trashed && <Pressable accessibilityRole="button" style={button} onPress={() => props.onOpen(model)}><Text style={{ color: colors.text }}>Open creation</Text></Pressable>}
        {props.trashed ? <Pressable accessibilityRole="button" style={button} onPress={() => props.onRestore(model)}><Text style={{ color: colors.text }}>Restore</Text></Pressable> : <Pressable accessibilityRole="button" accessibilityLabel={`Rename ${model.title}`} style={button} onPress={() => props.onRename(model)}><Text style={{ color: colors.text }}>Rename</Text></Pressable>}
        <Pressable accessibilityRole="button" accessibilityLabel={`Delete ${model.title}`} style={button} onPress={() => props.onDelete(model)}><Text style={{ color: colors.danger }}>{props.trashed ? "Delete permanently" : "Delete"}</Text></Pressable>
      </View>
    </View>
  </div>;
}

export default function ModelGallery(props: ModelGalleryProps) {
  const { colors } = useAppTheme();
  const { models, loading, error, refresh } = useSavedModels(props);
  const root = useRef<HTMLDivElement>(null);
  const visible = models.filter(model => model.title.toLowerCase().includes(props.query.trim().toLowerCase()));
  return <div ref={root} style={{ position: "relative" }}>
    {error && <View style={{ gap: 8, padding: 16 }}><Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text><Pressable accessibilityRole="button" onPress={() => void refresh()}><Text style={{ color: colors.text }}>Retry models</Text></Pressable></View>}
    {loading && !models.length && <View style={{ padding: 24, gap: 12 }}><ActivityIndicator color={colors.primary} /><Text style={{ color: colors.textMuted }}>Preparing your model gallery…</Text></View>}
    {!loading && !error && !visible.length && <Text style={{ color: colors.textMuted, padding: 24 }}>No saved 3D models{props.query ? " match this search" : " yet"}.</Text>}
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 280px), 1fr))", gap: 16 }}>
      {models.map((model,index) => <div key={model.modelKey} style={{ display: visible.includes(model) ? "block" : "none" }}><ModelCard model={model} index={index} props={props} /></div>)}
    </div>
    {typeof document !== "undefined" && createPortal(<div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 3, display: props.active ? "block" : "none" }}>
      <Canvas eventSource={root as React.RefObject<HTMLElement>} frameloop={props.active ? "demand" : "never"} dpr={[1, 1.5]} onCreated={({ gl }) => configureModelRenderer(gl)} style={{ pointerEvents: "none" }}>
        <ViewportUpdates active={props.active} /><ModelView.Port />
      </Canvas>
    </div>, document.body)}
  </div>;
}
