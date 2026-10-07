import React, { useRef, useState } from "react";
import { GestureResponderEvent, Pressable, Text, View } from "react-native";
import Svg, { Circle, Polyline, Rect } from "react-native-svg";
import { SketchStroke } from "../historyStorage";

interface Props {
  strokes: SketchStroke[];
  onChange: (strokes: SketchStroke[]) => void;
  disabled?: boolean;
  previewOnly?: boolean;
}

/** Normalized vector strokes preserve the drawing across screen sizes and history. */
export default function SketchCanvas({ strokes, onChange, disabled = false, previewOnly = false }: Props) {
  const [tool, setTool] = useState<"pen" | "eraser">("pen");
  const [redo, setRedo] = useState<SketchStroke[]>([]);
  const [draft, setDraft] = useState<SketchStroke | null>(null);
  const active = useRef<SketchStroke | null>(null);
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
  const button = (label: string, action: () => void, unavailable = false) => (
    <Pressable key={label} disabled={disabled || unavailable} accessibilityRole="button"
      onPress={action} style={{ padding: 10, borderRadius: 8, backgroundColor: "#e2e8f0", opacity: disabled || unavailable ? 0.4 : 1 }}>
      <Text style={{ color: "#0f172a", fontWeight: "600" }}>{label}</Text>
    </Pressable>
  );
  return <View style={{ gap: 10 }}>
    {!previewOnly && <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      {button(tool === "pen" ? "Pen selected" : "Pen", () => setTool("pen"))}
      {button(tool === "eraser" ? "Eraser selected" : "Eraser", () => setTool("eraser"))}
      {button("Undo", () => { setRedo([...redo, strokes[strokes.length - 1]]); onChange(strokes.slice(0, -1)); }, !strokes.length)}
      {button("Redo", () => { onChange([...strokes, redo[redo.length - 1]]); setRedo(redo.slice(0, -1)); }, !redo.length)}
      {button("Clear", () => { onChange([]); setRedo([]); }, !strokes.length)}
    </View>}
    <View accessibilityLabel="Drawing canvas" style={{ width: "100%", aspectRatio: 1, backgroundColor: "white", borderWidth: 1, borderColor: "#94a3b8", overflow: "hidden", touchAction: "none" } as any}
      onLayout={(event) => { size.current = event.nativeEvent.layout.width; }}
      onStartShouldSetResponder={() => !disabled}
      onMoveShouldSetResponder={() => !disabled}
      onResponderTerminationRequest={() => false}
      onResponderGrant={(event) => {
        if (strokes.length >= 500) return;
        active.current = { points: [point(event)], width: tool === "pen" ? 0.006 : 0.04, tool };
        setDraft(active.current);
      }}
      onResponderMove={(event) => {
        if (!active.current || active.current.points.length >= 5000) return;
        const next = point(event);
        const previous = active.current.points[active.current.points.length - 1];
        if (Math.hypot(next[0] - previous[0], next[1] - previous[1]) < 0.002) return;
        active.current = { ...active.current, points: [...active.current.points, next] };
        setDraft(active.current);
      }}
      onResponderRelease={finish} onResponderTerminate={finish}>
      <Svg pointerEvents="none" width="100%" height="100%" viewBox="0 0 1024 1024">
        <Rect width={1024} height={1024} fill="white" />
        {[...strokes, ...(draft ? [draft] : [])].map((stroke, index) => stroke.points.length === 1
          ? <Circle key={index} cx={stroke.points[0][0] * 1024} cy={stroke.points[0][1] * 1024} r={stroke.width * 512} fill={stroke.tool === "pen" ? "black" : "white"} />
          : <Polyline key={index} points={stroke.points.map(([x, y]) => `${x * 1024},${y * 1024}`).join(" ")} fill="none" stroke={stroke.tool === "pen" ? "black" : "white"} strokeWidth={stroke.width * 1024} strokeLinecap="round" strokeLinejoin="round" />)}
      </Svg>
    </View>
  </View>;
}
