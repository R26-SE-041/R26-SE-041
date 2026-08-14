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

interface Props {
  text: string;
}

export default function OcrResult({ text }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await Clipboard.setStringAsync(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isEmpty = !text.trim();
  const wordCount = text.split(/\s+/).filter(Boolean).length;

  return (
    <View style={styles.card}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <FileText size={16} color="#a78bfa" strokeWidth={1.75} />
          <Text style={styles.title}>Extracted Sinhala Text</Text>
          {!isEmpty && (
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
  textBox: {
    maxHeight: 280,
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
