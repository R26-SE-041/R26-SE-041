import React, { useRef, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import IconButton from "./IconButton";
import { useAppTheme } from "../theme";

export type FeedbackAgent = "prompt-agent" | "prompt-anatomy" | "prompt-generic" | "image-agent" | "interactive-agent" | "eval-agent" | "threed-agent";
export interface FeedbackReason { code: string; label: string }

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
  const pending = useRef(false);
  const chooseRating = async (next: -1 | 1) => {
    if (pending.current || rating === next) return;
    pending.current = true; setSaving(true); setError(null);
    const previous = rating; setRating(next);
    try {
      const response = await fetch(`${props.apiUrl.replace(/\/$/, "")}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(props.accessToken ? { Authorization: `Bearer ${props.accessToken}` } : {}) },
        body: JSON.stringify({ session_id: props.sessionId, agent_name: props.agentName, output_id: props.outputId,
          parent_feedback_id: next === 1 ? props.parentFeedbackId : undefined, parent_output_id: props.parentOutputId,
          rating: next, reason_codes: [], comment: next === -1 ? "User marked this output as not useful." : undefined,
          input_context: props.inputContext, output_snapshot: props.outputSnapshot }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(messageFrom(data, `Feedback HTTP ${response.status}`));
    } catch (caught) {
      setRating(previous); setError(caught instanceof Error ? caught.message : "Feedback could not be saved. Try again.");
    } finally { pending.current = false; setSaving(false); }
  };
  return <View style={{ marginTop: 12, gap: 6 }}>
    <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
      {([1, -1] as const).map(value => {
        const active = rating === value;
        return <IconButton key={value} label={value === 1 ? "Like output" : "Dislike output"}
          icon={value === 1 ? "thumb-up" : "thumb-down"} selected={active} disabled={saving} onPress={() => void chooseRating(value)} />;
      })}
      {saving && <ActivityIndicator size="small" color={colors.textDim} />}
    </View>
    {error && <Text accessibilityRole="alert" style={{ color: colors.danger, fontSize: 12 }}>{error}</Text>}
  </View>;
}
