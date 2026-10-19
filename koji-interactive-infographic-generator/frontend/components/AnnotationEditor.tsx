import React, { useEffect, useMemo, useRef, useState } from "react";
import { Image, PanResponder, Pressable, StyleSheet, TextInput, View } from "react-native";
import type { AnatomyAnnotation } from "../App";
import AnatomyOverlay from "./AnatomyOverlay";
import Icon from "./Icon";
import { annotationGeometry, annotationHit, clamp, labelWidth } from "./annotationGeometry";
import { useAppTheme } from "../theme";

interface Props {
  imageBase64: string;
  aspectRatio?: number;
  annotations: AnatomyAnnotation[];
  onChange: (items: AnatomyAnnotation[]) => void;
  commitRef?: React.MutableRefObject<(() => void) | null>;
}
export default function AnnotationEditor({ imageBase64, aspectRatio = 1, annotations, onChange, commitRef }: Props) {
  const { colors } = useAppTheme();
  const [selected, setSelected] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [size, setSize] = useState({ width: 1, height: 1 });
  const [draft, setDraft] = useState(annotations);
  const latest = useRef(draft);
  const change = useRef(onChange); change.current = onChange;
  const gesture = useRef<{ item: AnatomyAnnotation; part: "target" | "label"; moved: boolean } | null>(null);
  const tap = useRef<{ x: number; y: number; at: number } | null>(null);
  useEffect(() => { latest.current = annotations; setDraft(annotations); }, [annotations]);
  const update = (items: AnatomyAnnotation[], persist = false) => {
    latest.current = items; setDraft(items);
    if (persist) change.current(items);
  };
  const finishName = () => {
    update(latest.current.map(item => ({ ...item, label: item.label.trim() || "New label" })), true);
    setRenaming(null);
  };
  if (commitRef) commitRef.current = finishName;
  const responder = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: event => {
      setRenaming(null);
      const x = clamp(event.nativeEvent.locationX / size.width), y = clamp(event.nativeEvent.locationY / size.height);
      const hit = annotationHit(latest.current, x, y, size.width, size.height);
      const item = latest.current.find(value => value.structure_id === hit?.id);
      const geometry = item && annotationGeometry(item);
      gesture.current = item && hit && geometry ? { item: { ...item, label_x: geometry.x / 1000, label_y: geometry.y / 1000 }, part: hit.part, moved: false } : null;
      setSelected(item?.structure_id ?? null);
    },
    onPanResponderMove: (_event, state) => {
      const current = gesture.current;
      if (!current || (!current.moved && Math.hypot(state.dx, state.dy) < 4)) return;
      current.moved = true;
      const { item, part } = current;
      const patch = part === "target"
        ? { anchor_x: clamp(item.anchor_x + state.dx / size.width), anchor_y: clamp(item.anchor_y + state.dy / size.height) }
        : { label_x: clamp(item.label_x + state.dx / size.width, 0, 1 - labelWidth(item.label) / 1000), label_y: clamp(item.label_y + state.dy / size.height, .018, .982) };
      update(latest.current.map(value => value.structure_id === item.structure_id ? { ...value, ...patch, user_edited: true } : value));
    },
    onPanResponderRelease: (event, state) => {
      const current = gesture.current; gesture.current = null;
      if (current) {
        tap.current = null;
        if (current.moved) change.current(latest.current);
        else if (current.part === "label") setRenaming(current.item.structure_id);
        return;
      }
      if (Math.hypot(state.dx, state.dy) >= 4) { tap.current = null; return; }
      const x = clamp(event.nativeEvent.locationX / size.width), y = clamp(event.nativeEvent.locationY / size.height);
      const now = Date.now();
      if (tap.current && now - tap.current.at < 350 && Math.hypot((x - tap.current.x) * size.width, (y - tap.current.y) * size.height) < 20) {
        const id = "manual." + now.toString(36) + Math.random().toString(36).slice(2, 6);
        update([...latest.current, { structure_id: id, label: "New label", anchor_x: x, anchor_y: y,
          label_x: clamp(x - .15, 0, .862), label_y: clamp(y - .08, .018, .982), confidence: 0,
          verified: false, user_edited: true, source: "manual" }], true);
        setSelected(id); setRenaming(id); tap.current = null;
      } else tap.current = { x, y, at: now };
    },
    onPanResponderTerminate: () => {
      if (gesture.current?.moved) change.current(latest.current);
      gesture.current = null;
    },
  }), [size]);
  const item = draft.find(value => value.structure_id === renaming);
  const geometry = item && annotationGeometry(item);
  return <View onLayout={event => setSize(event.nativeEvent.layout)} style={{ width: "100%", aspectRatio, backgroundColor: "white", position: "relative" }}>
    <Image source={{ uri: "data:image/png;base64," + imageBase64 }} style={StyleSheet.absoluteFill} resizeMode="contain" />
    <AnatomyOverlay annotations={draft} selectedStructureId={selected} />
    <View {...{ dataSet: { dragSurface: "true" } }} accessibilityLabel="Label editing canvas" accessibilityHint="Click a label to rename it. Drag a label or arrow to move it. Double tap empty space to add a label." {...responder.panHandlers} style={StyleSheet.absoluteFill} />
    {item && geometry && <TextInput key={item.structure_id} autoFocus selectTextOnFocus accessibilityLabel="Label name" value={item.label} maxLength={80}
      onChangeText={label => update(latest.current.map(value => value.structure_id === item.structure_id ? { ...value, label, user_edited: true } : value))}
      onBlur={finishName} onSubmitEditing={finishName} returnKeyType="done"
      style={{ position: "absolute", left: `${geometry.x / 10}%`, top: `${(geometry.y - 18) / 10}%`, width: `${geometry.width / 10}%`,
        minHeight: 28, height: size.height * .036, paddingHorizontal: 6, paddingVertical: 0, fontSize: Math.max(12, size.width * .017),
        color: colors.text, backgroundColor: colors.surface, borderColor: colors.primary, borderWidth: 2, borderRadius: 6 }} />}
    {selected && <Pressable accessibilityRole="button" accessibilityLabel="Remove selected label" onPress={() => {
      update(latest.current.filter(value => value.structure_id !== selected), true); setSelected(null); setRenaming(null);
    }} style={({ pressed }) => ({ position: "absolute", top: 8, right: 8, padding: 10, borderRadius: 8, backgroundColor: colors.surface, opacity: pressed ? .65 : 1 })}>
      <Icon name="close" color={colors.danger} size={20} />
    </Pressable>}
  </View>;
}
