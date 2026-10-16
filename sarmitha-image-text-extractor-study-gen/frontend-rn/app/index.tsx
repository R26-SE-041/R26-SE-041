import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ArrowRight, RotateCcw } from "lucide-react-native";
import ImageUploader from "@/components/ImageUploader";
import ImageComparison from "@/components/ImageComparison";
import OcrResult from "@/components/OcrResult";
import ProcessingStatus, { type Step } from "@/components/ProcessingStatus";
import { processImage, type ProcessResult, ApiError } from "@/lib/api";
import { fonts, editorialSurface, type AppColors, useAppTheme } from "@/theme";

export default function HomeScreen() {
  const { colors } = useAppTheme();
  const { width } = useWindowDimensions();
  const desktop = width >= 860;
  const compact = width < 1000;
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
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <View style={[styles.header, { borderColor: colors.text }]}>
          <View style={styles.brandRow}>
            <View style={styles.wordmarkIcon}>
              <View style={[styles.wordmarkSlash, { backgroundColor: colors.text }]} />
              <View style={[styles.wordmarkSlash, styles.wordmarkSlashTwo, { backgroundColor: colors.text }]} />
              <View style={[styles.wordmarkSlash, styles.wordmarkSlashThree, { backgroundColor: colors.text }]} />
            </View>
            <Text style={[styles.brandName, { color: colors.text }]}>SINHALA OCR</Text>
          </View>
          <View style={[styles.headerRight, !compact && styles.headerRightAligned]}>
            {!compact && (
              <View style={styles.nav}>
                <Text style={[styles.navLink, { color: colors.text }]}>Enhance</Text>
                <Text style={[styles.navLink, { color: colors.text }]}>Extract</Text>
                <Text style={[styles.navLink, { color: colors.text }]}>Translate</Text>
              </View>
            )}
            <View style={[styles.headerAction, { backgroundColor: colors.text }]}>
              <Text style={[styles.headerActionText, { color: colors.background }]}>Start processing</Text>
              <ArrowRight size={14} color={colors.background} />
            </View>
          </View>
        </View>

        <View style={[styles.hero, desktop && styles.heroDesktop]}>
          <View style={[styles.heroCopy, desktop && styles.heroCopyDesktop]}>
            <Text style={[styles.heroEyebrow, { color: colors.textMuted }]}>SINHALA DOCUMENT INTELLIGENCE</Text>
            <View style={styles.titleWrap} accessibilityRole="header">
              {["Sinhala handwritten", "image enhancement,", "extraction and", "multilingual translation"].map((line) => (
                <Text
                  key={line}
                  style={[
                    styles.title,
                    desktop ? styles.titleDesktop : styles.titleMobile,
                    { color: colors.text },
                  ]}
                >
                  {line}
                </Text>
              ))}
            </View>
          </View>
          <View style={[styles.heroIntro, desktop && styles.heroIntroDesktop]}>
            <Text style={[styles.subtitle, { color: colors.text }]}>Enhance handwritten Sinhala images, extract readable text, and translate the result into Tamil and English.</Text>
            <View style={styles.modelLine}>
              <Text style={[styles.modelLineLabel, { color: colors.textMuted }]}>MODELS</Text>
              <Text style={[styles.modelLineValue, { color: colors.text }]}>SwinSR · TrOCR</Text>
            </View>
          </View>
        </View>

        <View style={[styles.section, editorialSurface(colors)]}>
          <SectionHeading title="Start with the source." description="Upload a clear scan or photograph of Sinhala handwriting." colors={colors} />
          <View style={[styles.workspace, desktop && styles.workspaceDesktop]}>
            <View style={styles.workspaceMain}>
              <ImageUploader onImageSelected={handleImageSelected} disabled={isProcessing} currentUri={imageUri} />
            </View>
            <View style={[styles.workspaceAside, { borderColor: colors.text }]}>
              <Text style={[styles.asideLabel, { color: colors.textDim }]}>SUPPORTED</Text>
              <Text style={[styles.asideValue, { color: colors.text }]}>JPG{`\n`}JPEG{`\n`}PNG{`\n`}WEBP</Text>
              <View style={[styles.asideRule, { backgroundColor: colors.border }]} />
              <Text style={[styles.asideLabel, { color: colors.textDim }]}>PROCESS</Text>
              <Text style={[styles.asideBody, { color: colors.textMuted }]}>4× image refinement followed by Sinhala text recognition.</Text>
            </View>
          </View>
          <View style={styles.cardFooter}>
            <View>
              <Text style={[styles.fileOverline, { color: colors.textDim }]}>CURRENT FILE</Text>
              <Text numberOfLines={1} style={[styles.fileName, { color: imageUri ? colors.text : colors.textDim }]}>{imageUri ? imageName : "Nothing selected yet"}</Text>
            </View>
            <View style={styles.footerButtons}>
              {(result || imageUri) && (
                <Pressable style={({ pressed }) => [styles.textButton, { borderColor: colors.text }, pressed && styles.pressed]} onPress={handleReset}>
                  <RotateCcw size={15} color={colors.text} />
                  <Text style={[styles.textButtonText, { color: colors.text }]}>Reset</Text>
                </Pressable>
              )}
              <Pressable
                style={({ pressed }) => [styles.primaryButton, { backgroundColor: colors.text }, disabled && styles.disabled, pressed && !disabled && styles.pressed]}
                onPress={handleProcess}
                disabled={disabled}
              >
                <Text style={[styles.primaryButtonText, { color: colors.background }]}>{isProcessing ? "Processing…" : "Enhance & extract"}</Text>
                <ArrowRight size={18} color={colors.background} />
              </Pressable>
            </View>
          </View>
        </View>

        {step !== "idle" && <ProcessingStatus step={step} errorMessage={errorMsg} />}

        {result && (
          <View style={styles.results}>
            <View style={styles.resultsHeading}>
              <Text style={[styles.resultsEyebrow, { color: colors.textMuted }]}>OUTPUT WORKSPACE</Text>
              <Text style={[styles.resultsTitle, { color: colors.text }]}>Review and test the extracted results.</Text>
            </View>
            <View style={[styles.section, editorialSurface(colors)]}>
              <SectionHeading number="02" title="See what changed." description="Compare the source image with the four-times enhanced output." colors={colors} />
              <ImageComparison originalB64={result.original_b64} enhancedB64={result.enhanced_b64} />
            </View>
            <OcrResult result={result} />
          </View>
        )}

      </ScrollView>
    </SafeAreaView>
  );
}

