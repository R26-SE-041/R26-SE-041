import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Image, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import Icon from "./Icon";
import ThreeDViewer from "./ThreeDViewer";
import { clearHistory, deleteHistoryItem, GenerationHistoryItem, listHistory } from "../historyStorage";
import { makeSharedStyles, useAppTheme } from "../theme";

function download(item: GenerationHistoryItem) {
  if (Platform.OS !== "web" || typeof document === "undefined") return;
  const anchor = document.createElement("a");
  anchor.href = `data:image/png;base64,${item.imageBase64}`;
  anchor.download = `eduvision-${item.mode}-${item.createdAt.slice(0, 10)}.png`;
  anchor.click();
}

interface HistoryPanelProps { onResume?: (item: GenerationHistoryItem) => void }

export default function HistoryPanel({ onResume }: HistoryPanelProps) {
  const { colors } = useAppTheme();
  const shared = makeSharedStyles(colors);
  const styles = makeStyles(colors);
  const [items, setItems] = useState<GenerationHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<GenerationHistoryItem | null>(null);
  const chats = React.useMemo(() => {
    const grouped = new Map<string, GenerationHistoryItem[]>();
    items.forEach((item) => {
      const key = item.chatId ?? item.id;
      grouped.set(key, [...(grouped.get(key) ?? []), item]);
    });
    return [...grouped.values()].map((versions) => versions.sort((a, b) => (a.version ?? 1) - (b.version ?? 1)));
  }, [items]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try { setItems(await listHistory()); } finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const remove = async (id: string) => {
    await deleteHistoryItem(id);
    setItems((current) => current.filter((item) => item.id !== id));
    if (selected?.id === id) setSelected(null);
  };

  const clear = async () => {
    await clearHistory();
    setItems([]);
    setSelected(null);
  };

  return (
    <View style={styles.section}>
      <View style={styles.header}>
        <View><Text style={styles.eyebrow}>LOCAL ARCHIVE</Text><Text style={styles.title}>Generation history</Text><Text style={styles.subtitle}>Stored only in this browser. Up to 50 creations.</Text></View>
        {!!items.length && <Pressable onPress={() => void clear()} style={styles.clearButton}><Text style={styles.clearText}>Clear all</Text></Pressable>}
      </View>
      {loading && <View style={[shared.card, styles.empty]}><ActivityIndicator color={colors.primary} /><Text style={styles.subtitle}>Opening your local archive…</Text></View>}
      {!loading && !items.length && <View style={[shared.card, styles.empty]}><Icon color={colors.primary} name="layers" size={28} /><Text style={styles.emptyTitle}>No saved generations yet</Text><Text style={styles.subtitle}>Your next successful image will appear here automatically.</Text></View>}
      {selected && (
        <View style={[shared.card, styles.detail]}>
          <View style={styles.detailHeader}>
            <View><Text style={styles.eyebrow}>{selected.mode === "anatomy" ? "HUMAN ANATOMY" : "GENERAL IMAGE"}</Text><Text style={styles.detailTitle}>Saved creation</Text></View>
            <View style={styles.actions}>
              {onResume && <Pressable onPress={() => onResume(selected)} style={styles.download}><Text style={styles.downloadText}>Continue chat</Text></Pressable>}
              <Pressable onPress={() => setSelected(null)} style={styles.clearButton}><Text style={styles.clearText}>Close</Text></Pressable>
            </View>
          </View>
          <View style={styles.versions}>{items.filter((item) => (item.chatId ?? item.id) === (selected.chatId ?? selected.id)).sort((a, b) => (a.version ?? 1) - (b.version ?? 1)).map((item) => <Pressable key={item.id} onPress={() => setSelected(item)} style={[styles.versionChip, item.id === selected.id && styles.versionChipActive]}><Text style={styles.versionText}>Version {item.version ?? 1}</Text></Pressable>)}</View>
          <Image resizeMode="contain" source={{ uri: `data:image/png;base64,${selected.imageBase64}` }} style={styles.detailImage} />
          <View style={styles.detailCopy}><Text style={styles.detailLabel}>Original prompt</Text><Text style={styles.detailText}>{selected.prompt}</Text></View>
          <View style={styles.detailCopy}><Text style={styles.detailLabel}>Model prompt</Text><Text style={styles.detailText}>{selected.enhancedPrompt}</Text></View>
          {!!selected.anatomyAnnotations?.length && <View style={styles.detailCopy}><Text style={styles.detailLabel}>Verified anatomy labels</Text><View style={styles.labels}>{selected.anatomyAnnotations.map((annotation) => <Text key={annotation.structure_id} style={styles.labelChip}>{annotation.label}</Text>)}</View></View>}
          {selected.evaluation && <Text style={styles.score}>Visual {selected.evaluation.visualScore.toFixed(1)} · Educational {selected.evaluation.pedagogicalScore.toFixed(1)}</Text>}
          {!!selected.interactions?.length && <View style={styles.detailCopy}><Text style={styles.detailLabel}>Questions &amp; answers</Text>{selected.interactions.map((interaction) => <View key={interaction.id} style={styles.qaTurn}><Text style={styles.prompt}>{interaction.question || (interaction.mode === "identify" ? "Identify selected object" : "Explain selected region")}</Text><Text style={styles.detailText}>{interaction.answer}</Text></View>)}</View>}
          {selected.glbBase64 ? <View style={styles.modelSection}><Text style={styles.detailLabel}>Interactive 3D model</Text><ThreeDViewer glbBase64={selected.glbBase64} sizeKb={selected.glbSizeKb} /></View> : <Text style={styles.subtitle}>No 3D model was created for this image.</Text>}
        </View>
      )}
      <View style={styles.grid}>
        {chats.map((versions) => {
          const item = versions[versions.length - 1];
          return <Pressable key={item.chatId ?? item.id} onPress={() => setSelected(item)} style={({ pressed }) => [shared.card, styles.card, pressed && styles.cardPressed]}>
            <Image resizeMode="cover" source={{ uri: `data:image/png;base64,${item.imageBase64}` }} style={styles.image} />
            <View style={styles.cardBody}>
              <View style={styles.metaRow}><Text style={styles.mode}>{item.mode === "anatomy" ? "Human anatomy" : "General image"}</Text><Text style={styles.date}>{new Date(item.createdAt).toLocaleString()}</Text></View>
              <Text numberOfLines={2} style={styles.prompt}>{item.prompt}</Text>
              <Text style={styles.score}>{versions.length} version{versions.length === 1 ? "" : "s"} · {versions.reduce((count, version) => count + (version.interactions?.length ?? 0), 0)} Q&amp;A</Text>
              <Text numberOfLines={2} style={styles.enhanced}>{item.enhancedPrompt}</Text>
              {item.evaluation && <Text style={styles.score}>Visual {item.evaluation.visualScore.toFixed(1)} · Educational {item.evaluation.pedagogicalScore.toFixed(1)}</Text>}
              {!!item.anatomyAnnotations?.length && <View style={styles.labels}>{item.anatomyAnnotations.map((annotation) => <Text key={annotation.structure_id} style={styles.labelChip}>{annotation.label}</Text>)}</View>}
              {item.glbBase64 && <Text style={styles.score}>Interactive 3D model saved</Text>}
              <View style={styles.actions}>
                <Pressable onPress={(event) => { event.stopPropagation(); download(item); }} style={styles.download}><Icon color="#fff" name="download" size={15} /><Text style={styles.downloadText}>Download</Text></Pressable>
                <Pressable onPress={(event) => { event.stopPropagation(); void remove(item.id); }} style={styles.delete}><Text style={styles.deleteText}>Delete</Text></Pressable>
              </View>
            </View>
          </Pressable>;
        })}
      </View>
    </View>
  );
}

const makeStyles = (colors: ReturnType<typeof useAppTheme>["colors"]) => StyleSheet.create({
  section: { gap: 18 },
  header: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", alignItems: "flex-end", gap: 16, paddingVertical: 12 },
  eyebrow: { color: colors.primary, fontSize: 10, fontWeight: "900", letterSpacing: 2 },
  title: { color: colors.text, fontFamily: Platform.select({ web: "Georgia, serif", default: "serif" }), fontSize: 34, fontWeight: "700", marginTop: 5 },
  subtitle: { color: colors.textMuted, fontSize: 12, lineHeight: 18, marginTop: 5 },
  clearButton: { paddingHorizontal: 14, paddingVertical: 9, borderRadius: 50, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSoft },
  clearText: { color: colors.danger, fontSize: 12, fontWeight: "800" },
  empty: { minHeight: 210, alignItems: "center", justifyContent: "center", gap: 8 },
  emptyTitle: { color: colors.text, fontSize: 18, fontWeight: "800" },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 16 },
  card: { flexGrow: 1, flexBasis: 300, maxWidth: 500, padding: 10, overflow: "hidden" },
  cardPressed: { opacity: 0.86, transform: [{ scale: 0.995 }] },
  image: { width: "100%", aspectRatio: 1.35, borderRadius: 18, backgroundColor: colors.canvas },
  cardBody: { padding: 10, gap: 8 },
  metaRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", gap: 8 },
  mode: { color: colors.primary, fontSize: 11, fontWeight: "900", textTransform: "uppercase", letterSpacing: 0.8 },
  date: { color: colors.textDim, fontSize: 10 },
  prompt: { color: colors.text, fontSize: 15, fontWeight: "800", lineHeight: 21 },
  enhanced: { color: colors.textMuted, fontSize: 11, lineHeight: 17 },
  score: { color: colors.success, fontSize: 11, fontWeight: "800" },
  labels: { flexDirection: "row", flexWrap: "wrap", gap: 5 },
  labelChip: { color: colors.textMuted, fontSize: 10, fontWeight: "700", paddingHorizontal: 8, paddingVertical: 5, borderRadius: 50, backgroundColor: colors.surfaceSoft, overflow: "hidden" },
  detail: { gap: 18 },
  detailHeader: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 12 },
  detailTitle: { color: colors.text, fontFamily: Platform.select({ web: "Georgia, serif", default: "serif" }), fontSize: 26, fontWeight: "700", marginTop: 4 },
  detailImage: { width: "100%", height: 520, maxHeight: 520, borderRadius: 20, backgroundColor: colors.canvas },
  detailCopy: { gap: 6 },
  detailLabel: { color: colors.primary, fontSize: 10, fontWeight: "900", letterSpacing: 1.2, textTransform: "uppercase" },
  detailText: { color: colors.text, fontSize: 14, lineHeight: 22 },
  modelSection: { gap: 10 },
  actions: { flexDirection: "row", gap: 8, marginTop: 4 },
  versions: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  versionChip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 50, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border },
  versionChipActive: { borderColor: colors.primary, backgroundColor: "rgba(139,92,246,0.18)" },
  versionText: { color: colors.text, fontSize: 11, fontWeight: "800" },
  qaTurn: { gap: 5, padding: 12, borderRadius: 12, backgroundColor: colors.surfaceSoft },
  download: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 12, paddingVertical: 9, borderRadius: 11, backgroundColor: colors.primary },
  downloadText: { color: "#fff", fontSize: 11, fontWeight: "800" },
  delete: { paddingHorizontal: 12, paddingVertical: 9, borderRadius: 11, backgroundColor: colors.surfaceSoft },
  deleteText: { color: colors.danger, fontSize: 11, fontWeight: "800" },
});
