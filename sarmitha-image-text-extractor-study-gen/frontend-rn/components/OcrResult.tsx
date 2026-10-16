import React, { useState } from "react";
import { Platform, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import { Check, Copy } from "lucide-react-native";
import type { ProcessResult } from "@/lib/api";
import { editorialSurface, fonts, type AppColors, useAppTheme } from "@/theme";

interface Props { result: ProcessResult; }
type Language = "si" | "ta" | "en";

export default function OcrResult({ result }: Props) {
  const { colors } = useAppTheme();
  const { width } = useWindowDimensions();
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
    <View style={[styles.section, editorialSurface(colors), { padding: width < 680 ? 24 : width >= 1000 ? 56 : 36 }]}>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={[styles.sectionLabel, { color: colors.textMuted }]}>02 / YOUR WORDS</Text>
          <Text accessibilityRole="header" style={[styles.title, { color: colors.text }, width < 680 && { fontSize: 32, lineHeight: 37 }]}>A page, now in words.</Text>
          {activeTab === "si" && !isEmpty ? <Text style={[styles.wordCount, { color: colors.textMuted }]}>{wordCount} {wordCount === 1 ? "word" : "words"} extracted</Text> : null}
        </View>
        {!isEmpty ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={copied ? "Text copied to clipboard" : "Copy the selected language text"}
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
        <View style={[styles.emptyWrap, { backgroundColor: colors.background, borderColor: colors.border }]}><Text style={[styles.emptyText, { color: colors.textMuted }]}>No text was detected in this image.</Text></View>
      ) : (
        <ScrollView style={[styles.textBox, { backgroundColor: colors.background, borderColor: colors.border }]} nestedScrollEnabled showsVerticalScrollIndicator={Platform.OS !== "web"}>
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
      accessibilityRole="tab"
      accessibilityState={{ selected }}
      style={({ pressed }) => [styles.tab, { borderColor: selected ? colors.text : "transparent" }, pressed && styles.pressed]}
      onPress={() => onPress(id)}
    >
      <Text style={[styles.tabText, { color: selected ? colors.text : colors.textMuted }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  section: { marginBottom: 0 },
  header: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28, flexWrap: "wrap", gap: 16 },
  headerCopy: { flex: 1, minWidth: 230 },
  sectionLabel: { fontSize: 10, letterSpacing: 1.1, marginBottom: 14, fontFamily: fonts.mono },
  title: { fontSize: 44, lineHeight: 49, fontWeight: "400", letterSpacing: -1.3, fontFamily: fonts.serif },
  wordCount: { fontSize: 12, marginTop: 8, fontFamily: fonts.sans },
  copyBtn: { minHeight: 38, borderWidth: 1, borderRadius: 8, paddingHorizontal: 15, flexDirection: "row", alignItems: "center", gap: 9 },
  copyBtnText: { fontSize: 13, fontWeight: "500", fontFamily: fonts.sans },
  tabsContainer: { flexDirection: "row", borderBottomWidth: 1, marginBottom: 24 },
  tab: { minHeight: 44, borderBottomWidth: 2, paddingHorizontal: 18, alignItems: "center", justifyContent: "center" },
  tabText: { fontSize: 14, fontWeight: "500", fontFamily: fonts.sans },
  textBox: { minHeight: 220, maxHeight: 460, borderRadius: 12, padding: 24 },
  ocrText: { fontSize: 18, lineHeight: 34, fontWeight: "400", fontFamily: fonts.sans },
  emptyWrap: { minHeight: 220, padding: 24, alignItems: "center", justifyContent: "center", borderRadius: 12 },
  emptyText: { fontSize: 14, fontFamily: fonts.sans },
  pressed: { opacity: 0.72 },
});
