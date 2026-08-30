import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import InteractiveCanvas from "./components/InteractiveCanvas";
import FeedbackControls, { createOutputId, FeedbackReason } from "./components/FeedbackControls";
import PersonalMemoryPanel from "./components/PersonalMemoryPanel";
import ThreeDViewer from "./components/ThreeDViewer";
import HistoryPanel from "./components/HistoryPanel";
import Icon, { IconName, StatusDot } from "./components/Icon";
import { appendHistoryInteraction, GenerationHistoryItem, listHistory, saveHistoryItem, updateHistoryItem } from "./historyStorage";
import { ColorPalette, makeSharedStyles, ThemeProvider, useAppTheme } from "./theme";
import {
  PROMPT_AGENT_URL,
  IMAGE_AGENT_URL,
  INTERACTIVE_AGENT_URL,
  THREED_AGENT_URL,
  BACKEND_URL,
  EVAL_AGENT_URL,
} from "./config";

const BACKEND_HEALTH_URL = BACKEND_URL;

type Stage = "idle" | "enhancing" | "preview" | "generating" | "done";
type GenerationWorkspace = "general" | "anatomy" | "history";
export type SpeedMode = "normal" | "pro" | "promax";
type ThreeDStage = "idle" | "converting" | "done";
type Health = "ok" | "error" | "checking";
type AgentKey = "prompt" | "image" | "eval" | "interactive" | "threed";
type ProcessKey = AgentKey;
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
// The Modal worker allows 60 minutes. Stop polling slightly earlier so the UI
// can report a controlled timeout instead of surfacing a platform task kill.
const THREED_MAX_WAIT_MS = 55 * 60 * 1_000;
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
  { id: "normal", label: "Normal", icon: "bolt", desc: "A10G / A10G / A10G", promptGpu: "A10G", imageGpu: "A10G", interactiveGpu: "A10G" },
  { id: "pro", label: "Pro", icon: "rocket", desc: "A10G / A100 / A100", promptGpu: "A10G", imageGpu: "A100", interactiveGpu: "A100" },
  { id: "promax", label: "Pro Max", icon: "layers", desc: "A10G / H100 / H100", promptGpu: "A10G", imageGpu: "H100", interactiveGpu: "H100" },
];

