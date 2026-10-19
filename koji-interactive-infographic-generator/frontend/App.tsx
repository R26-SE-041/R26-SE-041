import { cloudEnabled, configureStudio, studioOwner, studioRequest, runJob, waitJob, getCloudHistory, getCloudModel, modelRequest, appendChatEvent } from "./studioClient";
import { markHistoryChanged } from "./historyActivity";
import * as DocumentPicker from "expo-document-picker";
import { File } from "expo-file-system";
import { PROCESS_LABELS, ProcessKey, ProcessOutcome, formatDuration } from "./processing";
import { THREED_IMAGE_TYPES, validateThreeDImage } from "./threeDSource";
import { useStudioSession } from "./studioAuth";
import StudioSessionPanel from "./components/StudioSessionPanel";
import AuthScreen from "./components/AuthScreen";
import LearnXHomeLink from "./components/LearnXHomeLink";
import EditorialHeadline from "./components/EditorialHeadline";
import JobsPanel from "./components/JobsPanel";
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import SketchCanvas from "./components/SketchCanvas";
import { SketchStroke, SketchGenerationMetadata } from "./historyStorage";
import InteractiveCanvas from "./components/InteractiveCanvas";
import SpeedSelector from "./components/SpeedSelector";
import FeedbackControls, { createOutputId, FeedbackReason } from "./components/FeedbackControls";
import StudioSettings from "./components/StudioSettings";
import ThreeDViewer from "./components/ThreeDViewer";
import HistoryPanel from "./components/HistoryPanel";
import Icon, { IconName, StatusDot } from "./components/Icon";
import { appendHistoryInteraction, GenerationHistoryItem, GenerationInteraction, listHistory, saveHistoryItem, updateHistoryItem } from "./historyStorage";
import { ColorPalette, displayFont, headingFont, makeSharedStyles, ThemeProvider, useAppTheme } from "./theme";
import {
  STUDIO_API_URL,
  PROMPT_AGENT_URL,
  IMAGE_AGENT_URL,
  SKETCH_AGENT_URL,
  INTERACTIVE_AGENT_URL,
  THREED_AGENT_URL,
  BACKEND_URL,
  EVAL_AGENT_URL,
} from "./config";

const BACKEND_HEALTH_URL = STUDIO_API_URL || BACKEND_URL;

type Stage = "idle" | "enhancing" | "preview" | "generating" | "done";
type GenerationWorkspace = "general" | "anatomy" | "sketch" | "history";
export type SpeedMode = "normal" | "pro" | "promax";
type ThreeDStage = "idle" | "converting" | "done";
interface UploadedThreeDImage { base64: string; uri: string; name: string; id: string; historyId?: string }
type Health = "ok" | "error" | "checking";
type AgentKey = "prompt" | "image" | "eval" | "interactive" | "threed";
export interface AnatomySpec {
  is_anatomy: boolean;
  organ?: string;
  view?: string;
  view_description?: string;
  required_structures?: string[];
  focus_structures?: string[];
}
interface EnhancedPromptPayload {
  schema_version: "1.0";
  final_prompt: string;
  anatomy_spec: AnatomySpec;
  route: "anatomy" | "generic";
  anatomy_mode?: "verified" | "general" | null;
  routing?: { confidence?: number; reason_code?: string; source?: "rules" | "qwen"; subject?: string };
}
export interface AnatomyAnnotation {
  structure_id: string;
  label: string;
  anchor_x: number;
  anchor_y: number;
  label_x: number;
  label_y: number;
  confidence: number;
  verified: boolean;
  user_edited?: boolean;
  source?: "automatic" | "manual";
}
interface RetryLink { feedbackId: string; outputId: string }
interface EvaluationResult {
  clipScore: number | null;
  vlmScore: number | null;
  visualScore: number;
  pedagogicalScore: number;
  feedback: string;
  anatomyHardFailures: string[];
}
interface QualityControlledImage {
  historyId?: string;
  sketchMetadata?: SketchGenerationMetadata;
  image: string;
  prompt: string;
  anatomy: AnatomySpec;
  payload: EnhancedPromptPayload;
  evaluation: EvaluationResult | null;
  retryCount: number;
  warning: string | null;
}

const ANATOMY_PROMPT_NEGATIVE: FeedbackReason[] = [
  { code: "wrong_view", label: "Wrong view" }, { code: "missing_structure", label: "Missing structure" },
  { code: "extra_structure", label: "Extra anatomy" }, { code: "labels_requested", label: "Labels requested" },
  { code: "background_not_white", label: "Background not white" }, { code: "inaccurate_anatomy", label: "Inaccurate anatomy" },
  { code: "wrong_detail_level", label: "Wrong detail level" },
];
const ANATOMY_PROMPT_POSITIVE: FeedbackReason[] = [
  { code: "view_preserved", label: "View preserved" }, { code: "structures_preserved", label: "Structures preserved" },
  { code: "concise", label: "Concise" }, { code: "accurate", label: "Accurate" },
];
const GENERIC_PROMPT_NEGATIVE: FeedbackReason[] = [
  { code: "subject_changed", label: "Subject changed" }, { code: "wrong_style", label: "Wrong style" },
  { code: "poor_composition", label: "Poor composition" }, { code: "missing_detail", label: "Missing detail" },
  { code: "too_verbose", label: "Too verbose" },
];
const GENERIC_PROMPT_POSITIVE: FeedbackReason[] = [
  { code: "subject_preserved", label: "Subject preserved" }, { code: "good_style", label: "Good style" },
  { code: "good_composition", label: "Good composition" }, { code: "concise", label: "Concise" },
];

