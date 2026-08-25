import React, { useMemo, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import Icon from "./Icon";
import { ColorPalette, useAppTheme } from "../theme";

export type FeedbackAgent = "prompt-agent" | "prompt-anatomy" | "prompt-generic" | "image-agent" | "interactive-agent" | "eval-agent" | "threed-agent";
export interface FeedbackReason { code: string; label: string }

interface FeedbackControlsProps {
  accessToken?: string;
  agentName: FeedbackAgent;
  apiUrl: string;
  inputContext: Record<string, unknown>;
  negativeReasons: FeedbackReason[];
  onRegenerate?: (feedback: string, feedbackId: string, outputId: string) => Promise<void> | void;
  outputId: string;
  outputSnapshot: Record<string, unknown>;
  parentFeedbackId?: string;
  parentOutputId?: string;
  positiveReasons: FeedbackReason[];
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
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [rating, setRating] = useState<-1 | 1 | null>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "saved">("idle");
  const [regenerated, setRegenerated] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const options = rating === 1 ? props.positiveReasons : props.negativeReasons;

  const chooseRating = (next: -1 | 1) => {
    if (status === "saved") return;
    if (rating === next) {
      setRating(null);
      setReasons([]);
      setComment("");
      setError(null);
      return;
    }
    setRating(next);
    setReasons([]);
    setComment("");
    setRegenerated(false);
    setError(null);
  };

  const toggleReason = (code: string) => {
    setReasons((current) => current.includes(code) ? current.filter((item) => item !== code) : [...current, code]);
  };

  const submit = async (regenerate: boolean) => {
    if (!rating || status !== "idle") return;
    if (reasons.length === 0) {
      setError(`Select what ${rating === 1 ? "worked" : "needs correction"}.`);
      return;
    }
    setStatus("saving");
    setError(null);
    try {
      const response = await fetch(`${props.apiUrl.replace(/\/$/, "")}/feedback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(props.accessToken ? { Authorization: `Bearer ${props.accessToken}` } : {}),
        },
        body: JSON.stringify({
          session_id: props.sessionId,
          agent_name: props.agentName,
          output_id: props.outputId,
          parent_feedback_id: rating === 1 ? props.parentFeedbackId : undefined,
          parent_output_id: props.parentOutputId,
          rating,
          reason_codes: reasons,
          comment: comment.trim() || undefined,
          input_context: props.inputContext,
          output_snapshot: props.outputSnapshot,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(messageFrom(data, `Feedback HTTP ${response.status}`));
      if (regenerate && rating === -1 && props.onRegenerate) {
        const labels = options.filter((item) => reasons.includes(item.code)).map((item) => item.label);
        const feedback = [...labels, comment.trim()].filter(Boolean).join(". ");
        await props.onRegenerate(feedback, String(data.feedback_id), props.outputId);
      }
      setRegenerated(regenerate);
      setStatus("saved");
    } catch (caught) {
      setStatus("idle");
      setError(caught instanceof Error ? caught.message : "Feedback could not be saved");
    }
  };

  if (status === "saved") {
    return <View style={styles.saved}><Icon color={colors.success} name="check" size={15} /><Text style={styles.savedText}>{rating === 1 ? "Preference saved" : regenerated ? "Feedback saved; corrected retry requested" : "Feedback saved"}</Text></View>;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.question}>Was this {props.agentName.replace("-agent", "")} output useful?</Text>
      <View style={styles.row}>
        <Pressable accessibilityLabel="Like output" onPress={() => chooseRating(1)} style={[styles.ratingButton, rating === 1 && styles.likeActive]}>
          <Icon color={rating === 1 ? colors.success : colors.textMuted} name="thumb-up" size={17} /><Text style={styles.buttonText}>Like</Text>
        </Pressable>
        <Pressable accessibilityLabel="Dislike output" onPress={() => chooseRating(-1)} style={[styles.ratingButton, rating === -1 && styles.dislikeActive]}>
          <Icon color={rating === -1 ? colors.danger : colors.textMuted} name="thumb-down" size={17} /><Text style={styles.buttonText}>Dislike</Text>
        </Pressable>
      </View>
      {rating && (
        <View style={styles.panel}>
          <Text style={styles.panelLabel}>{rating === 1 ? "What worked?" : "What should be corrected?"}</Text>
          <View style={styles.reasonRow}>
            {options.map((reason) => (
              <Pressable key={reason.code} onPress={() => toggleReason(reason.code)} style={[styles.reason, reasons.includes(reason.code) && styles.reasonActive]}>
                <Text style={[styles.reasonText, reasons.includes(reason.code) && styles.reasonTextActive]}>{reason.label}</Text>
              </Pressable>
            ))}
          </View>
          <TextInput
            maxLength={2000}
            multiline
            onChangeText={setComment}
            placeholder="Optional detail"
            placeholderTextColor={colors.textDim}
            style={styles.comment}
            value={comment}
          />
          {error && <Text style={styles.error}>{error}</Text>}
          <View style={styles.submitRow}>
            <Pressable disabled={status === "saving"} onPress={() => submit(false)} style={[styles.submit, rating === -1 && props.onRegenerate && styles.submitSecondary, status === "saving" && styles.disabled]}>
              {status === "saving" && <ActivityIndicator color={rating === -1 && props.onRegenerate ? colors.text : "#fff"} size="small" />}
              <Text style={[styles.submitText, rating === -1 && props.onRegenerate && styles.submitSecondaryText]}>Submit</Text>
            </Pressable>
            {rating === -1 && props.onRegenerate && (
              <Pressable disabled={status === "saving"} onPress={() => submit(true)} style={[styles.submit, status === "saving" && styles.disabled]}>
                <Text style={styles.submitText}>Submit & regenerate</Text>
              </Pressable>
            )}
          </View>
        </View>
      )}
    </View>
  );
}

const makeStyles = (colors: ColorPalette) => StyleSheet.create({
  container: { marginTop: 14, gap: 10, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 14 },
  question: { color: colors.textDim, fontSize: 12, fontWeight: "700" },
  row: { flexDirection: "row", gap: 8 },
  ratingButton: { flexDirection: "row", alignItems: "center", gap: 7, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 9 },
  likeActive: { borderColor: colors.success },
  dislikeActive: { borderColor: colors.danger },
  buttonText: { color: colors.textMuted, fontSize: 12, fontWeight: "700" },
  panel: { gap: 10, backgroundColor: colors.surfaceSoft, borderRadius: 12, padding: 12 },
  panelLabel: { color: colors.text, fontSize: 12, fontWeight: "800" },
  reasonRow: { flexDirection: "row", flexWrap: "wrap", gap: 7 },
  reason: { borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingHorizontal: 10, paddingVertical: 7 },
  reasonActive: { borderColor: colors.primaryBright, backgroundColor: "rgba(139,92,246,0.18)" },
  reasonText: { color: colors.textDim, fontSize: 11 },
  reasonTextActive: { color: colors.text },
  comment: { minHeight: 54, color: colors.text, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 10, fontSize: 12 },
  submit: { alignSelf: "flex-start", flexDirection: "row", alignItems: "center", gap: 7, backgroundColor: colors.primary, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10 },
  submitRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  submitSecondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.primaryBright },
  submitText: { color: "#fff", fontWeight: "800", fontSize: 12 },
  submitSecondaryText: { color: colors.text },
  error: { color: colors.danger, fontSize: 11 },
  disabled: { opacity: 0.55 },
  saved: { marginTop: 14, flexDirection: "row", alignItems: "center", gap: 7 },
  savedText: { color: colors.success, fontSize: 12, fontWeight: "700" },
});