function formatDuration(milliseconds: number): string {
  if (milliseconds < 1_000) return `${Math.max(1, Math.round(milliseconds))} ms`;
  if (milliseconds < 60_000) return `${(milliseconds / 1_000).toFixed(1)} s`;
  const minutes = Math.floor(milliseconds / 60_000);
  const seconds = Math.round((milliseconds % 60_000) / 1_000);
  return `${minutes} min ${seconds} s`;
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

interface AppProps { accessToken?: string }

export default function App({ accessToken }: AppProps) {
  return <ThemeProvider><Home accessToken={accessToken} /></ThemeProvider>;
}

function Home({ accessToken }: AppProps) {
  const { colors, mode: themeMode, toggleTheme } = useAppTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const shared = useMemo(() => makeSharedStyles(colors), [colors]);
  const [workspace, setWorkspace] = useState<GenerationWorkspace>("general");
  const [prompt, setPrompt] = useState("");
  const [stage, setStage] = useState<Stage>("idle");
  const [speedMode, setSpeedMode] = useState<SpeedMode>("pro");
  const [enhancedPrompt, setEnhancedPrompt] = useState<string | null>(null);
  const [enhancedPromptJson, setEnhancedPromptJson] = useState<EnhancedPromptPayload | null>(null);
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [anatomySpec, setAnatomySpec] = useState<AnatomySpec>({ is_anatomy: false });
  const [anatomyAnnotations, setAnatomyAnnotations] = useState<AnatomyAnnotation[]>([]);
  const [localizationError, setLocalizationError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [threedStage, setThreedStage] = useState<ThreeDStage>("idle");
  const [glbBase64, setGlbBase64] = useState<string | null>(null);
  const [glbSizeKb, setGlbSizeKb] = useState<number>();
  const [threedError, setThreedError] = useState<string | null>(null);
  const [promptHealth, setPromptHealth] = useState<Health>("checking");
  const [imageHealth, setImageHealth] = useState<Health>("checking");
  const [interactiveHealth, setInteractiveHealth] = useState<Health>("checking");
  const [evalHealth, setEvalHealth] = useState<Health>("checking");
  const [threedHealth, setThreedHealth] = useState<Health>("checking");
  const [backendHealth, setBackendHealth] = useState<Health>("checking");
  const [now, setNow] = useState(Date.now());
  const [warmUntil, setWarmUntil] = useState<Record<AgentKey, number>>({ prompt: 0, image: 0, eval: 0, interactive: 0, threed: 0 });
  const [timings, setTimings] = useState<Partial<Record<ProcessKey, number>>>({});
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
  const threedRequestInFlight = useRef(false);
  const workspaceSnapshots = useRef<Partial<Record<"general" | "anatomy", {
    prompt: string; stage: Stage; speedMode: SpeedMode; enhancedPrompt: string | null;
    enhancedPromptJson: EnhancedPromptPayload | null; imageBase64: string | null;
    anatomySpec: AnatomySpec; anatomyAnnotations: AnatomyAnnotation[]; evaluation: EvaluationResult | null;
    evaluationRetries: number; evaluationWarning: string | null; glbBase64: string | null;
    glbSizeKb?: number; threedStage: ThreeDStage; historyId: string | null; chatId: string | null;
  }>>>({});

  const isLoading = stage === "enhancing" || stage === "generating";
  // The 3D agent has its own browser-facing endpoint. Orchestrator downtime
  // must not incorrectly mark a healthy 3D service as offline.
  const displayedThreeDHealth: Health = threedHealth;
  const speed = useMemo(
    () => SPEED_MODES.find((item) => item.id === speedMode) ?? SPEED_MODES[1],
    [speedMode],
  );

  useEffect(() => {
    let mounted = true;
    const check = async (url: string, setter: (health: Health) => void, timeoutMs = 5_000) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(`${url}/health`, {
          headers: { Accept: "application/json" },
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
      void check(PROMPT_AGENT_URL, setPromptHealth);
      void check(IMAGE_AGENT_URL, setImageHealth);
      void check(INTERACTIVE_AGENT_URL, setInteractiveHealth);
      void check(EVAL_AGENT_URL, setEvalHealth, 30_000);
      void check(THREED_AGENT_URL, setThreedHealth, 30_000);
      void check(BACKEND_HEALTH_URL, setBackendHealth);
    };
    checkAll();
    const refresh = setInterval(checkAll, 15_000);
    return () => { mounted = false; clearInterval(refresh); };
  }, []);

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
      return await operation();
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
    setGlbSizeKb(undefined);
    setThreedError(null);
    setTimings({});
    setActiveTimers({});
    setPromptOutputId(null);
    setImageOutputId(null);
    setPromptRetryLink(null);
    setImageRetryLink(null);
    setEvaluation(null);
    setEvaluationRetries(0);
    setEvaluationWarning(null);
    setCurrentHistoryId(null);
    currentChatId.current = null;
  };

  const handlePromptChange = (value: string) => {
    setPrompt(value);
    if (stage !== "idle") reset();
  };

  const selectWorkspace = (next: GenerationWorkspace) => {
    if (next === workspace || isLoading) return;
    if (workspace !== "history") {
      workspaceSnapshots.current[workspace] = {
        prompt, stage, speedMode, enhancedPrompt, enhancedPromptJson, imageBase64, anatomySpec,
        anatomyAnnotations, evaluation, evaluationRetries, evaluationWarning, glbBase64, glbSizeKb,
        threedStage, historyId: currentHistoryId, chatId: currentChatId.current,
      };
    }
    if (next !== "history") {
      const saved = workspaceSnapshots.current[next];
      reset();
      if (saved) {
        setPrompt(saved.prompt); setStage(saved.stage); setSpeedMode(saved.speedMode);
        setEnhancedPrompt(saved.enhancedPrompt); setEnhancedPromptJson(saved.enhancedPromptJson);
        setImageBase64(saved.imageBase64); setAnatomySpec(saved.anatomySpec);
        setAnatomyAnnotations(saved.anatomyAnnotations); setEvaluation(saved.evaluation);
        setEvaluationRetries(saved.evaluationRetries); setEvaluationWarning(saved.evaluationWarning);
        setGlbBase64(saved.glbBase64); setGlbSizeKb(saved.glbSizeKb); setThreedStage(saved.threedStage);
        setCurrentHistoryId(saved.historyId); currentChatId.current = saved.chatId;
      } else {
        setPrompt("");
        currentChatId.current = null;
      }
    }
    setWorkspace(next);
  };

  const archiveResult = async (result: QualityControlledImage): Promise<string | null> => {
    const id = createOutputId("history");
    const mode = result.anatomy.is_anatomy ? "anatomy" : "general";
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
        chatId,
        version,
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
      return null;
    }
  };

  const restoreHistory = (item: GenerationHistoryItem) => {
    const nextWorkspace = item.mode;
    const restoredAnatomy = (item.anatomy as AnatomySpec | undefined) ?? { is_anatomy: item.mode === "anatomy" };
    reset();
    setWorkspace(nextWorkspace);
    setPrompt(item.prompt);
    setSpeedMode(item.speedMode);
    setEnhancedPrompt(item.enhancedPrompt);
    setEnhancedPromptJson(item.mode === "anatomy" ? {
      schema_version: "1.0", final_prompt: item.enhancedPrompt, anatomy_spec: restoredAnatomy,
      route: "anatomy", anatomy_mode: "verified",
    } : null);
    setImageBase64(item.imageBase64);
    setAnatomySpec(restoredAnatomy);
    setAnatomyAnnotations(item.anatomyAnnotations ?? []);
    setEvaluation(item.evaluation ? { clipScore: null, vlmScore: null, visualScore: item.evaluation.visualScore, pedagogicalScore: item.evaluation.pedagogicalScore, feedback: item.evaluation.feedback, anatomyHardFailures: [] } : null);
    setGlbBase64(item.glbBase64 ?? null); setGlbSizeKb(item.glbSizeKb);
    setThreedStage(item.glbBase64 ? "done" : "idle");
    setCurrentHistoryId(item.id); currentChatId.current = item.chatId ?? item.id;
    setImageOutputId(createOutputId("image")); setStage("done");
  };

  const callEnhance = async (
    raw: string,
    retryFeedback?: string,
  ): Promise<{ prompt: string; anatomy: AnatomySpec; payload: EnhancedPromptPayload }> => {
    const routedRaw = workspace === "anatomy"
      ? `Human anatomy educational illustration: ${raw}`
      : raw;
    const [anatomyMemory, genericMemory] = await Promise.all([
      recallMemory("prompt-anatomy", routedRaw),
      recallMemory("prompt-generic", routedRaw),
    ]);
    const response = await fetch(`${PROMPT_AGENT_URL}/enhance`, {
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
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorMessage(data, `Enhance HTTP ${response.status}`));
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

  const callGenerate = async (
    finalPrompt: string,
    anatomy: AnatomySpec,
    regenerationFeedback?: string,
    enhancement?: EnhancedPromptPayload,
    useRuntimeContext = true,
  ): Promise<string> => {
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

  const localizeAnatomy = async (image: string, anatomy: AnatomySpec): Promise<AnatomyAnnotation[]> => {
    setAnatomyAnnotations([]);
    setLocalizationError(null);
    if (!anatomy.is_anatomy || !anatomy.organ) return [];
    try {
      const response = await fetch(`${INTERACTIVE_AGENT_URL}/auto-labels`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_base64: image,
          domain: "anatomy",
          organ: anatomy.organ,
          view: anatomy.view_description || anatomy.view || "",
          speed_mode: speedMode,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(errorMessage(data, `Auto-label HTTP ${response.status}`));
      if (data.error) throw new Error(String(data.error));
      const annotations: AnatomyAnnotation[] = (Array.isArray(data.annotations) ? data.annotations : [])
        .map((item: Partial<AnatomyAnnotation>) => {
          const label = extractAnatomyLabel(typeof item.label === "string" ? item.label : "");
          if (
            !label || item.verified !== true ||
            typeof item.anchor_x !== "number" || typeof item.anchor_y !== "number" ||
            typeof item.label_x !== "number" || typeof item.label_y !== "number" ||
            typeof item.confidence !== "number" || item.confidence < 0.75 ||
            item.anchor_x < 0 || item.anchor_x > 1 || item.anchor_y < 0 || item.anchor_y > 1
          ) return null;
          return { ...item, label } as AnatomyAnnotation;
        })
        .filter((item: AnatomyAnnotation | null): item is AnatomyAnnotation => item !== null);
      setAnatomyAnnotations(annotations);
      markWarm("interactive");
      return annotations;
    } catch (caught) {
      setLocalizationError(caught instanceof Error ? caught.message : "Anatomy localization failed");
      return [];
    }
  };

  const handleSubmit = async () => {
    if (!prompt.trim() || isLoading) return;
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
      void runTimed("interactive", () => localizeAnatomy(result.image, result.anatomy)).then((annotations) =>
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
      void runTimed("interactive", () => localizeAnatomy(result.image, result.anatomy)).then((annotations) =>
        historyId && annotations.length ? updateHistoryItem(historyId, { anatomyAnnotations: annotations }).catch(() => undefined) : undefined,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Image regeneration failed");
      setStage("done");
    }
  };

  const handleConvertTo3D = async () => {
    if (!imageBase64 || threedStage === "converting" || threedRequestInFlight.current) return;
    threedRequestInFlight.current = true;
    const fingerprint = imageFingerprint(imageBase64);
    const storedJob = readStoredThreeDJob();
    const requestId = storedJob?.imageFingerprint === fingerprint && storedJob.speedMode === speedMode
      ? storedJob.requestId
      : createRequestId();
    storeThreeDJob({ requestId, imageFingerprint: fingerprint, speedMode });
    const conversionStartedAt = Date.now();
    setActiveTimers((current) => ({ ...current, threed: conversionStartedAt }));
    setThreedStage("converting");
    setThreedError(null);
    setGlbBase64(null);
    try {
      let response: Response;
      try {
        response = await fetch(`${THREED_AGENT_URL}/convert/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            image_base64: imageBase64,
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
        if (resultResponse.status === 202) continue;
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
        clearStoredThreeDJob();
        markWarm("threed");
        if (currentHistoryId) {
          await updateHistoryItem(currentHistoryId, { glbBase64: generatedGlb, glbSizeKb: generatedSizeKb });
        }
        return;
      }
      throw new Error("3D conversion timed out after 55 minutes");
    } catch (caught) {
      setThreedError(caught instanceof Error ? caught.message : "3D conversion failed");
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
    ? `Enhancing with Qwen3.5-9B on ${speed.promptGpu}...`
    : workspace === "general"
      ? `Sending your raw prompt directly to FLUX.1-dev on ${speed.imageGpu}...`
      : `Generating, evaluating, and retrying when needed on ${speed.imageGpu}...`;

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style={themeMode === "dark" ? "light" : "dark"} />
      <View pointerEvents="none" style={styles.ambientTop} />
      <View pointerEvents="none" style={styles.ambientBottom} />
      {workspace !== "history" && (
        <Pressable
          accessibilityLabel="Start a new chat"
          disabled={isLoading}
          onPress={() => { reset(); setPrompt(""); }}
          style={({ pressed }) => [styles.floatingNewPrompt, pressed && styles.pressed, isLoading && shared.disabled]}
        >
          <Icon color="#fff" name="wand" size={16} />
          <Text style={styles.floatingNewPromptText}>New chat</Text>
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
            <View style={styles.header}>
              <View style={styles.topBar}>
                <View style={styles.brandRow}>
                  <View style={styles.brandMark}><Text style={styles.brandMarkText}>E</Text></View>
                  <Text style={styles.brand}>EduVision</Text>
                </View>
                <Pressable
                  accessibilityLabel={`Switch to ${themeMode === "dark" ? "light" : "dark"} mode`}
                  onPress={toggleTheme}
                  style={({ pressed }) => [styles.themeToggle, pressed && styles.pressed]}
                >
                  <Icon color={colors.text} name={themeMode === "dark" ? "sun" : "moon"} size={15} />
                  <Text style={styles.themeToggleText}>{themeMode === "dark" ? "Light mode" : "Dark mode"}</Text>
                </Pressable>
              </View>
              <View style={styles.heroGrid}>
                <View style={styles.heroCopy}>
                  <Text style={styles.eyebrow}>A VISUAL LEARNING STUDIO</Text>
                  <Text style={styles.title}>Make ideas <Text style={styles.titleAccent}>visible.</Text></Text>
                  <Text style={styles.subtitle}>
                    Create thoughtful educational imagery, explore human anatomy, and turn flat visuals into interactive learning experiences.
                  </Text>
                </View>
                <View style={styles.systemGlass}>
                  <View style={styles.systemHeader}>
                    <View><Text style={styles.systemKicker}>STUDIO STATUS</Text><Text style={styles.systemTitle}>Creative engine</Text></View>
                    <View style={styles.liveBadge}><StatusDot color={colors.success} /><Text style={styles.liveBadgeText}>Live</Text></View>
                  </View>
                  <View style={[shared.wrap, styles.healthWrap]}>
                    <HealthPill label="Prompt" now={now} status={promptHealth} warmUntil={warmUntil.prompt} />
                    <HealthPill label="Image" now={now} status={imageHealth} warmUntil={warmUntil.image} />
                    <HealthPill label="Eval" now={now} status={evalHealth} warmUntil={warmUntil.eval} />
                    <HealthPill label="Interact" now={now} status={interactiveHealth} warmUntil={warmUntil.interactive} />
                    <HealthPill label="3D" now={now} status={displayedThreeDHealth} warmUntil={warmUntil.threed} />
                  </View>
                  <Text style={styles.warmNote}>Warm-state estimates update after successful studio activity.</Text>
                </View>
              </View>
            </View>

            <View accessibilityRole="tablist" style={styles.workspaceTabs}>
              <Pressable
                accessibilityRole="tab"
                accessibilityState={{ selected: workspace === "general", disabled: isLoading }}
                disabled={isLoading}
                onPress={() => selectWorkspace("general")}
                style={({ pressed }) => [styles.workspaceTab, workspace === "general" && styles.workspaceTabActive, pressed && styles.pressed, isLoading && shared.disabled]}
              >
                <Icon color={workspace === "general" ? colors.primaryBright : colors.textMuted} name="wand" size={20} />
                <View style={styles.workspaceTabCopy}>
                  <Text style={[styles.workspaceTabTitle, workspace === "general" && styles.workspaceTabTitleActive]}>Image Generation</Text>
                  <Text style={styles.workspaceTabDescription}>General educational visuals and diagrams</Text>
                </View>
              </Pressable>
              <Pressable
                accessibilityRole="tab"
                accessibilityState={{ selected: workspace === "anatomy", disabled: isLoading }}
                disabled={isLoading}
                onPress={() => selectWorkspace("anatomy")}
                style={({ pressed }) => [styles.workspaceTab, workspace === "anatomy" && styles.workspaceTabActive, pressed && styles.pressed, isLoading && shared.disabled]}
              >
                <Icon color={workspace === "anatomy" ? colors.primaryBright : colors.textMuted} name="target" size={20} />
                <View style={styles.workspaceTabCopy}>
                  <Text style={[styles.workspaceTabTitle, workspace === "anatomy" && styles.workspaceTabTitleActive]}>Human Anatomy Generation</Text>
                  <Text style={styles.workspaceTabDescription}>Validated organs, views, labels, and 3D</Text>
                </View>
              </Pressable>
              <Pressable
                accessibilityRole="tab"
                accessibilityState={{ selected: workspace === "history", disabled: isLoading }}
                disabled={isLoading}
                onPress={() => selectWorkspace("history")}
                style={({ pressed }) => [styles.workspaceTab, workspace === "history" && styles.workspaceTabActive, pressed && styles.pressed, isLoading && shared.disabled]}
              >
                <Icon color={workspace === "history" ? colors.primaryBright : colors.textMuted} name="layers" size={20} />
                <View style={styles.workspaceTabCopy}>
                  <Text style={[styles.workspaceTabTitle, workspace === "history" && styles.workspaceTabTitleActive]}>History</Text>
                  <Text style={styles.workspaceTabDescription}>Your last 50 local creations</Text>
                </View>
              </Pressable>
            </View>

            {workspace === "history" ? <HistoryPanel onResume={restoreHistory} /> : <>
            <View style={styles.speedSection}>
              <Text style={[shared.label, styles.centerText]}>Speed Mode</Text>
              <View style={[shared.wrap, styles.speedPicker]}>
                {SPEED_MODES.map((item) => {
                  const selected = speedMode === item.id;
                  return (
                    <Pressable
                      key={item.id}
                      accessibilityRole="button"
                      accessibilityState={{ selected, disabled: isLoading }}
                      disabled={isLoading}
                      onPress={() => setSpeedMode(item.id)}
                      style={({ pressed }) => [
                        styles.speedPill,
                        selected && styles.speedPillActive,
                        pressed && styles.pressed,
                        isLoading && shared.disabled,
                      ]}
                    >
                      <Icon color={selected ? colors.primaryBright : colors.textMuted} name={item.icon} size={19} />
                      <Text style={[styles.speedName, selected && styles.speedNameActive]}>{item.label}</Text>
                      <Text style={styles.speedDesc}>{item.desc}</Text>
                    </Pressable>
                  );
                })}
              </View>
              <Text style={styles.hint}>
                {workspace === "general" && `${speed.label} sends the raw prompt directly to FLUX on ${speed.imageGpu}.`}
                {workspace === "anatomy" && speedMode === "normal" && "Standard GPUs - same validated anatomy workflow, moderate wait times."}
                {workspace === "anatomy" && speedMode === "pro" && "Upgraded GPUs - faster enhancement and interactive analysis."}
                {workspace === "anatomy" && speedMode === "promax" && "Top-tier GPUs - maximum speed across the validated anatomy pipeline."}
              </Text>
            </View>

            {workspace === "anatomy" && <PersonalMemoryPanel accessToken={accessToken} apiUrl={BACKEND_HEALTH_URL} />}

            <View style={[shared.card, styles.promptCard]}>
              <Text style={shared.label}>{workspace === "anatomy" ? "Human Anatomy Prompt" : "Your Prompt"}</Text>
              <TextInput
                accessibilityLabel="Your prompt"
                editable={!isLoading}
                multiline
                numberOfLines={4}
                onChangeText={handlePromptChange}
                placeholder={workspace === "anatomy"
                  ? "e.g. anterior view of the human heart for medical students"
                  : "e.g. photosynthesis diagram for 8th graders with labeled chloroplasts"}
                placeholderTextColor={colors.textDim}
                style={styles.promptInput}
                textAlignVertical="top"
                value={prompt}
              />
              <View style={styles.promptFooter}>
                <Text style={styles.hint}>
                  {workspace === "anatomy"
                    ? "Anatomy mode enforces a human-anatomy route and validates the requested organ and view."
                    : "Raw mode sends your prompt directly to the base FLUX model without enhancement, memory, evaluation, or retries."}
                </Text>
                <View style={styles.actionButtons}>
                  <ActionButton
                    disabled={isLoading || !prompt.trim()}
                    icon="wand"
                    label={workspace === "general" ? (stage === "generating" ? "Generating..." : "Generate Image") : (stage === "enhancing" ? "Enhancing..." : "Enhance Prompt")}
                    loading={isLoading}
                    onPress={handleSubmit}
                  />
                </View>
              </View>
            </View>

            {isLoading && (
              <View style={[shared.card, styles.loadingCard]} accessibilityLiveRegion="polite">
                <ActivityIndicator color={colors.primaryBright} size="large" />
                <Text style={styles.loadingText}>{loadingLabel}</Text>
                <View style={styles.stageRow}>
                  {workspace === "anatomy" && <StagePill active={stage === "enhancing"} done={stage === "generating"} label="Enhance" />}
                  <StagePill active={stage === "generating"} label="Generate" />
                </View>
                <View style={styles.inlineInfo}><Icon color={colors.textMuted} name={speed.icon} size={14} /><Text style={styles.gpuText}>{speed.label}. GPU: {stage === "enhancing" ? speed.promptGpu : speed.imageGpu}</Text></View>
              </View>
            )}

            {(Object.keys(timings).length > 0 || Object.keys(activeTimers).length > 0) && (
              <PerformanceInsights activeTimers={activeTimers} now={now} timings={timings} />
            )}

            {error && <ErrorBanner title="Failed" message={error} />}

            {enhancedPromptJson && stage !== "enhancing" && (
              <View style={shared.card}>
                <View style={styles.cardHeader}>
                  <View style={styles.inlineInfo}><Icon color={colors.primaryBright} name="wand" size={15} /><Text style={styles.badge}>Enhanced Prompt JSON</Text></View>
                  <Text style={styles.modelTag}>
                    {enhancedPromptJson.route === "anatomy"
                      ? `Anatomy · ${enhancedPromptJson.anatomy_mode === "verified" ? "verified catalog" : "general"}`
                      : "General image"}
                  </Text>
                </View>
                <Text style={styles.enhancedPrompt}>{JSON.stringify(enhancedPromptJson, null, 2)}</Text>
                {enhancedPromptJson.routing && (
                  <Text style={styles.hint}>
                    Selected by {enhancedPromptJson.routing.source === "qwen" ? "Qwen reasoning" : "routing rules"}
                    {typeof enhancedPromptJson.routing.confidence === "number" ? ` · ${Math.round(enhancedPromptJson.routing.confidence * 100)}% confidence` : ""}
                  </Text>
                )}
                {stage === "preview" && (
                  <View style={styles.actionButtons}>
                    <ActionButton icon="wand" label="Generate Image" onPress={generateEnhancedPreview} />
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
                {imageOutputId && (
                  <View style={shared.card}>
                    <Text style={styles.badge}>Generated Image</Text>
                    <FeedbackControls
                      key={imageOutputId}
                      agentName="image-agent"
                      accessToken={accessToken}
                      apiUrl={BACKEND_HEALTH_URL}
                      inputContext={{ prompt: enhancedPrompt || prompt }}
                      negativeReasons={IMAGE_NEGATIVE}
                      onRegenerate={regenerateImageFromFeedback}
                      outputId={imageOutputId}
                      outputSnapshot={{ prompt: enhancedPrompt || prompt }}
                      parentFeedbackId={imageRetryLink?.feedbackId}
                      parentOutputId={imageRetryLink?.outputId}
                      positiveReasons={IMAGE_POSITIVE}
                      sessionId={sessionId}
                    />
                  </View>
                )}
                <SectionTitle title="Interactive Image Analysis" subtitle="Tap any object or drag a box to segment with SAM 2 and explain with Qwen2.5-VL" />
                {localizationError && <ErrorBanner title="Labels unavailable; clean image preserved" message={localizationError} />}
                <InteractiveCanvas
                  accessToken={accessToken}
                  anatomyAnnotations={anatomyAnnotations}
                  anatomyOrgan={anatomySpec.organ}
                  feedbackApiUrl={BACKEND_HEALTH_URL}
                  imageBase64={imageBase64}
                  onInteractionComplete={(interaction) => {
                    if (currentHistoryId) void appendHistoryInteraction(currentHistoryId, interaction);
                  }}
                  onOperationComplete={(duration) => {
                    setTimings((current) => ({ ...current, interactive: duration }));
                    markWarm("interactive");
                  }}
                  speedMode={speedMode}
                  sessionId={sessionId}
                />

                <View style={styles.threeDSection}>
                  <SectionTitle icon="cube" title="2D to 3D Conversion" subtitle="Convert your generated image into a textured 3D model using Hunyuan3D-2" />
                  {threedStage === "idle" && (
                    <View style={styles.centeredBlock}>
                      <ActionButton icon="cube" label={`Convert to 3D. ${speedMode === "promax" ? "H100" : speedMode === "pro" ? "A100" : "A10G"}`} onPress={handleConvertTo3D} />
                      <Text style={styles.hint}>{speedMode === "promax" ? "Pro Max. H100. About 2-3 min for shape and texture." : "A10G or A100. About 3-5 min for shape and texture."}</Text>
                    </View>
                  )}
                  {threedStage === "converting" && (
                    <View style={[shared.card, styles.loadingCard]}>
                      <ActivityIndicator color={colors.cyan} size="large" />
                      <Text style={styles.loadingText}>Hunyuan3D-2 is generating shape and texture...</Text>
                      <View style={styles.stageRow}>
                        <StagePill active label="Shape" />
                        <StagePill label="Texture" />
                        <StagePill label="GLB Export" />
                      </View>
                      <Text style={styles.gpuText}>GPU: {speedMode === "promax" ? "H100" : speedMode === "pro" ? "A100" : "A10G"}</Text>
                    </View>
                  )}
                  {threedError && <ErrorBanner title="3D conversion failed" message={threedError} />}
                  {threedStage === "done" && glbBase64 && <ThreeDViewer glbBase64={glbBase64} sizeKb={glbSizeKb} />}
                  {threedStage === "done" && (
                    <Pressable onPress={() => { setThreedStage("idle"); setGlbBase64(null); setThreedError(null); }} style={styles.ghostButton}>
                      <Icon color={colors.textMuted} name="refresh" size={16} /><Text style={styles.ghostText}>Convert again</Text>
                    </Pressable>
                  )}
                </View>
              </View>
            )}

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
    <Pressable disabled={disabled} onPress={onPress} style={({ pressed }) => [shared.button, secondary ? shared.secondaryButton : shared.primaryButton, pressed && styles.pressed, disabled && shared.disabled]}>
      {loading && <ActivityIndicator color={secondary ? colors.primary : "#fff"} size="small" style={styles.buttonSpinner} />}
      {!loading && icon && <Icon color={secondary ? colors.text : "#ffffff"} name={icon} size={17} />}
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

function PerformanceInsights({ activeTimers, now, timings }: { activeTimers: Partial<Record<ProcessKey, number>>; now: number; timings: Partial<Record<ProcessKey, number>> }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  const shared = makeSharedStyles(colors);
  const items: Array<{ key: ProcessKey; label: string }> = [
    { key: "prompt", label: "Prompt enhancement" },
    { key: "image", label: "Image generation" },
    { key: "eval", label: "Quality evaluation" },
    { key: "interactive", label: "Interactive analysis" },
    { key: "threed", label: "3D generation" },
  ];
  return (
    <View style={[shared.card, styles.insightsCard]}>
      <View style={styles.insightsHeader}><Icon color={colors.primaryBright} name="clock" size={18} /><Text style={styles.insightsTitle}>Processing insights</Text></View>
      <View style={styles.metricsGrid}>
        {items.map((item) => {
          const activeSince = activeTimers[item.key];
          const elapsed = activeSince ? now - activeSince : timings[item.key];
          return (
            <View key={item.key} style={styles.metricItem}>
              <Text style={styles.metricLabel}>{item.label}</Text>
              <Text style={styles.metricValue}>{elapsed === undefined ? "Not run" : activeSince ? `${formatDuration(elapsed)} running` : formatDuration(elapsed)}</Text>
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
  floatingNewPrompt: { position: "absolute", zIndex: 100, top: 18, right: 22, flexDirection: "row", alignItems: "center", gap: 7, paddingHorizontal: 16, paddingVertical: 11, borderRadius: 50, backgroundColor: colors.primary, ...Platform.select({ web: { boxShadow: `0 10px 30px ${colors.shadow}` } as object }) },
  floatingNewPromptText: { color: "#fff", fontSize: 12, fontWeight: "900" },
  ambientTop: { position: "absolute", width: 620, height: 620, borderRadius: 310, right: -190, top: -270, backgroundColor: "rgba(211, 105, 55, 0.20)" },
  ambientBottom: { position: "absolute", width: 520, height: 520, borderRadius: 260, left: -230, bottom: -170, backgroundColor: "rgba(175, 125, 73, 0.16)" },
  scrollContent: { flexGrow: 1, paddingHorizontal: 18, paddingTop: 16, paddingBottom: 44 },
  container: { width: "100%", maxWidth: 1040, alignSelf: "center", gap: 20 },
  header: { paddingVertical: 8, gap: 40 },
  topBar: { width: "100%", flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 16 },
  themeToggle: { flexDirection: "row", alignItems: "center", gap: 7, backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: 50, paddingHorizontal: 14, paddingVertical: 10, minHeight: 42, ...Platform.select({ web: { boxShadow: `0 12px 35px ${colors.shadow}`, backdropFilter: "blur(20px)" } as object }) },
  themeToggleText: { color: colors.text, fontSize: 12, fontWeight: "800" },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  brandMark: { width: 34, height: 34, borderRadius: 12, alignItems: "center", justifyContent: "center", backgroundColor: colors.primary },
  brandMarkText: { color: "#fffaf1", fontFamily: Platform.select({ web: "Georgia, serif", default: "serif" }), fontWeight: "800", fontSize: 18 },
  brand: { color: colors.primaryBright, fontSize: 17, fontWeight: "900", letterSpacing: 2.4, textTransform: "uppercase" },
  heroGrid: { width: "100%", flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 34 },
  heroCopy: { flexGrow: 1, flexShrink: 1, flexBasis: 500, minWidth: 280, maxWidth: "100%" as unknown as number },
  eyebrow: { color: colors.textDim, fontSize: 11, fontWeight: "800", letterSpacing: 2.6, marginBottom: 12 },
  title: { color: colors.text, fontFamily: Platform.select({ web: "Georgia, 'Times New Roman', serif", default: "serif" }), fontSize: 58, lineHeight: 63, fontWeight: "700", textAlign: "left", letterSpacing: -2 },
  titleAccent: { color: colors.primaryBright },
  subtitle: { color: colors.textMuted, textAlign: "left", fontSize: 16, lineHeight: 26, maxWidth: 610, marginTop: 16 },
  systemGlass: { flexGrow: 1, flexShrink: 1, flexBasis: 340, minWidth: 290, maxWidth: "100%" as unknown as number, padding: 20, borderRadius: 26, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, ...Platform.select({ web: { boxShadow: `0 28px 80px ${colors.shadow}, inset 0 1px 0 rgba(255,255,255,0.86)`, backdropFilter: "blur(28px) saturate(130%)" } as object }) },
  systemHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14 },
  systemKicker: { color: colors.textDim, fontSize: 9, fontWeight: "900", letterSpacing: 1.8 },
  systemTitle: { color: colors.text, fontFamily: Platform.select({ web: "Georgia, serif", default: "serif" }), fontSize: 22, fontWeight: "700", marginTop: 3 },
  liveBadge: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 50, backgroundColor: "rgba(100,122,81,0.10)" },
  liveBadgeText: { color: colors.success, fontWeight: "800", fontSize: 11 },
  healthWrap: { gap: 7 },
  healthPill: { flexGrow: 1, minWidth: 86, gap: 6, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 14, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border },
  agentSignals: { flexDirection: "row", alignItems: "center", gap: 10 },
  signal: { flexDirection: "row", alignItems: "center", gap: 5 },
  healthLabel: { color: colors.textMuted, fontSize: 12, fontWeight: "600" },
  healthState: { color: colors.textDim, fontSize: 12 },
  warmNote: { color: colors.textDim, fontSize: 10, lineHeight: 15, marginTop: 12 },
  workspaceTabs: { flexDirection: "row", flexWrap: "wrap", gap: 8, padding: 6, borderRadius: 26, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, ...Platform.select({ web: { boxShadow: `0 22px 65px ${colors.shadow}, inset 0 1px 0 rgba(255,255,255,0.88)`, backdropFilter: "blur(26px) saturate(125%)" } as object }) },
  workspaceTab: { flex: 1, minWidth: 260, minHeight: 74, flexDirection: "row", alignItems: "center", gap: 12, borderRadius: 14, paddingHorizontal: 16, paddingVertical: 13, borderWidth: 1, borderColor: "transparent" },
  workspaceTabActive: { borderColor: "rgba(185,79,39,0.38)", backgroundColor: "rgba(201,95,50,0.13)" },
  workspaceTabCopy: { flex: 1, gap: 3 },
  workspaceTabTitle: { color: colors.textMuted, fontWeight: "800", fontSize: 14 },
  workspaceTabTitleActive: { color: colors.text },
  workspaceTabDescription: { color: colors.textDim, fontSize: 11, lineHeight: 16 },
  speedSection: { gap: 12, alignItems: "center", padding: 20, borderRadius: 24, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border, ...Platform.select({ web: { backdropFilter: "blur(18px)", boxShadow: `0 18px 50px ${colors.shadow}` } as object }) },
  centerText: { textAlign: "center" },
  speedPicker: { justifyContent: "center", gap: 10 },
  speedPill: { minWidth: 160, flexBasis: 160, flexGrow: 1, maxWidth: 260, padding: 15, borderRadius: 20, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border, alignItems: "center" },
  speedPillActive: { borderColor: colors.primaryBright, backgroundColor: "rgba(201,95,50,0.12)" },
  speedName: { color: colors.textMuted, fontWeight: "800", fontSize: 14 },
  speedNameActive: { color: colors.text },
  speedDesc: { color: colors.textDim, fontSize: 12, marginTop: 4 },
  hint: { color: colors.textDim, fontSize: 12, lineHeight: 18, textAlign: "center" },
  promptCard: { gap: 14 },
  promptInput: { minHeight: 124, borderRadius: 18, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSoft, color: colors.text, padding: 17, fontSize: 15, lineHeight: 23 },
  promptFooter: { gap: 14 },
  actionButtons: { flexDirection: "row", flexWrap: "wrap", justifyContent: "flex-start", gap: 10 },
  inlineInfo: { flexDirection: "row", alignItems: "center", gap: 7 },
  pressed: { opacity: 0.78, transform: [{ scale: 0.99 }] },
  buttonSpinner: { marginRight: 8 },
  loadingCard: { alignItems: "center", gap: 14 },
  loadingText: { color: colors.text, fontWeight: "700", textAlign: "center" },
  stageRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: 8 },
  stagePill: { flexDirection: "row", alignItems: "center", gap: 5, backgroundColor: colors.surfaceSoft, paddingVertical: 7, paddingHorizontal: 12, borderRadius: 50, overflow: "hidden" },
  stagePillText: { color: colors.textDim, fontSize: 11 },
  stagePillActive: { backgroundColor: "rgba(201,95,50,0.18)" },
  stagePillActiveText: { color: colors.text },
  stagePillDone: { color: colors.success },
  gpuText: { color: colors.textMuted, fontSize: 11 },
  errorTitle: { color: colors.danger, fontWeight: "800", marginBottom: 4 },
  errorMessage: { color: colors.textMuted, lineHeight: 20 },
  cardHeader: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 10 },
  badge: { color: colors.primaryBright, fontSize: 12, fontWeight: "800" },
  modelTag: { color: colors.textDim, fontSize: 12, backgroundColor: colors.surfaceSoft, paddingHorizontal: 9, paddingVertical: 5, borderRadius: 20, overflow: "hidden" },
  enhancedPrompt: { color: colors.textMuted, fontStyle: "italic", lineHeight: 22, marginTop: 14 },
  resultSection: { gap: 16 },
  qualityCard: { gap: 10 },
  qualityScore: { color: colors.text, fontSize: 14, fontWeight: "800", lineHeight: 21 },
  sectionTitle: { alignItems: "center", gap: 5, marginTop: 4 },
  sectionHeading: { color: colors.text, fontWeight: "900", fontSize: 22, textAlign: "center" },
  sectionSubtitle: { color: colors.textMuted, textAlign: "center", lineHeight: 20, fontSize: 13 },
  threeDSection: { gap: 16, marginTop: 10 },
  centeredBlock: { alignItems: "center", gap: 10 },
  ghostButton: { alignSelf: "center", flexDirection: "row", alignItems: "center", gap: 7, paddingHorizontal: 18, paddingVertical: 12 },
  ghostText: { color: colors.textMuted, fontWeight: "700" },
  insightsCard: { gap: 14 },
  insightsHeader: { flexDirection: "row", alignItems: "center", gap: 8 },
  insightsTitle: { color: colors.text, fontWeight: "800", fontSize: 14 },
  metricsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  metricItem: { flexGrow: 1, flexBasis: 180, maxWidth: "50%" as unknown as number, backgroundColor: colors.surfaceSoft, borderRadius: 12, padding: 12, gap: 5 },
  metricLabel: { color: colors.textDim, fontSize: 11 },
  metricValue: { color: colors.text, fontSize: 14, fontWeight: "800" },
});
