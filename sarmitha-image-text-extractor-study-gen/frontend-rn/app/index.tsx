import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ArrowRight, RotateCcw, Sparkles } from "lucide-react-native";
import ImageUploader from "@/components/ImageUploader";
import ImageComparison from "@/components/ImageComparison";
import OcrResult from "@/components/OcrResult";
import ProcessingStatus, { type Step } from "@/components/ProcessingStatus";
import { processImage, type ProcessResult, ApiError } from "@/lib/api";
import { fonts, glassSurface, type AppColors, useAppTheme } from "@/theme";

export default function HomeScreen() {
  const { colors } = useAppTheme();
  const { width } = useWindowDimensions();
  const desktop = width >= 760;
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [imageName, setImageName] = useState("image.jpg");
  const [imageMime, setImageMime] = useState("image/jpeg");
  const [step, setStep] = useState<Step>("idle");
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleImageSelected = (uri: string, name: string, mime: string) => {
    setImageUri(uri);
    setImageName(name);
    setImageMime(mime);
    setResult(null);
    setStep("idle");
    setErrorMsg("");
  };

  const handleProcess = async () => {
    if (!imageUri) return;
    setResult(null);
    setErrorMsg("");
    setStep("uploading");
    try {
      await new Promise((resolve) => setTimeout(resolve, 400));
      setStep("enhancing");
      const response = await processImage(imageUri, imageName, imageMime);
      setStep("extracting");
      await new Promise((resolve) => setTimeout(resolve, 300));
      setResult(response);
      setStep("done");
    } catch (error) {
      const message = error instanceof ApiError
        ? `[${error.status}] ${error.message}`
        : error instanceof Error ? error.message : "An unexpected error occurred";
      setErrorMsg(message);
      setStep("error");
    }
  };

  const handleReset = () => {
    setImageUri(null);
    setResult(null);
    setStep("idle");
    setErrorMsg("");
  };

  const isProcessing = step === "uploading" || step === "enhancing" || step === "extracting";
  const disabled = !imageUri || isProcessing;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <View pointerEvents="none" style={styles.ambientLayer}>
        <View style={styles.ambientTop} />
        <View style={styles.ambientBottom} />
      </View>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <View style={[styles.header, { borderColor: colors.border }]}>
          <View style={styles.brandRow}>
            <View style={[styles.brandMark, { backgroundColor: colors.primary }]}>
              <Text style={styles.brandMarkText}>ST</Text>
            </View>
            <View>
              <Text style={[styles.brandName, { color: colors.text }]}>Sinhala Text Services</Text>
              <Text style={[styles.brandDescriptor, { color: colors.textDim }]}>Document Processing Portal</Text>
            </View>
          </View>
          <View style={[styles.headerPill, { backgroundColor: colors.surfaceSoft, borderColor: colors.border }]}>
            <Sparkles size={14} color={colors.primaryBright} />
            <Text style={[styles.headerPillText, { color: colors.textMuted }]}>AI document workspace</Text>
          </View>
        </View>

        <View style={[styles.intro, desktop && styles.introDesktop]}>
          <Text style={[styles.eyebrow, { color: colors.textDim }]}>IMAGE TO TEXT CONVERSION</Text>
          <Text style={[styles.title, desktop ? styles.titleDesktop : styles.titleMobile, { color: colors.text }]}>Sinhala handwritten text, made clear.</Text>
          <Text style={[styles.subtitle, { color: colors.textMuted }]}>Upload a Sinhala handwritten document to refine its image with SwinSR and extract readable text using TrOCR.</Text>
          <View style={[styles.modelNote, { backgroundColor: colors.surfaceSoft, borderColor: colors.border }]}>
            <Text style={[styles.modelNoteLabel, { color: colors.textDim }]}>PROCESSING MODELS</Text>
            <Text style={[styles.modelNoteValue, { color: colors.primaryBright }]}>SwinSR · TrOCR</Text>
          </View>
        </View>

        <View style={[styles.card, glassSurface(colors)]}>
          <SectionHeading number="01" title="Select a handwritten image" description="Choose a clear Sinhala handwritten image to begin extraction." colors={colors} />
          <ImageUploader onImageSelected={handleImageSelected} disabled={isProcessing} currentUri={imageUri} />
          <View style={styles.cardFooter}>
            <View style={[styles.fileTag, { backgroundColor: colors.surfaceSoft, borderColor: colors.border }]}>
              <Text numberOfLines={1} style={[styles.footerLabel, { color: imageUri ? colors.textMuted : colors.textDim }]}>{imageUri ? imageName : "No image selected"}</Text>
            </View>
            <View style={styles.footerButtons}>
              {(result || imageUri) && (
                <Pressable
                  style={({ pressed }) => [styles.button, styles.secondaryButton, { backgroundColor: colors.surfaceSoft, borderColor: colors.border }, pressed && styles.pressed]}
                  onPress={handleReset}
                >
                  <RotateCcw size={16} color={colors.textMuted} />
                  <Text style={[styles.secondaryButtonText, { color: colors.textMuted }]}>Reset</Text>
                </Pressable>
              )}
              <Pressable
                style={({ pressed }) => [styles.button, styles.primaryButton, { backgroundColor: colors.primary, borderColor: colors.border }, disabled && styles.disabled, pressed && !disabled && styles.pressed]}
                onPress={handleProcess}
                disabled={disabled}
              >
                <Text style={styles.primaryButtonText}>{isProcessing ? "Processing..." : "Enhance & extract"}</Text>
                <ArrowRight size={17} color="#ffffff" />
              </Pressable>
            </View>
          </View>
        </View>

        {step !== "idle" && <ProcessingStatus step={step} errorMessage={errorMsg} />}

        {result && (
          <View style={styles.results}>
            <View style={[styles.card, glassSurface(colors)]}>
              <SectionHeading number="02" title="Image enhancement" description="Compare your original document with the refined SwinSR output." colors={colors} />
              <ImageComparison originalB64={result.original_b64} enhancedB64={result.enhanced_b64} />
            </View>
            <OcrResult result={result} />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function SectionHeading({ number, title, description, colors }: { number: string; title: string; description: string; colors: AppColors }) {
  return (
    <View style={styles.cardHeading}>
      <View style={[styles.stepNumber, { backgroundColor: colors.primary }]}><Text style={styles.stepNumberText}>{number}</Text></View>
      <View style={styles.cardHeadingText}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>{title}</Text>
        <Text style={[styles.sectionDescription, { color: colors.textMuted }]}>{description}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 18, paddingBottom: 72, maxWidth: 1040, alignSelf: "center", width: "100%" },
  ambientLayer: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, overflow: "hidden" },
  ambientTop: { position: "absolute", width: 620, height: 620, borderRadius: 310, backgroundColor: "rgba(211,105,55,0.20)", top: -330, right: -250 },
  ambientBottom: { position: "absolute", width: 520, height: 520, borderRadius: 260, backgroundColor: "rgba(175,125,73,0.16)", bottom: -260, left: -230 },
  header: { minHeight: 76, paddingVertical: 16, marginBottom: 60, borderBottomWidth: 1, flexDirection: "row", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  brandMark: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  brandMarkText: { color: "#ffffff", fontSize: 13, fontWeight: "800", letterSpacing: 1.1, fontFamily: fonts.sans },
  brandName: { fontSize: 15, fontWeight: "700", fontFamily: fonts.sans },
  brandDescriptor: { fontSize: 12, marginTop: 2, fontFamily: fonts.sans },
  headerPill: { minHeight: 38, borderRadius: 50, borderWidth: 1, paddingHorizontal: 14, flexDirection: "row", alignItems: "center", gap: 8 },
  headerPillText: { fontSize: 12, fontWeight: "600", fontFamily: fonts.sans },
  intro: { maxWidth: 820, width: "100%", marginBottom: 42, alignSelf: "center", alignItems: "center" },
  introDesktop: { paddingTop: 20, marginBottom: 52 },
  eyebrow: { fontSize: 11, fontWeight: "800", letterSpacing: 2.6, marginBottom: 18, fontFamily: fonts.sans, textAlign: "center" },
  title: { fontFamily: fonts.serif, fontWeight: "700", letterSpacing: -2, maxWidth: 810, textAlign: "center" },
  titleDesktop: { fontSize: 58, lineHeight: 63 },
  titleMobile: { fontSize: 40, lineHeight: 46 },
  subtitle: { fontSize: 16, lineHeight: 26, maxWidth: 670, marginTop: 18, fontWeight: "400", fontFamily: fonts.sans, textAlign: "center" },
  modelNote: { flexDirection: "row", alignItems: "center", alignSelf: "center", marginTop: 24, borderWidth: 1, borderRadius: 50, paddingHorizontal: 14, minHeight: 38, gap: 10 },
  modelNoteLabel: { fontSize: 10, fontWeight: "700", letterSpacing: 1.1, fontFamily: fonts.sans },
  modelNoteValue: { fontSize: 12, fontWeight: "700", fontFamily: fonts.sans },
  card: { marginBottom: 20 },
  cardHeading: { flexDirection: "row", alignItems: "flex-start", gap: 14, marginBottom: 20 },
  stepNumber: { minWidth: 42, height: 30, borderRadius: 20, alignItems: "center", justifyContent: "center", paddingHorizontal: 9 },
  stepNumberText: { color: "#ffffff", fontSize: 11, fontWeight: "800", letterSpacing: 1.1, fontFamily: fonts.sans },
  cardHeadingText: { flex: 1 },
  sectionTitle: { fontSize: 24, lineHeight: 29, fontWeight: "700", fontFamily: fonts.serif },
  sectionDescription: { fontSize: 13, marginTop: 5, lineHeight: 20, fontFamily: fonts.sans },
  cardFooter: { marginTop: 20, flexDirection: "row", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 14 },
  fileTag: { maxWidth: 320, minHeight: 38, borderRadius: 20, borderWidth: 1, paddingHorizontal: 14, justifyContent: "center", flexShrink: 1 },
  footerLabel: { fontSize: 12, fontWeight: "600", fontFamily: fonts.sans },
  footerButtons: { flexDirection: "row", gap: 10, alignItems: "center", flexWrap: "wrap" },
  button: { minHeight: 46, borderRadius: 13, paddingHorizontal: 18, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  secondaryButton: { borderWidth: 1 },
  primaryButton: { borderWidth: 1 },
  secondaryButtonText: { fontSize: 13, fontWeight: "700", fontFamily: fonts.sans },
  primaryButtonText: { color: "#ffffff", fontSize: 13, fontWeight: "700", fontFamily: fonts.sans },
  pressed: { opacity: 0.78, transform: [{ scale: 0.99 }] },
  disabled: { opacity: 0.45 },
  results: { gap: 20 },
});
