import React, { useRef, useState } from "react";
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native";
import IconButton from "./IconButton";
import { useAppTheme } from "../theme";

export type FeedbackAgent = "prompt-agent" | "prompt-anatomy" | "prompt-generic" | "image-agent" | "interactive-agent" | "eval-agent" | "threed-agent";
export interface FeedbackReason { code: string; label: string }
const DEFAULT_REASONS: FeedbackReason[] = [
  { code: "poor_quality", label: "Poor quality" },
  { code: "missed_request", label: "Didn't follow my request" },
  { code: "incorrect_details", label: "Incorrect details" },
];

interface FeedbackControlsProps {
  accessToken?: string;
  agentName: FeedbackAgent;
  apiUrl: string;
  inputContext: Record<string, unknown>;
  negativeReasons?: FeedbackReason[];
  onRegenerate?: (feedback: string, feedbackId: string, outputId: string) => Promise<void> | void;
  outputId: string;
  outputSnapshot: Record<string, unknown>;
  parentFeedbackId?: string;
  parentOutputId?: string;
  positiveReasons?: FeedbackReason[];
  sessionId: string;
}

export function createOutputId(agent: string): string {
  return `${agent}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function messageFrom(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const value = payload as { detail?: unknown; error?: unknown };
  if (typeof value.error === "string") return value.error;
  if (typeof value.detail === "string") return value.detail;
  if (value.detail && typeof value.detail === "object") {
    const detail = value.detail as { error?: unknown; detail?: unknown };
    if (typeof detail.error === "string") return detail.error;
    if (typeof detail.detail === "string") return detail.detail;
  }
  return fallback;
}

export default function FeedbackControls(props: FeedbackControlsProps) {
  const { colors } = useAppTheme();
  const [rating, setRating] = useState<-1 | 1 | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const [comment, setComment] = useState("");
  const [detailsSaved, setDetailsSaved] = useState(false);
  const pending = useRef(false);
  const send = async (next: -1 | 1 | null, codes: string[] = [], note = "") => {
    const response = await fetch(`${props.apiUrl.replace(/\/$/, "")}/feedback`, {
      method: next === null ? "DELETE" : "POST",
      headers: { "Content-Type": "application/json", ...(props.accessToken ? { Authorization: `Bearer ${props.accessToken}` } : {}) },
      body: JSON.stringify(next === null ? { agent_name: props.agentName, output_id: props.outputId } : {
        session_id: props.sessionId, agent_name: props.agentName, output_id: props.outputId,
        parent_feedback_id: next === 1 ? props.parentFeedbackId : undefined, parent_output_id: props.parentOutputId,
        rating: next, reason_codes: codes, comment: note.trim() || undefined,
        input_context: props.inputContext, output_snapshot: props.outputSnapshot,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(messageFrom(data, `Feedback HTTP ${response.status}`));
  };
  const chooseRating = async (next: -1 | 1) => {
    if (pending.current) return;
    pending.current = true; setSaving(true); setError(null);
    const previous = rating, value = rating === next ? null : next;
    setRating(value);
    try {
      await send(value);
      setReasons([]); setComment(""); setDetailsSaved(false);
    } catch (caught) {
      setRating(previous); setError(caught instanceof Error ? caught.message : "Feedback could not be saved. Try again.");
    } finally { pending.current = false; setSaving(false); }
  };
  const saveDetails = async () => {
    if (pending.current || rating !== -1) return;
    pending.current = true; setSaving(true); setError(null);
    try { await send(-1, reasons, comment); setDetailsSaved(true); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Feedback could not be saved. Try again."); }
    finally { pending.current = false; setSaving(false); }
  };
  return <View style={{ marginTop: 12, gap: 6 }}>
    <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
      {([1, -1] as const).map(value => {
        const active = rating === value;
        return <IconButton key={value} label={value === 1 ? "Like output" : "Dislike output"}
          icon={value === 1 ? "thumb-up" : "thumb-down"} variant="plain" filled={active} selected={active} disabled={saving} onPress={() => void chooseRating(value)} />;
      })}
      {saving && <ActivityIndicator size="small" color={colors.textDim} />}
    </View>
    {rating === -1 && <View style={{ gap: 12, paddingVertical: 12 }}>
      <Text style={{ color: colors.text, fontSize: 14, fontWeight: "600" }}>What could be improved? <Text style={{ color: colors.textMuted, fontWeight: "400" }}>(optional)</Text></Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {(props.negativeReasons?.length ? props.negativeReasons : DEFAULT_REASONS).map(reason => {
          const selected = reasons.includes(reason.code);
          return <Pressable key={reason.code} accessibilityRole="checkbox" accessibilityLabel={reason.label} accessibilityState={{ checked: selected, disabled: saving }} disabled={saving}
            onPress={() => { setReasons(current => selected ? current.filter(code => code !== reason.code) : [...current, reason.code].slice(0, 8)); setDetailsSaved(false); }}
            style={{ minHeight: 44, justifyContent: "center", paddingHorizontal: 12, borderRadius: 8, borderWidth: 1, borderColor: selected ? colors.text : colors.border, backgroundColor: selected ? colors.surfaceSoft : "transparent" }}>
            <Text style={{ color: colors.text, fontSize: 13 }}>{reason.label}</Text>
          </Pressable>;
        })}
      </View>
      <TextInput accessibilityLabel="Optional feedback comment" placeholder="Tell us more (optional)" placeholderTextColor={colors.textDim} multiline maxLength={2000} value={comment} editable={!saving}
        onChangeText={value => { setComment(value); setDetailsSaved(false); }}
        style={{ minHeight: 80, padding: 12, borderRadius: 8, borderWidth: 1, borderColor: colors.border, color: colors.text, backgroundColor: colors.surface, textAlignVertical: "top" }} />
      <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
        <Pressable accessibilityRole="button" disabled={saving || detailsSaved || (!reasons.length && !comment.trim())} onPress={() => void saveDetails()}
          style={{ minHeight: 44, paddingHorizontal: 16, justifyContent: "center", borderRadius: 8, backgroundColor: colors.buttonBackground, opacity: saving || detailsSaved || (!reasons.length && !comment.trim()) ? .45 : 1 }}>
          <Text style={{ color: colors.onButton }}>Send feedback</Text>
        </Pressable>
        {detailsSaved && <Text accessibilityLiveRegion="polite" style={{ color: colors.textMuted, fontSize: 12 }}>Feedback saved. Thank you.</Text>}
      </View>
    </View>}
    {error && <Text accessibilityRole="alert" style={{ color: colors.danger, fontSize: 12 }}>{error}</Text>}
  </View>;
}
