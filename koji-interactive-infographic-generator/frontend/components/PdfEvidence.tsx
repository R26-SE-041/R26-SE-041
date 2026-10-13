import React, { useState } from "react";
import { Linking, Platform, Pressable, Text, View } from "react-native";
import { PdfSource, pdfPageUrl } from "../pdfSources";
import { useAppTheme } from "../theme";

export default function PdfEvidence({ sources = [], grounding }: { sources?: PdfSource[]; grounding?: "image" | "pdf" | "no_match" }) {
  const { colors } = useAppTheme();
  const [expanded, setExpanded] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);
  const open = async (source: PdfSource) => {
    setError(null); setOpening(true);
    // Open during the click so the browser does not block a tab after the URL fetch.
    const tab = Platform.OS === "web" ? window.open("about:blank", "_blank") : null;
    if (tab) tab.opener = null;
    try {
      if (Platform.OS === "web" && !tab) throw new Error("Allow popups to open this PDF page, then retry.");
      const url = await pdfPageUrl(source.documentId, source.page);
      if (tab) tab.location.href = url;
      else await Linking.openURL(url);
    }
    catch (failure) { tab?.close(); setError(failure instanceof Error ? failure.message : "Could not open this PDF. Please retry."); }
    finally { setOpening(false); }
  };
  if (!grounding && !sources.length) return null;
  return <View style={{ gap: 8 }}>
    <Text style={{ color: colors.textDim, fontSize: 12 }}>{grounding === "no_match" ? "No relevant evidence found in your selected PDFs" : grounding === "pdf" ? "PDF evidence retrieved · check the passages below" : "Image-based explanation · no PDF sources used"}</Text>
    {sources.map(source => <View key={`${source.documentId}:${source.number}`} style={{ gap: 6 }}>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12 }}>
        <Pressable accessibilityRole="button" disabled={opening} onPress={() => void open(source)}><Text style={{ color: colors.primaryBright }}>[{source.number}] {source.filename} · PDF page {source.page}{opening ? " · opening…" : " ↗"}</Text></Pressable>
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: expanded === source.number }} onPress={() => setExpanded(expanded === source.number ? null : source.number)}><Text style={{ color: colors.textDim }}>{expanded === source.number ? "Hide passage" : "Show passage"}</Text></Pressable>
      </View>
      {expanded === source.number && <Text selectable style={{ color: colors.text, lineHeight: 22, padding: 12, backgroundColor: colors.surfaceSoft, borderRadius: 8 }}>{source.excerpt}</Text>}
    </View>)}
    {error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}
  </View>;
}