function SectionHeading({ number, title, description, colors }: { number?: string; title: string; description: string; colors: AppColors }) {
  return (
    <View style={styles.cardHeading}>
      {number ? <Text style={[styles.stepNumber, { color: colors.primary }]}>{number}</Text> : null}
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
  scrollContent: { paddingHorizontal: 24, paddingBottom: 24, maxWidth: 1480, alignSelf: "center", width: "100%" },
  header: { height: 88, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 18 },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 11 },
  wordmarkIcon: { width: 28, height: 28, position: "relative" },
  wordmarkSlash: { position: "absolute", width: 2, height: 25, left: 13, top: 1, transform: [{ rotate: "0deg" }] },
  wordmarkSlashTwo: { transform: [{ rotate: "60deg" }] },
  wordmarkSlashThree: { transform: [{ rotate: "120deg" }] },
  brandName: { fontSize: 24, fontWeight: "800", letterSpacing: -0.4, fontFamily: fonts.display },
  headerRight: { flexDirection: "row", alignItems: "center", justifyContent: "flex-end", gap: 8 },
  headerRightAligned: { width: "37%", minWidth: 520, justifyContent: "flex-end" },
  nav: { flexDirection: "row", gap: 18, alignItems: "center" },
  navLink: { fontSize: 17, fontWeight: "600", fontFamily: fonts.sans },
  headerAction: { height: 44, borderRadius: 11, paddingHorizontal: 15, flexDirection: "row", alignItems: "center", gap: 16 },
  headerActionText: { fontSize: 15, fontWeight: "700", fontFamily: fonts.sans },
  hero: { minHeight: 530, paddingVertical: 68 },
  heroDesktop: { minHeight: 540, flexDirection: "row", alignItems: "center" },
  heroCopy: { flex: 1, paddingRight: 12 },
  heroCopyDesktop: { flex: 1.45, paddingRight: 64 },
  heroEyebrow: { fontSize: 11, fontWeight: "700", letterSpacing: 1.2, fontFamily: fonts.sans },
  titleWrap: { marginTop: 30, overflow: "hidden" },
  title: { fontFamily: fonts.display, fontWeight: "800", letterSpacing: -3.2 },
  titleDesktop: { fontSize: 66, lineHeight: 66, maxWidth: 880 },
  titleMobile: { fontSize: 43, lineHeight: 44 },
  heroIntro: { paddingTop: 40 },
  heroIntroDesktop: { flex: 0.85, paddingTop: 72, alignSelf: "stretch", justifyContent: "center" },
  subtitle: { fontSize: 24, lineHeight: 33, maxWidth: 510, fontFamily: fonts.serif },
  modelLine: { borderTopWidth: 1, borderColor: "#D2CEC2", marginTop: 34, paddingTop: 15, flexDirection: "row", justifyContent: "space-between", gap: 16 },
  modelLineLabel: { fontSize: 10, fontWeight: "700", letterSpacing: 1.1, fontFamily: fonts.sans },
  modelLineValue: { fontSize: 12, fontWeight: "700", fontFamily: fonts.sans },
  section: { marginBottom: 24 },
  cardHeading: { flexDirection: "row", alignItems: "flex-start", gap: 34, marginBottom: 38 },
  stepNumber: { width: 44, fontSize: 12, lineHeight: 46, fontWeight: "700", fontFamily: fonts.sans },
  cardHeadingText: { flex: 1 },
  sectionTitle: { fontSize: 52, lineHeight: 53, fontWeight: "700", letterSpacing: -2, fontFamily: fonts.display },
  sectionDescription: { fontSize: 17, marginTop: 12, lineHeight: 25, fontFamily: fonts.serif },
  workspace: { gap: 14 },
  workspaceDesktop: { flexDirection: "row" },
  workspaceMain: { flex: 1 },
  workspaceAside: { width: 220, borderWidth: 1, borderRadius: 20, padding: 24 },
  asideLabel: { fontSize: 9, fontWeight: "700", letterSpacing: 1.3, fontFamily: fonts.sans },
  asideValue: { fontSize: 23, lineHeight: 34, fontWeight: "700", marginTop: 15, fontFamily: fonts.display },
  asideRule: { height: 1, marginVertical: 28 },
  asideBody: { fontSize: 13, lineHeight: 20, marginTop: 12, fontFamily: fonts.serif },
  cardFooter: { marginTop: 18, flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 18 },
  fileOverline: { fontSize: 9, fontWeight: "700", letterSpacing: 1.2, marginBottom: 5, fontFamily: fonts.sans },
  fileName: { fontSize: 13, fontFamily: fonts.sans, flexShrink: 1, maxWidth: 520 },
  footerButtons: { flexDirection: "row", gap: 10, alignItems: "center", flexWrap: "wrap" },
  textButton: { minHeight: 50, borderWidth: 1, borderRadius: 10, paddingHorizontal: 18, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 9 },
  textButtonText: { fontSize: 13, fontWeight: "700", fontFamily: fonts.sans },
  primaryButton: { minHeight: 52, borderRadius: 10, paddingHorizontal: 21, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 28 },
  primaryButtonText: { fontSize: 13, fontWeight: "700", fontFamily: fonts.sans },
  pressed: { opacity: 0.72, transform: [{ translateY: 1 }] },
  disabled: { opacity: 0.34 },
  results: { gap: 0, marginTop: 52, marginHorizontal: -24 },
  resultsHeading: { paddingHorizontal: 36, marginBottom: 26 },
  resultsEyebrow: { fontSize: 10, fontWeight: "700", letterSpacing: 1.3, marginBottom: 12, fontFamily: fonts.sans },
  resultsTitle: { fontSize: 46, lineHeight: 50, maxWidth: 760, fontWeight: "700", letterSpacing: -1.8, fontFamily: fonts.display },
});
