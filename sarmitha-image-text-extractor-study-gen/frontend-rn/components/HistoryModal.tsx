import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { ArrowLeft, ArrowRight, RefreshCw, Trash2, X } from "lucide-react-native";
import { loadHistory, loadHistoryItem, removeHistoryItem, type HistoryItem } from "@/lib/history";
import { fonts } from "@/theme";
import OcrResult from "./OcrResult";
import ImageComparison from "./ImageComparison";

export default function HistoryModal({ visible, onClose, onAccount, revision }: { visible: boolean; onClose: () => void; onAccount: () => void; revision: number }) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [selected, setSelected] = useState<HistoryItem | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const refresh = async (offset = 0) => {
    setBusy(true); setError("");
    try {
      const data = await loadHistory(offset);
      if (!active.current) return;
      setItems(old => offset ? [...old, ...data.items.filter(item => !old.some(row => row.id === item.id))] : data.items);
      setMore(data.has_more);
    } catch (failure) { if (active.current) setError((failure as Error).message); }
    finally { if (active.current) setBusy(false); }
  };
  useEffect(() => { if (visible) { setSelected(null); setPendingDelete(null); void refresh(); } }, [visible, revision]);
  const open = async (id: string) => {
    setBusy(true); setError("");
    try { const item = await loadHistoryItem(id); if (active.current) setSelected(item); }
    catch (failure) { if (active.current) setError((failure as Error).message); }
    finally { if (active.current) setBusy(false); }
  };
  const remove = async (id: string) => {
    setBusy(true); setError("");
    try { await removeHistoryItem(id); if (active.current) { setPendingDelete(null); setItems(old => old.filter(row => row.id !== id)); } }
    catch (failure) { if (active.current) setError((failure as Error).message); }
    finally { if (active.current) setBusy(false); }
  };
  return <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
    <View style={styles.backdrop}><View accessibilityViewIsModal style={styles.card}>
      <View style={styles.header}><Text style={styles.overline}>YOUR PRIVATE WORKSPACE</Text><View style={styles.headerActions}><Pressable accessibilityRole="button" onPress={onAccount}><Text style={styles.accountLink}>Account</Text></Pressable><Pressable accessibilityRole="button" accessibilityLabel="Close history" onPress={onClose}><X size={22} color="#141413" /></Pressable></View></View>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text accessibilityRole="header" style={styles.title}>Your document history.</Text><Text style={styles.description}>Revisit your original image, enhanced image, Sinhala text, and Tamil and English translations together.</Text>
        <View style={styles.toolbar}>{selected ? <Pressable accessibilityRole="button" onPress={() => setSelected(null)} style={styles.action}><ArrowLeft size={16} color="#141413" /><Text style={styles.actionText}>All documents</Text></Pressable> : <Pressable accessibilityRole="button" disabled={busy} onPress={() => void refresh()} style={styles.action}><RefreshCw size={16} color="#141413" /><Text style={styles.actionText}>Refresh history</Text></Pressable>}</View>
        {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
        {busy && <ActivityIndicator style={styles.spinner} color="#141413" />}
        {selected ? <>
          <Text style={styles.filename}>{selected.filename}</Text><Text style={styles.date}>{new Date(selected.created_at).toLocaleString()}</Text>
          <View style={styles.savedImages}>
            <Text accessibilityRole="header" style={styles.imageTitle}>01 / Original & enhanced images</Text>
            {selected.image_error ? <Text accessibilityRole="alert" style={styles.error}>{selected.image_error}</Text> : !selected.original_image_url && !selected.enhanced_image_url ? <Text style={styles.legacyNotice}>This older document contains saved text only. Process the image again to save both images with the results.</Text> : null}
            {(selected.original_image_url || selected.enhanced_image_url) && <ImageComparison key={selected.id + selected.original_image_url + selected.enhanced_image_url} originalUri={selected.original_image_url} enhancedUri={selected.enhanced_image_url} />}
            <Pressable accessibilityRole="button" disabled={busy} onPress={() => void open(selected.id)} style={styles.action}><RefreshCw size={16} color="#141413" /><Text style={styles.actionText}>Reload document</Text></Pressable>
          </View>
          <OcrResult key={selected.id} result={{ ...selected, original_b64: "", enhanced_b64: "" }} />
        </> : <>
          {!items.length && !busy && !error && <View style={styles.empty}><Text style={styles.emptyTitle}>Your next clear idea starts here.</Text><Text style={styles.description}>Process an image while signed in to save its original, enhanced version, extracted text, and translations here.</Text><Pressable accessibilityRole="button" onPress={onClose} style={styles.action}><Text style={styles.actionText}>Back to the workspace</Text><ArrowRight size={16} color="#141413" /></Pressable></View>}
          {items.map(item => <View key={item.id} style={styles.row}>
            <Pressable accessibilityRole="button" accessibilityLabel={`Open ${item.filename}`} disabled={busy} onPress={() => void open(item.id)} style={styles.rowMain}><Text style={styles.filename}>{item.filename}</Text><Text style={styles.date}>{new Date(item.created_at).toLocaleString()}</Text><Text numberOfLines={2} style={styles.preview}>{item.extracted_text || "No text detected"}</Text></Pressable>
            <Pressable accessibilityRole="button" accessibilityLabel={`Delete ${item.filename}`} disabled={busy} onPress={() => setPendingDelete(item.id)} style={styles.deleteButton}><Trash2 size={17} color="#5E5D59" /></Pressable>
            {pendingDelete === item.id && <View style={styles.confirm}><Text style={styles.confirmText}>Delete this document, including its saved images, text, and translations?</Text><View style={styles.confirmActions}><Pressable accessibilityRole="button" disabled={busy} onPress={() => void remove(item.id)}><Text style={styles.deleteText}>Delete</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} onPress={() => setPendingDelete(null)}><Text style={styles.actionText}>Keep document</Text></Pressable></View></View>}
          </View>)}
          {more && <Pressable accessibilityRole="button" disabled={busy} onPress={() => void refresh(items.length)} style={styles.action}><Text style={styles.actionText}>Load more documents</Text><ArrowRight size={16} color="#141413" /></Pressable>}
        </>}
      </ScrollView>
    </View></View>
  </Modal>;
}

