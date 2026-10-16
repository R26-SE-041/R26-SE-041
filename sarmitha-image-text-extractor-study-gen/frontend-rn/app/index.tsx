import React, { useEffect, useRef, useState } from "react";
import { Platform, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ArrowRight, ArrowUpRight, Menu, RotateCcw, X } from "lucide-react-native";
import Svg, { Path, Rect } from "react-native-svg";
import ImageUploader from "@/components/ImageUploader";
import ImageComparison from "@/components/ImageComparison";
import OcrResult from "@/components/OcrResult";
import ProcessingStatus, { type Step } from "@/components/ProcessingStatus";
import { processImage, type ProcessResult, ApiError } from "@/lib/api";
import { fonts, editorialSurface, useAppTheme } from "@/theme";
import { useAccount } from "@/components/AuthProvider";
import AccountModal from "@/components/AccountModal";
import HistoryModal from "@/components/HistoryModal";

type Section = "workspace" | "how" | "languages";
export default function HomeScreen() {
  const { colors } = useAppTheme();
  const account = useAccount();
  const [accountOpen, setAccountOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyRevision, setHistoryRevision] = useState(0);
  const owner = useRef<string | null>(null);
  owner.current = account.user?.id ?? null;
  const { width } = useWindowDimensions();
  const desktop = width >= 1000, mobile = width < 680;
  const gutter = mobile ? 20 : width < 1000 ? 36 : Math.max(48, Math.min(width * .055, 88));
  const scroll = useRef<ScrollView>(null);
  const positions = useRef<Record<Section, number>>({ workspace: 0, how: 0, languages: 0 });
  const [menuOpen, setMenuOpen] = useState(false);
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [imageName, setImageName] = useState("image.jpg");
  const [imageMime, setImageMime] = useState("image/jpeg");
  const [step, setStep] = useState<Step>("idle");
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  useEffect(() => {
    setResult(null); setStep("idle"); setErrorMsg(""); setHistoryOpen(false);
  }, [account.user?.id]);
  const goTo = (section: Section) => {
    setMenuOpen(false);
    const reduced = Platform.OS === "web" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    scroll.current?.scrollTo({ y: Math.max(0, positions.current[section] - 24), animated: !reduced });
  };
  const selectImage = (uri: string, name: string, mime: string) => {
    setImageUri(uri); setImageName(name); setImageMime(mime);
    setResult(null); setStep("idle"); setErrorMsg("");
  };
  const handleProcess = async () => {
    if (!imageUri) return;
    if (account.enabled && !account.user) { setAccountOpen(true); return; }
    const requestOwner = owner.current;
    setResult(null); setErrorMsg(""); setStep("enhancing");
    try {
      const response = await processImage(imageUri, imageName, imageMime);
      if (owner.current !== requestOwner) return;
      setResult(response); setStep("done");
      setHistoryRevision(value => value + 1);
    } catch (error) {
      if (owner.current !== requestOwner) return;
      setErrorMsg(error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Something went wrong. Please try again.");
      setStep("error");
    }
  };
  const reset = () => { setImageUri(null); setResult(null); setStep("idle"); setErrorMsg(""); };
  const processing = ["uploading", "enhancing", "extracting"].includes(step);
  const disabled = !imageUri || processing || account.loading;
  const surface = [editorialSurface(colors), { padding: mobile ? 24 : desktop ? 56 : 36 }];
  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <View nativeID="site-header" style={[styles.headerOuter, { backgroundColor: colors.background }]}>
        <View style={[styles.header, { paddingHorizontal: gutter }]}>
          <Pressable accessibilityRole="button" accessibilityLabel="Sinhala OCR, back to top" onPress={() => scroll.current?.scrollTo({ y: 0, animated: false })}><Text style={[styles.brand, { fontSize: mobile ? 21 : 24 }]}>SINHALA OCR</Text></Pressable>
          <View style={styles.headerActions}>
            {desktop && <View style={styles.navigation}><Nav label="Workspace" onPress={() => goTo("workspace")} /><Nav label="How it works" onPress={() => goTo("how")} /><Nav label="Languages" onPress={() => goTo("languages")} /></View>}
            <Pressable accessibilityRole="button" onPress={() => account.enabled ? account.user ? setHistoryOpen(true) : setAccountOpen(true) : goTo("workspace")} style={({ pressed }) => [styles.headerCta, pressed && styles.pressed]}><Text style={styles.headerCtaText}>{account.loading ? "Loading…" : account.enabled ? account.user ? "My history" : "Sign in" : mobile ? "Get started" : "Try Sinhala OCR"}</Text>{!mobile && <ArrowUpRight size={16} color={colors.surface} />}</Pressable>
            {!desktop && <Pressable accessibilityRole="button" accessibilityLabel={menuOpen ? "Close navigation" : "Open navigation"} accessibilityState={{ expanded: menuOpen }} onPress={() => setMenuOpen(!menuOpen)} style={styles.menuButton}>{menuOpen ? <X size={22} color={colors.text} /> : <Menu size={22} color={colors.text} />}</Pressable>}
          </View>
        </View>
        {menuOpen && <View style={[styles.mobileNav, { paddingHorizontal: gutter }]}><Nav label="Workspace" onPress={() => goTo("workspace")} /><Nav label="How it works" onPress={() => goTo("how")} /><Nav label="Languages" onPress={() => goTo("languages")} /></View>}
      </View>
      <ScrollView ref={scroll} style={styles.scroll} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
        <View style={[styles.container, { paddingHorizontal: gutter }]}>
          <View style={[styles.hero, desktop && styles.heroDesktop, mobile && styles.heroMobile]}>
            <View nativeID="hero-copy" style={[styles.heroCopy, desktop && styles.heroCopyDesktop]}><Text accessibilityRole="header" style={[styles.title, { fontSize: desktop ? 64 : mobile ? 43 : 58, lineHeight: desktop ? 67 : mobile ? 46 : 61 }]}>Sinhala handwriting,{"\n"}made clear in{"\n"}three languages.</Text></View>
            <View nativeID="hero-intro" style={[styles.heroIntro, desktop && styles.heroIntroDesktop]}><Text style={[styles.subtitle, { fontSize: mobile ? 23 : 28, lineHeight: mobile ? 30 : 34 }]}>Your notes hold a world of ideas. Bring them into focus with clearer images, editable Sinhala text, and translations in Tamil and English.</Text></View>
          </View>
          <View nativeID="document-workspace" onLayout={event => { positions.current.workspace = event.nativeEvent.layout.y; }} style={surface}>
            <View style={styles.workspaceHeading}><Text style={styles.overline}>THE DOCUMENT WORKSPACE</Text><Text accessibilityRole="header" style={[styles.workspaceTitle, { fontSize: mobile ? 36 : 52, lineHeight: mobile ? 40 : 57 }]}>A clearer way to read your notes.</Text><Text style={styles.workspaceDescription}>Start with a photograph. See where your words can go.</Text></View>
            <View style={[styles.workspace, desktop && styles.workspaceDesktop]}>
              <View style={styles.workspaceMain}><ImageUploader onImageSelected={selectImage} disabled={processing} currentUri={imageUri} /></View>
              {desktop ? <View style={[styles.guide, styles.guideDesktop]}>
                {desktop && <DocumentDrawing />}<Text style={[styles.guideTitle, !desktop && { fontSize: 24, lineHeight: 29 }]}>A little care.{"\n"}A clearer result.</Text><Text style={styles.guideText}>Keep the page flat, the light even, and the handwriting in focus.</Text><View style={styles.guideRule} /><Text style={styles.guideFormats}>JPG · PNG · WEBP</Text><Text style={styles.guideLimit}>Up to 10 MB per image</Text>
              </View> : <View style={styles.guideCompact}><Text style={styles.guideFormats}>JPG · PNG · WEBP  /  UP TO 10 MB</Text><Text style={styles.compactGuideText}>A flat page, even light, and clear handwriting work best.</Text></View>}
            </View>
            <View style={[styles.workspaceFooter, mobile && styles.workspaceFooterMobile]}>
              <View style={styles.fileCopy}><Text style={styles.fileLabel}>YOUR SOURCE</Text><Text numberOfLines={1} style={[styles.fileName, !imageUri && { color: colors.textDim }]}>{imageUri ? imageName : "Choose an image to begin"}</Text></View>
              <View style={[styles.footerActions, mobile && { width: "100%" }]}>
                {imageUri && <Pressable accessibilityRole="button" accessibilityLabel="Clear image and results" disabled={processing} onPress={reset} style={({ pressed }) => [styles.resetButton, processing && styles.disabled, pressed && styles.pressed]}><RotateCcw size={16} color={colors.text} /><Text style={styles.resetText}>Reset</Text></Pressable>}
                <Pressable nativeID="process-button" accessibilityRole="button" accessibilityState={{ disabled, busy: processing }} disabled={disabled} onPress={handleProcess} style={({ pressed }) => [styles.primaryButton, mobile && { flex: 1 }, disabled && styles.disabled, pressed && styles.pressed]}><Text style={styles.primaryButtonText}>{processing ? "Reading your image…" : account.enabled && !account.user ? "Sign in to extract" : "Enhance & extract"}</Text><ArrowRight size={17} color={colors.surface} /></Pressable>
              </View>
            </View>
          </View>
          {result?.id && account.user && <Pressable accessibilityRole="button" onPress={() => setHistoryOpen(true)} style={styles.inlineLink}><Text style={styles.inlineLinkText}>Saved to your private history</Text><ArrowRight size={17} color={colors.text} /></Pressable>}
          {step !== "idle" && <ProcessingStatus step={step} errorMessage={errorMsg} />}
          {result && <View style={styles.results}>
            <View style={styles.resultHeading}><Text style={styles.overline}>YOUR RESULTS</Text><Text accessibilityRole="header" style={[styles.resultTitle, mobile && { fontSize: 36, lineHeight: 41 }]}>The same page.{"\n"}New possibilities.</Text></View>
            <View style={surface}><Text style={styles.overline}>01 / IMAGE ENHANCEMENT</Text><Text accessibilityRole="header" style={[styles.resultCardTitle, mobile && { fontSize: 32, lineHeight: 37 }]}>See the difference.</Text><Text style={styles.resultDescription}>Your original image, alongside its enhanced version.</Text><ImageComparison originalB64={result.original_b64} enhancedB64={result.enhanced_b64} /></View>
            <OcrResult result={result} />
          </View>}
          <View nativeID="how-it-works" onLayout={event => { positions.current.how = event.nativeEvent.layout.y; }} style={[styles.howSection, mobile && { paddingVertical: 64 }]}>
            <View style={[styles.howHeading, desktop && styles.howHeadingDesktop]}><Text accessibilityRole="header" style={[styles.howTitle, { fontSize: mobile ? 38 : 48, lineHeight: mobile ? 42 : 52 }]}>From handwriting{"\n"}to understanding.</Text><Text style={styles.howIntro}>Three thoughtful steps to make your handwritten notes easier to read, use, and share.</Text></View>
            <View nativeID="capability-cards" style={[styles.capabilities, width >= 760 && styles.capabilitiesRow]}>
              {[
                { number: "01", title: "A clearer image.", body: "Refine the source with image enhancement, bringing the details of your handwriting into focus.", action: "Enhance your image", color: "#E3DACC", kind: "image" },
                { number: "02", title: "Words you can use.", body: "Turn Sinhala handwriting into digital text. Read it, copy it, and take your ideas further.", action: "Extract your text", color: "#CED6BF", kind: "text" },
                { number: "03", title: "More ways to read.", body: "Keep the original Sinhala, or explore your notes through Tamil and English translations.", action: "Explore languages", color: "#CBCADB", kind: "language" },
              ].map(card => <Pressable key={card.number} accessibilityRole="button" onPress={() => goTo("workspace")} style={({ pressed }) => [styles.capability, { backgroundColor: card.color }, pressed && styles.pressed]}>
                <View style={styles.capabilityTop}><Text style={styles.overline}>{card.number} / {card.kind === "image" ? "ENHANCE" : card.kind === "text" ? "RECOGNISE" : "TRANSLATE"}</Text><ArrowUpRight size={19} color={colors.text} /></View>
                <View style={styles.cardIllustration}>{card.kind === "image" ? <DocumentDrawing /> : <Text style={[styles.typeDrawing, card.kind === "text" && { fontSize: 52 }]}>{card.kind === "text" ? "අ ආ ඇ" : "Aa ↔ அ"}</Text>}</View>
                <Text style={styles.capabilityTitle}>{card.title}</Text><Text style={styles.capabilityBody}>{card.body}</Text><View style={styles.capabilityAction}><Text style={styles.capabilityActionText}>{card.action}</Text><ArrowRight size={16} color={colors.text} /></View>
              </Pressable>)}
            </View>
          </View>
          <View nativeID="languages" onLayout={event => { positions.current.languages = event.nativeEvent.layout.y; }} style={[styles.languageSection, mobile && { paddingBottom: 64 }]}>
            <Text style={styles.overline}>ONE DOCUMENT. THREE LANGUAGES.</Text>
            <View style={[styles.languageRow, mobile && { flexDirection: "column", gap: 28 }]}>{[{ word: "සිංහල", label: "Sinhala", detail: "Your original words" }, { word: "தமிழ்", label: "Tamil", detail: "A new perspective" }, { word: "English", label: "English", detail: "A wider conversation" }].map(language => <View key={language.label} style={styles.languageItem}><Text style={[styles.languageWord, mobile && { fontSize: 40 }]}>{language.word}</Text><Text style={styles.languageLabel}>{language.label}<Text style={styles.languageDetail}> / {language.detail}</Text></Text></View>)}</View>
            <Pressable accessibilityRole="button" onPress={() => goTo("workspace")} style={({ pressed }) => [styles.inlineLink, pressed && styles.pressed]}><Text style={styles.inlineLinkText}>Start with your own handwriting</Text><ArrowRight size={18} color={colors.text} /></Pressable>
          </View>
        </View>
        <View style={styles.footer}><View style={[styles.container, styles.footerInner, { paddingHorizontal: gutter }, mobile && styles.footerMobile]}><View><Text style={styles.footerBrand}>SINHALA OCR</Text><Text style={styles.footerTagline}>A little clarity goes a long way.</Text></View><View style={styles.footerRight}><Pressable accessibilityRole="button" onPress={() => goTo("workspace")}><Text style={styles.footerLink}>Back to the workspace ↗</Text></Pressable><Text style={styles.copyright}>© 2026 Sinhala OCR</Text></View></View></View>
      </ScrollView>
      <AccountModal visible={accountOpen} onClose={() => setAccountOpen(false)} />
      {account.user && <HistoryModal key={account.user.id} visible={historyOpen} onClose={() => setHistoryOpen(false)} onAccount={() => { setHistoryOpen(false); setAccountOpen(true); }} revision={historyRevision} />}
    </SafeAreaView>
  );
}
function Nav({ label, onPress }: { label: string; onPress: () => void }) {
  return <Pressable accessibilityRole="button" onPress={onPress} style={styles.navButton}><Text style={styles.navText}>{label}</Text></Pressable>;
}
function DocumentDrawing() {
  return <Svg width={116} height={112} viewBox="0 0 116 112" accessibilityElementsHidden><Rect x={30} y={14} width={62} height={82} rx={3} transform="rotate(8 61 55)" fill="none" stroke="#141413" strokeWidth={1.1} /><Rect x={22} y={14} width={62} height={82} rx={3} transform="rotate(-6 53 55)" fill="none" stroke="#141413" strokeWidth={1.4} /><Path d="M34 36 C43 31 45 40 53 34 S65 37 72 32 M33 48 C43 42 46 52 55 46 S65 48 73 44 M32 60 C41 56 45 65 53 58 S64 61 71 55 M31 72 C39 68 44 76 52 70 S61 72 68 67" fill="none" stroke="#141413" strokeWidth={1.3} strokeLinecap="round" /></Svg>;
}
const styles = StyleSheet.create({
  safe: { flex: 1 }, scroll: { flex: 1 }, scrollContent: { paddingBottom: 0 }, container: { width: "100%", maxWidth: 1600, alignSelf: "center" },
  headerOuter: { zIndex: 10 }, header: { height: 68, maxWidth: 1600, width: "100%", alignSelf: "center", flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }, brand: { fontFamily: fonts.sans, fontWeight: "700", letterSpacing: -.3, color: "#141413" },
  headerActions: { flexDirection: "row", alignItems: "center", gap: 18 }, navigation: { flexDirection: "row", gap: 28, marginRight: 10 }, navButton: { minHeight: 40, justifyContent: "center" }, navText: { fontFamily: fonts.sans, fontSize: 16, color: "#141413" }, headerCta: { backgroundColor: "#141413", borderRadius: 8, height: 36, paddingHorizontal: 17, flexDirection: "row", alignItems: "center", gap: 16 }, headerCtaText: { fontFamily: fonts.sans, fontSize: 15, fontWeight: "500", color: "#FAF9F5" }, menuButton: { width: 30, height: 40, alignItems: "center", justifyContent: "center" }, mobileNav: { paddingBottom: 22, gap: 8, borderBottomWidth: 1, borderColor: "#D1CFC5" },
  hero: { paddingTop: 76, paddingBottom: 76, gap: 36 }, heroDesktop: { flexDirection: "row", alignItems: "center", minHeight: 450, paddingTop: 112, paddingBottom: 112, gap: 72 }, heroMobile: { paddingTop: 54, paddingBottom: 54, gap: 28 }, heroCopy: { flexShrink: 1 }, heroCopyDesktop: { flex: 1.4 }, title: { fontFamily: fonts.display, color: "#141413", fontWeight: "700", letterSpacing: -2.1 }, heroIntro: { maxWidth: 550 }, heroIntroDesktop: { flex: 1, paddingTop: 45 }, subtitle: { fontFamily: fonts.serif, color: "#141413", fontWeight: "400", letterSpacing: -.45 },
  workspaceHeading: { alignItems: "center", marginBottom: 38 }, overline: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1.1, lineHeight: 16, color: "#5E5D59" }, workspaceTitle: { fontFamily: fonts.serif, fontWeight: "400", letterSpacing: -1.7, color: "#141413", textAlign: "center", marginTop: 15, maxWidth: 850 }, workspaceDescription: { fontFamily: fonts.serif, fontSize: 19, lineHeight: 27, color: "#5E5D59", textAlign: "center", marginTop: 14 },
  workspace: { gap: 20 }, workspaceDesktop: { flexDirection: "row" }, workspaceMain: { flex: 1 }, guide: { backgroundColor: "#F0EEE6", borderRadius: 14, padding: 28 }, guideDesktop: { width: 266 }, guideCompact: { paddingVertical: 2, gap: 8 }, compactGuideText: { fontFamily: fonts.serif, fontSize: 15, lineHeight: 21, color: "#5E5D59" }, guideTitle: { fontFamily: fonts.serif, fontSize: 28, lineHeight: 32, letterSpacing: -.5, color: "#141413", marginTop: 8 }, guideText: { fontFamily: fonts.serif, fontSize: 16, lineHeight: 23, marginTop: 14, color: "#5E5D59" }, guideRule: { height: 1, backgroundColor: "#D1CFC5", marginVertical: 22 }, guideFormats: { fontFamily: fonts.mono, fontSize: 11, color: "#141413", letterSpacing: .5 }, guideLimit: { fontFamily: fonts.sans, fontSize: 12, color: "#5E5D59", marginTop: 6 },
  workspaceFooter: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 20, paddingTop: 26 }, workspaceFooterMobile: { flexDirection: "column", alignItems: "stretch" }, fileCopy: { flex: 1, minWidth: 100 }, fileLabel: { fontFamily: fonts.mono, fontSize: 9, letterSpacing: 1, color: "#87867F", marginBottom: 6 }, fileName: { fontFamily: fonts.sans, fontSize: 13, color: "#141413" }, footerActions: { flexDirection: "row", gap: 14 }, primaryButton: { backgroundColor: "#141413", minHeight: 46, borderRadius: 8, paddingHorizontal: 20, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 22 }, primaryButtonText: { fontFamily: fonts.sans, fontSize: 15, fontWeight: "500", color: "#FAF9F5" }, resetButton: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 8, minHeight: 46 }, resetText: { fontFamily: fonts.sans, fontSize: 14, color: "#141413" }, disabled: { opacity: .38 }, pressed: { opacity: .72 },
  results: { marginTop: 60 }, resultHeading: { marginBottom: 32 }, resultTitle: { fontFamily: fonts.display, fontSize: 48, lineHeight: 52, letterSpacing: -1.5, color: "#141413", fontWeight: "700", marginTop: 18 }, resultCardTitle: { fontFamily: fonts.serif, fontSize: 44, lineHeight: 49, letterSpacing: -1.3, color: "#141413", marginTop: 12 }, resultDescription: { fontFamily: fonts.serif, fontSize: 18, lineHeight: 26, color: "#5E5D59", marginTop: 12, marginBottom: 30 },
  howSection: { paddingVertical: 104 }, howHeading: { gap: 24, marginBottom: 40 }, howHeadingDesktop: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between" }, howTitle: { fontFamily: fonts.display, fontWeight: "700", letterSpacing: -1.6, color: "#141413" }, howIntro: { fontFamily: fonts.serif, fontSize: 21, lineHeight: 29, color: "#141413", maxWidth: 390 }, capabilities: { gap: 20 }, capabilitiesRow: { flexDirection: "row" }, capability: { flex: 1, borderRadius: 16, padding: 28, minHeight: 370 }, capabilityTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" }, cardIllustration: { minHeight: 125, alignItems: "flex-start", justifyContent: "center", marginVertical: 10 }, typeDrawing: { fontFamily: fonts.serif, fontSize: 47, lineHeight: 80, color: "#141413", letterSpacing: -2 }, capabilityTitle: { fontFamily: fonts.serif, fontSize: 30, lineHeight: 35, letterSpacing: -.6, color: "#141413" }, capabilityBody: { fontFamily: fonts.serif, fontSize: 17, lineHeight: 25, color: "#3D3D3A", marginTop: 14, flex: 1 }, capabilityAction: { flexDirection: "row", gap: 12, alignItems: "center", marginTop: 30 }, capabilityActionText: { fontFamily: fonts.sans, fontSize: 13, fontWeight: "500", color: "#141413" },
  languageSection: { borderTopWidth: 1, borderColor: "#D1CFC5", paddingTop: 32, paddingBottom: 104 }, languageRow: { flexDirection: "row", marginTop: 36, marginBottom: 38, gap: 20 }, languageItem: { flex: 1 }, languageWord: { fontFamily: fonts.serif, fontSize: 48, lineHeight: 67, color: "#141413", letterSpacing: -1 }, languageLabel: { fontFamily: fonts.sans, fontSize: 13, color: "#141413", marginTop: 10 }, languageDetail: { color: "#5E5D59", fontSize: 12 }, inlineLink: { flexDirection: "row", alignItems: "center", gap: 15, alignSelf: "flex-start", paddingVertical: 10 }, inlineLinkText: { fontFamily: fonts.sans, fontSize: 15, color: "#141413", textDecorationLine: "underline" },
  footer: { backgroundColor: "#141413" }, footerInner: { paddingVertical: 64, flexDirection: "row", justifyContent: "space-between", gap: 36 }, footerMobile: { flexDirection: "column", paddingVertical: 44 }, footerBrand: { fontFamily: fonts.sans, fontSize: 25, fontWeight: "700", color: "#FAF9F5" }, footerTagline: { fontFamily: fonts.serif, fontSize: 18, color: "#D1CFC5", marginTop: 18 }, footerRight: { justifyContent: "space-between", gap: 30 }, footerLink: { fontFamily: fonts.sans, fontSize: 14, color: "#FAF9F5" }, copyright: { fontFamily: fonts.sans, fontSize: 12, color: "#B0AEA5" },
});
