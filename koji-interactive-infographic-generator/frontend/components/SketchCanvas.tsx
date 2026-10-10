import React, { useRef, useState } from "react";
import { GestureResponderEvent, Platform, Pressable, Text, View } from "react-native";
import Svg, { Circle, Polyline, Rect } from "react-native-svg";
import Icon, { IconName } from "./Icon";
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
  const button = (label: string, action: () => void, unavailable = false, selected = false, icon?: IconName) => (
    <Pressable key={label} disabled={disabled || unavailable} accessibilityRole="button" accessibilityLabel={label}
      accessibilityState={{ disabled: disabled || unavailable, ...(label === "Pen" || label === "Eraser" ? { selected } : {}) }}
      onPress={action} style={({ pressed }) => ({ paddingHorizontal: 14, minHeight: 42, flexDirection: "row", alignItems: "center", gap: 7, borderRadius: 10, borderWidth: 1,
        borderColor: selected ? colors.primaryBright : colors.border, backgroundColor: selected ? colors.primary : colors.surfaceSoft,
        opacity: disabled || unavailable ? .4 : pressed ? .75 : 1 })}>
      {icon && <Icon name={icon} color={selected ? "#fff" : colors.textMuted} size={18} />}
      <Text style={{ color: selected ? "#fff" : colors.textMuted, fontWeight: "600" }}>{label}</Text>
    </Pressable>
  );
  const webPointerProps = Platform.OS === "web" && editable ? {
    onPointerMove: (event: any) => {
      const bounds = event.currentTarget.getBoundingClientRect();
      setCursor([Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)), Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height))]);
    },
    onPointerLeave: () => setCursor(null),
  } : {};
  return <View style={{ gap: 10 }}>
    {!previewOnly && <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      {button("Pen", () => setTool("pen"), false, tool === "pen", "pencil")}
      {button("Eraser", () => setTool("eraser"), false, tool === "eraser", "eraser")}
      {button("Undo", () => { setRedo([...redo, strokes[strokes.length - 1]]); onChange(strokes.slice(0, -1)); }, !strokes.length)}
      {button("Redo", () => { onChange([...strokes, redo[redo.length - 1]]); setRedo(redo.slice(0, -1)); }, !redo.length)}
      {button("Clear", () => { onChange([]); setRedo([]); }, !strokes.length)}
    </View>}
    <View {...webPointerProps} accessibilityLabel="Drawing canvas" style={{ width: "100%", aspectRatio: 1, backgroundColor: "white", borderWidth: 1, borderColor: "#94a3b8", overflow: "hidden", borderRadius: 14, touchAction: "none", ...(Platform.OS === "web" && editable ? { cursor: tool === "eraser" ? "none" : "crosshair" } : {}) } as any}
      onLayout={(event) => { size.current = event.nativeEvent.layout.width; }}
      onStartShouldSetResponder={() => editable}
      onMoveShouldSetResponder={() => editable}
      onResponderTerminationRequest={() => false}
      onResponderGrant={(event) => {
        if (!editable || strokes.length >= 500) return;
        active.current = { points: [point(event)], width: tool === "pen" ? PEN_WIDTH : ERASER_WIDTH, tool };
        setCursor(point(event));
        setDraft(active.current);
      }}
      onResponderMove={(event) => {
        if (!active.current || active.current.points.length >= 5000) return;
        const next = point(event);
        setCursor(next);
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
        {editable && tool === "eraser" && cursor && <>
          <Circle cx={cursor[0] * 1024} cy={cursor[1] * 1024} r={ERASER_WIDTH * 512} fill="none" stroke="white" strokeWidth={6} />
          <Circle cx={cursor[0] * 1024} cy={cursor[1] * 1024} r={ERASER_WIDTH * 512} fill="none" stroke="#475569" strokeWidth={3} />
        </>}
      </Svg>
    </View>
  </View>;
}
