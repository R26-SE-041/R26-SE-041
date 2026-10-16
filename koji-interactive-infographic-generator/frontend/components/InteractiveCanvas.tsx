import { modelRequest, cloudEnabled, runJob, getCloudHistory } from "../studioClient";
import { formatDuration } from "../processing";
import type { GenerationInteraction } from "../historyStorage";
import AnnotationEditor from "./AnnotationEditor";
import PdfSourcesPanel from "./PdfSourcesPanel";
import PdfEvidence from "./PdfEvidence";
import type { PdfSource } from "../pdfSources";
import React, { useEffect, useMemo, useRef, useState } from "react";
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
import type { AnatomyAnnotation } from "../App";
import AnatomyOverlay from "./AnatomyOverlay";
import Icon, { IconName } from "./Icon";
import FeedbackControls, { createOutputId, FeedbackReason } from "./FeedbackControls";
import ImageDownloadControls from "./ImageDownloadControls";
import { INTERACTIVE_AGENT_URL } from "../config";

type SelectionType = "point" | "box";
type AnalysisMode = "identify" | "explain" | "ask";
type SpeedMode = "normal" | "pro" | "promax";

interface InteractionCoords {
  type: SelectionType;
  coords: number[];
}

interface Point { x: number; y: number }

interface InteractiveCanvasProps {
  imageFeedback?: React.ReactNode;
  chatId?: string;
  generationId?: string;
  interactions?: GenerationInteraction[];
  onAnnotationsChange?: (items: AnatomyAnnotation[]) => void;
  accessToken?: string;
  anatomyAnnotations?: AnatomyAnnotation[];
  anatomyOrgan?: string;
  feedbackApiUrl: string;
  imageBase64: string;
  onOperationStart?: (mode: AnalysisMode) => void;
  onOperationComplete?: (durationMs: number, mode: AnalysisMode, outcome: "completed" | "failed") => void;
  onInteractionComplete?: (interaction: GenerationInteraction) => void;
  speedMode?: SpeedMode;
  sessionId: string;
}

const NEGATIVE_REASONS: FeedbackReason[] = [
  { code: "wrong_region", label: "Wrong region" }, { code: "incorrect_explanation", label: "Incorrect explanation" },
  { code: "too_complex", label: "Too complex" }, { code: "not_useful", label: "Not useful" },
];
const POSITIVE_REASONS: FeedbackReason[] = [
  { code: "grounded", label: "Grounded" }, { code: "clear", label: "Clear" }, { code: "helpful", label: "Helpful" },
];

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

