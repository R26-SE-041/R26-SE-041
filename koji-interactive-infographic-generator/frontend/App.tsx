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

const THREED_POLL_INTERVAL_MS = 3_000;
const THREED_MAX_WAIT_MS = 20 * 60 * 1_000;
const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const SPEED_MODES: Array<{
  id: SpeedMode;
  label: string;
  icon: string;
  desc: string;
  promptGpu: string;
  imageGpu: string;
  interactiveGpu: string;
}> = [
  { id: "normal", label: "Normal", icon: "⚡", desc: "T4 · A10G · A10G", promptGpu: "T4", imageGpu: "A10G", interactiveGpu: "A10G" },
  { id: "pro", label: "Pro", icon: "🚀", desc: "A10G · A100 · A100", promptGpu: "A10G", imageGpu: "A100", interactiveGpu: "A100" },
  { id: "promax", label: "Pro Max", icon: "⚡⚡", desc: "A10G · H100 · H100", promptGpu: "A10G", imageGpu: "H100", interactiveGpu: "H100" },
];

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

  const reset = () => {
    setStage("idle");
    setEnhancedPrompt(null);
    setImageBase64(null);
    setError(null);
    setThreedStage("idle");
    setGlbBase64(null);
    setGlbSizeKb(undefined);
    setThreedError(null);
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
        finalPrompt = await callEnhance(finalPrompt);
        setEnhancedPrompt(finalPrompt);
      }
      setStage("generating");
      setImageBase64(await callGenerate(finalPrompt));
      setStage("done");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown error");
      setStage("idle");
    }
  };

  const handleConvertTo3D = async () => {
    if (!imageBase64 || threedStage === "converting") return;
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
        return;
      }
      throw new Error("3D conversion timed out after 20 minutes");
    } catch (caught) {
      setThreedError(caught instanceof Error ? caught.message : "3D conversion failed");
      setThreedStage("idle");
    }
  };

  const loadingLabel = stage === "enhancing"
    ? `✦ Enhancing with Qwen 2.5-3B on ${speed.promptGpu}…`
    : `🎨 Generating with FLUX.1-dev on ${speed.imageGpu}…`;

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
                <Text style={styles.themeToggleText}>{themeMode === "dark" ? "☀ Light" : "☾ Dark"}</Text>
              </Pressable>
              <View style={styles.brandRow}>
                <View style={styles.logo}><Text style={styles.logoGlyph}>✦</Text></View>
                <Text style={styles.brand}>EduVision</Text>
              </View>
              <Text style={styles.title}>Generate & <Text style={styles.titleAccent}>Interact</Text>{"\n"}with Educational AI</Text>
              <Text style={styles.subtitle}>
                Enhance with Qwen 2.5-3B, generate with FLUX.1-dev, and tap any object to analyze with SAM 2 + Qwen2.5-VL.
              </Text>
              <View style={[shared.wrap, styles.healthWrap]}>
                <HealthPill label="Prompt Agent" status={promptHealth} />
                <HealthPill label="Image Agent" status={imageHealth} />
                <HealthPill label="Interactive Agent" status={interactiveHealth} />
                <HealthPill label="3D Agent" status={displayedThreeDHealth} />
              </View>
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
                      <Text style={styles.speedIcon}>{item.icon}</Text>
                      <Text style={[styles.speedName, selected && styles.speedNameActive]}>{item.label}</Text>
                      <Text style={styles.speedDesc}>{item.desc}</Text>
                    </Pressable>
                  );
                })}
              </View>
              <Text style={styles.hint}>
                {speedMode === "normal" && "Standard GPUs — same quality, moderate wait times."}
                {speedMode === "pro" && "Upgraded GPUs — faster enhancement & interactive analysis."}
                {speedMode === "promax" && "Top-tier GPUs — maximum speed across all stages."}
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
                <Text style={styles.hint}>Direct skips enhancement · Enhance uses Qwen 2.5-3B</Text>
                <View style={styles.actionButtons}>
                  <ActionButton
                    disabled={isLoading || !prompt.trim()}
                    label={mode === "direct" && isLoading ? "Generating…" : "⚡ Direct"}
                    loading={mode === "direct" && isLoading}
                    onPress={() => handleSubmit("direct")}
                    secondary
                  />
                  <ActionButton
                    disabled={isLoading || !prompt.trim()}
                    label={mode === "enhance" && stage === "enhancing" ? "Enhancing…" : mode === "enhance" && stage === "generating" ? "Generating…" : "✦ Enhance & Generate"}
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
                <Text style={styles.gpuText}>{speed.icon} {speed.label} · GPU: {stage === "enhancing" ? speed.promptGpu : speed.imageGpu}</Text>
              </View>
            )}

            {error && <ErrorBanner title="Failed" message={error} />}

            {enhancedPrompt && stage !== "enhancing" && (
              <View style={shared.card}>
                <View style={styles.cardHeader}>
                  <Text style={styles.badge}>✦ Enhanced Prompt</Text>
                  <Text style={styles.modelTag}>Qwen 2.5-3B · {speed.promptGpu}</Text>
                </View>
                <Text style={styles.enhancedPrompt}>“{enhancedPrompt}”</Text>
              </View>
            )}

            {imageBase64 && stage === "done" && (
              <View style={styles.resultSection}>
                <SectionTitle title="Interactive Image Analysis" subtitle="Tap any object or drag a box to segment with SAM 2 and explain with Qwen2.5-VL" />
                <InteractiveCanvas imageBase64={imageBase64} speedMode={speedMode} />

                <View style={styles.threeDSection}>
                  <SectionTitle title="🧊 2D → 3D Conversion" subtitle="Convert your generated image into a textured 3D model using Hunyuan3D-2" />
                  {threedStage === "idle" && (
                    <View style={styles.centeredBlock}>
                      <ActionButton label={`🧊 Convert to 3D  ·  ${speedMode === "promax" ? "H100" : speedMode === "pro" ? "A100" : "A10G"}`} onPress={handleConvertTo3D} />
                      <Text style={styles.hint}>{speedMode === "promax" ? "Pro Max · H100 · ~2–3 min (shape + texture)" : "A10G/A100 · ~3–5 min (shape + texture)"}</Text>
                    </View>
                  )}
                  {threedStage === "converting" && (
                    <View style={[shared.card, styles.loadingCard]}>
                      <ActivityIndicator color={colors.cyan} size="large" />
                      <Text style={styles.loadingText}>🧊 Hunyuan3D-2 — generating shape & texture…</Text>
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
                      <Text style={styles.ghostText}>↻ Convert again</Text>
                    </Pressable>
                  )}
                </View>
              </View>
            )}

            {stage === "done" && (
              <Pressable onPress={reset} style={styles.ghostButton}>
                <Text style={styles.ghostText}>← New prompt</Text>
              </Pressable>
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function ActionButton({ disabled = false, label, loading = false, onPress, secondary = false }: { disabled?: boolean; label: string; loading?: boolean; onPress: () => void; secondary?: boolean }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  const shared = makeSharedStyles(colors);
  return (
    <Pressable disabled={disabled} onPress={onPress} style={({ pressed }) => [shared.button, secondary ? shared.secondaryButton : shared.primaryButton, pressed && styles.pressed, disabled && shared.disabled]}>
      {loading && <ActivityIndicator color="#fff" size="small" style={styles.buttonSpinner} />}
      <Text style={shared.buttonText}>{label}</Text>
    </Pressable>
  );
}

function HealthPill({ label, status }: { label: string; status: Health }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  return (
    <View style={styles.healthPill}>
      <View style={[styles.healthDot, status === "ok" ? styles.healthOk : status === "error" ? styles.healthError : styles.healthChecking]} />
      <Text style={styles.healthLabel}>{label}</Text>
      <Text style={styles.healthState}>{status === "ok" ? "online" : status === "error" ? "offline" : "…"}</Text>
    </View>
  );
}

function StagePill({ active = false, done = false, label }: { active?: boolean; done?: boolean; label: string }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  return <Text style={[styles.stagePill, active && styles.stagePillActive, done && styles.stagePillDone]}>{done ? "✓ " : ""}{label}</Text>;
}

function SectionTitle({ title, subtitle }: { title: string; subtitle: string }) {
  const { colors } = useAppTheme();
  const styles = makeStyles(colors);
  return <View style={styles.sectionTitle}><Text style={styles.sectionHeading}>{title}</Text><Text style={styles.sectionSubtitle}>{subtitle}</Text></View>;
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
  scrollContent: { flexGrow: 1, paddingHorizontal: 16, paddingVertical: 28 },
  container: { width: "100%", maxWidth: 980, alignSelf: "center", gap: 20 },
  header: { alignItems: "center", paddingVertical: 24 },
  themeToggle: { alignSelf: "flex-end", backgroundColor: colors.surfaceSoft, borderColor: colors.border, borderWidth: 1, borderRadius: 50, paddingHorizontal: 13, paddingVertical: 8, marginBottom: 4 },
  themeToggleText: { color: colors.text, fontSize: 12, fontWeight: "800" },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 22 },
  logo: { width: 36, height: 36, borderRadius: 12, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  logoGlyph: { color: "white", fontSize: 22 },
  brand: { color: colors.text, fontSize: 18, fontWeight: "800", letterSpacing: 0.4 },
  title: { color: colors.text, fontSize: 38, lineHeight: 45, fontWeight: "900", textAlign: "center", letterSpacing: -1.2 },
  titleAccent: { color: colors.primaryBright },
  subtitle: { color: colors.textMuted, textAlign: "center", fontSize: 15, lineHeight: 23, maxWidth: 680, marginTop: 14 },
  healthWrap: { justifyContent: "center", gap: 8, marginTop: 18 },
  healthPill: { flexDirection: "row", alignItems: "center", gap: 7, paddingVertical: 7, paddingHorizontal: 11, borderRadius: 50, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border },
  healthDot: { width: 7, height: 7, borderRadius: 4 },
  healthOk: { backgroundColor: colors.success },
  healthError: { backgroundColor: colors.danger },
  healthChecking: { backgroundColor: colors.warning },
  healthLabel: { color: colors.textMuted, fontSize: 11, fontWeight: "600" },
  healthState: { color: colors.textDim, fontSize: 10 },
  speedSection: { gap: 12, alignItems: "center" },
  centerText: { textAlign: "center" },
  speedPicker: { justifyContent: "center", gap: 10 },
  speedPill: { minWidth: 160, flexGrow: 1, maxWidth: 250, padding: 14, borderRadius: 16, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border, alignItems: "center" },
  speedPillActive: { borderColor: colors.primaryBright, backgroundColor: "rgba(139,92,246,0.17)" },
  speedIcon: { fontSize: 18, marginBottom: 4 },
  speedName: { color: colors.textMuted, fontWeight: "800", fontSize: 14 },
  speedNameActive: { color: colors.text },
  speedDesc: { color: colors.textDim, fontSize: 10, marginTop: 4 },
  hint: { color: colors.textDim, fontSize: 12, lineHeight: 18, textAlign: "center" },
  promptCard: { gap: 12 },
  promptInput: { minHeight: 112, borderRadius: 14, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSoft, color: colors.text, padding: 14, fontSize: 15, lineHeight: 22 },
  promptFooter: { gap: 14 },
  actionButtons: { flexDirection: "row", flexWrap: "wrap", justifyContent: "flex-end", gap: 10 },
  pressed: { opacity: 0.78, transform: [{ scale: 0.99 }] },
  buttonSpinner: { marginRight: 8 },
  loadingCard: { alignItems: "center", gap: 14 },
  loadingText: { color: colors.text, fontWeight: "700", textAlign: "center" },
  stageRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: 8 },
  stagePill: { color: colors.textDim, backgroundColor: colors.surfaceSoft, paddingVertical: 7, paddingHorizontal: 12, borderRadius: 50, overflow: "hidden", fontSize: 11 },
  stagePillActive: { color: colors.text, backgroundColor: "rgba(139,92,246,0.27)" },
  stagePillDone: { color: colors.success },
  gpuText: { color: colors.textMuted, fontSize: 11 },
  errorTitle: { color: colors.danger, fontWeight: "800", marginBottom: 4 },
  errorMessage: { color: colors.textMuted, lineHeight: 20 },
  cardHeader: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 10 },
  badge: { color: colors.primaryBright, fontSize: 12, fontWeight: "800" },
  modelTag: { color: colors.textDim, fontSize: 10, backgroundColor: colors.surfaceSoft, paddingHorizontal: 9, paddingVertical: 5, borderRadius: 20, overflow: "hidden" },
  enhancedPrompt: { color: colors.textMuted, fontStyle: "italic", lineHeight: 22, marginTop: 14 },
  resultSection: { gap: 20 },
  sectionTitle: { alignItems: "center", gap: 6, marginTop: 8 },
  sectionHeading: { color: colors.text, fontWeight: "900", fontSize: 22, textAlign: "center" },
  sectionSubtitle: { color: colors.textMuted, textAlign: "center", lineHeight: 20, fontSize: 13 },
  threeDSection: { gap: 16, marginTop: 10 },
  centeredBlock: { alignItems: "center", gap: 10 },
  ghostButton: { alignSelf: "center", paddingHorizontal: 18, paddingVertical: 12 },
  ghostText: { color: colors.textMuted, fontWeight: "700" },
});
