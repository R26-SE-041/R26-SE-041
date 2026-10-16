import React from "react";
import { ActivityIndicator, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { Check } from "lucide-react-native";
import { editorialSurface, fonts, useAppTheme } from "@/theme";

export type Step = "idle" | "uploading" | "enhancing" | "extracting" | "done" | "error";
interface Props { step: Step; errorMessage?: string; }

const STEPS = [
  { id: "uploading" as Step, label: "Receive image", doneLabel: "Image received" },
  { id: "enhancing" as Step, label: "Enhance and recognise handwriting", doneLabel: "Image enhanced and text recognised" },
  { id: "extracting" as Step, label: "Prepare text and translations", doneLabel: "Text and translations ready" },
] as const;
const ORDER: Step[] = ["idle", "uploading", "enhancing", "extracting", "done", "error"];

export default function ProcessingStatus({ step, errorMessage }: Props) {
  const { colors } = useAppTheme();
  const { width } = useWindowDimensions();
  if (step === "idle") return null;
  const currentIndex = ORDER.indexOf(step);

  return (
    <View accessibilityLiveRegion="polite" style={[styles.section, editorialSurface(colors), { padding: width < 680 ? 24 : 40 }]}>
      <View style={styles.heading}>
        <Text style={[styles.sectionLabel, { color: colors.primary }]}>LIVE PROCESS</Text>
        <Text accessibilityRole="header" style={[styles.title, { color: colors.text }, width < 680 && { fontSize: 32, lineHeight: 37 }]}>From image to language.</Text>
      </View>
      <View style={[styles.steps, { borderColor: colors.border }]}>
        {STEPS.map((item, index) => {
          const isActive = step === item.id;
          const isDone = currentIndex > ORDER.indexOf(item.id) && step !== "error";
          return (
            <View key={item.id} style={[styles.stepRow, { borderColor: colors.border }]}>
              <Text style={[styles.stepIndex, { color: isActive || isDone ? colors.primary : colors.textDim }]}>0{index + 1}</Text>
              <View style={styles.stepCopy}>
                <Text style={[styles.stepLabel, { color: isDone || isActive ? colors.text : colors.textMuted }]}>{isDone ? item.doneLabel : item.label}</Text>
                <Text style={[styles.stepMeta, { color: colors.textDim }]}>{isDone ? "Complete" : isActive ? "In progress" : "Waiting"}</Text>
              </View>
              {isDone ? <Check size={18} color={colors.success} strokeWidth={2} /> : isActive ? <ActivityIndicator size="small" color={colors.primary} /> : <View style={[styles.waitingMark, { borderColor: colors.border }]} />}
            </View>
          );
        })}
      </View>
      {step === "error" && errorMessage ? (
        <View style={[styles.errorBox, { borderColor: colors.danger }]}>
          <Text style={[styles.errorTitle, { color: colors.danger }]}>Processing error</Text>
          <Text style={[styles.errorMsg, { color: colors.textMuted }]}>{errorMessage}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginBottom: 0 },
  heading: { marginBottom: 26 },
  sectionLabel: { fontSize: 10, letterSpacing: 1.1, marginBottom: 14, fontFamily: fonts.mono },
  title: { fontSize: 40, lineHeight: 45, fontWeight: "400", letterSpacing: -1.1, fontFamily: fonts.serif },
  steps: { gap: 0 },
  stepRow: { minHeight: 76, borderTopWidth: 1, paddingHorizontal: 2, flexDirection: "row", alignItems: "center", gap: 18 },
  stepIndex: { width: 30, fontSize: 11, fontWeight: "700", fontFamily: fonts.sans },
  stepCopy: { flex: 1 },
  stepLabel: { fontSize: 14, fontWeight: "600", fontFamily: fonts.sans },
  stepMeta: { fontSize: 11, marginTop: 4, fontFamily: fonts.sans },
  waitingMark: { width: 16, height: 16, borderWidth: 1 },
  errorBox: { marginTop: 20, borderWidth: 1, borderLeftWidth: 4, borderRadius: 12, padding: 16 },
  errorTitle: { fontSize: 13, fontWeight: "700", marginBottom: 5, fontFamily: fonts.sans },
  errorMsg: { fontSize: 13, lineHeight: 20, fontFamily: fonts.sans },
});
