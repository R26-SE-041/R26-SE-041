import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Platform,
} from "react-native";
import { ScanText, ImageUp, ArrowRight, RotateCcw } from "lucide-react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import ImageUploader from "@/components/ImageUploader";
import ImageComparison from "@/components/ImageComparison";
import OcrResult from "@/components/OcrResult";
import ProcessingStatus, { type Step } from "@/components/ProcessingStatus";
import { processImage, type ProcessResult, ApiError } from "@/lib/api";

export default function HomeScreen() {
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [imageName, setImageName] = useState<string>("image.jpg");
  const [imageMime, setImageMime] = useState<string>("image/jpeg");
  const [step, setStep] = useState<Step>("idle");
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

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
      await new Promise((r) => setTimeout(r, 400));
      setStep("enhancing");
      const res = await processImage(imageUri, imageName, imageMime);
      setStep("extracting");
      await new Promise((r) => setTimeout(r, 300));
      setResult(res);
      setStep("done");
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? `[${err.status}] ${err.message}`
          : err instanceof Error
          ? err.message
          : "An unexpected error occurred";
      setErrorMsg(msg);
      setStep("error");
    }
  };

  const handleReset = () => {
    setImageUri(null);
    setResult(null);
    setStep("idle");
    setErrorMsg("");
  };

  const isProcessing =
    step === "uploading" || step === "enhancing" || step === "extracting";

  return (
    <SafeAreaView style={styles.safe}>
      {/* Gradient ambient blobs — web only (RN doesn't support CSS filters) */}
      {Platform.OS === "web" && (
        <View style={styles.blobsContainer} pointerEvents="none">
          <View style={[styles.blob, styles.blob1]} />
          <View style={[styles.blob, styles.blob2]} />
          <View style={[styles.blob, styles.blob3]} />
        </View>
      )}

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        {/* ── Header ── */}
        <View style={styles.header}>
          <View style={styles.badge}>
            <ScanText size={13} color="#c4b5fd" strokeWidth={1.75} />
            <Text style={styles.badgeText}>SRCNN + TrOCR · Modal Serverless</Text>
          </View>

          <Text style={styles.title}>
            Sinhala Handwritten{" "}
            <Text style={styles.titleAccent}>OCR</Text>
          </Text>

          <Text style={styles.subtitle}>
            Upload a low-quality Sinhala handwritten image. The system enhances
            it 4× with SRCNN, then extracts text using a fine-tuned TrOCR model.
          </Text>
        </View>

        {/* ── Upload card ── */}
        <View style={styles.card}>
          <ImageUploader
            onImageSelected={handleImageSelected}
            disabled={isProcessing}
            currentUri={imageUri}
          />

          <View style={styles.cardFooter}>
            <Text style={styles.footerLabel}>
              {imageUri ? `Selected: ${imageName}` : "No image selected"}
            </Text>

            <View style={styles.footerButtons}>
              {result && (
                <TouchableOpacity
                  style={styles.resetBtn}
                  onPress={handleReset}
                  activeOpacity={0.7}
                >
                  <RotateCcw size={15} color="rgba(255,255,255,0.6)" strokeWidth={1.75} />
                  <Text style={styles.resetBtnText}>Reset</Text>
                </TouchableOpacity>
              )}

              <TouchableOpacity
                style={[
                  styles.processBtn,
                  (!imageUri || isProcessing) && styles.processBtnDisabled,
                ]}
                onPress={handleProcess}
                disabled={!imageUri || isProcessing}
                activeOpacity={0.8}
              >
                <ImageUp size={15} color={!imageUri || isProcessing ? "rgba(167,139,250,0.35)" : "#fff"} strokeWidth={1.75} />
                <Text
                  style={[
                    styles.processBtnText,
                    (!imageUri || isProcessing) && styles.processBtnTextDisabled,
                  ]}
                >
                  {isProcessing ? "Processing..." : "Enhance & Extract"}
                </Text>
                {!isProcessing && (
                  <ArrowRight size={15} color="#fff" strokeWidth={1.75} />
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* ── Processing status ── */}
        {step !== "idle" && (
          <ProcessingStatus step={step} errorMessage={errorMsg} />
        )}

        {/* ── Results ── */}
        {result && (
          <View style={styles.results}>
            <View style={styles.card}>
              <View style={styles.sectionHeader}>
                <Text style={styles.sectionTitle}>Enhancement Result</Text>
              </View>
              <ImageComparison
                originalB64={result.original_b64}
                enhancedB64={result.enhanced_b64}
              />
            </View>

            <OcrResult text={result.extracted_text} />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: "#09090f",
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 48,
    maxWidth: 800,
    alignSelf: "center",
    width: "100%",
  },
  blobsContainer: {
    position: "absolute",
    inset: 0,
    pointerEvents: "none",
    overflow: "hidden",
  } as never,
  blob: {
    position: "absolute",
    borderRadius: 9999,
  },
  blob1: {
    top: -160,
    left: -160,
    width: 450,
    height: 450,
    backgroundColor: "rgba(124,58,237,0.12)",
  },
  blob2: {
    top: "50%",
    right: -64,
    width: 350,
    height: 350,
    backgroundColor: "rgba(79,70,229,0.10)",
  },
  blob3: {
    bottom: 0,
    left: "33%",
    width: 300,
    height: 300,
    backgroundColor: "rgba(109,40,217,0.08)",
  },

  // Header
  header: {
    alignItems: "center",
    marginBottom: 32,
    marginTop: 12,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(139,92,246,0.3)",
    backgroundColor: "rgba(139,92,246,0.08)",
    paddingHorizontal: 14,
    paddingVertical: 6,
    marginBottom: 16,
  },
  badgeText: {
    color: "#c4b5fd",
    fontSize: 12,
    fontWeight: "500",
  },
  title: {
    fontSize: 32,
    fontWeight: "700",
    color: "#ffffff",
    textAlign: "center",
    lineHeight: 42,
    marginBottom: 12,
  },
  titleAccent: {
    color: "#a78bfa",
  },
  subtitle: {
    fontSize: 14,
    color: "rgba(255,255,255,0.45)",
    textAlign: "center",
    lineHeight: 22,
    maxWidth: 380,
  },

  // Card
  card: {
    backgroundColor: "rgba(255,255,255,0.03)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
    borderRadius: 20,
    padding: 20,
    marginBottom: 16,
  },
  cardFooter: {
    marginTop: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: 10,
  },
  footerLabel: {
    fontSize: 12,
    color: "rgba(255,255,255,0.35)",
    flex: 1,
  },
  footerButtons: {
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
  },

  // Reset button
  resetBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.1)",
    backgroundColor: "rgba(255,255,255,0.04)",
  },
  resetBtnText: {
    fontSize: 13,
    fontWeight: "500",
    color: "rgba(255,255,255,0.6)",
  },

  // Process button
  processBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: "#7c3aed",
  },
  processBtnDisabled: {
    backgroundColor: "rgba(139,92,246,0.15)",
  },
  processBtnText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#ffffff",
  },
  processBtnTextDisabled: {
    color: "rgba(167,139,250,0.35)",
  },

  // Results
  results: {
    gap: 16,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: "rgba(255,255,255,0.9)",
  },
});
