import React, { useEffect, useMemo, useState } from "react";
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
import ThreeDViewer from "./components/ThreeDViewer";
import Icon, { IconName, StatusDot } from "./components/Icon";
import { ColorPalette, makeSharedStyles, ThemeProvider, useAppTheme } from "./theme";

const PROMPT_AGENT_URL =
  process.env.EXPO_PUBLIC_PROMPT_AGENT_URL ??
  "https://kojithan-y--prompt-agent-api-dev.modal.run";
const IMAGE_AGENT_URL =
  process.env.EXPO_PUBLIC_IMAGE_AGENT_URL ??
  "https://kojithan-y--image-agent-api-dev.modal.run";
const INTERACTIVE_AGENT_URL =
  process.env.EXPO_PUBLIC_INTERACTIVE_AGENT_URL ??
  "https://kojithan-y--interactive-agent-api-dev.modal.run";
const THREED_AGENT_URL =
  process.env.EXPO_PUBLIC_THREED_AGENT_URL ??
  "https://kojithan-y--threed-agent-api.modal.run";
const BACKEND_HEALTH_URL =
  process.env.EXPO_PUBLIC_BACKEND_HEALTH_URL ??
  "https://kojithan-y--image-gen-orchestrator-api-dev.modal.run";

type Stage = "idle" | "enhancing" | "generating" | "done";
type Mode = "direct" | "enhance";
export type SpeedMode = "normal" | "pro" | "promax";
type ThreeDStage = "idle" | "converting" | "done";
type Health = "ok" | "error" | "checking";
type AgentKey = "prompt" | "image" | "interactive" | "threed";
type ProcessKey = AgentKey;

