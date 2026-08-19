import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Platform,
} from "react-native";
import * as Clipboard from "expo-clipboard";
import { FileText, Copy, Check } from "lucide-react-native";

import type { ProcessResult } from "@/lib/api";

interface Props {
  result: ProcessResult;
}

export default function OcrResult({ result }: Props) {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"si" | "ta" | "en">("si");
  
  const getText = () => {
    switch (activeTab) {
      case "ta": return result.extracted_text_ta || "Translation not available";
      case "en": return result.extracted_text_en || "Translation not available";
      default: return result.extracted_text || "";
    }
  };

  const text = getText();
  const isEmpty = activeTab === "si" ? !text.trim() : false;
  const wordCount = text.split(/\s+/).filter(Boolean).length;

  const handleCopy = async () => {
    await Clipboard.setStringAsync(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <View style={styles.card}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <FileText size={16} color="#a78bfa" strokeWidth={1.75} />
          <Text style={styles.title}>Extracted Text</Text>
          {activeTab === "si" && !isEmpty && (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>
                {wordCount} {wordCount === 1 ? "word" : "words"}
              </Text>
            </View>
          )}
        </View>

        {!isEmpty && (
          <TouchableOpacity style={styles.copyBtn} onPress={handleCopy} activeOpacity={0.7}>
            {copied ? (
              <>
                <Check size={13} color="#34d399" strokeWidth={2} />
                <Text style={[styles.copyBtnText, { color: "#34d399" }]}>Copied</Text>
              </>
            ) : (
              <>
                <Copy size={13} color="rgba(255,255,255,0.6)" strokeWidth={1.75} />
                <Text style={styles.copyBtnText}>Copy</Text>
              </>
            )}
          </TouchableOpacity>
        )}
      </View>

      {/* Tabs */}
      <View style={styles.tabsContainer}>
        <TouchableOpacity
          style={[styles.tab, activeTab === "si" && styles.activeTab]}
          onPress={() => setActiveTab("si")}
        >
          <Text style={[styles.tabText, activeTab === "si" && styles.activeTabText]}>Sinhala</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === "ta" && styles.activeTab]}
          onPress={() => setActiveTab("ta")}
        >
          <Text style={[styles.tabText, activeTab === "ta" && styles.activeTabText]}>Tamil</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === "en" && styles.activeTab]}
          onPress={() => setActiveTab("en")}
        >
          <Text style={[styles.tabText, activeTab === "en" && styles.activeTabText]}>English</Text>
        </TouchableOpacity>
      </View>

      {/* Body */}
      {isEmpty ? (
        <View style={styles.emptyWrap}>
          <Text style={styles.emptyText}>No text detected in the image</Text>
        </View>
      ) : (
        <ScrollView
          style={styles.textBox}
          nestedScrollEnabled
          showsVerticalScrollIndicator={Platform.OS !== "web"}
        >
          <Text style={styles.ocrText} selectable>
            {text}
          </Text>
        </ScrollView>
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
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 14,
    flexWrap: "wrap",
    gap: 8,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flex: 1,
    flexWrap: "wrap",
  },
  title: {
    fontSize: 14,
    fontWeight: "600",
    color: "rgba(255,255,255,0.9)",
  },
  badge: {
    borderRadius: 999,
    backgroundColor: "rgba(139,92,246,0.15)",
    paddingHorizontal: 10,
    paddingVertical: 2,
  },
  badgeText: {
    fontSize: 12,
    color: "#c4b5fd",
  },
  copyBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderRadius: 8,
    backgroundColor: "rgba(255,255,255,0.08)",
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  copyBtnText: {
    fontSize: 12,
    fontWeight: "500",
    color: "rgba(255,255,255,0.6)",
  },
  emptyWrap: {
    paddingVertical: 32,
    alignItems: "center",
  },
  emptyText: {
    fontSize: 14,
    color: "rgba(255,255,255,0.25)",
  },
  tabsContainer: {
    flexDirection: "row",
    backgroundColor: "rgba(0,0,0,0.2)",
    borderRadius: 10,
    padding: 4,
    marginBottom: 16,
  },
  tab: {
    flex: 1,
    paddingVertical: 8,
    alignItems: "center",
    borderRadius: 6,
  },
  activeTab: {
    backgroundColor: "rgba(139,92,246,0.2)",
  },
  tabText: {
    fontSize: 13,
    fontWeight: "500",
    color: "rgba(255,255,255,0.4)",
  },
  activeTabText: {
    color: "#c4b5fd",
  },
  textBox: {
    maxHeight: 400,
    borderRadius: 12,
    backgroundColor: "rgba(0,0,0,0.35)",
    padding: 16,
  },
  ocrText: {
    fontSize: 16,
    lineHeight: 30,
    color: "rgba(255,255,255,0.85)",
    fontFamily: Platform.OS === "web" ? "system-ui, sans-serif" : undefined,
  },
});

