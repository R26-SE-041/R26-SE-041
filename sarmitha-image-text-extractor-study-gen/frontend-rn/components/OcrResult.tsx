import React, { useState } from "react";
import { Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import { Check, Copy } from "lucide-react-native";
import type { ProcessResult } from "@/lib/api";
import { editorialSurface, fonts, type AppColors, useAppTheme } from "@/theme";

interface Props { result: ProcessResult; }
type Language = "si" | "ta" | "en";

export default function OcrResult({ result }: Props) {
  const { colors } = useAppTheme();
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<Language>("si");
  const text = activeTab === "ta"
    ? result.extracted_text_ta || "Translation not available"
    : activeTab === "en" ? result.extracted_text_en || "Translation not available" : result.extracted_text || "";
  const isEmpty = activeTab === "si" && !text.trim();
  const wordCount = text.split(/\s+/).filter(Boolean).length;

  const handleCopy = async () => {
    await Clipboard.setStringAsync(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <View style={[styles.section, editorialSurface(colors)]}>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={[styles.sectionLabel, { color: colors.primary }]}>03 / EXTRACTED TEXT</Text>
          <Text style={[styles.title, { color: colors.text }]}>Your document, digitised.</Text>
          {activeTab === "si" && !isEmpty ? <Text style={[styles.wordCount, { color: colors.textMuted }]}>{wordCount} {wordCount === 1 ? "word" : "words"} extracted</Text> : null}
        </View>
        {!isEmpty ? (
          <Pressable
            style={({ pressed }) => [styles.copyBtn, { borderColor: colors.text }, pressed && styles.pressed]}
            onPress={handleCopy}
          >
            {copied ? <Check size={15} color={colors.success} /> : <Copy size={15} color={colors.text} />}
            <Text style={[styles.copyBtnText, { color: copied ? colors.success : colors.text }]}>{copied ? "Copied" : "Copy text"}</Text>
          </Pressable>
        ) : null}
      </View>

      <View style={[styles.tabsContainer, { borderColor: colors.border }]}>
        <LanguageTab id="si" label="Sinhala" active={activeTab} onPress={setActiveTab} colors={colors} />
        <LanguageTab id="ta" label="Tamil" active={activeTab} onPress={setActiveTab} colors={colors} />
        <LanguageTab id="en" label="English" active={activeTab} onPress={setActiveTab} colors={colors} />
      </View>

      {isEmpty ? (
        <View style={[styles.emptyWrap, { backgroundColor: colors.surfaceSoft, borderColor: colors.border }]}><Text style={[styles.emptyText, { color: colors.textMuted }]}>No text was detected in this image.</Text></View>
      ) : (
        <ScrollView style={[styles.textBox, { backgroundColor: colors.surfaceSoft, borderColor: colors.border }]} nestedScrollEnabled showsVerticalScrollIndicator={Platform.OS !== "web"}>
          <Text style={[styles.ocrText, { color: colors.text }]} selectable>{text}</Text>
        </ScrollView>
      )}
    </View>
  );
}

function LanguageTab({ id, label, active, onPress, colors }: { id: Language; label: string; active: Language; onPress: (id: Language) => void; colors: AppColors }) {
  const selected = active === id;
  return (
    <Pressable
      style={({ pressed }) => [styles.tab, { borderColor: colors.border }, selected && { backgroundColor: colors.text }, pressed && styles.pressed]}
      onPress={() => onPress(id)}
    >
      <Text style={[styles.tabText, { color: selected ? colors.background : colors.textMuted }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  section: { marginBottom: 0 },
  header: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28, flexWrap: "wrap", gap: 16 },
  headerCopy: { flex: 1, minWidth: 230 },
  sectionLabel: { fontSize: 10, fontWeight: "700", letterSpacing: 1.4, marginBottom: 10, fontFamily: fonts.sans },
  title: { fontSize: 44, lineHeight: 47, fontWeight: "700", letterSpacing: -1.4, fontFamily: fonts.display },
  wordCount: { fontSize: 12, marginTop: 8, fontFamily: fonts.sans },
  copyBtn: { minHeight: 46, borderWidth: 1, borderRadius: 10, paddingHorizontal: 17, flexDirection: "row", alignItems: "center", gap: 9 },
  copyBtnText: { fontSize: 12, fontWeight: "700", fontFamily: fonts.sans },
  tabsContainer: { flexDirection: "row", alignSelf: "flex-start", borderWidth: 1, borderRadius: 12, overflow: "hidden", marginBottom: 16 },
  tab: { minHeight: 42, borderRightWidth: 1, paddingHorizontal: 20, alignItems: "center", justifyContent: "center" },
  tabText: { fontSize: 11, fontWeight: "700", fontFamily: fonts.sans },
  textBox: { minHeight: 220, maxHeight: 460, borderWidth: 1, borderRadius: 18, padding: 24 },
  ocrText: { fontSize: 18, lineHeight: 34, fontWeight: "400", fontFamily: fonts.sans },
  emptyWrap: { minHeight: 220, padding: 24, alignItems: "center", justifyContent: "center", borderRadius: 18, borderWidth: 1 },
  emptyText: { fontSize: 14, fontFamily: fonts.sans },
  pressed: { opacity: 0.72 },
});