const THREED_POLL_INTERVAL_MS = 3_000;
const THREED_MAX_WAIT_MS = 20 * 60 * 1_000;
const ESTIMATED_WARM_WINDOW_MS = 5 * 60 * 1_000;
const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const SPEED_MODES: Array<{
  id: SpeedMode;
  label: string;
  icon: IconName;
  desc: string;
  promptGpu: string;
  imageGpu: string;
  interactiveGpu: string;
}> = [
  { id: "normal", label: "Normal", icon: "bolt", desc: "T4 / A10G / A10G", promptGpu: "T4", imageGpu: "A10G", interactiveGpu: "A10G" },
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

export default function App() {
  return <ThemeProvider><Home /></ThemeProvider>;
}

function Home() {
  const { colors, mode: themeMode, toggleTheme } = useAppTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const shared = useMemo(() => makeSharedStyles(colors), [colors]);
  const [prompt, setPrompt] = useState("");
  const [stage, setStage] = useState<Stage>("idle");
  const [mode, setMode] = useState<Mode>("enhance");
  const [speedMode, setSpeedMode] = useState<SpeedMode>("pro");
  const [enhancedPrompt, setEnhancedPrompt] = useState<string | null>(null);
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [threedStage, setThreedStage] = useState<ThreeDStage>("idle");
  const [glbBase64, setGlbBase64] = useState<string | null>(null);
  const [glbSizeKb, setGlbSizeKb] = useState<number>();
  const [threedError, setThreedError] = useState<string | null>(null);
  const [promptHealth, setPromptHealth] = useState<Health>("checking");
  const [imageHealth, setImageHealth] = useState<Health>("checking");
  const [interactiveHealth, setInteractiveHealth] = useState<Health>("checking");
  const [threedHealth, setThreedHealth] = useState<Health>("checking");
  const [backendHealth, setBackendHealth] = useState<Health>("checking");
  const [now, setNow] = useState(Date.now());
  const [warmUntil, setWarmUntil] = useState<Record<AgentKey, number>>({ prompt: 0, image: 0, interactive: 0, threed: 0 });
  const [timings, setTimings] = useState<Partial<Record<ProcessKey, number>>>({});
  const [activeTimers, setActiveTimers] = useState<Partial<Record<ProcessKey, number>>>({});

  const isLoading = stage === "enhancing" || stage === "generating";
  const displayedThreeDHealth: Health =
    backendHealth === "checking" || threedHealth === "checking"
      ? "checking"
      : backendHealth === "ok" && threedHealth === "ok"
        ? "ok"
        : "error";
  const speed = useMemo(
    () => SPEED_MODES.find((item) => item.id === speedMode) ?? SPEED_MODES[1],
    [speedMode],
  );

  useEffect(() => {
    let mounted = true;
    const check = async (url: string, setter: (health: Health) => void) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5_000);
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
      void check(THREED_AGENT_URL, setThreedHealth);
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

  const reset = () => {
    setStage("idle");
    setEnhancedPrompt(null);
    setImageBase64(null);
    setError(null);
    setThreedStage("idle");
    setGlbBase64(null);
    setGlbSizeKb(undefined);
    setThreedError(null);
    setTimings({});
    setActiveTimers({});
  };

  const callEnhance = async (raw: string): Promise<string> => {
    const response = await fetch(`${PROMPT_AGENT_URL}/enhance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_prompt: raw, speed_mode: speedMode }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorMessage(data, `Enhance HTTP ${response.status}`));
    if (data.error && !data.enhanced_prompt) throw new Error(String(data.error));
    return data.enhanced_prompt ?? raw;
  };

  const callGenerate = async (finalPrompt: string): Promise<string> => {
    const response = await fetch(`${IMAGE_AGENT_URL}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: finalPrompt, speed_mode: speedMode }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorMessage(data, `Generate HTTP ${response.status}`));
    if (data.error) throw new Error(String(data.error));
    if (!data.image_base64) throw new Error("Empty image response");
    return data.image_base64;
  };

  const handleSubmit = async (selectedMode: Mode) => {
    if (!prompt.trim() || isLoading) return;
    reset();
    setMode(selectedMode);
    try {
      let finalPrompt = prompt.trim();
      if (selectedMode === "enhance") {
        setStage("enhancing");
        finalPrompt = await runTimed("prompt", () => callEnhance(finalPrompt));
        markWarm("prompt");
        setEnhancedPrompt(finalPrompt);
      }
      setStage("generating");
      setImageBase64(await runTimed("image", () => callGenerate(finalPrompt)));
      markWarm("image");
      setStage("done");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
      setStage("idle");
    }
  };

  const handleConvertTo3D = async () => {
    if (!imageBase64 || threedStage === "converting") return;
    const conversionStartedAt = Date.now();
    setActiveTimers((current) => ({ ...current, threed: conversionStartedAt }));
    setThreedStage("converting");
    setThreedError(null);
    setGlbBase64(null);
    try {
      const response = await fetch(`${THREED_AGENT_URL}/convert/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_base64: imageBase64,
          speed_mode: speedMode,
          texture: true,
          num_inference_steps: speedMode === "promax" ? 50 : 30,
        }),
      });
      const started = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(errorMessage(started, `3D Convert HTTP ${response.status}`));
      if (!started.call_id) throw new Error("3D agent did not return a job ID");

      const deadline = Date.now() + THREED_MAX_WAIT_MS;
      while (Date.now() < deadline) {
        await delay(THREED_POLL_INTERVAL_MS);
        const resultResponse = await fetch(
          `${THREED_AGENT_URL}/convert/result/${encodeURIComponent(started.call_id)}`,
        );
        if (resultResponse.status === 202) continue;
        const data = await resultResponse.json().catch(() => ({}));
        if (!resultResponse.ok) throw new Error(errorMessage(data, `3D Result HTTP ${resultResponse.status}`));
        if (data.error) throw new Error(String(data.error));
        if (!data.glb_base64) throw new Error("Empty GLB response");
        setGlbBase64(data.glb_base64);
        setGlbSizeKb(data.size_kb);
        setThreedStage("done");
        markWarm("threed");
        return;
      }
      throw new Error("3D conversion timed out after 20 minutes");
    } catch (caught) {
      setThreedError(caught instanceof Error ? caught.message : "3D conversion failed");
      setThreedStage("idle");
    } finally {
      setTimings((current) => ({ ...current, threed: Date.now() - conversionStartedAt }));
      setActiveTimers((current) => {
        const next = { ...current };
        delete next.threed;
        return next;
      });
    }
  };

  const loadingLabel = stage === "enhancing"
    ? `Enhancing with Qwen 2.5-3B on ${speed.promptGpu}...`
    : `Generating with FLUX.1-dev on ${speed.imageGpu}...`;

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style={themeMode === "dark" ? "light" : "dark"} />
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
              <Pressable
                accessibilityLabel={`Switch to ${themeMode === "dark" ? "light" : "dark"} mode`}
                onPress={toggleTheme}
                style={({ pressed }) => [styles.themeToggle, pressed && styles.pressed]}
              >
                <Icon color={colors.text} name={themeMode === "dark" ? "sun" : "moon"} size={15} />
                <Text style={styles.themeToggleText}>{themeMode === "dark" ? "Light mode" : "Dark mode"}</Text>
              </Pressable>
              <View style={styles.brandRow}>
                <Text style={styles.brand}>EduVision</Text>
              </View>
              <Text style={styles.title}>Generate & <Text style={styles.titleAccent}>Interact</Text>{"\n"}with Educational AI</Text>
              <Text style={styles.subtitle}>
                Enhance with Qwen 2.5-3B, generate with FLUX.1-dev, and tap any object to analyze with SAM 2 + Qwen2.5-VL.
              </Text>
              <View style={[shared.wrap, styles.healthWrap]}>
                <HealthPill label="Prompt Agent" now={now} status={promptHealth} warmUntil={warmUntil.prompt} />
                <HealthPill label="Image Agent" now={now} status={imageHealth} warmUntil={warmUntil.image} />
                <HealthPill label="Interactive Agent" now={now} status={interactiveHealth} warmUntil={warmUntil.interactive} />
                <HealthPill label="3D Agent" now={now} status={displayedThreeDHealth} warmUntil={warmUntil.threed} />
              </View>
              <Text style={styles.warmNote}>Warm time is an estimate based on successful activity in this session.</Text>
            </View>

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
                {speedMode === "normal" && "Standard GPUs - same quality, moderate wait times."}
                {speedMode === "pro" && "Upgraded GPUs - faster enhancement and interactive analysis."}
                {speedMode === "promax" && "Top-tier GPUs - maximum speed across all stages."}
              </Text>
            </View>

            <View style={[shared.card, styles.promptCard]}>
              <Text style={shared.label}>Your Prompt</Text>
              <TextInput
                accessibilityLabel="Your prompt"
                editable={!isLoading}
                multiline
                numberOfLines={4}
                onChangeText={setPrompt}
                placeholder="e.g. photosynthesis diagram for 8th graders with labeled chloroplasts"
                placeholderTextColor={colors.textDim}
                style={styles.promptInput}
                textAlignVertical="top"
                value={prompt}
              />
              <View style={styles.promptFooter}>
                <Text style={styles.hint}>Direct skips enhancement. Enhance uses Qwen 2.5-3B.</Text>
                <View style={styles.actionButtons}>
                  <ActionButton
                    disabled={isLoading || !prompt.trim()}
                    icon="bolt"
                    label={mode === "direct" && isLoading ? "Generating..." : "Direct"}
                    loading={mode === "direct" && isLoading}
                    onPress={() => handleSubmit("direct")}
                    secondary
                  />
                  <ActionButton
                    disabled={isLoading || !prompt.trim()}
                    icon="wand"
                    label={mode === "enhance" && stage === "enhancing" ? "Enhancing..." : mode === "enhance" && stage === "generating" ? "Generating..." : "Enhance and Generate"}
                    loading={mode === "enhance" && isLoading}
                    onPress={() => handleSubmit("enhance")}
                  />
                </View>
              </View>
            </View>

            {isLoading && (
              <View style={[shared.card, styles.loadingCard]} accessibilityLiveRegion="polite">
                <ActivityIndicator color={colors.primaryBright} size="large" />
                <Text style={styles.loadingText}>{loadingLabel}</Text>
                {mode === "enhance" && (
                  <View style={styles.stageRow}>
                    <StagePill active={stage === "enhancing"} done={stage === "generating"} label="Enhance" />
                    <StagePill active={stage === "generating"} label="Generate" />
                  </View>
                )}
                <View style={styles.inlineInfo}><Icon color={colors.textMuted} name={speed.icon} size={14} /><Text style={styles.gpuText}>{speed.label}. GPU: {stage === "enhancing" ? speed.promptGpu : speed.imageGpu}</Text></View>
              </View>
            )}

            {(Object.keys(timings).length > 0 || Object.keys(activeTimers).length > 0) && (
              <PerformanceInsights activeTimers={activeTimers} now={now} timings={timings} />
            )}

            {error && <ErrorBanner title="Failed" message={error} />}

            {enhancedPrompt && stage !== "enhancing" && (
              <View style={shared.card}>
                <View style={styles.cardHeader}>
                  <View style={styles.inlineInfo}><Icon color={colors.primaryBright} name="wand" size={15} /><Text style={styles.badge}>Enhanced Prompt</Text></View>
                  <Text style={styles.modelTag}>Qwen 2.5-3B. {speed.promptGpu}</Text>
                </View>
                <Text style={styles.enhancedPrompt}>{`"${enhancedPrompt}"`}</Text>
              </View>
            )}

            {imageBase64 && stage === "done" && (
              <View style={styles.resultSection}>
                <SectionTitle title="Interactive Image Analysis" subtitle="Tap any object or drag a box to segment with SAM 2 and explain with Qwen2.5-VL" />
                <InteractiveCanvas
                  imageBase64={imageBase64}
                  onOperationComplete={(duration) => {
                    setTimings((current) => ({ ...current, interactive: duration }));
                    markWarm("interactive");
                  }}
                  speedMode={speedMode}
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

            {stage === "done" && (
              <Pressable onPress={reset} style={styles.ghostButton}>
                <Icon color={colors.textMuted} name="arrow-left" size={16} /><Text style={styles.ghostText}>New prompt</Text>
              </Pressable>
            )}
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
  safeArea: { flex: 1, backgroundColor: colors.background },
  scrollContent: { flexGrow: 1, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 28 },
  container: { width: "100%", maxWidth: 980, alignSelf: "center", gap: 16 },
  header: { alignItems: "center", paddingVertical: 12, gap: 0 },
  themeToggle: { alignSelf: "flex-end", flexDirection: "row", alignItems: "center", gap: 7, backgroundColor: colors.surfaceSoft, borderColor: colors.border, borderWidth: 1, borderRadius: 50, paddingHorizontal: 13, paddingVertical: 11, marginBottom: 4, minHeight: 44 },
  themeToggleText: { color: colors.text, fontSize: 12, fontWeight: "800" },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 12 },
  brand: { color: colors.text, fontSize: 18, fontWeight: "800", letterSpacing: 0.4 },
  title: { color: colors.text, fontSize: 32, lineHeight: 40, fontWeight: "900", textAlign: "center", letterSpacing: -0.8 },
  titleAccent: { color: colors.primaryBright },
  subtitle: { color: colors.textMuted, textAlign: "center", fontSize: 15, lineHeight: 23, maxWidth: 680, marginTop: 10 },
  healthWrap: { justifyContent: "center", gap: 8, marginTop: 12 },
  healthPill: { gap: 7, paddingVertical: 9, paddingHorizontal: 12, borderRadius: 14, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border },
  agentSignals: { flexDirection: "row", alignItems: "center", gap: 10 },
  signal: { flexDirection: "row", alignItems: "center", gap: 5 },
  healthLabel: { color: colors.textMuted, fontSize: 12, fontWeight: "600" },
  healthState: { color: colors.textDim, fontSize: 12 },
  warmNote: { color: colors.textDim, fontSize: 12, textAlign: "center", marginTop: 9 },
  speedSection: { gap: 12, alignItems: "center" },
  centerText: { textAlign: "center" },
  speedPicker: { justifyContent: "center", gap: 10 },
  speedPill: { minWidth: 160, flexBasis: 160, flexGrow: 1, maxWidth: 260, padding: 14, borderRadius: 16, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border, alignItems: "center" },
  speedPillActive: { borderColor: colors.primaryBright, backgroundColor: "rgba(139,92,246,0.17)" },
  speedName: { color: colors.textMuted, fontWeight: "800", fontSize: 14 },
  speedNameActive: { color: colors.text },
  speedDesc: { color: colors.textDim, fontSize: 12, marginTop: 4 },
  hint: { color: colors.textDim, fontSize: 12, lineHeight: 18, textAlign: "center" },
  promptCard: { gap: 14 },
  promptInput: { minHeight: 112, borderRadius: 14, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSoft, color: colors.text, padding: 14, fontSize: 15, lineHeight: 22 },
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
  stagePillActive: { backgroundColor: "rgba(139,92,246,0.27)" },
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