export default function InteractiveCanvas({ imageFeedback, chatId, generationId, interactions = [], onAnnotationsChange, accessToken, anatomyAnnotations = [], anatomyOrgan, feedbackApiUrl, imageBase64, onInteractionComplete, onOperationStart, onOperationComplete, sessionId, speedMode = "pro" }: InteractiveCanvasProps) {
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
  const [analysisDuration, setAnalysisDuration] = useState<number | null>(null);
  const [analysisStartedAt, setAnalysisStartedAt] = useState<number | null>(null);
  const [analysisNow, setAnalysisNow] = useState(Date.now());
  useEffect(() => {
    if (analysisStartedAt === null) return;
    setAnalysisNow(Date.now());
    const timer = setInterval(() => setAnalysisNow(Date.now()), 1_000);
    return () => clearInterval(timer);
  }, [analysisStartedAt]);
  const [error, setError] = useState<string | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 1, height: 1 });
  const [aspectRatio, setAspectRatio] = useState(1);
  const dragStartRef = useRef<Point | null>(null);
  const [outputId, setOutputId] = useState<string | null>(null);
  const [retryLink, setRetryLink] = useState<{ feedbackId: string; outputId: string } | null>(null);
  const [editingLabels, setEditingLabels] = useState(false);
  const commitLabelEdits = useRef<(() => void) | null>(null);
  const [showAnatomyLabels, setShowAnatomyLabels] = useState(true);
  const [selectedStructureId, setSelectedStructureId] = useState<string | null>(null);
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>(() => interactions.at(-1)?.documentIds ?? []);
  const [resultSources, setResultSources] = useState<PdfSource[]>([]);
  const [resultGrounding, setResultGrounding] = useState<GenerationInteraction["grounding"]>();
  const conversation = chatId ?? generationId;
  const lastSelection = useRef(interactions.at(-1)?.documentIds);
  const activeImage = useRef(imageBase64);
  activeImage.current = imageBase64;
  lastSelection.current = interactions.at(-1)?.documentIds;
  useEffect(() => {
    setSelectedDocuments(lastSelection.current ?? []);
  }, [conversation]);
  useEffect(() => {
    setResultSources([]); setResultGrounding(undefined); setAnalysisResult(null);
    setIsLoading(false); setError(null); setCurrentSelection(null); setHighlightedImage(null);
  }, [conversation, imageBase64]);

  const nearestStructure = (point: Point): string | null => {
    let best: AnatomyAnnotation | undefined;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (const item of anatomyAnnotations) {
      const distance = Math.hypot(item.anchor_x - point.x, item.anchor_y - point.y);
      if (distance < bestDistance) {
        best = item;
        bestDistance = distance;
      }
    }
    return best && bestDistance <= 0.10 ? best.structure_id : null;
  };

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
        setSelectedStructureId(nearestStructure(point));
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
  }), [anatomyAnnotations, canvasSize, isLoading, selectionType]);

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
    setAnalysisDuration(null);
    setError(null);
    setOutputId(null);
    setRetryLink(null);
  };

  const runAnalysis = async (regenerationFeedback?: string) => {
    if (!currentSelection || isLoading || (analysisMode === "ask" && !customQuestion.trim())) return;
    const startedAt = Date.now();
    setAnalysisStartedAt(startedAt);
    let outcome: "completed" | "failed" = "failed";
    onOperationStart?.(analysisMode);
    const turnId = createOutputId("question");
    const turnQuestion = analysisMode === "ask" ? customQuestion.trim() : analysisMode === "identify" ? "Identify selected object" : "Explain selected region";
    const selection = { ...currentSelection, coords: [...currentSelection.coords] };
    const documentIds = analysisMode === "ask" ? [...selectedDocuments] : [];
    setIsLoading(true);
    setError(null);
    setAnalysisResult(null);
    setResultSources([]); setResultGrounding(undefined);
    setAnalysisDuration(null);
    try {
      let memoryContext = "";
      try {
        const memoryResponse = await fetch(`${feedbackApiUrl.replace(/\/$/, "")}/memory/context`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          },
          body: JSON.stringify({
            agent_name: "interactive-agent",
            query: customQuestion.trim() || `${analysisMode} selected educational image region`,
            limit: 5,
          }),
        });
        const memoryData = await memoryResponse.json().catch(() => ({}));
        if (memoryResponse.ok && typeof memoryData.context === "string") memoryContext = memoryData.context;
      } catch {
        memoryContext = "";
      }
      let data: { response_text?: string; highlighted_base64?: string; error?: string; sources?: PdfSource[]; grounding?: GenerationInteraction["grounding"] };
      if (cloudEnabled() && generationId && /^[0-9a-f-]{36}$/i.test(generationId)) {
        await runJob({kind:"analysis",generation_id:generationId,speed_mode:speedMode,analysis:{
          id:turnId,mode:analysisMode,question:turnQuestion,interaction:selection,
          organ:anatomyOrgan,structure_id:selectedStructureId ?? undefined,
          regeneration_feedback:regenerationFeedback,memory_context:memoryContext,document_ids:documentIds
        }});
        const saved = await getCloudHistory(generationId);
        const turn = saved.interactions?.find(item => item.id === turnId);
        if (!turn?.answer) throw new Error("Saved answer is not available. Reopen this conversation from History.");
        data = { response_text: turn.answer, sources: turn.sources, grounding: turn.grounding };
      } else {
      if (documentIds.length) throw new Error("Save this image to your cloud workspace to ask questions using PDFs.");
      const response = await modelRequest("interactive", INTERACTIVE_AGENT_URL, "/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_base64: imageBase64,
          interaction: currentSelection,
          mode: analysisMode,
          question: analysisMode === "ask" ? customQuestion.trim() : undefined,
          speed_mode: speedMode,
          enable_rag: false,
          regeneration_feedback: regenerationFeedback,
          memory_context: memoryContext,
          organ: anatomyOrgan,
          structure_id: selectedStructureId,
        }),
      });
      data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(data, `HTTP ${response.status}`));
      if (data.error) throw new Error(String(data.error));
      }
      if (activeImage.current !== imageBase64) return;
      if (data.highlighted_base64) setHighlightedImage(`data:image/png;base64,${data.highlighted_base64}`);
      const answer = data.response_text || "No analysis provided.";
      setAnalysisResult(answer);
      setResultSources(data.sources ?? []); setResultGrounding(data.grounding ?? "image");
      onInteractionComplete?.({
        id: turnId,
        createdAt: new Date().toISOString(),
        mode: analysisMode,
        question: turnQuestion,
        answer, selection, structureId: selectedStructureId, status: "completed",
        documentIds, sources:data.sources ?? [], grounding:data.grounding ?? "image",
      });
      setOutputId(createOutputId("interactive"));
      const duration = Date.now() - startedAt;
      setAnalysisDuration(duration);
      outcome = "completed";
    } catch (caught) {
      if (activeImage.current !== imageBase64) return;
      setError(caught instanceof Error ? caught.message : "Analysis failed");
      setAnalysisDuration(Date.now() - startedAt);
    } finally {
      setAnalysisStartedAt(null);
      onOperationComplete?.(Date.now() - startedAt, analysisMode, outcome);
      if (activeImage.current === imageBase64) setIsLoading(false);
    }
  };

  const regenerateFromFeedback = async (feedback: string, feedbackId: string, previousOutputId: string) => {
    setRetryLink({ feedbackId, outputId: previousOutputId });
    await runAnalysis(feedback);
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
          <ModeButton active={selectionType === "point"} icon="target" label="Tap Object" onPress={() => handleTypeChange("point")} />
          <ModeButton active={selectionType === "box"} icon="box-select" label="Select Region" onPress={() => handleTypeChange("box")} />
        </View>
        <Text style={styles.toolbarHint}>{selectionType === "point" ? "Tap any object in the diagram to segment & analyze" : "Touch and drag a box around a region"}</Text>
        {anatomyAnnotations.length > 0 && (
          <Pressable accessibilityRole="button" accessibilityState={{ selected: showAnatomyLabels }} onPress={() => setShowAnatomyLabels((value) => !value)} style={styles.labelToggle}>
            <Text style={styles.labelToggleText}>{showAnatomyLabels ? "Hide labels" : "Show labels"}</Text>
          </Pressable>
        )}
      </View>

      {onAnnotationsChange && <Pressable accessibilityRole="button" accessibilityState={{ selected: editingLabels }} onPress={() => { if (editingLabels) commitLabelEdits.current?.(); setEditingLabels(value => !value); }} style={styles.labelToggle}><Text style={styles.labelToggleText}>{editingLabels ? "Save changes" : "Edit labels"}</Text></Pressable>}
      {editingLabels && onAnnotationsChange && <AnnotationEditor aspectRatio={aspectRatio} imageBase64={imageBase64} annotations={anatomyAnnotations} onChange={onAnnotationsChange} commitRef={commitLabelEdits} />}

      <ImageDownloadControls annotations={anatomyAnnotations} imageBase64={imageBase64} organ={anatomyOrgan} />

      {!editingLabels && <View
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
        {showAnatomyLabels && anatomyAnnotations.length > 0 && (
          <AnatomyOverlay annotations={anatomyAnnotations} selectedStructureId={selectedStructureId} />
        )}
        {selectionType === "point" && currentSelection?.type === "point" && (
          <View pointerEvents="none" style={[styles.pointMarker, { left: `${currentSelection.coords[0] * 100}%`, top: `${currentSelection.coords[1] * 100}%` }]} />
        )}
        {previewBox && <SelectionBox coords={previewBox} drawing />}
        {selectionType === "box" && currentSelection?.type === "box" && !isDrawingBox && <SelectionBox coords={currentSelection.coords} />}
      </View>

      }

      {imageFeedback}

      {!editingLabels && currentSelection && (
        <View style={[shared.card, styles.actionPanel]}>
          <View style={styles.modeSelector}>
            <ModeButton active={analysisMode === "identify"} icon="tag" label="Identify Object" onPress={() => setAnalysisMode("identify")} />
            <ModeButton active={analysisMode === "explain"} icon="book" label="Explain Region" onPress={() => setAnalysisMode("explain")} />
            <ModeButton active={analysisMode === "ask"} icon="help" label="Ask Question" onPress={() => setAnalysisMode("ask")} />
          </View>
          {analysisMode === "ask" && (
            <View style={{ gap: 12 }}>
              <TextInput
                onChangeText={setCustomQuestion}
                onSubmitEditing={() => void runAnalysis()}
                placeholder="e.g. What is the role of this organelle?"
                placeholderTextColor={colors.textDim}
                returnKeyType="send"
                style={styles.questionInput}
                value={customQuestion}
              />
              <PdfSourcesPanel key={conversation} chatId={conversation} selected={selectedDocuments} onSelectionChange={setSelectedDocuments} disabled={isLoading} restoreSelection />
            </View>
          )}
          <Pressable
            disabled={isLoading || (analysisMode === "ask" && !customQuestion.trim())}
            onPress={() => void runAnalysis()}
            style={({ pressed }) => [shared.button, shared.primaryButton, pressed && styles.pressed, (isLoading || (analysisMode === "ask" && !customQuestion.trim())) && shared.disabled]}
          >
            {isLoading && <ActivityIndicator color={colors.onButton} size="small" style={styles.spinner} />}
            {!isLoading && <Icon color={colors.onButton} name="search" size={17} />}
            <Text style={shared.buttonText}>
              {isLoading
                ? selectionType === "point" ? "SAM 2 and Qwen2.5-VL analyzing..." : "Qwen2.5-VL analyzing selected region..."
                : analysisMode === "ask" ? "Ask Question" : "Analyze Selected Region"}
            </Text>
          </Pressable>
        </View>
      )}

      {isLoading && analysisStartedAt !== null && <Text style={styles.durationText}>{analysisMode === "ask" ? "Question answering" : analysisMode === "identify" ? "Object identification" : "Region explanation"} · {formatDuration(Math.max(0, analysisNow - analysisStartedAt))} elapsed</Text>}

      {!!interactions.length && <View style={[shared.card, { gap: 12 }]}>
        <Text style={styles.badge}>Conversation about this image</Text>
        {interactions.map(turn => <View key={turn.id} style={{ gap: 8, paddingVertical: 10 }}>
          <Text style={{ color: colors.textDim, fontSize: 11 }}>{new Date(turn.createdAt).toLocaleString()} · {turn.selection?.type === "box" ? "Selected region" : "Selected point"}</Text>
          <Text style={{ color: colors.primaryBright, fontWeight: "700" }}>You: {turn.question || (turn.mode === "identify" ? "Identify selected object" : "Explain selected region")}</Text>
          <Text style={styles.resultText}>{turn.status === "failed" ? turn.error : turn.answer || "Answer pending — reopen History to retrieve it."}</Text>
          <PdfEvidence sources={turn.sources} grounding={turn.grounding} />
          {turn.answer && turn.status !== "failed" && <FeedbackControls key={turn.id} agentName="interactive-agent"
            accessToken={accessToken} apiUrl={feedbackApiUrl} inputContext={{ interaction: turn.selection, mode: turn.mode, question: turn.question }}
            outputId={"interaction-" + turn.id} outputSnapshot={{ response_text: turn.answer }} positiveReasons={POSITIVE_REASONS}
            negativeReasons={NEGATIVE_REASONS} sessionId={sessionId} />}
          {!!turn.selection && <Pressable onPress={() => { setCurrentSelection(turn.selection!); setSelectionType(turn.selection!.type); setAnalysisMode(turn.mode); setSelectedStructureId(turn.structureId ?? null); setCustomQuestion(turn.question || ""); }}><Text style={{ color: colors.primaryBright }}>Show selected region</Text></Pressable>}
        </View>)}
      </View>}

      {error && <View style={shared.error}><Text style={styles.errorTitle}>Interactive analysis failed</Text><Text style={styles.errorText}>{error}</Text></View>}
      {error && analysisDuration !== null && <Text style={styles.durationText}>Attempt duration: {formatDuration(analysisDuration)}</Text>}

      {analysisResult && (
        <View style={[shared.card, styles.resultPanel]}>
          <View style={styles.resultHeader}>
            <View style={styles.inlineInfo}><Icon color={colors.primaryBright} name="search" size={15} /><Text style={styles.badge}>Qwen2.5-VL Visual Explanation</Text></View>
            <Text style={styles.modelTag}>
              {selectionType === "point" ? "SAM 2 + Qwen2.5-VL-7B" : "Direct region + Qwen2.5-VL-7B"}. {speedMode === "normal" ? "A10G" : speedMode === "promax" ? "H100" : "A100"}
            </Text>
          </View>
          <Text style={styles.resultText}>{analysisResult}</Text>
          <PdfEvidence sources={resultSources} grounding={resultGrounding} />
          {analysisDuration !== null && <View style={styles.inlineInfo}><Icon color={colors.textDim} name="clock" size={14} /><Text style={styles.durationText}>Completed in {formatDuration(analysisDuration)}</Text></View>}
          {outputId && (
            <FeedbackControls
              key={outputId}
              agentName="interactive-agent"
              accessToken={accessToken}
              apiUrl={feedbackApiUrl}
              inputContext={{ interaction: currentSelection, mode: analysisMode, question: customQuestion || undefined }}
              negativeReasons={NEGATIVE_REASONS}
              onRegenerate={regenerateFromFeedback}
              outputId={outputId}
              outputSnapshot={{ response_text: analysisResult }}
              parentFeedbackId={retryLink?.feedbackId}
              parentOutputId={retryLink?.outputId}
              positiveReasons={POSITIVE_REASONS}
              sessionId={sessionId}
            />
          )}
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

function ModeButton({ active, icon, label, onPress }: { active: boolean; icon: IconName; label: string; onPress: () => void }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  return (
    <Pressable accessibilityState={{ selected: active }} onPress={onPress} style={({ pressed }) => [styles.modeButton, active && styles.modeButtonActive, pressed && styles.pressed]}>
      <Icon color={active ? colors.primaryBright : colors.textMuted} name={icon} size={15} />
      <Text style={[styles.modeButtonText, active && styles.modeButtonTextActive]}>{label}</Text>
    </Pressable>
  );
}

const makeStyles = (colors: ColorPalette) => StyleSheet.create({
  container: { gap: 16 },
  toolbar: { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: 8, padding: 13, gap: 10 },
  toolbarModes: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 },
  toolbarLabel: { color: colors.textMuted, fontSize: 11, fontWeight: "700", marginRight: 2, alignSelf: "center" },
  toolbarHint: { color: colors.textDim, fontSize: 11 },
  labelToggle: { alignSelf: "flex-start", borderWidth: 1, borderColor: colors.cyan, borderRadius: 50, paddingHorizontal: 12, paddingVertical: 7 },
  labelToggleText: { color: colors.cyan, fontSize: 12, fontWeight: "800" },
  modeButton: { flexDirection: "row", alignItems: "center", gap: 7, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSoft, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 9 },
  modeButtonActive: { borderColor: colors.primaryBright, backgroundColor: colors.accentSoft },
  modeButtonText: { color: colors.textMuted, fontSize: 12, fontWeight: "700" },
  modeButtonTextActive: { color: colors.text },
  canvas: { width: "100%", minHeight: 200, maxHeight: 720, backgroundColor: colors.canvas, borderRadius: 8, overflow: "hidden", borderWidth: 1, borderColor: colors.border },
  pointMarker: { position: "absolute", width: 32, height: 32, borderRadius: 16, marginLeft: -16, marginTop: -16, backgroundColor: colors.markerFill, borderWidth: 3, borderColor: "#fff" },
  boxMarker: { position: "absolute", borderWidth: 3, borderColor: colors.primaryBright, backgroundColor: colors.accentSoft },
  boxDrawing: { borderColor: colors.cyan, borderStyle: "dashed", backgroundColor: colors.accentSoft },
  actionPanel: { gap: 14 },
  modeSelector: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  questionInput: { minHeight: 46, borderWidth: 1, borderColor: colors.border, borderRadius: 8, backgroundColor: colors.surfaceSoft, color: colors.text, paddingHorizontal: 13, fontSize: 14 },
  pressed: { opacity: 0.76 },
  spinner: { marginRight: 8 },
  errorTitle: { color: colors.danger, fontWeight: "800", marginBottom: 4 },
  errorText: { color: colors.textMuted, lineHeight: 20 },
  resultPanel: { gap: 14 },
  resultHeader: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", alignItems: "flex-start", gap: 8 },
  badge: { color: colors.primaryBright, fontSize: 12, fontWeight: "800" },
  modelTag: { color: colors.textDim, fontSize: 12 },
  resultText: { color: colors.textMuted, lineHeight: 23, fontSize: 14 },
  inlineInfo: { flexDirection: "row", alignItems: "center", gap: 7 },
  durationText: { color: colors.textDim, fontSize: 11 },
});
