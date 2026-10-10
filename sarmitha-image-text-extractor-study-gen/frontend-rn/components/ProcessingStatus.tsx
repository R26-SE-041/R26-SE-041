import React from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { Check } from "lucide-react-native";
import { fonts, glassSurface, useAppTheme } from "@/theme";

export type Step = "idle" | "uploading" | "enhancing" | "extracting" | "done" | "error";
interface Props { step: Step; errorMessage?: string; }

const STEPS = [
  { id: "uploading" as Step, label: "Uploading image", doneLabel: "Image received" },
  { id: "enhancing" as Step, label: "Enhancing with SwinSR", doneLabel: "Image enhanced · 4×" },
  { id: "extracting" as Step, label: "Extracting Sinhala text", doneLabel: "Sinhala text extracted" },
] as const;
const ORDER: Step[] = ["idle", "uploading", "enhancing", "extracting", "done", "error"];

export default function ProcessingStatus({ step, errorMessage }: Props) {
  const { colors } = useAppTheme();
  if (step === "idle") return null;
  const currentIndex = ORDER.indexOf(step);

  return (
    <View style={[styles.card, glassSurface(colors)]}>
      <Text style={[styles.sectionLabel, { color: colors.textDim }]}>PROCESSING STATUS</Text>
      <Text style={[styles.title, { color: colors.text }]}>Turning pixels into text</Text>
      <View style={styles.steps}>
        {STEPS.map((item, index) => {
          const isActive = step === item.id;
          const isDone = currentIndex > ORDER.indexOf(item.id) && step !== "error";
          return (
            <View key={item.id} style={[styles.stepRow, { backgroundColor: colors.surfaceSoft, borderColor: colors.border }]}>
              <View style={[styles.number, { backgroundColor: isDone ? colors.success : isActive ? colors.primary : colors.canvas }]}>
                {isDone ? <Check size={15} color="#ffffff" strokeWidth={3} /> : <Text style={[styles.numberText, { color: isActive ? "#ffffff" : colors.textDim }]}>{index + 1}</Text>}
              </View>
              <View style={styles.stepCopy}>
                <Text style={[styles.stepLabel, { color: isDone ? colors.success : isActive ? colors.text : colors.textMuted }]}>{isDone ? item.doneLabel : item.label}</Text>
                <Text style={[styles.stepMeta, { color: colors.textDim }]}>{isDone ? "Complete" : isActive ? "In progress" : "Waiting"}</Text>
              </View>
              {isActive && <ActivityIndicator size="small" color={colors.primaryBright} />}
            </View>
          );
        })}
      </View>
      {step === "error" && errorMessage ? (
        <View style={[styles.errorBox, { backgroundColor: colors.surfaceSoft, borderColor: colors.danger }]}>
          <Text style={[styles.errorTitle, { color: colors.danger }]}>Processing error</Text>
          <Text style={[styles.errorMsg, { color: colors.textMuted }]}>{errorMessage}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { marginBottom: 20 },
  sectionLabel: { fontSize: 12, fontWeight: "700", letterSpacing: 1.1, marginBottom: 8, fontFamily: fonts.sans },
  title: { fontSize: 24, lineHeight: 29, fontWeight: "700", marginBottom: 20, fontFamily: fonts.serif },
  steps: { gap: 10 },
  stepRow: { minHeight: 66, borderRadius: 20, borderWidth: 1, paddingHorizontal: 14, flexDirection: "row", alignItems: "center", gap: 12 },
  number: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center" },
  numberText: { fontSize: 12, fontWeight: "800", fontFamily: fonts.sans },
  stepCopy: { flex: 1 },
  stepLabel: { fontSize: 14, fontWeight: "600", fontFamily: fonts.sans },
  stepMeta: { fontSize: 11, marginTop: 3, fontFamily: fonts.sans },
  errorBox: { marginTop: 14, borderRadius: 20, borderWidth: 1, padding: 16 },
  errorTitle: { fontSize: 14, fontWeight: "700", marginBottom: 5, fontFamily: fonts.sans },
  errorMsg: { fontSize: 13, lineHeight: 20, fontFamily: fonts.sans },
});