function extractAnatomyLabel(responseText: string): string | null {
  const firstLine = responseText.split(/\r?\n/).map((line) => line.trim()).find(Boolean) ?? "";
  const label = firstLine
    .replace(/^[#*\-:\s]+/, "")
    .replace(/^(?:identified\s+)?(?:structure|object|label)\s*:\s*/i, "")
    .replace(/^(?:the\s+)?(?:highlighted\s+)?(?:structure|region|object)\s+is\s+(?:the\s+)?/i, "")
    .replace(/[.!:;,]+$/, "")
    .trim()
    .slice(0, 80);
  if (
    label.length < 2 ||
    label.split(/\s+/).length > 8 ||
    !/^[a-z][a-z0-9 .()'/-]*$/i.test(label) ||
    /\b(?:cannot|can't|unable|unknown|unidentified|unclear|not sure|no visible|no identifiable|background|appears|likely)\b/i.test(label)
  ) return null;
  return label;
}
const IMAGE_NEGATIVE: FeedbackReason[] = [
  { code: "bad_labels", label: "Bad labels" }, { code: "poor_layout", label: "Poor layout" },
  { code: "wrong_content", label: "Wrong content" }, { code: "wrong_style", label: "Wrong style" },
  { code: "inaccurate_diagram", label: "Inaccurate diagram" },
];
const IMAGE_POSITIVE: FeedbackReason[] = [
  { code: "clear_labels", label: "Clear labels" }, { code: "good_layout", label: "Good layout" },
  { code: "accurate", label: "Accurate" }, { code: "matches_request", label: "Matches request" },
];

const THREED_POLL_INTERVAL_MS = 3_000;
// Cover the GPU worker's 60-minute limit plus cold start/result retrieval.
const THREED_MAX_WAIT_MS = 70 * 60 * 1_000;
const THREED_ACTIVE_JOB_KEY = "eduvision:active-3d-conversion";
const ESTIMATED_WARM_WINDOW_MS = 5 * 60 * 1_000;
const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

interface StoredThreeDJob {
  requestId: string;
  imageFingerprint: string;
  speedMode: SpeedMode;
}

function imageFingerprint(imageBase64: string): string {
  return `${imageBase64.length}:${imageBase64.slice(0, 24)}:${imageBase64.slice(-24)}`;
}

function readStoredThreeDJob(): StoredThreeDJob | null {
  if (Platform.OS !== "web" || typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(THREED_ACTIVE_JOB_KEY);
    return value ? JSON.parse(value) as StoredThreeDJob : null;
  } catch {
    return null;
  }
}

function storeThreeDJob(job: StoredThreeDJob): void {
  if (Platform.OS !== "web" || typeof window === "undefined") return;
  try {
    window.localStorage.setItem(THREED_ACTIVE_JOB_KEY, JSON.stringify(job));
  } catch {
    // Storage can be disabled in private/restricted browser contexts. The
    // synchronous in-memory guard still prevents duplicate clicks.
  }
}

function clearStoredThreeDJob(): void {
  if (Platform.OS !== "web" || typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(THREED_ACTIVE_JOB_KEY);
  } catch {
    // Nothing else to clean up when browser storage is unavailable.
  }
}

function createRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `3d-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const SPEED_MODES: Array<{
  id: SpeedMode;
  label: string;
  icon: IconName;
  desc: string;
  promptGpu: string;
  imageGpu: string;
  interactiveGpu: string;
}> = [
  { id: "normal", label: "Standard", icon: "bolt", desc: "Everyday generation", promptGpu: "A10G", imageGpu: "A10G", interactiveGpu: "A10G" },
  { id: "pro", label: "Fast", icon: "rocket", desc: "Higher GPU capacity", promptGpu: "A10G", imageGpu: "A100", interactiveGpu: "A100" },
];

function friendlyPhase(phase: string, fallback: string): string {
  const labels: Record<string, string> = {
    queued: "Waiting for a generation worker…", enhancing: "Preparing your instruction…",
    generating: "Creating your image…", evaluating: "Checking image quality…",
    labeling: "Finding and labeling structures…", analyzing: "Exploring your selected region…",
    converting: "Creating your 3D model…", saving: "Saving your creation…",
    "preparing image": "Preparing your image for 3D…",
    "generating shape": "Building your model’s shape…",
    "simplifying mesh": "Preparing the mesh for texturing…",
    "synthesizing texture": "Creating your model’s texture…",
    "exporting model": "Exporting your 3D model…",
    "opening saved model": "Opening your completed 3D model…",
  };
  return phase.startsWith("retrying") ? "Refining the image after its quality check…" : labels[phase] || fallback;
}

function formatRemaining(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.ceil(milliseconds / 1_000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function errorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const value = payload as { error?: unknown; detail?: unknown };
  if (typeof value.error === "string") return value.error;
  if (typeof value.detail === "string") return value.detail;
  if (value.detail && typeof value.detail === "object") {
    const nested = value.detail as { error?: unknown };
    if (typeof nested.error === "string") return nested.error;
  }
  return fallback;
}

async function readApiResponse(response: Response): Promise<{ payload: Record<string, unknown>; raw: string }> {
  const raw = await response.text();
  if (!raw) return { payload: {}, raw: "" };
  try {
    const parsed: unknown = JSON.parse(raw);
    return {
      payload: parsed && typeof parsed === "object" ? parsed as Record<string, unknown> : {},
      raw,
    };
  } catch {
    return { payload: {}, raw };
  }
}

function threeDApiError(response: Response, payload: unknown, raw: string, fallback: string): string {
  if (response.status === 404 && /modal-http:\s*workspace\b.*\bis disabled/i.test(raw)) {
    return "The 3D service's Modal workspace is disabled. Re-enable the Modal workspace and redeploy threed-agent.";
  }
  return errorMessage(payload, fallback);
}

interface AppProps { accessToken?: string; studioSession?: ReturnType<typeof useStudioSession> }

export default function App({ accessToken }: AppProps) {
  const session = useStudioSession(accessToken);
  configureStudio(session.token, session.getAccessToken);
  useEffect(() => {
    if (typeof window !== "undefined" && session.token && !session.recovering && !session.loading) {
      if (["/signin", "/signup", "/auth/callback", "/forgot-password", "/verify-email", "/reset-password"].includes(window.location.pathname)) window.history.replaceState({}, "", "/");
      document.title = "learnX";
    }
  }, [session.token, session.recovering, session.loading]);
  const needsAccount = Boolean(STUDIO_API_URL && !accessToken && (!session.token || session.recovering || session.loading));
  return <ThemeProvider>{needsAccount ? <AuthScreen session={session} /> : <Home key={studioOwner()} accessToken={session.token} studioSession={accessToken ? undefined : session} />}</ThemeProvider>;
}

function Home({ accessToken, studioSession }: AppProps) {
  const screenWidth = useWindowDimensions().width;
  const workspaceGridStyle = Platform.OS === "web" ? { display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))" } as any : undefined;
  const { colors, mode: themeMode, toggleTheme } = useAppTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const shared = useMemo(() => makeSharedStyles(colors), [colors]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [statusOpen, setStatusOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [jobPhase, setJobPhase] = useState<string | null>(null);
  const [labelBusy, setLabelBusy] = useState(false);
  const visibleImage = useRef<string | null>(null);
  const cloudGeneration = useRef<{ item: GenerationHistoryItem; labelJobId?: string | null } | null>(null);
  const [workspace, setWorkspace] = useState<GenerationWorkspace>("general");
  const [prompt, setPrompt] = useState("");
  const [sketchStrokes, setSketchStrokes] = useState<SketchStroke[]>([]);
  const [sketchStrength, setSketchStrength] = useState(0.85);
  const [sketchCanvasKey, setSketchCanvasKey] = useState(0);
  const [sketchMetadata, setSketchMetadata] = useState<SketchGenerationMetadata | undefined>();
  const [stage, setStage] = useState<Stage>("idle");
  const [speedMode, setSpeedMode] = useState<SpeedMode>("pro");
  const [enhancedPrompt, setEnhancedPrompt] = useState<string | null>(null);
  const [enhancedPromptJson, setEnhancedPromptJson] = useState<EnhancedPromptPayload | null>(null);
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  visibleImage.current = imageBase64;
  const [anatomySpec, setAnatomySpec] = useState<AnatomySpec>({ is_anatomy: false });
  const [anatomyAnnotations, setAnatomyAnnotations] = useState<AnatomyAnnotation[]>([]);
  const [localizationError, setLocalizationError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [threedStage, setThreedStage] = useState<ThreeDStage>("idle");
  const [glbBase64, setGlbBase64] = useState<string | null>(null);
  const [modelAsset, setModelAsset] = useState<{ modelUrl: string; modelKey: string } | null>(null);
  const [savedThreeD, setSavedThreeD] = useState<{ id: string; sourceKey: string | null } | null>(null);
  const [glbSizeKb, setGlbSizeKb] = useState<number>();
  const threedOutputId = useMemo(() => glbBase64 || modelAsset ? createOutputId("threed") : null, [glbBase64, modelAsset]);
  const [threedError, setThreedError] = useState<string | null>(null);
  const [uploadedThreeD, setUploadedThreeD] = useState<UploadedThreeDImage | null>(null);
  const [pickingThreeD, setPickingThreeD] = useState(false);
  const [promptHealth, setPromptHealth] = useState<Health>("checking");
  const [imageHealth, setImageHealth] = useState<Health>("checking");
  const [interactiveHealth, setInteractiveHealth] = useState<Health>("checking");
  const [evalHealth, setEvalHealth] = useState<Health>("checking");
  const [threedHealth, setThreedHealth] = useState<Health>("checking");
  const [backendHealth, setBackendHealth] = useState<Health>("checking");
  const [now, setNow] = useState(Date.now());
  const [warmUntil, setWarmUntil] = useState<Record<AgentKey, number>>({ prompt: 0, image: 0, eval: 0, interactive: 0, threed: 0 });
  const [timings, setTimings] = useState<Partial<Record<ProcessKey, number>>>({});
  const [outcomes, setOutcomes] = useState<Partial<Record<ProcessKey, ProcessOutcome>>>({});
  const [activeTimers, setActiveTimers] = useState<Partial<Record<ProcessKey, number>>>({});
  const [sessionId] = useState(() => createOutputId("session"));
  const [promptOutputId, setPromptOutputId] = useState<string | null>(null);
  const [imageOutputId, setImageOutputId] = useState<string | null>(null);
  const [promptRetryLink, setPromptRetryLink] = useState<RetryLink | null>(null);
  const [imageRetryLink, setImageRetryLink] = useState<RetryLink | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [evaluationRetries, setEvaluationRetries] = useState(0);
  const [evaluationWarning, setEvaluationWarning] = useState<string | null>(null);
  const [currentHistoryId, setCurrentHistoryId] = useState<string | null>(null);
  const currentChatId = useRef<string | null>(null);
  const [historyInteractions, setHistoryInteractions] = useState<GenerationInteraction[]>([]);
  const threedRequestInFlight = useRef(false);
  const workspaceSnapshots = useRef<Partial<Record<"general" | "anatomy" | "sketch", {
    historyInteractions: GenerationInteraction[];
    sketchStrokes: SketchStroke[]; sketchStrength: number; sketchMetadata?: SketchGenerationMetadata;
    prompt: string; stage: Stage; speedMode: SpeedMode; enhancedPrompt: string | null;
    enhancedPromptJson: EnhancedPromptPayload | null; imageBase64: string | null;
    anatomySpec: AnatomySpec; anatomyAnnotations: AnatomyAnnotation[]; evaluation: EvaluationResult | null;
    evaluationRetries: number; evaluationWarning: string | null; glbBase64: string | null;
    modelAsset: { modelUrl: string; modelKey: string } | null;
    savedThreeD: { id: string; sourceKey: string | null } | null;
    glbSizeKb?: number; threedStage: ThreeDStage; historyId: string | null; chatId: string | null;
    uploadedThreeD: UploadedThreeDImage | null;
    timings: Partial<Record<ProcessKey, number>>; outcomes: Partial<Record<ProcessKey, ProcessOutcome>>;
  }>>>({});

  useEffect(() => { setStartedAt(stage === "enhancing" || stage === "generating" ? Date.now() : null); }, [stage]);
  const unsavedDraft = !currentHistoryId && Boolean(prompt.trim() || sketchStrokes.length);
  useEffect(() => {
    if (Platform.OS !== "web" || typeof window === "undefined" || !unsavedDraft) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [unsavedDraft]);
  const isLoading = stage === "enhancing" || stage === "generating" || threedStage === "converting";
  // The 3D agent has its own browser-facing endpoint. Orchestrator downtime
  // must not incorrectly mark a healthy 3D service as offline.
  const displayedThreeDHealth: Health = threedHealth;
  const speed = useMemo(
    () => SPEED_MODES.find((item) => item.id === speedMode) ?? SPEED_MODES[1],
    [speedMode],
  );

  useEffect(() => {
    let mounted = true;
    const check = async (url: string, setter: (health: Health) => void, timeoutMs = 5_000, service?: string) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const throughStudio = Boolean(service && STUDIO_API_URL);
        if (throughStudio && !accessToken) return;
        const healthUrl = throughStudio
          ? `${STUDIO_API_URL.replace(/\/$/, '')}/agents/${service}/health`
          : `${url}/health`;
        const response = await fetch(healthUrl, {
          headers: { Accept: "application/json", ...(throughStudio ? { Authorization: `Bearer ${accessToken}` } : {}) },
          signal: controller.signal,
        });
        const body = await response.json().catch(() => null);
        const healthy = response.ok && body?.status === "ok";
        if (mounted) setter(healthy ? "ok" : "error");
      } catch {
        if (mounted) setter("error");
      } finally {
        clearTimeout(timeout);
      }
    };
    const checkAll = () => {
      void check(PROMPT_AGENT_URL, setPromptHealth, 5_000, 'prompt');
      void check(IMAGE_AGENT_URL, setImageHealth, 5_000, 'image');
      void check(INTERACTIVE_AGENT_URL, setInteractiveHealth, 5_000, 'interactive');
      void check(EVAL_AGENT_URL, setEvalHealth, 30_000, 'evaluation');
      void check(THREED_AGENT_URL, setThreedHealth, 30_000, 'threed');
      void check(BACKEND_HEALTH_URL, setBackendHealth);
    };
    checkAll();
    const refresh = setInterval(checkAll, 15_000);
    return () => { mounted = false; clearInterval(refresh); };
  }, [accessToken]);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1_000);
    return () => clearInterval(timer);
  }, []);

  const markWarm = (agent: AgentKey) => {
    setWarmUntil((current) => ({ ...current, [agent]: Date.now() + ESTIMATED_WARM_WINDOW_MS }));
  };

  async function runTimed<T>(process: ProcessKey, operation: () => Promise<T>): Promise<T> {
    const startedAt = Date.now();
    setActiveTimers((current) => ({ ...current, [process]: startedAt }));
    try {
      const result = await operation();
      setOutcomes((current) => ({ ...current, [process]: "completed" }));
      return result;
    } catch (error) {
      setOutcomes((current) => ({ ...current, [process]: "failed" }));
      throw error;
    } finally {
      setTimings((current) => ({ ...current, [process]: Date.now() - startedAt }));
      setActiveTimers((current) => {
        const next = { ...current };
        delete next[process];
        return next;
      });
    }
  }

  const recallMemory = async (agentName: string, query: string): Promise<string> => {
    try {
      const response = await fetch(`${BACKEND_HEALTH_URL}/memory/context`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({ agent_name: agentName, query, limit: 5 }),
      });
      if (!response.ok) return "";
      const data = await response.json().catch(() => ({}));
      return typeof data.context === "string" ? data.context : "";
    } catch {
      return "";
    }
  };

  const reset = () => {
    setStage("idle");
    setEnhancedPrompt(null);
    setEnhancedPromptJson(null);
    setImageBase64(null);
    setAnatomySpec({ is_anatomy: false });
    setAnatomyAnnotations([]);
    setLocalizationError(null);
    setError(null);
    setThreedStage("idle");
    setGlbBase64(null);
    setModelAsset(null);
    setSavedThreeD(null);
    setGlbSizeKb(undefined);
    setThreedError(null);
    setUploadedThreeD(null);
    setTimings({});
    setOutcomes({});
    setActiveTimers({});
    setPromptOutputId(null);
    setImageOutputId(null);
    setPromptRetryLink(null);
    setImageRetryLink(null);
    setEvaluation(null);
    setEvaluationRetries(0);
    setEvaluationWarning(null);
    setCurrentHistoryId(null); setHistoryInteractions([]);
    currentChatId.current = null;
  };

  const handlePromptChange = (value: string) => {
    setPrompt(value);
    if (stage !== "idle") reset();
  };

  const selectWorkspace = (next: GenerationWorkspace) => {
    if (next === workspace || isLoading || threedRequestInFlight.current) return;
    if (workspace !== "history") {
      workspaceSnapshots.current[workspace] = {
        historyInteractions, sketchStrokes, sketchStrength, sketchMetadata,
        prompt, stage, speedMode, enhancedPrompt, enhancedPromptJson, imageBase64, anatomySpec,
        anatomyAnnotations, evaluation, evaluationRetries, evaluationWarning, glbBase64, glbSizeKb, modelAsset, savedThreeD,
        threedStage, historyId: currentHistoryId, chatId: currentChatId.current, uploadedThreeD, timings, outcomes,
      };
    }
    if (next !== "history") {
      const saved = workspaceSnapshots.current[next];
      reset();
      if (saved) {
        setHistoryInteractions(saved.historyInteractions);
        setSketchStrokes(saved.sketchStrokes); setSketchStrength(saved.sketchStrength); setSketchMetadata(saved.sketchMetadata);
        setPrompt(saved.prompt); setStage(saved.stage); setSpeedMode(saved.speedMode);
        setEnhancedPrompt(saved.enhancedPrompt); setEnhancedPromptJson(saved.enhancedPromptJson);
        setImageBase64(saved.imageBase64); setAnatomySpec(saved.anatomySpec);
        setAnatomyAnnotations(saved.anatomyAnnotations); setEvaluation(saved.evaluation);
        setEvaluationRetries(saved.evaluationRetries); setEvaluationWarning(saved.evaluationWarning);
        setGlbBase64(saved.glbBase64); setGlbSizeKb(saved.glbSizeKb); setThreedStage(saved.threedStage);
        setModelAsset(saved.modelAsset);
        setSavedThreeD(saved.savedThreeD);
        setUploadedThreeD(saved.uploadedThreeD); setTimings(saved.timings); setOutcomes(saved.outcomes);
        setCurrentHistoryId(saved.historyId); currentChatId.current = saved.chatId;
      } else {
        setPrompt(""); setSketchStrokes([]); setSketchStrength(0.85); setSketchMetadata(undefined);
        currentChatId.current = null;
      }
    }
    setWorkspace(next);
  };

  const archiveResult = async (result: QualityControlledImage): Promise<string | null> => {
    const cloud = cloudGeneration.current;
    if (cloudEnabled() && cloud?.item.imageBase64 === result.image) {
      setCurrentHistoryId(cloud.item.id); currentChatId.current = cloud.item.chatId ?? cloud.item.id;
      await saveHistoryItem(cloud.item).catch(() => setError("Cloud history saved, but local cache is unavailable."));
      return cloud.item.id;
    }
    const id = createOutputId("history");
    const mode = workspace === "sketch" ? "sketch" : result.anatomy.is_anatomy ? "anatomy" : "general";
    try {
      const chatId = currentChatId.current ?? createOutputId("chat");
      currentChatId.current = chatId;
      const version = (await listHistory()).filter((item) => (item.chatId ?? item.id) === chatId).length + 1;
      await saveHistoryItem({
        id,
        createdAt: new Date().toISOString(),
        prompt: prompt.trim(),
        enhancedPrompt: result.prompt,
        imageBase64: result.image,
        mode,
        speedMode,
        ...(mode === "sketch" ? { sketchStrokes, sketchStrength, sketchMetadata: result.sketchMetadata } : {}),
        evaluationRetries: result.retryCount,
        evaluationWarning: result.warning,
        chatId,
        version,
        enhancedPayload: result.payload,
        anatomy: result.anatomy,
        evaluation: result.evaluation ? {
          visualScore: result.evaluation.visualScore,
          pedagogicalScore: result.evaluation.pedagogicalScore,
          feedback: result.evaluation.feedback,
        } : null,
      });
      setCurrentHistoryId(id);
      return id;
    } catch {
      setCurrentHistoryId(null);
      setError("Image generated, but history could not be saved. Browser storage may be full.");
      return null;
    }
  };

  const restoreHistory = (item: GenerationHistoryItem) => {
    const nextWorkspace = item.mode;
    const restoredAnatomy = (item.anatomy as AnatomySpec | undefined) ?? { is_anatomy: item.mode === "anatomy" };
    reset();
    setWorkspace(nextWorkspace);
    setPrompt(item.prompt);
    if (!cloudEnabled() && item.threeDJob?.status === "converting") {
      storeThreeDJob({ requestId: item.threeDJob.requestId, imageFingerprint: imageFingerprint(item.imageBase64), speedMode: item.speedMode });
    }
    setSketchStrokes(item.sketchStrokes ?? []); setSketchMetadata(item.sketchMetadata);
    setSketchStrength(item.sketchStrength ?? item.sketchMetadata?.requested_control_strength ?? item.sketchMetadata?.control_strength ?? 0.85);
    setSpeedMode(item.speedMode === "promax" ? "pro" : item.speedMode);
    setEnhancedPrompt(item.enhancedPrompt);
    setEnhancedPromptJson((item.enhancedPayload as EnhancedPromptPayload) ?? (item.mode === "anatomy" ? {
      schema_version: "1.0", final_prompt: item.enhancedPrompt, anatomy_spec: restoredAnatomy,
      route: "anatomy", anatomy_mode: "verified",
    } : null));
    setImageBase64(item.imageBase64 || null);
    setAnatomySpec(restoredAnatomy);
    setAnatomyAnnotations(item.anatomyAnnotations ?? []);
    setHistoryInteractions(item.interactions ?? []);
    setEvaluation(item.evaluation ? { clipScore: null, vlmScore: null, visualScore: item.evaluation.visualScore, pedagogicalScore: item.evaluation.pedagogicalScore, feedback: item.evaluation.feedback, anatomyHardFailures: [] } : null);
    setEvaluationRetries(item.evaluationRetries ?? 0);
    setEvaluationWarning(item.evaluationWarning ?? null);
    setGlbBase64(item.glbBase64 ?? null); setGlbSizeKb(item.glbSizeKb);
    setModelAsset(item.glbUrl ? { modelUrl: item.glbUrl, modelKey: item.modelKey || item.id } : null);
    setThreedStage(item.glbBase64 || item.glbUrl ? "done" : "idle");
    setCurrentHistoryId(item.imageBase64 ? item.id : null); currentChatId.current = item.chatId ?? item.id;
    setImageOutputId(createOutputId("image")); setStage(item.imageBase64 ? "done" : "preview");
  };

  const callEnhance = async (
    raw: string,
    retryFeedback?: string,
  ): Promise<{ prompt: string; anatomy: AnatomySpec; payload: EnhancedPromptPayload }> => {
    if (!currentChatId.current) currentChatId.current = createOutputId("chat");
    const promptEventId = await appendChatEvent(currentChatId.current,"prompt",{prompt:raw,mode:workspace,status:"enhancing"});
    const routedRaw = workspace === "anatomy"
      ? `Human anatomy educational illustration: ${raw}`
      : raw;
    const [anatomyMemory, genericMemory] = await Promise.all([
      recallMemory("prompt-anatomy", routedRaw),
      recallMemory("prompt-generic", routedRaw),
    ]);
    let data: Record<string, any>;
    if (cloudEnabled()) {
      const job = await runJob({kind:"enhance",chat_id:currentChatId.current,prompt_event_id:promptEventId,
        prompt:routedRaw,raw_prompt:raw,mode:workspace==="anatomy"?"anatomy":"general",speed_mode:speedMode,
        enhancement_context:{retry_feedback:retryFeedback,anatomy_memory:anatomyMemory,generic_memory:genericMemory}
      },setJobPhase);
      data=job.result?.enhancement || {};
    } else {
    const response = await modelRequest("prompt", PROMPT_AGENT_URL, "/enhance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        raw_prompt: routedRaw,
        speed_mode: speedMode,
        retry_feedback: retryFeedback,
        anatomy_memory: anatomyMemory,
        generic_memory: genericMemory,
      }),
    });
    data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorMessage(data, `Enhance HTTP ${response.status}`));
    }
    if (data.error && !data.enhanced_prompt) throw new Error(String(data.error));
    const returnedPrompt = typeof data.enhanced_prompt === "string" ? data.enhanced_prompt.trim() : "";
    const receivedPayload = data.enhanced_prompt_json;
    const receivedSpec = receivedPayload?.anatomy_spec ?? data.anatomy_spec;
    const anatomy: AnatomySpec = receivedSpec && typeof receivedSpec.is_anatomy === "boolean"
      ? receivedSpec
      : { is_anatomy: false };
    const finalPrompt = typeof receivedPayload?.final_prompt === "string"
      ? receivedPayload.final_prompt.trim()
      : returnedPrompt;
    if (!finalPrompt) {
      throw new Error("Prompt agent did not return the enhanced_prompt_json contract");
    }
    if (returnedPrompt && returnedPrompt !== finalPrompt) {
      throw new Error("Prompt agent returned inconsistent enhanced prompt fields");
    }
    const route: "anatomy" | "generic" =
      receivedPayload?.route === "anatomy" || receivedPayload?.route === "generic"
        ? receivedPayload.route
        : anatomy.is_anatomy ? "anatomy" : "generic";
    const payload: EnhancedPromptPayload = {
      schema_version: "1.0",
      final_prompt: finalPrompt,
      anatomy_spec: anatomy,
      route,
      anatomy_mode: receivedPayload?.anatomy_mode
        ?? (route === "anatomy" ? (anatomy.view ? "verified" : "general") : null),
      routing: receivedPayload?.routing ?? {
        source: "rules",
        reason_code: "legacy_contract_compatibility",
      },
    };

    return {
      prompt: payload.final_prompt,
      anatomy,
      payload,
    };
  };

  const cloudGenerate = async (request: Record<string, unknown>): Promise<QualityControlledImage> => {
    setJobPhase("queued");
    const job = await runJob({ raw_prompt:prompt.trim(),mode:workspace,speed_mode:speedMode,
      chat_id:currentChatId.current,...request },setJobPhase);
    if (!job.result?.history_id) throw new Error("Job returned no history record");
    const item = await getCloudHistory(job.result.history_id);
    cloudGeneration.current = {item,labelJobId:job.result.label_job_id};
    const anatomy = item.anatomy as AnatomySpec || {is_anatomy:false};
    return {image:item.imageBase64,prompt:item.enhancedPrompt,anatomy,
      payload:(item.enhancedPayload as EnhancedPromptPayload) || {schema_version:"1.0",final_prompt:item.enhancedPrompt,anatomy_spec:anatomy,route:anatomy.is_anatomy?"anatomy":"generic"},
      evaluation:item.evaluation ? {...item.evaluation,clipScore:null,vlmScore:null,anatomyHardFailures:(item.evaluation as EvaluationResult).anatomyHardFailures || []}:null,
      retryCount:item.evaluationRetries ?? 0,warning:item.evaluationWarning ?? null,sketchMetadata:item.sketchMetadata,historyId:item.id};
  };

  const callGenerate = async (
    finalPrompt: string,
    anatomy: AnatomySpec,
    regenerationFeedback?: string,
    enhancement?: EnhancedPromptPayload,
    useRuntimeContext = true,
  ): Promise<string> => {
    if (cloudEnabled()) {
      const result = await cloudGenerate({kind:"generate",prompt:finalPrompt,anatomy,enhanced_payload:enhancement,feedback:regenerationFeedback || "",mode:workspace === "general" ? "general" : "anatomy"});
      return result.image;
    }
    const memoryContext = useRuntimeContext ? await recallMemory("image-agent", finalPrompt) : "";
    const response = await fetch(`${IMAGE_AGENT_URL}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: finalPrompt,
        enhanced_prompt_json: enhancement,
        speed_mode: speedMode,
        domain: anatomy.is_anatomy ? "anatomy" : "generic",
        organ: anatomy.organ,
        view: anatomy.view,
        regeneration_feedback: regenerationFeedback,
        memory_context: memoryContext,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorMessage(data, `Generate HTTP ${response.status}`));
    if (data.error) throw new Error(String(data.error));
    if (!data.image_base64) throw new Error("Empty image response");
    return data.base_image_base64 ?? data.image_base64;
  };

  const callEvaluate = async (
    image: string,
    finalPrompt: string,
    anatomy: AnatomySpec,
  ): Promise<EvaluationResult> => {
    const request: RequestInit = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_base64: image,
        enhanced_prompt: finalPrompt,
        raw_prompt: prompt.trim(),
        anatomy_spec: anatomy,
        enable_anatomy_critic: anatomy.is_anatomy,
      }),
    };
    let response: Response;
    try {
      response = await fetch(`${EVAL_AGENT_URL}/evaluate`, request);
    } catch {
      // A Modal dev endpoint can briefly drop transport while a cold container
      // becomes ready. Retry once; HTTP errors remain visible without retrying.
      response = await fetch(`${EVAL_AGENT_URL}/evaluate`, request);
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorMessage(data, `Evaluate HTTP ${response.status}`));
    const numericScore = (value: unknown): number | null =>
      typeof value === "number" && Number.isFinite(value) ? value : null;
    const visual = numericScore(data.visual_score) ?? numericScore(data.vlm_score);
    const pedagogical = numericScore(data.pedagogical_score) ?? numericScore(data.vlm_score);
    if (visual === null || pedagogical === null) {
      throw new Error(typeof data.error === "string" ? data.error : "Evaluation scores were unavailable");
    }
    return {
      clipScore: numericScore(data.clip_score),
      vlmScore: numericScore(data.vlm_score),
      visualScore: visual,
      pedagogicalScore: pedagogical,
      feedback: typeof data.vlm_feedback === "string" ? data.vlm_feedback.trim() : "",
      anatomyHardFailures: Array.isArray(data.anatomy_hard_failures)
        ? data.anatomy_hard_failures.filter((item: unknown): item is string => typeof item === "string")
        : [],
    };
  };

  const evaluationPassed = (result: EvaluationResult): boolean =>
    result.visualScore >= 7 && result.pedagogicalScore >= 7 && result.anatomyHardFailures.length === 0;

  const evaluationRank = (result: EvaluationResult): number =>
    result.visualScore + result.pedagogicalScore - (result.anatomyHardFailures.length > 0 ? 20 : 0);

  const retryFeedbackFor = (result: EvaluationResult): string => {
    const corrections: string[] = [];
    if (result.visualScore < 7) corrections.push("Improve composition, clarity, lighting, and visual legibility");
    if (result.pedagogicalScore < 7) corrections.push("Correct factual content and match the learner's level");
    if (result.anatomyHardFailures.length) {
      corrections.push(`Correct these anatomy failures: ${result.anatomyHardFailures.join("; ")}`);
    }
    if (result.feedback) corrections.push(`Evaluator notes: ${result.feedback}`);
    return corrections.join(". ").slice(0, 2000);
  };

  const generateWithQualityControl = async (
    initialPrompt: string,
    initialAnatomy: AnatomySpec,
    initialPayload: EnhancedPromptPayload,
    initialFeedback?: string,
  ): Promise<QualityControlledImage> => {
    if (cloudEnabled()) return cloudGenerate({kind:"generate",prompt:initialPrompt,anatomy:initialAnatomy,enhanced_payload:initialPayload,feedback:initialFeedback || "",mode:"anatomy"});
    let currentPrompt = initialPrompt;
    let currentAnatomy = initialAnatomy;
    let currentPayload = initialPayload;
    let correction = initialFeedback;
    let best: QualityControlledImage | null = null;

    for (let attempt = 0; attempt <= 2; attempt += 1) {
      if (attempt > 0 && !currentAnatomy.is_anatomy) {
        let enhanced: Awaited<ReturnType<typeof callEnhance>>;
        try {
          enhanced = await callEnhance(prompt.trim(), correction);
        } catch (caught) {
          if (best) return {
            ...best,
            retryCount: attempt - 1,
            warning: caught instanceof Error ? `Prompt retry stopped: ${caught.message}` : "Prompt retry stopped",
          };
          throw caught;
        }
        currentPrompt = enhanced.prompt;
        currentAnatomy = enhanced.anatomy;
        currentPayload = enhanced.payload;
        markWarm("prompt");
      }

      let image: string;
      try {
        image = await callGenerate(currentPrompt, currentAnatomy, correction, currentPayload);
      } catch (caught) {
        if (best) return {
          ...best,
          retryCount: attempt - 1,
          warning: caught instanceof Error ? `Image retry stopped: ${caught.message}` : "Image retry stopped",
        };
        throw caught;
      }
      markWarm("image");
      let evaluated: EvaluationResult;
      try {
        evaluated = await runTimed("eval", () => callEvaluate(image, currentPrompt, currentAnatomy));
        markWarm("eval");
      } catch (caught) {
        if (best) return {
          ...best,
          retryCount: attempt,
          warning: caught instanceof Error ? `Evaluation retry stopped: ${caught.message}` : "Evaluation retry stopped",
        };
        return {
          image,
          prompt: currentPrompt,
          anatomy: currentAnatomy,
          payload: currentPayload,
          evaluation: null,
          retryCount: attempt,
          warning: caught instanceof Error ? caught.message : "Evaluation unavailable",
        };
      }

      const candidate: QualityControlledImage = {
        image,
        prompt: currentPrompt,
        anatomy: currentAnatomy,
        payload: currentPayload,
        evaluation: evaluated,
        retryCount: attempt,
        warning: null,
      };
      if (!best || evaluationRank(evaluated) > evaluationRank(best.evaluation!)) best = candidate;
      if (evaluationPassed(evaluated)) return candidate;
      correction = retryFeedbackFor(evaluated);
    }

    return { ...best!, retryCount: 2, warning: "Quality threshold was not reached; showing the best of three attempts." };
  };

  const localizeAnatomy = async (image: string, anatomy: AnatomySpec, allowGeneric = false): Promise<AnatomyAnnotation[]> => {
    const priorAnnotations = visibleImage.current === image ? anatomyAnnotations : [];
    setLocalizationError(null);
    if (!allowGeneric && (!anatomy.is_anatomy || !anatomy.organ)) return [];
    const labelingStartedAt = Date.now();
    setActiveTimers(current => ({ ...current, labels: labelingStartedAt }));
    setLabelBusy(true);
    try {
      let data: Record<string, any>;
      const cloud = cloudGeneration.current;
      const sourceId = cloud?.item.imageBase64 === image ? cloud.item.id : currentHistoryId;
      if (cloudEnabled() && sourceId) {
        if (cloud?.labelJobId) { await waitJob(cloud.labelJobId); cloud.labelJobId = null; }
        else await runJob({kind:"labels",generation_id:sourceId,speed_mode:speedMode});
        const item = await getCloudHistory(sourceId);
        data = { annotations:item.anatomyAnnotations || [] };
      } else {
      const response = await modelRequest("interactive", INTERACTIVE_AGENT_URL, "/auto-labels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_base64: image,
          domain: anatomy.is_anatomy ? "anatomy" : "generic",
          organ: anatomy.organ || "subject",
          view: anatomy.view_description || anatomy.view || "",
          speed_mode: speedMode,
        }),
      });
      data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(errorMessage(data, `Auto-label HTTP ${response.status}`));
      if (data.error) throw new Error(String(data.error));
      }
      const annotations: AnatomyAnnotation[] = (Array.isArray(data.annotations) ? data.annotations : [])
        .map((item: Partial<AnatomyAnnotation>) => {
          const label = extractAnatomyLabel(typeof item.label === "string" ? item.label : "");
          if (
            !label || (item.verified !== true && !item.user_edited) ||
            typeof item.anchor_x !== "number" || typeof item.anchor_y !== "number" ||
            typeof item.label_x !== "number" || typeof item.label_y !== "number" ||
            typeof item.confidence !== "number" || (!item.user_edited && item.confidence < 0.75) ||
            item.anchor_x < 0 || item.anchor_x > 1 || item.anchor_y < 0 || item.anchor_y > 1
          ) return null;
          return { ...item, label } as AnatomyAnnotation;
        })
        .filter((item: AnatomyAnnotation | null): item is AnatomyAnnotation => item !== null);
      if (visibleImage.current === image) setAnatomyAnnotations(annotations);
      markWarm("interactive");
      setOutcomes(current => ({ ...current, labels: "completed" }));
      return annotations;
    } catch (caught) {
      setOutcomes(current => ({ ...current, labels: "failed" }));
      if (visibleImage.current === image) setLocalizationError(caught instanceof Error ? caught.message : "Automatic labeling failed");
      return priorAnnotations;
    } finally {
      setLabelBusy(false);
      setTimings(current => ({ ...current, labels: Date.now() - labelingStartedAt }));
      setActiveTimers(current => { const next = { ...current }; delete next.labels; return next; });
    }
  };

  const generateSketch = async (feedback = "") => {
    if (isLoading || threedRequestInFlight.current || !sketchStrokes.some((stroke) => stroke.tool === "pen")) return;
    if (!SKETCH_AGENT_URL) { setError("Sketch service is not configured. Set EXPO_PUBLIC_SKETCH_AGENT_URL."); return; }
    setError(null); setStage("generating");
    setThreedStage("idle"); setGlbBase64(null); setGlbSizeKb(undefined); setThreedError(null);
    try {
      const data = await runTimed("image", async () => {
        if (cloudEnabled()) {
          const result = await cloudGenerate({kind:"sketch",prompt:prompt.trim(),mode:"sketch",sketch:{strokes:sketchStrokes,instruction:[prompt.trim(),feedback].filter(Boolean).join(". "),control_strength:sketchStrength}});
          return {image_base64:result.image,prompt:result.prompt,generation_metadata:result.sketchMetadata,
            anatomy_spec:result.anatomy,quality_warning:result.warning,retry_count:result.retryCount};
        }
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 600_000);
        try {
          const response = await fetch(SKETCH_AGENT_URL + "/generate/start", {
            method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
            body: JSON.stringify({ strokes: sketchStrokes, instruction: [prompt.trim(), feedback].filter(Boolean).join(". "), control_strength: sketchStrength }),
          });
          const body = await response.json().catch(() => ({}));
          if (!response.ok || body.error) throw new Error(errorMessage(body, "Sketch generation failed"));
          if (!body.call_id) throw new Error("Sketch service returned no job ID");
          const deadline = Date.now() + 600_000;
          while (Date.now() < deadline) {
            await delay(2500);
            const result = await fetch(SKETCH_AGENT_URL + "/generate/result/" + encodeURIComponent(body.call_id), { signal: controller.signal });
            if (result.status === 202) continue;
            const output = await result.json().catch(() => ({}));
            if (!result.ok || output.error) throw new Error(errorMessage(output, "Sketch generation failed"));
            if (!output.image_base64) throw new Error("Sketch service returned no image");
            return output;
          }
          throw new Error("Sketch generation timed out. Please retry.");
        } finally { clearTimeout(timer); }
      });
      const anatomy: AnatomySpec = data.anatomy_spec ?? { is_anatomy: false };
      const payload: EnhancedPromptPayload = { schema_version: "1.0", final_prompt: data.prompt, anatomy_spec: anatomy, route: anatomy.is_anatomy ? "anatomy" : "generic" };
      setSketchMetadata(data.generation_metadata); setEnhancedPrompt(data.prompt); setEnhancedPromptJson(payload);
      setAnatomySpec(anatomy); setAnatomyAnnotations([]); setEvaluation(null); setEvaluationWarning(data.quality_warning ?? null);
      setEvaluationRetries(data.retry_count ?? 0);
      setImageBase64(data.image_base64); setImageOutputId(createOutputId("image"));
      const historyId = await archiveResult({ image: data.image_base64, prompt: data.prompt, anatomy, payload, evaluation: null, retryCount: data.retry_count ?? 0, warning: data.quality_warning ?? null, sketchMetadata: data.generation_metadata });
      setStage("done");
      void localizeAnatomy(data.image_base64, anatomy, true).then(annotations =>
        historyId ? updateHistoryItem(historyId,{anatomyAnnotations:annotations}).catch(() => undefined) : undefined);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sketch generation failed");
      setStage(imageBase64 ? "done" : "idle");
    }
  };

  const handleSubmit = async () => {
    if (workspace === "sketch") {
      if (isLoading || threedRequestInFlight.current) return;
      if (!currentChatId.current) currentChatId.current = createOutputId("chat");
      await generateSketch(); return;
    }
    if (!prompt.trim() || isLoading || threedRequestInFlight.current) return;
    reset();
    currentChatId.current = createOutputId("chat");
    if (workspace === "general") {
      const rawPrompt = prompt.trim();
      const anatomy: AnatomySpec = { is_anatomy: false };
      const payload: EnhancedPromptPayload = {
        schema_version: "1.0",
        final_prompt: rawPrompt,
        anatomy_spec: anatomy,
        route: "generic",
        anatomy_mode: null,
      };
      try {
        setStage("generating");
        const image = await runTimed("image", () => callGenerate(rawPrompt, anatomy, undefined, undefined, false));
        const result: QualityControlledImage = {
          image,
          prompt: rawPrompt,
          anatomy,
          payload,
          evaluation: null,
          retryCount: 0,
          warning: null,
        };
        setEnhancedPrompt(rawPrompt);
        setEnhancedPromptJson(null);
        setAnatomySpec(anatomy);
        setImageBase64(image);
        setEvaluation(null);
        setImageOutputId(createOutputId("image"));
        markWarm("image");
        setStage("done");
        await archiveResult(result);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Image generation failed");
        setStage("idle");
      }
      return;
    }
    try {
      setStage("enhancing");
      const enhanced = await runTimed("prompt", () => callEnhance(prompt.trim()));
      setAnatomySpec(enhanced.anatomy);
      markWarm("prompt");
      setEnhancedPrompt(enhanced.prompt);
      setEnhancedPromptJson(enhanced.payload);
      setPromptOutputId(createOutputId("prompt"));
      setStage("preview");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
      setStage("idle");
    }
  };

  const generateEnhancedPreview = async () => {
    if (!enhancedPrompt || !enhancedPromptJson || stage !== "preview") return;
    setError(null);
    try {
      setStage("generating");
      const result = await runTimed("image", () => generateWithQualityControl(
        enhancedPrompt,
        anatomySpec,
        enhancedPromptJson,
      ));
      setEnhancedPrompt(result.prompt);
      setEnhancedPromptJson(result.payload);
      setAnatomySpec(result.anatomy);
      setImageBase64(result.image);
      setEvaluation(result.evaluation);
      setEvaluationRetries(result.retryCount);
      setEvaluationWarning(result.warning);
      setImageOutputId(createOutputId("image"));
      setStage("done");
      const historyId = await archiveResult(result);
      void localizeAnatomy(result.image, result.anatomy).then((annotations) =>
        historyId && annotations.length ? updateHistoryItem(historyId, { anatomyAnnotations: annotations }).catch(() => undefined) : undefined,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Image generation failed");
      setStage("preview");
    }
  };

  const regenerateFromPromptFeedback = async (feedback: string, feedbackId: string, outputId: string) => {
    setPromptRetryLink({ feedbackId, outputId });
    setImageBase64(null);
    setImageOutputId(null);
    setImageRetryLink(null);
    setEvaluation(null);
    setEvaluationRetries(0);
    setEvaluationWarning(null);
    setThreedStage("idle");
    setGlbBase64(null);
    setError(null);
    try {
      setStage("enhancing");
      const enhanced = await runTimed("prompt", () => callEnhance(prompt.trim(), feedback));
      const nextPrompt = enhanced.prompt;
      setAnatomySpec(enhanced.anatomy);
      setEnhancedPrompt(nextPrompt);
      setEnhancedPromptJson(enhanced.payload);
      setPromptOutputId(createOutputId("prompt"));
      markWarm("prompt");
      setStage("preview");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Regeneration failed");
      setStage("preview");
    }
  };

  const regenerateImageFromFeedback = async (feedback: string, feedbackId: string, outputId: string) => {
    if (workspace === "sketch") { await generateSketch(feedback); return; }
    setImageRetryLink({ feedbackId, outputId });
    setThreedStage("idle");
    setGlbBase64(null);
    setThreedError(null);
    setError(null);
    if (workspace === "general") {
      const rawPrompt = prompt.trim();
      const anatomy: AnatomySpec = { is_anatomy: false };
      const payload: EnhancedPromptPayload = { schema_version: "1.0", final_prompt: rawPrompt, anatomy_spec: anatomy, route: "generic", anatomy_mode: null };
      try {
        setStage("generating");
        const image = await runTimed("image", () => callGenerate(rawPrompt, anatomy, feedback, undefined, false));
        setImageBase64(image);
        setEvaluation(null);
        setEvaluationRetries(0);
        setImageOutputId(createOutputId("image"));
        markWarm("image");
        setStage("done");
        await archiveResult({ image, prompt: rawPrompt, anatomy, payload, evaluation: null, retryCount: 0, warning: null });
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Image regeneration failed");
        setStage("done");
      }
      return;
    }
    try {
      setStage("generating");
      const finalPrompt = enhancedPrompt || prompt.trim();
      const payload = enhancedPromptJson;
      if (!payload) throw new Error("Validated prompt payload is unavailable");
      const result = await runTimed("image", () => generateWithQualityControl(finalPrompt, anatomySpec, payload, feedback));
      setEnhancedPrompt(result.prompt);
      setEnhancedPromptJson(result.payload);
      setAnatomySpec(result.anatomy);
      setImageBase64(result.image);
      setEvaluation(result.evaluation);
      setEvaluationRetries(result.retryCount);
      setEvaluationWarning(result.warning);
      setImageOutputId(createOutputId("image"));
      setStage("done");
      const historyId = await archiveResult(result);
      void localizeAnatomy(result.image, result.anatomy).then((annotations) =>
        historyId && annotations.length ? updateHistoryItem(historyId, { anatomyAnnotations: annotations }).catch(() => undefined) : undefined,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Image regeneration failed");
      setStage("done");
    }
  };

  const pickThreeDImage = async () => {
    if (isLoading || pickingThreeD || threedRequestInFlight.current) return;
    setPickingThreeD(true);
    try {
      const result = await DocumentPicker.getDocumentAsync({ type: THREED_IMAGE_TYPES, multiple: false, copyToCacheDirectory: true, base64: true });
      if (result.canceled) return;
      const asset = result.assets[0];
      validateThreeDImage(asset.size ?? asset.file?.size, asset.mimeType, asset.name);
      const encoded = Platform.OS === "web" ? asset.base64 || asset.uri : await new File(asset.uri).base64();
      if (Platform.OS === "web" && asset.uri.startsWith("blob:")) URL.revokeObjectURL(asset.uri);
      const base64 = encoded.replace(/^data:[^,]*,/, "");
      if (!base64 || base64.startsWith("blob:") || base64.startsWith("file:")) throw new Error("Could not read this image. Please choose it again.");
      // Decode before accepting the source so corrupt images cannot start a GPU job.
      const uri = `data:${asset.mimeType || "image/png"};base64,${base64}`;
      await new Promise<void>((resolve, reject) => Image.getSize(uri, () => resolve(), () => reject(new Error("This image could not be opened. Choose another image."))));
      setUploadedThreeD({ base64, uri, name: asset.name, id: createOutputId("upload") });
      setThreedStage("idle"); setGlbBase64(null); setGlbSizeKb(undefined); setThreedError(null);
    } catch (error) {
      setThreedError(error instanceof Error ? error.message : "Could not open this image.");
    } finally { setPickingThreeD(false); }
  };

  const openSaved3D = async (id: string) => {
    if (threedRequestInFlight.current) return;
    threedRequestInFlight.current = true; setThreedError(null); setThreedStage("converting"); setJobPhase("opening saved model");
    try {
      const model = await getCloudModel(id);
      setModelAsset(model); setGlbBase64(null); setGlbSizeKb(model.sizeKb); setThreedStage("done");
      setOutcomes(current => ({ ...current, threed: "completed" }));
    } catch (failure) { setThreedError(failure instanceof Error ? failure.message : "Unable to open the saved model."); setThreedStage("idle"); }
    finally { threedRequestInFlight.current = false; }
  };
  const handleCloud3D = async () => {
    if ((!currentHistoryId && !uploadedThreeD) || threedRequestInFlight.current) return;
    const sourceKey = uploadedThreeD?.id || currentHistoryId;
    if (savedThreeD?.sourceKey === sourceKey && !modelAsset) { await openSaved3D(savedThreeD.id); return; }
    threedRequestInFlight.current = true; setThreedStage("converting"); setThreedError(null);
    setGlbBase64(null); setModelAsset(null); setGlbSizeKb(undefined);
    setJobPhase("queued");
    try {
      await runTimed("threed", async () => {
        let sourceId = uploadedThreeD?.historyId ?? currentHistoryId;
        if (uploadedThreeD && !uploadedThreeD.historyId) {
          setJobPhase("preparing image");
          const imported = await studioRequest<{ id: string }>("/studio/import", { method: "POST", body: JSON.stringify({
            legacy_id: uploadedThreeD.id, created_at: new Date().toISOString(), image_base64: uploadedThreeD.base64,
            metadata: { prompt: `3D model from ${uploadedThreeD.name}`, enhancedPrompt: `Uploaded image: ${uploadedThreeD.name}`, mode: "general", speedMode },
          }) });
          sourceId = imported.id;
          setUploadedThreeD(current => current ? { ...current, historyId: imported.id } : current);
        }
        const job = await runJob({kind:"threed",generation_id:sourceId,speed_mode:speedMode},setJobPhase);
        if (!job.result?.history_id) throw new Error("3D job returned no saved history");
        setSavedThreeD({ id: job.result.history_id, sourceKey });
        setJobPhase("opening saved model");
        const model = await getCloudModel(job.result.history_id);
        setModelAsset(model); setGlbBase64(null); setGlbSizeKb(model.sizeKb); setThreedStage("done");
        markHistoryChanged();
        markWarm("threed");
      });
    } catch(e) { setThreedError(e instanceof Error?e.message:"3D conversion failed"); setThreedStage("idle"); }
    finally { threedRequestInFlight.current = false; }
  };

  const handleConvertTo3D = async () => {
    if (isLoading || pickingThreeD) return;
    if (cloudEnabled() && (uploadedThreeD || (currentHistoryId && /^[0-9a-f-]{36}$/i.test(currentHistoryId)))) { await handleCloud3D(); return; }
    const sourceImage = uploadedThreeD?.base64 ?? imageBase64;
    if (!sourceImage || threedRequestInFlight.current) return;
    threedRequestInFlight.current = true;
    const conversionHistoryId = uploadedThreeD?.id ?? currentHistoryId;
    const fingerprint = imageFingerprint(sourceImage);
    const storedJob = readStoredThreeDJob();
    const requestId = storedJob?.imageFingerprint === fingerprint && storedJob.speedMode === speedMode
      ? storedJob.requestId
      : createRequestId();
    storeThreeDJob({ requestId, imageFingerprint: fingerprint, speedMode });
    const conversionStartedAt = Date.now();
    setActiveTimers((current) => ({ ...current, threed: conversionStartedAt }));
    setThreedStage("converting");
    setJobPhase("queued");
    setThreedError(null);
    setGlbBase64(null);
    try {
      if (uploadedThreeD) await saveHistoryItem({ id: uploadedThreeD.id, createdAt: new Date().toISOString(), prompt: `3D model from ${uploadedThreeD.name}`, enhancedPrompt: `Uploaded image: ${uploadedThreeD.name}`, imageBase64: sourceImage, mode: "general", speedMode });
      if (conversionHistoryId) await updateHistoryItem(conversionHistoryId, { threeDJob: { status: "converting", requestId } });
      let response: Response;
      try {
        response = await fetch(`${THREED_AGENT_URL}/convert/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            image_base64: sourceImage,
            request_id: requestId,
            speed_mode: speedMode,
            texture: true,
            num_inference_steps: 30,
          }),
        });
      } catch {
        throw new Error(`Could not reach 3D Agent at ${THREED_AGENT_URL}. Check that threed-agent is served or deployed.`);
      }
      const { payload: started, raw: startedRaw } = await readApiResponse(response);
      if (!response.ok) {
        if (response.status >= 400 && response.status < 500) clearStoredThreeDJob();
        throw new Error(threeDApiError(response, started, startedRaw, `3D Convert HTTP ${response.status}`));
      }
      const callId = typeof started.call_id === "string" ? started.call_id : null;
      if (!callId) throw new Error("3D agent did not return a job ID");
      if (conversionHistoryId) await updateHistoryItem(conversionHistoryId, { threeDJob: { status: "converting", requestId, callId } });

      const deadline = Date.now() + THREED_MAX_WAIT_MS;
      while (Date.now() < deadline) {
        await delay(THREED_POLL_INTERVAL_MS);
        let resultResponse: Response;
        try {
          resultResponse = await fetch(
            `${THREED_AGENT_URL}/convert/result/${encodeURIComponent(callId)}`,
          );
        } catch {
          // Polling is idempotent; tolerate a transient Modal connection drop.
          await delay(THREED_POLL_INTERVAL_MS);
          continue;
        }
        if (resultResponse.status === 202) {
          const { payload: progress } = await readApiResponse(resultResponse);
          if (typeof progress.stage === "string") setJobPhase(progress.stage);
          continue;
        }
        if ([408, 429, 502, 503, 504].includes(resultResponse.status)) continue;
        const { payload: data, raw: resultRaw } = await readApiResponse(resultResponse);
        if (!resultResponse.ok) {
          clearStoredThreeDJob();
          throw new Error(threeDApiError(resultResponse, data, resultRaw, `3D Result HTTP ${resultResponse.status}`));
        }
        if (data.error) {
          clearStoredThreeDJob();
          throw new Error(String(data.error));
        }
        const generatedGlb = typeof data.glb_base64 === "string" ? data.glb_base64 : null;
        const generatedSizeKb = typeof data.size_kb === "number" ? data.size_kb : undefined;
        if (!generatedGlb) {
          clearStoredThreeDJob();
          throw new Error("Empty GLB response");
        }
        setGlbBase64(generatedGlb);
        setGlbSizeKb(generatedSizeKb);
        setThreedStage("done");
        setOutcomes(current => ({ ...current, threed: "completed" }));
        clearStoredThreeDJob();
        markWarm("threed");
        if (conversionHistoryId) {
          await updateHistoryItem(conversionHistoryId, { glbBase64: generatedGlb, glbSizeKb: generatedSizeKb, threeDJob: { status: "done", requestId, callId } });
        }
        return;
      }
      throw new Error("3D conversion exceeded its processing deadline. Check the job status before retrying.");
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "3D conversion failed";
      setOutcomes(current => ({ ...current, threed: "failed" }));
      setThreedError(message);
      if (conversionHistoryId) await updateHistoryItem(conversionHistoryId, { threeDJob: { status: "failed", requestId, error: message } }).catch(() => undefined);
      setThreedStage("idle");
    } finally {
      threedRequestInFlight.current = false;
      setTimings((current) => ({ ...current, threed: Date.now() - conversionStartedAt }));
      setActiveTimers((current) => {
        const next = { ...current };
        delete next.threed;
        return next;
      });
    }
  };

  const loadingLabel = stage === "enhancing"
    ? "Preparing your anatomy instruction…"
    : workspace === "sketch" ? "Turning your drawing into an image…" : workspace === "general"
      ? "Creating your educational image…"
      : "Creating and checking your anatomy image…";

  return (
    <SafeAreaView style={styles.safeArea}>
      <StudioSettings open={settingsOpen} onClose={() => setSettingsOpen(false)} accessToken={accessToken} apiUrl={BACKEND_HEALTH_URL} />
      <StatusBar style={themeMode === "dark" ? "light" : "dark"} />
      {workspace !== "history" && (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Start a new chat"
          disabled={isLoading}
          onPress={() => {
            const clear = () => { reset(); setPrompt(""); setSketchStrokes([]); setSketchMetadata(undefined); setSketchCanvasKey(value => value + 1); };
            if (!unsavedDraft) { clear(); return; }
            if (Platform.OS === "web") { if (window.confirm("Discard this unsaved prompt or drawing and start again?")) clear(); }
            else Alert.alert("Start again?", "Your unsaved prompt or drawing will be discarded.", [{ text: "Cancel", style: "cancel" }, { text: "Discard", style: "destructive", onPress: clear }]);
          }}
          style={({ pressed }) => [styles.floatingNewPrompt, pressed && styles.pressed, isLoading && shared.disabled]}
        >
          <Icon color={colors.onButton} name="wand" size={24} />
        </Pressable>
      )}
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.container}>
            <View style={[styles.header, screenWidth < 600 && { gap: 20 }]}>
              <View style={styles.topBar}>
                <View style={styles.brandRow}>
                  <View style={styles.brandMark}><Text style={styles.brandMarkText}>L</Text></View>
                  <LearnXHomeLink color={colors.text} />
                </View>
                <View style={styles.headerActions}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`Switch to ${themeMode === "dark" ? "light" : "dark"} mode`}
                  onPress={toggleTheme}
                  style={({ pressed }) => [styles.themeToggle, pressed && styles.pressed]}
                >
                  <Icon color={colors.text} name={themeMode === "dark" ? "sun" : "moon"} size={20} />
                </Pressable>
                <Pressable accessibilityRole="button" accessibilityLabel="Studio settings" onPress={() => setSettingsOpen(true)} style={styles.themeToggle}><Icon name="help" color={colors.text} size={20} /></Pressable>
                {STUDIO_API_URL && studioSession?.configured && <StudioSessionPanel email={studioSession.email} name={studioSession.name} signOut={studioSession.signOut} changePassword={studioSession.changePassword} />}
                </View>
              </View>
              <View nativeID="studio-hero" style={[styles.heroGrid, screenWidth < 600 && { gap: 16, paddingBottom: 8 }]}>
                <View style={styles.heroCopy}>
                  <Text style={styles.eyebrow}>A VISUAL LEARNING STUDIO</Text>
                  <EditorialHeadline accessibilityRole="header" style={[styles.title, screenWidth < 600 && styles.titleCompact]}>Make ideas visible.</EditorialHeadline>
                  <Text style={[styles.subtitle, screenWidth < 600 && { fontSize: 16, lineHeight: 23, marginTop: 10 }]}>
                    Create thoughtful educational imagery, explore human anatomy, and turn flat visuals into interactive learning experiences.
                  </Text>
                </View>
                <View style={[styles.systemCard, screenWidth < 600 && { padding: 12 }]}>
                  <Pressable accessibilityRole="button" accessibilityLabel="Toggle service details" accessibilityState={{ expanded: statusOpen }} onPress={() => setStatusOpen(!statusOpen)} style={[styles.systemHeader, !statusOpen && { marginBottom: 0 }]}>
                    <View><Text style={styles.systemKicker}>STUDIO STATUS</Text><Text style={styles.systemTitle}>Creative engine</Text></View>
                    <View style={styles.liveBadge}><StatusDot color={backendHealth === "ok" ? colors.success : backendHealth === "error" ? colors.danger : colors.textDim} /><Text style={styles.liveBadgeText}>{backendHealth === "ok" ? "Connected" : backendHealth === "checking" ? "Checking" : "Unavailable"}</Text></View>
                  </Pressable>
                  {statusOpen && <><View style={[shared.wrap, styles.healthWrap]}>
                    <HealthPill label="Prompt" now={now} status={promptHealth} warmUntil={warmUntil.prompt} />
                    <HealthPill label="Image" now={now} status={imageHealth} warmUntil={warmUntil.image} />
                    <HealthPill label="Eval" now={now} status={evalHealth} warmUntil={warmUntil.eval} />
                    <HealthPill label="Interact" now={now} status={interactiveHealth} warmUntil={warmUntil.interactive} />
                    <HealthPill label="3D" now={now} status={displayedThreeDHealth} warmUntil={warmUntil.threed} />
                  </View>
                  <Text style={styles.warmNote}>Services may need time to warm up after inactivity.</Text></>}
                </View>
              </View>
            </View>

            <View accessibilityRole="tablist" style={[styles.workspaceTabs, workspaceGridStyle]}>
              <Pressable accessibilityRole="tab" accessibilityState={{ selected: workspace === "sketch", disabled: isLoading }} disabled={isLoading}
                onPress={() => selectWorkspace("sketch")} style={[styles.workspaceTab, screenWidth < 600 && { padding: 8, minHeight: 66, flexDirection: "column", gap: 6 }, workspace === "sketch" && styles.workspaceTabActive]}>
                <Icon name="pencil" color={workspace === "sketch" ? colors.primaryBright : colors.textMuted} size={20} />
                <View style={[styles.workspaceTabCopy, screenWidth < 600 && { alignItems: "center" }]}><Text style={[styles.workspaceTabTitle, screenWidth < 600 && { fontSize: 11, textAlign: "center" }, workspace === "sketch" && styles.workspaceTabTitleActive]}>{screenWidth < 600 ? "Draw" : "Draw to Image"}</Text><Text style={[styles.workspaceTabDescription, screenWidth < 600 && { display: "none" }]}>Sketch + optional instruction</Text></View>
              </Pressable>
              <Pressable
                accessibilityRole="tab"
                accessibilityState={{ selected: workspace === "general", disabled: isLoading }}
                disabled={isLoading}
                onPress={() => selectWorkspace("general")}
                style={({ pressed }) => [styles.workspaceTab, screenWidth < 600 && { padding: 8, minHeight: 66, flexDirection: "column", gap: 6 }, workspace === "general" && styles.workspaceTabActive, pressed && styles.pressed, isLoading && shared.disabled]}
              >
                <Icon color={workspace === "general" ? colors.primaryBright : colors.textMuted} name="image" size={20} />
                <View style={[styles.workspaceTabCopy, screenWidth < 600 && { alignItems: "center" }]}>
                  <Text style={[styles.workspaceTabTitle, screenWidth < 600 && { fontSize: 11, textAlign: "center" }, workspace === "general" && styles.workspaceTabTitleActive]}>{screenWidth < 600 ? "Image" : "Image Generation"}</Text>
                  <Text style={[styles.workspaceTabDescription, screenWidth < 600 && { display: "none" }]}>General educational visuals and diagrams</Text>
                </View>
              </Pressable>
              <Pressable
                accessibilityRole="tab"
                accessibilityState={{ selected: workspace === "anatomy", disabled: isLoading }}
                disabled={isLoading}
                onPress={() => selectWorkspace("anatomy")}
                style={({ pressed }) => [styles.workspaceTab, screenWidth < 600 && { padding: 8, minHeight: 66, flexDirection: "column", gap: 6 }, workspace === "anatomy" && styles.workspaceTabActive, pressed && styles.pressed, isLoading && shared.disabled]}
              >
                <Icon color={workspace === "anatomy" ? colors.primaryBright : colors.textMuted} name="heart" size={20} />
                <View style={[styles.workspaceTabCopy, screenWidth < 600 && { alignItems: "center" }]}>
                  <Text style={[styles.workspaceTabTitle, screenWidth < 600 && { fontSize: 11, textAlign: "center" }, workspace === "anatomy" && styles.workspaceTabTitleActive]}>{screenWidth < 600 ? "Anatomy" : "Human Anatomy Generation"}</Text>
                  <Text style={[styles.workspaceTabDescription, screenWidth < 600 && { display: "none" }]}>Validated organs, views, labels, and 3D</Text>
                </View>
              </Pressable>
              <Pressable
                accessibilityRole="tab"
                accessibilityState={{ selected: workspace === "history", disabled: isLoading }}
                disabled={isLoading}
                onPress={() => selectWorkspace("history")}
                style={({ pressed }) => [styles.workspaceTab, screenWidth < 600 && { padding: 8, minHeight: 66, flexDirection: "column", gap: 6 }, workspace === "history" && styles.workspaceTabActive, pressed && styles.pressed, isLoading && shared.disabled]}
              >
                <Icon color={workspace === "history" ? colors.primaryBright : colors.textMuted} name="layers" size={20} />
                <View style={[styles.workspaceTabCopy, screenWidth < 600 && { alignItems: "center" }]}>
                  <Text style={[styles.workspaceTabTitle, screenWidth < 600 && { fontSize: 11, textAlign: "center" }, workspace === "history" && styles.workspaceTabTitleActive]}>History</Text>
                  <Text style={[styles.workspaceTabDescription, screenWidth < 600 && { display: "none" }]}>{cloudEnabled() ? "Your cloud and local creations" : "Your saved local conversations"}</Text>
                </View>
              </Pressable>
            </View>

            {cloudEnabled() && <JobsPanel onResume={restoreHistory} />}
            <View style={workspace === "history" ? undefined : { display: "none" }}>
              <HistoryPanel active={workspace === "history"} onResume={restoreHistory} />
            </View>
            {workspace !== "history" && <>
            <View style={[shared.card, styles.promptCard]}>
              {workspace === "sketch" && <>
                <Text style={styles.promptLabel}>Draw your subject</Text>
                <SketchCanvas key={sketchCanvasKey} strokes={sketchStrokes} disabled={isLoading} onChange={(strokes) => { reset(); setSketchStrokes(strokes); setSketchMetadata(undefined); }} />
                <Text style={styles.hint}>Drawing adherence</Text>
                <View style={styles.actionButtons}>{[{ label: "Creative", value: 0.55 }, { label: "Balanced", value: 0.85 }, { label: "Strict", value: 1.1 }].map((option) =>
                  <Pressable key={option.label} accessibilityRole="button" accessibilityLabel={option.label + " drawing adherence"} aria-pressed={sketchStrength === option.value} accessibilityState={{ selected: sketchStrength === option.value, disabled: isLoading }} disabled={isLoading} onPress={() => setSketchStrength(option.value)} style={[styles.optionButton, sketchStrength === option.value && styles.optionButtonSelected, isLoading && shared.disabled]}>
                    <Text style={[styles.optionText, sketchStrength === option.value && styles.optionTextSelected]}>{sketchStrength === option.value ? "✓ " : ""}{option.label}</Text>
                  </Pressable>)}</View>
                {sketchMetadata && <Text style={styles.hint}>{sketchMetadata.subject ? `Detected: ${sketchMetadata.subject} · ` : ""}Seed {sketchMetadata.seed}</Text>}
              </>}
              <Text style={styles.promptLabel}>{workspace === "sketch" ? "Additional instruction (optional)" : workspace === "anatomy" ? "Human Anatomy Prompt" : "Your Prompt"}</Text>
              <TextInput
                accessibilityLabel="Your prompt"
                editable={!isLoading}
                multiline
                numberOfLines={4}
                onChangeText={handlePromptChange}
                placeholder={workspace === "sketch" ? "Optional: e.g. a colorful fish illustration on a white background" : workspace === "anatomy"
                  ? "e.g. anterior view of the human heart for medical students"
                  : "e.g. photosynthesis diagram for 8th graders with labeled chloroplasts"}
                placeholderTextColor={colors.textDim}
                style={styles.promptInput}
                textAlignVertical="top"
                value={prompt}
              />
              {stage === "idle" && workspace !== "sketch" && <View style={[shared.wrap, { gap: 8, marginTop: 10 }]}>{(workspace === "anatomy" ? ["Anterior view of the human heart", "Human lungs and airways", "Lateral view of the human brain"] : ["Photosynthesis for eighth graders", "The water cycle with clear labels", "Animal cell structure"]).map(example => <Pressable key={example} accessibilityRole="button" disabled={isLoading} style={styles.ghostButton} onPress={() => handlePromptChange(example)}><Text style={styles.ghostText}>{example}</Text></Pressable>)}</View>}
              {workspace !== "sketch" && <View style={[shared.wrap, { gap: 8, marginTop: 14 }]}><Text style={styles.optionLabel}>Speed</Text><SpeedSelector options={SPEED_MODES} value={speedMode} disabled={isLoading} onChange={setSpeedMode} /></View>}
              <View style={styles.promptFooter}>
                <Text style={styles.hint}>
                  {workspace === "sketch" ? "Create a finished colour image on a white background, ready for 3D conversion. Human anatomy receives extra structure checks. Add the subject or intended view if needed." : workspace === "anatomy"
                    ? "Choose an organ and view. Review the enhanced instruction before creating your image."
                    : "Describe your subject, audience and preferred visual style."}
                </Text>
                <View style={styles.actionButtons}>
                  <ActionButton
                    disabled={isLoading || (workspace === "sketch" ? !sketchStrokes.some((stroke) => stroke.tool === "pen") : !prompt.trim())}
                    icon={workspace === "anatomy" ? "sparkles" : "image"}
                    label={workspace === "sketch" ? (stage === "generating" ? "Generating..." : "Generate from Drawing") : workspace === "general" ? (stage === "generating" ? "Generating..." : "Generate Image") : (stage === "enhancing" ? "Enhancing..." : "Enhance Prompt")}
                    loading={isLoading}
                    onPress={handleSubmit}
                  />
                </View>
              </View>
            </View>

            {(stage === "enhancing" || stage === "generating") && (
              <View style={[shared.card, styles.loadingCard]} accessibilityLiveRegion="polite">
                <ActivityIndicator color={colors.primaryBright} size="large" />
                <Text style={styles.loadingText}>{cloudEnabled() && jobPhase ? friendlyPhase(jobPhase, loadingLabel) : loadingLabel}</Text>
                <View style={styles.stageRow}>
                  {workspace === "anatomy" && <StagePill active={stage === "enhancing"} done={stage === "generating"} label="Enhance" />}
                  <StagePill active={stage === "generating"} label="Generate" />
                </View>
                <Text style={styles.hint}>{startedAt ? `${formatDuration(Math.max(0, now - startedAt))} elapsed · ` : ""}{cloudEnabled() ? "Your creation continues in the background." : "Keep this page open while your creation is processing."}</Text>
              </View>
            )}

            {(Object.keys(timings).length > 0 || Object.keys(activeTimers).length > 0) && (
              <PerformanceInsights activeTimers={activeTimers} now={now} timings={timings} outcomes={outcomes} />
            )}

            {error && <View style={{ gap: 10 }}><ErrorBanner title="Unable to complete this request" message={error} /><ActionButton icon="refresh" label="Retry request" disabled={isLoading} onPress={handleSubmit} /></View>}

            {enhancedPromptJson && stage !== "enhancing" && (
              <View style={shared.card}>
                <View style={styles.cardHeader}>
                  <View style={styles.inlineInfo}><Icon color={colors.primaryBright} name="sparkles" size={15} /><Text style={styles.badge}>Review your instruction</Text></View>
                  <Text style={styles.modelTag}>
                    {enhancedPromptJson.route === "anatomy"
                      ? `Anatomy · ${enhancedPromptJson.anatomy_mode === "verified" ? "verified catalog" : "general"}`
                      : "General image"}
                  </Text>
                </View>
                <Text style={styles.enhancedPrompt}>{enhancedPromptJson.final_prompt}</Text>{detailsOpen && <Text selectable style={styles.hint}>{JSON.stringify(enhancedPromptJson, null, 2)}</Text>}
                {enhancedPromptJson.routing && (
                  <Text style={styles.hint}>
                    Selected by {enhancedPromptJson.routing.source === "qwen" ? "Qwen reasoning" : "routing rules"}
                    {typeof enhancedPromptJson.routing.confidence === "number" ? ` · ${Math.round(enhancedPromptJson.routing.confidence * 100)}% confidence` : ""}
                  </Text>
                )}
                {stage === "preview" && (
                  <View style={styles.actionButtons}>
                    <ActionButton icon="image" label="Generate Image" onPress={generateEnhancedPreview} />
                  </View>
                )}
                {promptOutputId && (stage === "preview" || stage === "done") && (
                  <FeedbackControls
                    key={promptOutputId}
                    agentName={enhancedPromptJson.route === "anatomy" ? "prompt-anatomy" : "prompt-generic"}
                    accessToken={accessToken}
                    apiUrl={BACKEND_HEALTH_URL}
                    inputContext={{ raw_prompt: prompt, mode: enhancedPromptJson.route, anatomy_mode: enhancedPromptJson.anatomy_mode }}
                    negativeReasons={enhancedPromptJson.route === "anatomy" ? ANATOMY_PROMPT_NEGATIVE : GENERIC_PROMPT_NEGATIVE}
                    onRegenerate={regenerateFromPromptFeedback}
                    outputId={promptOutputId}
                    outputSnapshot={{ enhanced_prompt_json: enhancedPromptJson }}
                    parentFeedbackId={promptRetryLink?.feedbackId}
                    parentOutputId={promptRetryLink?.outputId}
                    positiveReasons={enhancedPromptJson.route === "anatomy" ? ANATOMY_PROMPT_POSITIVE : GENERIC_PROMPT_POSITIVE}
                    sessionId={sessionId}
                  />
                )}
              </View>
            )}

            {imageBase64 && stage === "done" && (
              <View style={styles.resultSection}>
                {evaluationWarning && <ErrorBanner title="Quality-control notice" message={evaluationWarning} />}
                {evaluation && (
                  <View style={[shared.card, styles.qualityCard]}>
                    <View style={styles.cardHeader}>
                      <Text style={styles.badge}>Quality evaluation</Text>
                      <Text style={styles.modelTag}>{evaluationPassed(evaluation) ? "Approved" : "Best attempt"}</Text>
                    </View>
                    <Text style={styles.qualityScore}>Visual {evaluation.visualScore.toFixed(1)}/10 · Educational {evaluation.pedagogicalScore.toFixed(1)}/10 · Retries {evaluationRetries}/2</Text>
                    {!!evaluation.anatomyHardFailures.length && <Text style={styles.errorMessage}>Anatomy failures: {evaluation.anatomyHardFailures.join("; ")}</Text>}
                    {!!evaluation.feedback && <Text style={styles.hint}>{evaluation.feedback}</Text>}
                  </View>
                )}
                {workspace === "sketch" && <ActionButton icon="refresh" label="Regenerate from Drawing" disabled={isLoading} onPress={() => generateSketch()} />}
                <SectionTitle title="Interactive Image Analysis" subtitle="Tap an object or select a region to ask questions and explore its details." />
                {localizationError && <ErrorBanner title="Labels unavailable; clean image preserved" message={localizationError} />}
                <View style={styles.actionButtons}>
                  <ActionButton icon="tag" label={labelBusy ? "Labeling…" : "Label image automatically"} disabled={labelBusy || isLoading} onPress={() => { const sourceImage=imageBase64,sourceId=currentHistoryId; void localizeAnatomy(sourceImage,anatomySpec,true).then(items => sourceId ? updateHistoryItem(sourceId,{anatomyAnnotations:items}).catch(e=>setLocalizationError(e.message)) : undefined); }} />
                </View>
                <InteractiveCanvas
                  chatId={currentChatId.current ?? currentHistoryId ?? undefined}
                  accessToken={accessToken}
                  anatomyAnnotations={anatomyAnnotations}
                  generationId={currentHistoryId ?? undefined}
                  interactions={historyInteractions}
                  onAnnotationsChange={labelBusy ? undefined : (items) => { setAnatomyAnnotations(items); if(currentHistoryId) void updateHistoryItem(currentHistoryId,{anatomyAnnotations:items}).catch(e=>setLocalizationError("Label edits could not be saved: "+e.message)); }}
                  anatomyOrgan={anatomySpec.organ}
                  feedbackApiUrl={BACKEND_HEALTH_URL}
                  imageBase64={imageBase64}
                  imageFeedback={imageOutputId && <FeedbackControls
                    key={imageOutputId} agentName="image-agent" accessToken={accessToken} apiUrl={BACKEND_HEALTH_URL}
                    inputContext={{ prompt: enhancedPrompt || prompt }} negativeReasons={IMAGE_NEGATIVE}
                    outputId={imageOutputId} outputSnapshot={{ prompt: enhancedPrompt || prompt }}
                    parentFeedbackId={imageRetryLink?.feedbackId} parentOutputId={imageRetryLink?.outputId}
                    positiveReasons={IMAGE_POSITIVE} sessionId={sessionId}
                  />}
                  onInteractionComplete={(interaction) => {
                    if (visibleImage.current === imageBase64) setHistoryInteractions(current => [...current.filter(turn => turn.id !== interaction.id), interaction]);
                    if (currentHistoryId) void appendHistoryInteraction(currentHistoryId, interaction, cloudEnabled() && /^[0-9a-f-]{36}$/i.test(currentHistoryId)).catch(e=>setError("Interaction could not be saved: "+e.message));
                  }}
                  onOperationStart={(mode) => setActiveTimers(current => ({ ...current, [mode]: Date.now() }))}
                  onOperationComplete={(duration, mode, outcome) => {
                    setTimings((current) => ({ ...current, [mode]: duration }));
                    setOutcomes(current => ({ ...current, [mode]: outcome }));
                    setActiveTimers(current => { const next = { ...current }; delete next[mode]; return next; });
                    markWarm("interactive");
                  }}
                  speedMode={speedMode}
                  sessionId={sessionId}
                />
              </View>
            )}
                <View style={styles.threeDSection}>
                  <SectionTitle icon="cube" title="Explore in 3D" subtitle="Turn a generated image or an image from your device into a textured model." />
                  {threedStage !== "converting" && (
                    <View style={styles.centeredBlock}>
                      <View style={styles.actionButtons}>
                        <ActionButton icon="image" label={pickingThreeD ? "Opening image…" : "Upload image for 3D"} disabled={isLoading || pickingThreeD} onPress={pickThreeDImage} />
                        <ActionButton icon="cube" label="Convert to 3D" disabled={isLoading || pickingThreeD || (!imageBase64 && !uploadedThreeD)} onPress={handleConvertTo3D} />
                      </View>
                      {uploadedThreeD && <View style={{ alignItems: "center", gap: 10, width: "100%" }}>
                        <Image accessibilityLabel="Selected image for 3D generation" source={{ uri: uploadedThreeD.uri }} resizeMode="contain" style={{ width: "100%", maxWidth: 280, height: 200, borderRadius: 8 }} />
                        <Text style={styles.hint}>Selected: {uploadedThreeD.name}</Text>
                        <Pressable accessibilityRole="button" disabled={isLoading || pickingThreeD} onPress={() => { setUploadedThreeD(null); setThreedStage("idle"); setGlbBase64(null); setGlbSizeKb(undefined); setThreedError(null); }} style={styles.ghostButton}>
                          <Text style={styles.ghostText}>{imageBase64 ? "Use generated image" : "Remove selected image"}</Text>
                        </Pressable>
                      </View>}
                      <Text style={styles.hint}>PNG, JPEG or WebP, up to 10 MB. Shape and texture generation can take several minutes.</Text>
                    </View>
                  )}
                  {threedStage === "converting" && (
                    <View style={[shared.card, styles.loadingCard]}>
                      <ActivityIndicator color={colors.cyan} size="large" />
                      <Text style={styles.loadingText}>{friendlyPhase(jobPhase || "converting", "Creating your model’s shape and texture…")}</Text>
                      {activeTimers.threed !== undefined && <Text style={styles.hint}>{formatDuration(now - activeTimers.threed)} elapsed</Text>}
                      <View style={styles.stageRow}>
                        <StagePill active={jobPhase === "preparing image" || jobPhase === "generating shape"} label="Shape" />
                        <StagePill active={jobPhase === "simplifying mesh" || jobPhase === "synthesizing texture"} label="Texture" />
                        <StagePill active={jobPhase === "exporting model" || jobPhase === "saving"} label="GLB Export" />
                      </View>
                      <Text style={styles.gpuText}>GPU: {speedMode === "promax" ? "H100" : speedMode === "pro" ? "A100" : "A10G"}</Text>
                    </View>
                  )}
                  {threedError && <ErrorBanner title="3D conversion needs attention" message={threedError} />}
                  {threedError && savedThreeD?.sourceKey === (uploadedThreeD?.id || currentHistoryId) && <ActionButton icon="cube" label="Open saved model" disabled={isLoading} onPress={() => openSaved3D(savedThreeD.id)} />}
                  {threedStage !== "converting" && timings.threed !== undefined && <Text style={styles.hint}>3D generation · {outcomes.threed === "failed" ? "Attempt ended after" : "Completed in"} {formatDuration(timings.threed)}</Text>}
                  {threedStage === "done" && (glbBase64 || modelAsset) && <ThreeDViewer glbBase64={glbBase64 || undefined} modelUrl={glbBase64 ? undefined : modelAsset?.modelUrl} modelKey={glbBase64 ? threedOutputId || undefined : modelAsset?.modelKey} sizeKb={glbSizeKb} />}
                  {threedStage === "done" && threedOutputId && <FeedbackControls key={threedOutputId} agentName="threed-agent"
                    apiUrl={BACKEND_HEALTH_URL} accessToken={accessToken} sessionId={sessionId} outputId={threedOutputId}
                    inputContext={{ prompt: uploadedThreeD ? `Uploaded image: ${uploadedThreeD.name}` : enhancedPrompt || prompt }} outputSnapshot={{ size_kb: glbSizeKb }} />}

                  {threedStage === "done" && (
                    <Pressable onPress={() => { setThreedStage("idle"); setGlbBase64(null); setThreedError(null); }} style={styles.ghostButton}>
                      <Icon color={colors.textMuted} name="refresh" size={16} /><Text style={styles.ghostText}>Convert again</Text>
                    </Pressable>
                  )}
                </View>

            </>}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function ActionButton({ disabled = false, icon, label, loading = false, onPress, secondary = false }: { disabled?: boolean; icon?: IconName; label: string; loading?: boolean; onPress: () => void; secondary?: boolean }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  const shared = makeSharedStyles(colors);
  return (
    <Pressable {...(Platform.OS === "web" ? { dataSet: { themeButton: secondary ? "secondary" : "primary" } } : {})} accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress} style={({ pressed }) => [shared.button, secondary ? shared.secondaryButton : shared.primaryButton, pressed && styles.pressed, disabled && shared.disabled]}>
      {loading && <ActivityIndicator color={secondary ? colors.primary : colors.onButton} size="small" style={styles.buttonSpinner} />}
      {!loading && icon && <Icon color={secondary ? colors.text : colors.onButton} name={icon} size={17} />}
      <Text style={secondary ? shared.secondaryButtonText : shared.buttonText}>{label}</Text>
    </Pressable>
  );
}

function HealthPill({ label, now, status, warmUntil }: { label: string; now: number; status: Health; warmUntil: number }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  const isWarm = status === "ok" && warmUntil > now;
  const availabilityColor = status === "ok" ? colors.success : status === "error" ? colors.danger : colors.warning;
  return (
    <View style={styles.healthPill}>
      <Text style={styles.healthLabel}>{label}</Text>
      <View style={styles.agentSignals}>
        <View style={styles.signal}><StatusDot color={availabilityColor} /><Text style={styles.healthState}>{status === "ok" ? "online" : status === "error" ? "offline" : "checking"}</Text></View>
        {status === "ok" && (
          <View style={styles.signal}>
            <StatusDot color={isWarm ? colors.success : colors.warning} />
            <Text style={styles.healthState}>{isWarm ? `Warm ${formatRemaining(warmUntil - now)}` : "Cold"}</Text>
          </View>
        )}
      </View>
    </View>
  );
}

function StagePill({ active = false, done = false, label }: { active?: boolean; done?: boolean; label: string }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  return (
    <View style={[styles.stagePill, active && styles.stagePillActive]}>
      {done && <Icon color={colors.success} name="check" size={13} />}
      <Text style={[styles.stagePillText, active && styles.stagePillActiveText, done && styles.stagePillDone]}>{label}</Text>
    </View>
  );
}

function SectionTitle({ icon, title, subtitle }: { icon?: IconName; title: string; subtitle: string }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  return <View style={styles.sectionTitle}>{icon && <Icon color={colors.primaryBright} name={icon} size={25} />}<Text style={styles.sectionHeading}>{title}</Text><Text style={styles.sectionSubtitle}>{subtitle}</Text></View>;
}

function PerformanceInsights({ activeTimers, now, timings, outcomes }: { activeTimers: Partial<Record<ProcessKey, number>>; now: number; timings: Partial<Record<ProcessKey, number>>; outcomes: Partial<Record<ProcessKey, ProcessOutcome>> }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  const shared = makeSharedStyles(colors);
  const items = (Object.keys(PROCESS_LABELS) as ProcessKey[]).filter(key => timings[key] !== undefined || activeTimers[key] !== undefined);
  return (
    <View style={[shared.card, styles.insightsCard]}>
      <View style={styles.insightsHeader}><Icon color={colors.primaryBright} name="clock" size={18} /><Text style={styles.insightsTitle}>Processing time</Text></View>
      <Text style={styles.hint}>Latest attempt for each action, including queue and transfer time.</Text>
      <View style={styles.metricsGrid}>
        {items.map((key) => {
          const activeSince = activeTimers[key];
          const elapsed = activeSince !== undefined ? now - activeSince : timings[key];
          return (
            <View key={key} style={styles.metricItem}>
              <Text style={styles.metricLabel}>{PROCESS_LABELS[key]}</Text>
              <Text style={styles.metricValue}>{formatDuration(elapsed ?? 0)} · {activeSince !== undefined ? "Running" : outcomes[key] === "failed" ? "Failed attempt" : "Completed"}</Text>
            </View>
          );
        })}
      </View>
    </View>
  );
}

function ErrorBanner({ title, message }: { title: string; message: string }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  const shared = makeSharedStyles(colors);
  return <View style={shared.error} accessibilityRole="alert"><Text style={styles.errorTitle}>{title}</Text><Text style={styles.errorMessage}>{message}</Text></View>;
}

const makeStyles = (colors: ColorPalette) => StyleSheet.create({
  flex: { flex: 1 },
  safeArea: { flex: 1, backgroundColor: colors.background, overflow: "hidden" },
  floatingNewPrompt: { position: "absolute", zIndex: 100, bottom: 24, right: 24, width: 56, height: 56, alignItems: "center", justifyContent: "center", borderRadius: 28, backgroundColor: colors.buttonBackground, ...Platform.select({ web: { boxShadow: `0 10px 30px ${colors.shadow}` } as object }) },
  scrollContent: { flexGrow: 1, paddingHorizontal: 20, paddingTop: 24, paddingBottom: 100 },
  container: { width: "100%", maxWidth: 1160, alignSelf: "center", gap: 24 },
  header: { paddingVertical: 8, gap: 48 },
  topBar: { width: "100%", flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 16, paddingBottom: 22, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerActions: { flexDirection: "row", alignItems: "center", gap: 10 },
  themeToggle: { alignItems: "center", justifyContent: "center", width: 44, height: 44, backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: 8 },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  brandMark: { width: 34, height: 34, borderRadius: 4, alignItems: "center", justifyContent: "center", backgroundColor: colors.text },
  brandMarkText: { color: colors.onBrand, fontFamily: Platform.select({ web: "Georgia, serif", default: "serif" }), fontWeight: "800", fontSize: 18 },
  brand: { color: colors.text, fontSize: 24, fontWeight: "700", letterSpacing: -0.8 },
  heroGrid: { width: "100%", flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 40, paddingBottom: 24 },
  heroCopy: { flexGrow: 1, flexShrink: 1, flexBasis: 600, minWidth: 0, maxWidth: "100%" },
  eyebrow: { color: colors.textDim, fontSize: 11, fontWeight: "800", letterSpacing: 2.6, marginBottom: 12 },
  title: { color: colors.text, fontFamily: displayFont, fontSize: 64, lineHeight: 70, fontWeight: "700", textAlign: "left", letterSpacing: -1.2 },
  titleCompact: { fontSize: 44, lineHeight: 50, letterSpacing: -1.5 },
  subtitle: { color: colors.textMuted, fontFamily: headingFont, textAlign: "left", fontSize: 20, lineHeight: 28, maxWidth: 610, marginTop: 16 },
  systemCard: { flexGrow: 1, flexShrink: 1, flexBasis: 340, minWidth: 0, maxWidth: "100%", padding: 24, borderRadius: 8, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border },
  systemHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14 },
  systemKicker: { color: colors.textDim, fontSize: 9, fontWeight: "900", letterSpacing: 1.8 },
  systemTitle: { color: colors.text, fontFamily: headingFont, fontSize: 24, fontWeight: "400", marginTop: 5 },
  liveBadge: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 50, backgroundColor: "rgba(100,122,81,0.10)" },
  liveBadgeText: { color: colors.success, fontWeight: "800", fontSize: 11 },
  healthWrap: { gap: 7 },
  healthPill: { flexGrow: 1, minWidth: 86, gap: 6, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 8, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border },
  agentSignals: { flexDirection: "row", alignItems: "center", gap: 10 },
  signal: { flexDirection: "row", alignItems: "center", gap: 5 },
  healthLabel: { color: colors.textMuted, fontSize: 12, fontWeight: "600" },
  healthState: { color: colors.textDim, fontSize: 12 },
  warmNote: { color: colors.textDim, fontSize: 10, lineHeight: 15, marginTop: 12 },
  workspaceTabs: { flexDirection: "row", flexWrap: "wrap", gap: 8, padding: 0 },
  workspaceTab: { flexGrow: 1, flexBasis: 220, minWidth: 0, minHeight: 98, flexDirection: "row", alignItems: "center", gap: 12, borderRadius: 8, paddingHorizontal: 16, paddingVertical: 20, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  workspaceTabActive: { borderColor: colors.primaryBright, backgroundColor: colors.surfaceSoft },
  workspaceTabCopy: { flex: 1, gap: 3 },
  workspaceTabTitle: { color: colors.textMuted, fontWeight: "600", fontSize: 14 },
  workspaceTabTitleActive: { color: colors.text },
  workspaceTabDescription: { color: colors.textDim, fontSize: 11, lineHeight: 16 },
  speedSection: { gap: 12, alignItems: "center", padding: 20, borderRadius: 8, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border },
  centerText: { textAlign: "center" },
  speedPicker: { justifyContent: "center", gap: 10 },
  speedPill: { minWidth: 160, flexBasis: 160, flexGrow: 1, maxWidth: 260, padding: 15, borderRadius: 8, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, alignItems: "center" },
  speedPillActive: { borderColor: colors.primaryBright, backgroundColor: colors.surfaceSoft },
  speedName: { color: colors.textMuted, fontWeight: "800", fontSize: 14 },
  speedNameActive: { color: colors.text },
  speedDesc: { color: colors.textDim, fontSize: 12, marginTop: 4 },
  hint: { color: colors.textDim, fontSize: 12, lineHeight: 18, textAlign: "center" },
  promptCard: { gap: 14 },
  promptInput: { minHeight: 140, borderRadius: 8, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, color: colors.text, padding: 18, fontSize: 16, lineHeight: 25 },
  promptFooter: { gap: 14 },
  actionButtons: { flexDirection: "row", flexWrap: "wrap", justifyContent: "flex-start", gap: 10 },
  inlineInfo: { flexDirection: "row", alignItems: "center", gap: 7 },
  pressed: { opacity: 0.88 },
  buttonSpinner: { marginRight: 8 },
  loadingCard: { alignItems: "center", gap: 14 },
  loadingText: { color: colors.text, fontWeight: "700", textAlign: "center" },
  stageRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: 8 },
  stagePill: { flexDirection: "row", alignItems: "center", gap: 5, backgroundColor: colors.surfaceSoft, paddingVertical: 7, paddingHorizontal: 12, borderRadius: 50, overflow: "hidden" },
  stagePillText: { color: colors.textDim, fontSize: 11 },
  stagePillActive: { backgroundColor: colors.accentSoft },
  stagePillActiveText: { color: colors.text },
  stagePillDone: { color: colors.success },
  gpuText: { color: colors.textMuted, fontSize: 11 },
  errorTitle: { color: colors.danger, fontWeight: "800", marginBottom: 4 },
  errorMessage: { color: colors.textMuted, lineHeight: 20 },
  cardHeader: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 10 },
  badge: { color: colors.primaryBright, fontSize: 12, fontWeight: "800" },
  modelTag: { color: colors.textDim, fontSize: 12, backgroundColor: colors.surfaceSoft, paddingHorizontal: 9, paddingVertical: 5, borderRadius: 8, overflow: "hidden" },
  enhancedPrompt: { color: colors.textMuted, fontStyle: "italic", lineHeight: 22, marginTop: 14 },
  resultSection: { gap: 16 },
  qualityCard: { gap: 10 },
  qualityScore: { color: colors.text, fontSize: 14, fontWeight: "800", lineHeight: 21 },
  sectionTitle: { alignItems: "center", gap: 5, marginTop: 4 },
  sectionHeading: { color: colors.text, fontFamily: headingFont, fontWeight: "400", fontSize: 30, textAlign: "center" },
  sectionSubtitle: { color: colors.textMuted, textAlign: "center", lineHeight: 20, fontSize: 13 },
  threeDSection: { gap: 16, marginTop: 10 },
  centeredBlock: { alignItems: "center", gap: 10 },
  ghostButton: { alignSelf: "center", flexDirection: "row", alignItems: "center", gap: 7, paddingHorizontal: 18, paddingVertical: 12 },
  ghostText: { color: colors.textMuted, fontWeight: "700" },
  promptLabel: { color: colors.text, fontSize: 14, fontWeight: "700", letterSpacing: 0.5 },
  optionLabel: { color: colors.text, fontSize: 14, fontWeight: "700", alignSelf: "center", marginRight: 4 },
  optionButton: { minHeight: 44, minWidth: 104, paddingHorizontal: 16, paddingVertical: 11, borderRadius: 8, borderWidth: 1, borderColor: colors.textDim, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center" },
  optionButtonSelected: { backgroundColor: colors.buttonBackground, borderColor: colors.buttonBackground },
  optionText: { color: colors.text, fontSize: 14, fontWeight: "600" },
  optionTextSelected: { color: colors.onButton },
  insightsCard: { gap: 14 },
  insightsHeader: { flexDirection: "row", alignItems: "center", gap: 8 },
  insightsTitle: { color: colors.text, fontWeight: "800", fontSize: 14 },
  metricsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  metricItem: { flexGrow: 1, flexBasis: 180, maxWidth: "50%" as unknown as number, backgroundColor: colors.surfaceSoft, borderRadius: 8, padding: 12, gap: 5 },
  metricLabel: { color: colors.textDim, fontSize: 11 },
  metricValue: { color: colors.text, fontSize: 14, fontWeight: "800" },
});