const styles = StyleSheet.create({
  savedImages: { marginTop: 12, marginBottom: 24 }, imageTitle: { fontFamily: fonts.mono, fontSize: 12, color: "#5E5D59", marginBottom: 18 }, legacyNotice: { fontFamily: fonts.sans, fontSize: 14, lineHeight: 22, color: "#5E5D59", paddingVertical: 18 },
  backdrop: { flex: 1, backgroundColor: "rgba(20,20,19,.35)", padding: 16, justifyContent: "center", alignItems: "center" }, card: { backgroundColor: "#FAF9F5", width: "100%", maxWidth: 900, maxHeight: "92%", borderRadius: 24 },
  header: { padding: 24, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }, headerActions: { flexDirection: "row", gap: 22, alignItems: "center" }, overline: { fontFamily: fonts.mono, fontSize: 9, letterSpacing: .7, color: "#5E5D59", flexShrink: 1 }, accountLink: { fontFamily: fonts.sans, fontSize: 13, color: "#141413" },
  content: { paddingHorizontal: 24, paddingBottom: 32 }, title: { fontFamily: fonts.serif, fontSize: 37, lineHeight: 42, letterSpacing: -1, color: "#141413" }, description: { fontFamily: fonts.serif, fontSize: 17, lineHeight: 25, color: "#5E5D59", marginTop: 14 }, toolbar: { marginTop: 24, marginBottom: 10 }, action: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 12, alignSelf: "flex-start" }, actionText: { fontFamily: fonts.sans, fontSize: 14, color: "#141413" },
  row: { flexDirection: "row", flexWrap: "wrap", borderTopWidth: 1, borderColor: "#D1CFC5", paddingVertical: 22, gap: 14 }, rowMain: { flex: 1 }, filename: { fontFamily: fonts.sans, fontWeight: "500", fontSize: 16, color: "#141413" }, date: { fontFamily: fonts.mono, fontSize: 10, color: "#87867F", marginTop: 7, marginBottom: 12 }, preview: { fontFamily: fonts.sans, fontSize: 15, lineHeight: 24, color: "#5E5D59" }, deleteButton: { padding: 10, alignSelf: "flex-start" },
  confirm: { width: "100%", padding: 18, backgroundColor: "#F0EEE6", borderRadius: 10, gap: 15 }, confirmActions: { flexDirection: "row", gap: 28 }, confirmText: { fontFamily: fonts.serif, fontSize: 17, lineHeight: 23, color: "#141413" }, deleteText: { fontFamily: fonts.sans, fontSize: 14, color: "#A44735" }, error: { fontFamily: fonts.sans, fontSize: 14, lineHeight: 22, color: "#A44735", marginVertical: 16 }, spinner: { padding: 18 }, empty: { paddingVertical: 30 }, emptyTitle: { fontFamily: fonts.serif, fontSize: 28, lineHeight: 33, color: "#141413" },
});
