import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Platform, Pressable, Text, View } from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { decode } from "base64-arraybuffer";
import { cloudEnabled } from "../studioClient";
import { useAppTheme } from "../theme";
import { listPdfDocuments, MAX_PDF_BYTES, MAX_PDF_FILES, PdfDocument, reconcilePdfSelection, removePdfDocument, retryPdfDocument, uploadPdfDocument } from "../pdfSources";

interface Props {
  chatId?: string;
  disabled: boolean;
  selected: string[];
  onSelectionChange: (ids: string[]) => void;
  restoreSelection?: boolean;
}

export default function PdfSourcesPanel({ chatId, disabled, selected, onSelectionChange, restoreSelection }: Props) {
  const { colors } = useAppTheme();
  const [documents, setDocuments] = useState<PdfDocument[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef({ selected, onSelectionChange });
  latest.current = { selected, onSelectionChange };
  const known = useRef(new Set<string>());
  const scope = useRef(chatId);
  scope.current = chatId;
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const enabled = cloudEnabled() && Boolean(chatId);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    known.current = new Set(latest.current.selected);
    let firstLoad = true;
    setDocuments([]); setError(null); setLoading(enabled);
    const refresh = async () => {
      try {
        const rows = await listPdfDocuments(chatId!);
        if (!active) return;
        setDocuments(rows); setLoading(false); setError(null);
        if (firstLoad && restoreSelection) rows.forEach(row => known.current.add(row.id));
        firstLoad = false;
        const next = reconcilePdfSelection(rows, latest.current.selected, known.current);
        rows.filter(row => row.status === "ready").forEach(row => known.current.add(row.id));
        latest.current.onSelectionChange(next);
      } catch (failure) {
        if (active) { setLoading(false); setError(failure instanceof Error ? failure.message : "Could not load PDF sources"); }
      }
      if (active) timer = setTimeout(refresh, 4000);
    };
    if (enabled) void refresh();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [chatId, enabled]);

  const perform = async (action: () => Promise<unknown>) => {
    const current = chatId;
    setBusy(true); setError(null);
    try { await action(); }
    catch (failure) { if (mounted.current && scope.current === current) setError(failure instanceof Error ? failure.message : "PDF action failed. Please retry."); }
    finally { if (mounted.current && scope.current === current) setBusy(false); }
  };

  const upload = () => perform(async () => {
    const current = chatId!;
    const result = await DocumentPicker.getDocumentAsync({ type: "application/pdf", multiple: true, copyToCacheDirectory: true, base64: false });
    if (result.canceled) return;
    try {
      if (!mounted.current || scope.current !== current) return;
      if (documents.length + result.assets.length > MAX_PDF_FILES) throw new Error(`Attach up to ${MAX_PDF_FILES} PDFs per conversation.`);
      for (const asset of result.assets) {
        if (!mounted.current || scope.current !== current) return;
        if (!asset.name.toLowerCase().endsWith(".pdf")) throw new Error("Choose PDF files only.");
        if (asset.size && asset.size > MAX_PDF_BYTES) throw new Error(`${asset.name} exceeds the 15 MiB limit.`);
        let body: BodyInit;
        if (Platform.OS === "web") {
          body = asset.file ?? await fetch(asset.uri).then(response => response.blob());
        } else {
          const filesystem = await import("expo-file-system/legacy");
          const encoded = await filesystem.readAsStringAsync(asset.uri, { encoding: filesystem.EncodingType.Base64 });
          body = decode(encoded);
        }
        const row = await uploadPdfDocument(current, asset.name, body);
        if (mounted.current && scope.current === current) setDocuments(previous => [...previous.filter(item => item.id !== row.id), row]);
      }
    } finally {
      if (Platform.OS === "web") result.assets.forEach(asset => { if (asset.uri.startsWith("blob:")) URL.revokeObjectURL(asset.uri); });
    }
  });

  const button = { minHeight: 44, justifyContent: "center" as const, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: colors.border };
  const locked = disabled || busy || loading;
  return <View style={{ gap: 12, padding: 16, borderRadius: 12, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.border }}>
    <Text style={{ color: colors.text, fontWeight: "700", fontSize: 16 }}>Study sources · optional PDFs</Text>
    <Text style={{ color: colors.textMuted }}>Choose the files to use for your next image question. Answers include PDF page references.</Text>
    {!enabled ? <Text style={{ color: colors.textDim }}>Sign in to a cloud workspace and save this image to attach PDFs.</Text> : <>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <Pressable accessibilityRole="button" disabled={locked || documents.length >= MAX_PDF_FILES} onPress={() => void upload()} style={[button, locked && { opacity: .5 }]}><Text style={{ color: colors.primaryBright }}>Upload PDFs</Text></Pressable>
        <Pressable accessibilityRole="button" disabled={locked} onPress={() => onSelectionChange(documents.filter(item => item.status === "ready").map(item => item.id))} style={button}><Text style={{ color: colors.text }}>Select all ready</Text></Pressable>
        <Pressable accessibilityRole="button" disabled={locked} onPress={() => onSelectionChange([])} style={button}><Text style={{ color: colors.text }}>Clear selection</Text></Pressable>
        {(busy || loading) && <ActivityIndicator color={colors.primaryBright} />}
      </View>
      <Text accessibilityLiveRegion="polite" style={{ color: colors.textDim }}>{selected.length ? `${selected.length} PDF${selected.length === 1 ? "" : "s"} selected · only these files will be searched` : "No PDF sources selected · image-based explanation"}</Text>
      {documents.map(item => <View key={item.id} style={{ gap: 6, paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.border }}>
        <View style={{ flexDirection: "row", gap: 8, alignItems: "center" }}>
          <Pressable accessibilityRole="checkbox" accessibilityLabel={`Use ${item.filename}`} accessibilityState={{ checked: selected.includes(item.id), disabled: locked || item.status !== "ready" }} disabled={locked || item.status !== "ready"} onPress={() => onSelectionChange(selected.includes(item.id) ? selected.filter(id => id !== item.id) : [...selected, item.id])} style={{ flex: 1, flexDirection: "row", gap: 10, paddingVertical: 8, opacity: item.status === "ready" ? 1 : .6 }}>
            <Text style={{ color: colors.primaryBright }}>{selected.includes(item.id) ? "☑" : "☐"}</Text>
            <Text style={{ color: colors.text, flex: 1 }}>{item.filename}</Text>
          </Pressable>
          {item.status === "failed" && <Pressable accessibilityRole="button" disabled={locked} onPress={() => void perform(async () => { const row = await retryPdfDocument(item.id); if (mounted.current) setDocuments(current => current.map(value => value.id === row.id ? row : value)); })} style={button}><Text style={{ color: colors.primaryBright }}>Retry</Text></Pressable>}
          <Pressable accessibilityRole="button" accessibilityLabel={`Remove ${item.filename}`} disabled={locked || item.status === "processing"} onPress={() => void perform(async () => { await removePdfDocument(item.id); if (mounted.current) { setDocuments(current => current.filter(value => value.id !== item.id)); latest.current.onSelectionChange(latest.current.selected.filter(id => id !== item.id)); } })} style={button}><Text style={{ color: colors.textDim }}>Remove</Text></Pressable>
        </View>
        <Text style={{ color: item.status === "failed" ? colors.danger : colors.textDim, fontSize: 12 }}>{item.status === "processing" ? "Processing PDF… You can keep studying while it becomes ready." : item.status === "failed" ? item.error : `${item.page_count} pages · ready`}</Text>
        {item.status === "ready" && item.skipped_pages > 0 && <Text style={{ color: colors.textDim, fontSize: 12 }}>{item.skipped_pages} pages had no readable text and were skipped. Scanned pages need OCR.</Text>}
      </View>)}
      <Text style={{ color: colors.textDim, fontSize: 12 }}>Up to {MAX_PDF_FILES} text PDFs · 15 MiB and 300 pages each. Page references use PDF page numbers.</Text>
    </>}
    {error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}
  </View>;
}
