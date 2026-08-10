import React, { useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  GestureResponderEvent,
  Image,
  PanResponder,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { ColorPalette, makeSharedStyles, useAppTheme } from "../theme";

const INTERACTIVE_AGENT_URL =
  process.env.EXPO_PUBLIC_INTERACTIVE_AGENT_URL ??
  "https://kojithan-y--interactive-agent-api-dev.modal.run";

type SelectionType = "point" | "box";
type AnalysisMode = "identify" | "explain" | "ask";
type SpeedMode = "normal" | "pro" | "promax";

interface InteractionCoords {
  type: SelectionType;
  coords: number[];
}

interface Point { x: number; y: number }

interface InteractiveCanvasProps {
  imageBase64: string;
  speedMode?: SpeedMode;
}

function apiError(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const value = payload as { detail?: unknown; error?: unknown };
  if (typeof value.error === "string") return value.error;
  if (typeof value.detail === "string") return value.detail;
  if (value.detail && typeof value.detail === "object" && "error" in value.detail) {
    const nested = (value.detail as { error?: unknown }).error;
    if (typeof nested === "string") return nested;
  }
  return fallback;
}

export default function InteractiveCanvas({ imageBase64, speedMode = "pro" }: InteractiveCanvasProps) {
  const { colors } = useAppTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const shared = useMemo(() => makeSharedStyles(colors), [colors]);
  const [selectionType, setSelectionType] = useState<SelectionType>("point");
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("identify");
  const [customQuestion, setCustomQuestion] = useState("");
  const [currentSelection, setCurrentSelection] = useState<InteractionCoords | null>(null);
  const [boxStart, setBoxStart] = useState<Point | null>(null);
  const [boxCurrent, setBoxCurrent] = useState<Point | null>(null);
  const [isDrawingBox, setIsDrawingBox] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [highlightedImage, setHighlightedImage] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 1, height: 1 });
  const [aspectRatio, setAspectRatio] = useState(1);
  const dragStartRef = useRef<Point | null>(null);

  const normalizeEvent = (event: GestureResponderEvent): Point => ({
    x: Math.max(0, Math.min(1, event.nativeEvent.locationX / canvasSize.width)),
    y: Math.max(0, Math.min(1, event.nativeEvent.locationY / canvasSize.height)),
  });

  const panResponder = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => !isLoading,
    onMoveShouldSetPanResponder: () => !isLoading && selectionType === "box",
    onPanResponderGrant: (event) => {
      const point = normalizeEvent(event);
      if (selectionType === "point") {
        setCurrentSelection({ type: "point", coords: [point.x, point.y] });
        return;
      }
      dragStartRef.current = point;
      setBoxStart(point);
      setBoxCurrent(point);
      setIsDrawingBox(true);
    },
    onPanResponderMove: (event) => {
      if (selectionType === "box" && dragStartRef.current) setBoxCurrent(normalizeEvent(event));
    },
    onPanResponderRelease: (event) => finishBox(normalizeEvent(event)),
    onPanResponderTerminate: (event) => finishBox(normalizeEvent(event)),
  }), [canvasSize, isLoading, selectionType]);

  function finishBox(end: Point) {
    const start = dragStartRef.current;
    if (!start || selectionType !== "box") return;
    setIsDrawingBox(false);
    dragStartRef.current = null;
    let x1 = Math.min(start.x, end.x);
    let y1 = Math.min(start.y, end.y);
    let x2 = Math.max(start.x, end.x);
    let y2 = Math.max(start.y, end.y);
    if (x2 - x1 < 0.02 || y2 - y1 < 0.02) {
      const margin = 0.08;
      x1 = Math.max(0, start.x - margin);
      y1 = Math.max(0, start.y - margin);
      x2 = Math.min(1, start.x + margin);
      y2 = Math.min(1, start.y + margin);
    }
    setBoxCurrent(end);
    setCurrentSelection({ type: "box", coords: [x1, y1, x2, y2] });
  }

  const handleTypeChange = (type: SelectionType) => {
    setSelectionType(type);
    setCurrentSelection(null);
    setBoxStart(null);
    setBoxCurrent(null);
    setHighlightedImage(null);
    setAnalysisResult(null);
    setError(null);
  };

  const runAnalysis = async () => {
    if (!currentSelection || isLoading) return;
    setIsLoading(true);
    setError(null);
    setAnalysisResult(null);
    try {
      const response = await fetch(`${INTERACTIVE_AGENT_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_base64: imageBase64,
          interaction: currentSelection,
          mode: analysisMode,
          question: analysisMode === "ask" ? customQuestion.trim() : undefined,
          speed_mode: speedMode,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(data, `HTTP ${response.status}`));
      if (data.error) throw new Error(String(data.error));
      if (data.highlighted_base64) setHighlightedImage(`data:image/png;base64,${data.highlighted_base64}`);
      setAnalysisResult(data.response_text || "No analysis provided.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Analysis failed");
    } finally {
      setIsLoading(false);
    }
  };

  const imageUri = highlightedImage ?? `data:image/png;base64,${imageBase64}`;
  const previewBox = isDrawingBox && boxStart && boxCurrent
    ? [Math.min(boxStart.x, boxCurrent.x), Math.min(boxStart.y, boxCurrent.y), Math.max(boxStart.x, boxCurrent.x), Math.max(boxStart.y, boxCurrent.y)]
    : null;

  return (
    <View style={styles.container}>
      <View style={styles.toolbar}>
        <View style={styles.toolbarModes}>
          <Text style={styles.toolbarLabel}>Interaction Mode:</Text>
          <ModeButton active={selectionType === "point"} label="🎯 Tap Object" onPress={() => handleTypeChange("point")} />
          <ModeButton active={selectionType === "box"} label="🔲 Circle / Box Region" onPress={() => handleTypeChange("box")} />
        </View>
        <Text style={styles.toolbarHint}>{selectionType === "point" ? "Tap any object in the diagram to segment & analyze" : "Touch and drag a box around a region"}</Text>
      </View>

      <View
        {...panResponder.panHandlers}
        onLayout={(event) => setCanvasSize(event.nativeEvent.layout)}
        style={[styles.canvas, { aspectRatio }]}
      >
        <Image
          accessibilityLabel="Interactive educational image"
          onLoad={(event) => {
            const source = event.nativeEvent.source;
            if (source?.width && source?.height) setAspectRatio(source.width / source.height);
          }}
          resizeMode="contain"
          source={{ uri: imageUri }}
          style={StyleSheet.absoluteFill}
        />
        {selectionType === "point" && currentSelection?.type === "point" && (
          <View pointerEvents="none" style={[styles.pointMarker, { left: `${currentSelection.coords[0] * 100}%`, top: `${currentSelection.coords[1] * 100}%` }]} />
        )}
        {previewBox && <SelectionBox coords={previewBox} drawing />}
        {selectionType === "box" && currentSelection?.type === "box" && !isDrawingBox && <SelectionBox coords={currentSelection.coords} />}
      </View>

      {currentSelection && (
        <View style={[shared.card, styles.actionPanel]}>
          <View style={styles.modeSelector}>
            <ModeButton active={analysisMode === "identify"} label="🏷️ Identify Object" onPress={() => setAnalysisMode("identify")} />
            <ModeButton active={analysisMode === "explain"} label="📖 Explain Region" onPress={() => setAnalysisMode("explain")} />
            <ModeButton active={analysisMode === "ask"} label="❓ Ask Question" onPress={() => setAnalysisMode("ask")} />
          </View>
          {analysisMode === "ask" && (
            <TextInput
              onChangeText={setCustomQuestion}
              onSubmitEditing={runAnalysis}
              placeholder="e.g. What is the role of this organelle?"
              placeholderTextColor={colors.textDim}
              returnKeyType="send"
              style={styles.questionInput}
              value={customQuestion}
            />
          )}
          <Pressable
            disabled={isLoading || (analysisMode === "ask" && !customQuestion.trim())}
            onPress={runAnalysis}
            style={({ pressed }) => [shared.button, shared.primaryButton, pressed && styles.pressed, (isLoading || (analysisMode === "ask" && !customQuestion.trim())) && shared.disabled]}
          >
            {isLoading && <ActivityIndicator color="#fff" size="small" style={styles.spinner} />}
            <Text style={shared.buttonText}>{isLoading ? "SAM 2 & Qwen2.5-VL analyzing…" : "✦ Analyze Selected Region"}</Text>
          </Pressable>
        </View>
      )}

      {error && <View style={shared.error}><Text style={styles.errorTitle}>Interactive analysis failed</Text><Text style={styles.errorText}>{error}</Text></View>}

      {analysisResult && (
        <View style={[shared.card, styles.resultPanel]}>
          <View style={styles.resultHeader}>
            <Text style={styles.badge}>✦ Qwen2.5-VL Visual Explanation</Text>
            <Text style={styles.modelTag}>SAM 2 + Qwen2.5-VL-7B · {speedMode === "normal" ? "A10G" : speedMode === "promax" ? "H100" : "A100"}</Text>
          </View>
          <Text style={styles.resultText}>{analysisResult}</Text>
        </View>
      )}
    </View>
  );
}

function SelectionBox({ coords, drawing = false }: { coords: number[]; drawing?: boolean }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  return <View pointerEvents="none" style={[styles.boxMarker, drawing && styles.boxDrawing, { left: `${coords[0] * 100}%`, top: `${coords[1] * 100}%`, width: `${(coords[2] - coords[0]) * 100}%`, height: `${(coords[3] - coords[1]) * 100}%` }]} />;
}

function ModeButton({ active, label, onPress }: { active: boolean; label: string; onPress: () => void }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  return (
    <Pressable accessibilityState={{ selected: active }} onPress={onPress} style={({ pressed }) => [styles.modeButton, active && styles.modeButtonActive, pressed && styles.pressed]}>
      <Text style={[styles.modeButtonText, active && styles.modeButtonTextActive]}>{label}</Text>
    </Pressable>
  );
}

const makeStyles = (colors: ColorPalette) => StyleSheet.create({
  container: { gap: 16 },
  toolbar: { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: 16, padding: 13, gap: 10 },
  toolbarModes: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 },
  toolbarLabel: { color: colors.textMuted, fontSize: 11, fontWeight: "700", marginRight: 2 },
  toolbarHint: { color: colors.textDim, fontSize: 11 },
  modeButton: { borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSoft, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 9 },
  modeButtonActive: { borderColor: colors.primaryBright, backgroundColor: "rgba(139,92,246,0.22)" },
  modeButtonText: { color: colors.textMuted, fontSize: 12, fontWeight: "700" },
  modeButtonTextActive: { color: colors.text },
  canvas: { width: "100%", maxHeight: 720, backgroundColor: colors.canvas, borderRadius: 18, overflow: "hidden", borderWidth: 1, borderColor: colors.border },
  pointMarker: { position: "absolute", width: 24, height: 24, borderRadius: 12, marginLeft: -12, marginTop: -12, backgroundColor: "rgba(139,92,246,0.42)", borderWidth: 3, borderColor: "#fff" },
  boxMarker: { position: "absolute", borderWidth: 3, borderColor: colors.primaryBright, backgroundColor: "rgba(139,92,246,0.15)" },
  boxDrawing: { borderColor: colors.cyan, borderStyle: "dashed", backgroundColor: "rgba(34,211,238,0.12)" },
  actionPanel: { gap: 14 },
  modeSelector: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  questionInput: { minHeight: 46, borderWidth: 1, borderColor: colors.border, borderRadius: 12, backgroundColor: colors.surfaceSoft, color: colors.text, paddingHorizontal: 13, fontSize: 14 },
  pressed: { opacity: 0.76 },
  spinner: { marginRight: 8 },
  errorTitle: { color: colors.danger, fontWeight: "800", marginBottom: 4 },
  errorText: { color: colors.textMuted, lineHeight: 20 },
  resultPanel: { gap: 14 },
  resultHeader: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 8 },
  badge: { color: colors.primaryBright, fontSize: 12, fontWeight: "800" },
  modelTag: { color: colors.textDim, fontSize: 10 },
  resultText: { color: colors.textMuted, lineHeight: 23, fontSize: 14 },
});
