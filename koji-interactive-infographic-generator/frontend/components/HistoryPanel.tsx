import ConversationHistory from "./ConversationHistory";
import { cloudEnabled } from "../studioClient";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Image, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import SketchCanvas from "./SketchCanvas";
import Icon from "./Icon";
import ThreeDViewer from "./ThreeDViewer";
import { clearHistory, deleteHistoryItem, GenerationHistoryItem, listHistory, loadHistoryItem, syncLocalHistory } from "../historyStorage";
import { makeSharedStyles, useAppTheme } from "../theme";

function download(item: GenerationHistoryItem) {
  if (Platform.OS !== "web" || typeof document === "undefined") return;
  const anchor = document.createElement("a");
  anchor.href = item.imageBase64 ? `data:image/png;base64,${item.imageBase64}` : item.imageUrl || "";
  anchor.download = `learnX-${item.mode}-${item.createdAt.slice(0, 10)}.png`;
  anchor.click();
}

interface HistoryPanelProps { onResume?: (item: GenerationHistoryItem) => void }

export default function HistoryPanel({ onResume }: HistoryPanelProps) {
  const { colors } = useAppTheme();
  const shared = makeSharedStyles(colors);
  const styles = makeStyles(colors);
  const [items, setItems] = useState<GenerationHistoryItem[]>([]);
  const [error,setError] = useState<string|null>(null);
  const [loading, setLoading] = useState(true);
  const [canLoadOlder, setCanLoadOlder] = useState(true);
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
    setLoading(true); setCanLoadOlder(true);
    try { setError(null); setItems(await listHistory()); } catch(e) { setError(e instanceof Error?e.message:"Unable to load history"); } finally { setLoading(false); }
  }, []);

  useEffect(() => { if (!cloudEnabled()) void refresh(); }, [refresh]);

  const loadOlder = async () => {
    const cloudItems = items.filter(item => /^[0-9a-f-]{36}$/i.test(item.id));
    const before = cloudItems.map(item => item.createdAt).sort()[0];
    if (!before) { setCanLoadOlder(false); return; }
    setLoading(true); setError(null);
    try {
      const older = await listHistory(before);
      setItems(current => [...new Map([...current, ...older].map(item => [item.id, item])).values()]);
      setCanLoadOlder(older.length === 50);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load older history"); }
    finally { setLoading(false); }
  };

  const selectItem = async (item: GenerationHistoryItem) => {
    setLoading(true); setError(null);
    try { setSelected(await loadHistoryItem(item)); } catch(e) { setError(e instanceof Error?e.message:"Unable to open history"); } finally { setLoading(false); }
  };

  const remove = async (id: string) => {
    try { await deleteHistoryItem(id); } catch(e) { setError(e instanceof Error?e.message:"Unable to delete"); return; }
    setItems((current) => current.filter((item) => item.id !== id));
    if (selected?.id === id) setSelected(null);
  };

  const clear = async () => {
    try { await clearHistory(); } catch(e) { setError(e instanceof Error?e.message:"Unable to clear history"); await refresh(); return; }
    setItems([]);
    setSelected(null);
  };

  if (cloudEnabled()) return <ConversationHistory onResume={onResume} />;

  return (
    <View style={styles.section}>
      <View style={styles.header}>
        <View><Text style={styles.eyebrow}>{cloudEnabled()?"CLOUD ARCHIVE":"LOCAL ARCHIVE"}</Text><Text style={styles.title}>Generation history</Text><Text style={styles.subtitle}>{cloudEnabled()?"Your latest cloud creations, with local copies in this browser.":"Stored in this browser until you delete it or browser storage fills."}</Text></View>
        {!!items.length && <Pressable onPress={() => void clear()} style={styles.clearButton}><Text style={styles.clearText}>Clear all</Text></Pressable>}
      </View>
      {cloudEnabled() && <Pressable disabled={loading} onPress={async()=>{setLoading(true);try{await syncLocalHistory();await refresh()}catch(e){setError(e instanceof Error?e.message:"Sync failed")}finally{setLoading(false)}}}><Text style={{color:colors.primaryBright}}>Sync local creations to my cloud history</Text></Pressable>}
      {error && <Text style={{color:colors.danger}}>{error}</Text>}
      {cloudEnabled() && canLoadOlder && !!items.length && <Pressable disabled={loading} onPress={() => void loadOlder()}><Text style={{ color: colors.primaryBright }}>Load older creations</Text></Pressable>}
      <Pressable onPress={()=>void refresh()}><Text style={{color:colors.primaryBright}}>Refresh history</Text></Pressable>
      {loading && <View style={[shared.card, styles.empty]}><ActivityIndicator color={colors.primary} /><Text style={styles.subtitle}>Opening your archive…</Text></View>}
      {!loading && !items.length && <View style={[shared.card, styles.empty]}><Icon color={colors.primary} name="layers" size={28} /><Text style={styles.emptyTitle}>No saved generations yet</Text><Text style={styles.subtitle}>Your next successful image will appear here automatically.</Text></View>}
      {selected && (
        <View style={[shared.card, styles.detail]}>
          <View style={styles.detailHeader}>
            <View><Text style={styles.eyebrow}>{selected.mode === "sketch" ? "DRAW TO IMAGE" : selected.mode === "anatomy" ? "HUMAN ANATOMY" : "GENERAL IMAGE"}</Text><Text style={styles.detailTitle}>Saved creation</Text></View>
            <View style={styles.actions}>
              {onResume && <Pressable onPress={() => onResume(selected)} style={styles.download}><Text style={styles.downloadText}>Continue chat</Text></Pressable>}
              <Pressable onPress={() => setSelected(null)} style={styles.clearButton}><Text style={styles.clearText}>Close</Text></Pressable>
            </View>
          </View>
          <View style={styles.versions}>{items.filter((item) => (item.chatId ?? item.id) === (selected.chatId ?? selected.id)).sort((a, b) => (a.version ?? 1) - (b.version ?? 1)).map((item) => <Pressable key={item.id} onPress={() => void selectItem(item)} style={[styles.versionChip, item.id === selected.id && styles.versionChipActive]}><Text style={styles.versionText}>Version {item.version ?? 1}</Text></Pressable>)}</View>
          {selected.mode === "sketch" && selected.sketchStrokes && <View style={styles.detailCopy}>
            <Text style={styles.detailLabel}>Original drawing</Text>
            <SketchCanvas key={selected.id} strokes={selected.sketchStrokes} onChange={() => undefined} disabled previewOnly />
            {selected.sketchMetadata && <Text style={styles.subtitle}>SDXL + Xinsir Scribble · Seed {selected.sketchMetadata.seed} · Adherence {selected.sketchMetadata.control_strength}</Text>}
          </View>}
          <Image resizeMode="contain" source={{ uri: `data:image/png;base64,${selected.imageBase64}` }} style={styles.detailImage} />
          <View style={styles.detailCopy}><Text style={styles.detailLabel}>Original prompt</Text><Text style={styles.detailText}>{selected.prompt || (selected.mode === "sketch" ? "No additional instruction" : "")}</Text></View>
          <View style={styles.detailCopy}><Text style={styles.detailLabel}>Model prompt</Text><Text style={styles.detailText}>{selected.enhancedPrompt}</Text></View>
          {!!selected.anatomyAnnotations?.length && <View style={styles.detailCopy}><Text style={styles.detailLabel}>Saved labels</Text><View style={styles.labels}>{selected.anatomyAnnotations.map((annotation) => <Text key={annotation.structure_id} style={styles.labelChip}>{annotation.label}</Text>)}</View></View>}
          {selected.evaluation && <Text style={styles.score}>Visual {selected.evaluation.visualScore.toFixed(1)} · Educational {selected.evaluation.pedagogicalScore.toFixed(1)}</Text>}
          {!!selected.interactions?.length && <View style={styles.detailCopy}><Text style={styles.detailLabel}>Questions &amp; answers</Text>{selected.interactions.map((interaction) => <View key={interaction.id} style={styles.qaTurn}><Text style={styles.prompt}>{interaction.question || (interaction.mode === "identify" ? "Identify selected object" : "Explain selected region")}</Text><Text style={styles.detailText}>{interaction.answer}</Text></View>)}</View>}
          {selected.glbBase64 ? <View style={styles.modelSection}><Text style={styles.detailLabel}>Interactive 3D model</Text><ThreeDViewer glbBase64={selected.glbBase64} sizeKb={selected.glbSizeKb} /></View> : <Text style={styles.subtitle}>{selected.threeDJob?.status === "converting" ? "3D conversion was started. Continue chat to retrieve or retry it." : selected.threeDJob?.status === "failed" ? `3D conversion failed: ${selected.threeDJob.error ?? "Please retry"}` : "No 3D model was created for this image."}</Text>}
        </View>
      )}
      <View style={styles.grid}>
        {chats.map((versions) => {
          const item = versions[versions.length - 1];
          return <Pressable key={item.chatId ?? item.id} onPress={() => void selectItem(item)} style={({ pressed }) => [shared.card, styles.card, pressed && styles.cardPressed]}>
            <Image resizeMode="cover" source={{ uri: item.imageBase64 ? `data:image/png;base64,${item.imageBase64}` : item.imageUrl || "" }} style={styles.image} />
            <View style={styles.cardBody}>
              <View style={styles.metaRow}><Text style={styles.mode}>{item.mode === "sketch" ? "Drawing" : item.mode === "anatomy" ? "Human anatomy" : "General image"}</Text><Text style={styles.date}>{new Date(item.createdAt).toLocaleString()}</Text></View>
              <Text numberOfLines={2} style={styles.prompt}>{item.prompt || (item.mode === "sketch" ? "Drawing without additional instruction" : "")}</Text>
              <Text style={styles.score}>{versions.length} version{versions.length === 1 ? "" : "s"} · {versions.reduce((count, version) => count + (version.interactions?.length ?? 0), 0)} Q&amp;A</Text>
              <Text numberOfLines={2} style={styles.enhanced}>{item.enhancedPrompt}</Text>
              {item.evaluation && <Text style={styles.score}>Visual {item.evaluation.visualScore.toFixed(1)} · Educational {item.evaluation.pedagogicalScore.toFixed(1)}</Text>}
              {!!item.anatomyAnnotations?.length && <View style={styles.labels}>{item.anatomyAnnotations.map((annotation) => <Text key={annotation.structure_id} style={styles.labelChip}>{annotation.label}</Text>)}</View>}
              {(item.glbBase64 || item.hasThreeD) && <Text style={styles.score}>Interactive 3D model saved</Text>}
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
