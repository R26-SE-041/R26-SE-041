import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { CheckCircle, Upload, ImageUp, ScanText } from "lucide-react-native";

export type Step = "idle" | "uploading" | "enhancing" | "extracting" | "done" | "error";

interface Props {
  step: Step;
  errorMessage?: string;
}

const STEPS = [
  {
    id: "uploading" as Step,
    label: "Uploading image",
    Icon: Upload,
    doneLabel: "Image received",
  },
  {
    id: "enhancing" as Step,
    label: "Enhancing with SRCNN",
    Icon: ImageUp,
    doneLabel: "Image enhanced (4×)",
  },
  {
    id: "extracting" as Step,
    label: "Extracting Sinhala text with TrOCR",
    Icon: ScanText,
    doneLabel: "Sinhala text extracted",
  },
] as const;

const ORDER: Step[] = ["idle", "uploading", "enhancing", "extracting", "done", "error"];

function stepIndex(s: Step) {
  return ORDER.indexOf(s);
}

export default function ProcessingStatus({ step, errorMessage }: Props) {
  if (step === "idle") return null;

  const currentIdx = stepIndex(step);

  return (
    <View style={styles.card}>
      <Text style={styles.sectionLabel}>PROCESSING PIPELINE</Text>

      <View style={styles.steps}>
        {STEPS.map((s) => {
          const sIdx = stepIndex(s.id);
          const isActive = step === s.id;
          const isDone = currentIdx > sIdx && step !== "error";
          const { Icon } = s;

          const iconBg = isDone
            ? "rgba(52,211,153,0.12)"
            : isActive
            ? "rgba(139,92,246,0.15)"
            : "rgba(255,255,255,0.05)";

          const iconColor = isDone ? "#34d399" : isActive ? "#a78bfa" : "rgba(255,255,255,0.2)";
          const labelColor = isDone ? "#34d399" : isActive ? "#c4b5fd" : "rgba(255,255,255,0.25)";

          return (
            <View key={s.id} style={styles.stepRow}>
              {/* Icon */}
              <View
                style={[
                  styles.iconCircle,
                  { backgroundColor: iconBg },
                  isActive && styles.iconCircleActive,
                ]}
              >
                {isDone ? (
                  <CheckCircle size={18} color="#34d399" strokeWidth={1.75} />
                ) : isActive ? (
                  <ActivityIndicator size="small" color="#a78bfa" />
                ) : (
                  <Icon size={18} color={iconColor} strokeWidth={1.75} />
                )}
              </View>

              {/* Label */}
              <Text style={[styles.stepLabel, { color: labelColor }]}>
                {isDone ? s.doneLabel : s.label}
              </Text>

              {/* Badge */}
              {isActive && (
                <View style={styles.runningBadge}>
                  <View style={styles.runningDot} />
                  <Text style={styles.runningText}>Running</Text>
                </View>
              )}
              {isDone && (
                <CheckCircle size={16} color="#34d399" strokeWidth={1.75} />
              )}
            </View>
          );
        })}
      </View>

      {/* Error */}
      {step === "error" && errorMessage && (
        <View style={styles.errorBox}>
          <Text style={styles.errorTitle}>Error</Text>
          <Text style={styles.errorMsg}>{errorMessage}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "rgba(255,255,255,0.03)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
    borderRadius: 20,
    padding: 20,
    marginBottom: 16,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 1.2,
    color: "rgba(255,255,255,0.35)",
    marginBottom: 18,
  },
  steps: {
    gap: 16,
  },
  stepRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  iconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  iconCircleActive: {
    shadowColor: "#7c3aed",
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 6,
    elevation: 4,
  },
  stepLabel: {
    flex: 1,
    fontSize: 14,
    fontWeight: "500",
  },
  runningBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderRadius: 999,
    backgroundColor: "rgba(139,92,246,0.15)",
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  runningDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#a78bfa",
  },
  runningText: {
    fontSize: 11,
    fontWeight: "500",
    color: "#c4b5fd",
  },
  errorBox: {
    marginTop: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(248,113,113,0.2)",
    backgroundColor: "rgba(248,113,113,0.08)",
    padding: 14,
  },
  errorTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: "#f87171",
    marginBottom: 4,
  },
  errorMsg: {
    fontSize: 13,
    color: "rgba(252,165,165,0.75)",
    lineHeight: 20,
  },
});
