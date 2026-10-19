import React, { useRef, useState } from "react";
import { GestureResponderEvent, Platform, View } from "react-native";
import Svg, { Circle, Polyline, Rect } from "react-native-svg";
import type { IconName } from "./Icon";
import IconButton from "./IconButton";
import { useAppTheme } from "../theme";
import { SketchStroke } from "../historyStorage";

const PEN_WIDTH = 0.006;
const ERASER_WIDTH = 0.04;

interface Props {
  strokes: SketchStroke[];
  onChange: (strokes: SketchStroke[]) => void;
  disabled?: boolean;
  previewOnly?: boolean;
}

/** Normalized vector strokes preserve the drawing across screen sizes and history. */
export default function SketchCanvas({ strokes, onChange, disabled = false, previewOnly = false }: Props) {
  const { colors } = useAppTheme();
  const editable = !disabled && !previewOnly;
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  const [tool, setTool] = useState<"pen" | "eraser">("pen");
  const [redo, setRedo] = useState<SketchStroke[]>([]);
  const [draft, setDraft] = useState<SketchStroke | null>(null);
  const active = useRef<SketchStroke | null>(null);
  const activePointer = useRef<number | null>(null);
  const size = useRef(1);
  const point = (event: GestureResponderEvent): [number, number] => [
    Math.max(0, Math.min(1, event.nativeEvent.locationX / size.current)),
    Math.max(0, Math.min(1, event.nativeEvent.locationY / size.current)),
  ];
  const finish = () => {
    if (active.current) {
      onChange([...strokes, active.current]);
      setRedo([]);
    }
    active.current = null;
    setDraft(null);
  };
  const begin = (next: [number, number]) => {
    if (!editable || strokes.length >= 500 || active.current) return false;
    active.current = { points: [next], width: tool === "pen" ? PEN_WIDTH : ERASER_WIDTH, tool };
    setCursor(next);
    setDraft(active.current);
    return true;
  };
  const extend = (next: [number, number]) => {
    if (!active.current || active.current.points.length >= 5000) return;
    const previous = active.current.points[active.current.points.length - 1];
    // Keep short strokes too; ignore only effectively identical samples.
    if (Math.hypot(next[0] - previous[0], next[1] - previous[1]) < 0.0001) return;
    active.current = { ...active.current, points: [...active.current.points, next] };
    setDraft(active.current);
  };
  const button = (label: string, icon: IconName, action: () => void, unavailable = false, selected?: boolean) => (
    <IconButton key={label} label={label} icon={icon} onPress={action} disabled={disabled || unavailable} selected={selected} />
  );
  const pointerPoint = (event: React.PointerEvent<HTMLElement>): [number, number] => {
    const bounds = event.currentTarget.getBoundingClientRect();
    return [Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)), Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height))];
  };
  // RN's native pointer typings differ from the DOM events emitted by RN Web.
  const inputProps: Record<string, unknown> = Platform.OS === "web" ? {
    onPointerDown: (event: React.PointerEvent<HTMLElement>) => {
      if (event.button !== 0 || !begin(pointerPoint(event))) return;
      event.preventDefault();
      activePointer.current = event.pointerId;
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    onPointerMove: (event: React.PointerEvent<HTMLElement>) => {
      if (!editable || (activePointer.current !== null && activePointer.current !== event.pointerId)) return;
      const next = pointerPoint(event);
      if (event.pointerType !== "touch" || activePointer.current !== null) setCursor(next);
      if (activePointer.current === event.pointerId) extend(next);
    },
    onPointerUp: (event: React.PointerEvent<HTMLElement>) => {
      if (activePointer.current !== event.pointerId) return;
      // Quick touch strokes can end before the browser delivers a move event.
      extend(pointerPoint(event));
      activePointer.current = null;
      finish();
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      if (event.pointerType === "touch") setCursor(null);
    },
    onPointerCancel: (event: React.PointerEvent<HTMLElement>) => {
      if (activePointer.current !== event.pointerId) return;
      activePointer.current = null;
      finish();
      setCursor(null);
    },
    onPointerLeave: () => setCursor(null),
  } : {
    onStartShouldSetResponder: () => editable,
    onMoveShouldSetResponder: () => editable,
    onResponderTerminationRequest: () => false,
    onResponderGrant: (event: GestureResponderEvent) => { begin(point(event)); },
    onResponderMove: (event: GestureResponderEvent) => { const next = point(event); setCursor(next); extend(next); },
    onResponderRelease: (event: GestureResponderEvent) => { extend(point(event)); finish(); setCursor(null); },
    onResponderTerminate: () => { finish(); setCursor(null); },
  };
  return <View style={{ gap: 12, width: "100%", maxWidth: 720, alignSelf: "center" }}>
    {!previewOnly && <View accessibilityLabel="Drawing tools" style={{ flexDirection: "row", flexWrap: "wrap", gap: 4 }}>
      {button("Pen", "pencil", () => setTool("pen"), false, tool === "pen")}
      {button("Eraser", "eraser", () => setTool("eraser"), false, tool === "eraser")}
      {button("Undo", "undo", () => { setRedo([...redo, strokes[strokes.length - 1]]); onChange(strokes.slice(0, -1)); }, !strokes.length)}
      {button("Redo", "redo", () => { onChange([...strokes, redo[redo.length - 1]]); setRedo(redo.slice(0, -1)); }, !redo.length)}
      {button("Clear", "trash", () => { onChange([]); setRedo([]); }, !strokes.length)}
    </View>}
    <View {...inputProps} accessibilityLabel="Drawing canvas" style={{ width: "100%", aspectRatio: 1, backgroundColor: "white", borderWidth: 1, borderColor: colors.border, overflow: "hidden", borderRadius: 8, touchAction: "none", ...(Platform.OS === "web" && editable ? { cursor: tool === "eraser" ? "none" : "crosshair" } : {}) } as any}
      onLayout={(event) => { size.current = event.nativeEvent.layout.width; }}>
      <Svg pointerEvents="none" width="100%" height="100%" viewBox="0 0 1024 1024">
        <Rect width={1024} height={1024} fill="white" />
        {[...strokes, ...(draft ? [draft] : [])].map((stroke, index) => stroke.points.length === 1
          ? <Circle key={index} cx={stroke.points[0][0] * 1024} cy={stroke.points[0][1] * 1024} r={stroke.width * 512} fill={stroke.tool === "pen" ? "black" : "white"} />
          : <Polyline key={index} points={stroke.points.map(([x, y]) => `${x * 1024},${y * 1024}`).join(" ")} fill="none" stroke={stroke.tool === "pen" ? "black" : "white"} strokeWidth={stroke.width * 1024} strokeLinecap="round" strokeLinejoin="round" />)}
        {editable && tool === "eraser" && cursor && <>
          <Circle cx={cursor[0] * 1024} cy={cursor[1] * 1024} r={ERASER_WIDTH * 512} fill="none" stroke="white" strokeWidth={6} />
          <Circle cx={cursor[0] * 1024} cy={cursor[1] * 1024} r={ERASER_WIDTH * 512} fill="none" stroke={colors.textMuted} strokeWidth={3} />
        </>}
      </Svg>
    </View>
  </View>;
}
