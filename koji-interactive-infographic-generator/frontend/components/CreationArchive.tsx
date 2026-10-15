import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Image, Pressable, Text, TextInput, View } from "react-native";
import { cloudEnabled, getCloudHistory, studioRequest } from "../studioClient";
import { trashConversation, restoreConversation, purgeConversation, GenerationHistoryItem, listHistory, loadHistoryItem, syncLocalHistory, updateHistoryItem } from "../historyStorage";
import { CreationSummary, creationTitle, dateGroup, filterArchive, localSummaries, modeLabel } from "../historyView";
import { headingFont, makeSharedStyles, useAppTheme } from "../theme";
import Icon from "./Icon";
import AnatomyOverlay from "./AnatomyOverlay";
import ThreeDViewer from "./ThreeDViewer";
import ImageDownloadControls from "./ImageDownloadControls";
import PdfEvidence from "./PdfEvidence";
import type { GenerationInteraction } from "../historyStorage";
import type { AnatomyAnnotation } from "../App";

interface CloudChat { id: string; title: string; updated_at: string; deleted_at?: string | null; mode?: string; latest_generation_id?: string; imageUrl?: string; version_count?: number; has_three_d?: boolean }
interface SavedEvent { id: string; kind: string; generationId?: string; createdAt: string; imageUrl?: string; data: { sources?: GenerationInteraction["sources"]; grounding?: GenerationInteraction["grounding"]; prompt?: string; originalPrompt?: string; question?: string; answer?: string; error?: string; message?: string; enhancedPrompt?: string; payload?: unknown; mode?: string; version?: number; speedMode?: "normal" | "pro" | "promax" } }
interface Props { onResume?: (item: GenerationHistoryItem) => void }

export default function CreationArchive({ onResume }: Props) {
  const { colors } = useAppTheme();
  const shared = makeSharedStyles(colors);
  const cloud = cloudEnabled();
  const [items, setItems] = useState<CreationSummary[]>([]);
  const [selected, setSelected] = useState<CreationSummary | null>(null);
  const [creation, setCreation] = useState<GenerationHistoryItem | null>(null);
  const [events, setEvents] = useState<SavedEvent[]>([]);
  const [query, setQuery] = useState("");
  const [trash, setTrash] = useState(false);
  const [archiveWidth, setArchiveWidth] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [hasMoreEvents, setHasMoreEvents] = useState(false);
  const [menu, setMenu] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<CreationSummary | null>(null);
  const [renaming, setRenaming] = useState<CreationSummary | null>(null);
  const [title, setTitle] = useState("");
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const requestVersion = useRef(0);
  const openVersion = useRef(0);
  const button = { minHeight: 44, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 8, backgroundColor: colors.surfaceSoft, justifyContent: "center" as const };
  const text = { color: colors.text, fontSize: 14, lineHeight: 22 };
  const row = { flexDirection: "row" as const, flexWrap: "wrap" as const, alignItems: "center" as const, gap: 8 };
  const columns = Math.max(1, Math.floor((archiveWidth + 16) / (280 + 16)));
  const cardWidth = archiveWidth ? (archiveWidth - 16 * (columns - 1)) / columns : undefined;

  const refresh = useCallback(async (older?: CreationSummary) => {
    const version = ++requestVersion.current;
    setLoading(true); setError(null);
    try {
      let rows: CreationSummary[];
      if (cloud) {
        const params = new URLSearchParams({ query: query.trim() });
        if (trash) params.set("trashed", "true");
        if (older) { params.set("before", older.updatedAt); params.set("before_id", older.id); }
        const chats = await studioRequest<CloudChat[]>(`/studio/chats?${params}`);
        rows = chats.map(chat => {
          const mode = chat.mode === "anatomy" || chat.mode === "sketch" ? chat.mode : "general";
          return { id: chat.id, deletedAt: chat.deleted_at, title: creationTitle(chat.title, mode), updatedAt: chat.updated_at, mode,
            generationId: chat.latest_generation_id, imageUrl: chat.imageUrl, versionCount: chat.version_count || 0,
            hasThreeD: chat.has_three_d, source: "cloud" };
        });
        if (version === requestVersion.current) setHasMore(chats.length === 50);
      } else rows = localSummaries(await listHistory(undefined, trash));
      if (version !== requestVersion.current) return;
      setItems(previous => older ? [...new Map([...previous, ...rows].map(item => [item.id, item])).values()] : rows);
    } catch (failure) { if (version === requestVersion.current) setError(failure instanceof Error ? failure.message : "Unable to load history."); }
    finally { if (version === requestVersion.current) setLoading(false); }
  }, [cloud, query, trash]);
  useEffect(() => { const timer = setTimeout(() => void refresh(), 250); return () => { clearTimeout(timer); requestVersion.current++; }; }, [refresh]);
  useEffect(() => () => { openVersion.current++; }, []);

  const open = async (item: CreationSummary, resume = false) => {
    const version = ++openVersion.current;
    setBusy(true); setError(null); setMenu(null);
    if (!resume) { setSelected(item); setCreation(null); setEvents([]); setVersionsOpen(false); setDetailsOpen(false); }
    try {
      let [full, turns] = await Promise.all([
        item.generationId ? (item.source === "cloud" ? getCloudHistory(item.generationId) : loadHistoryItem(item.versions![item.versions!.length - 1])) : Promise.resolve(null),
        item.source === "cloud" ? studioRequest<SavedEvent[]>(`/studio/chats/${encodeURIComponent(item.id)}/events`) : Promise.resolve([]),
      ]);
      // Older API releases lack list previews; saved image events still allow
      // existing conversations to open during a rolling backend deployment.
      if (!full && item.source === "cloud") {
        const latest = [...turns].sort((a,b) => b.createdAt.localeCompare(a.createdAt) || b.id.localeCompare(a.id)).find(event => event.kind === "image" && event.generationId);
        if (latest?.generationId) full = await getCloudHistory(latest.generationId);
      }
      if (version !== openVersion.current) return;
      if (resume && full && onResume) { onResume(full); return; }
      if (resume) setSelected(item);
      if (item.source === "cloud" && !item.versionCount) setSelected({ ...item, versionCount: turns.filter(event => event.kind === "image" && event.generationId).length });
      setCreation(full); setEvents(turns.sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id)));
      setHasMoreEvents(turns.length === 50);
      if (resume && !full) setNotice("Open a saved instruction below to continue this creation.");
    } catch (failure) { if (version === openVersion.current) setError(failure instanceof Error ? failure.message : "Unable to open creation."); }
    finally { if (version === openVersion.current) setBusy(false); }
  };
  const action = async (operation: () => Promise<void>) => {
    setBusy(true); setError(null); setNotice(null);
    try { await operation(); } catch (failure) { setError(failure instanceof Error ? failure.message : "Please retry."); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    if (!deleting) return;
    const item = deleting;
    await action(async () => {
      if (trash) await purgeConversation(item.id, item.source === "cloud");
      else await trashConversation(item.id, item.source === "cloud");
      if (selected?.id === item.id) { setSelected(null); setCreation(null); }
      setItems(previous => previous.filter(row => row.id !== item.id)); setDeleting(null); setMenu(null);
      await refresh();
      setNotice(trash ? "Creation permanently deleted." : "Moved to Recycle Bin. You can restore it there.");
    });
  };
  const restore = async (item: CreationSummary) => action(async () => {
    await restoreConversation(item.id, item.source === "cloud");
    setItems(previous => previous.filter(row => row.id !== item.id));
    await refresh();
    setNotice("Creation restored to your history.");
  });
  const rename = async () => {
    if (!renaming || !title.trim()) return;
    const item = renaming;
    await action(async () => {
      if (item.source === "cloud") await studioRequest(`/studio/chats/${encodeURIComponent(item.id)}`, { method: "PATCH", body: JSON.stringify({ title: title.trim() }) });
      else for (const version of item.versions || []) await updateHistoryItem(version.id, { title: title.trim() });
      setItems(previous => previous.map(row => row.id === item.id ? { ...row, title: title.trim() } : row));
      if (selected?.id === item.id) setSelected({ ...selected, title: title.trim() });
      setRenaming(null); setMenu(null); setNotice("Title updated.");
    });
  };
  const loadOlderEvents = async () => {
    if (!selected || !events.length) return;
    const first = events[0];
    await action(async () => {
      const older = await studioRequest<SavedEvent[]>(`/studio/chats/${encodeURIComponent(selected.id)}/events?before=${encodeURIComponent(first.createdAt)}&before_id=${encodeURIComponent(first.id)}`);
      setEvents(previous => [...new Map([...older, ...previous].map(event => [event.id, event])).values()].sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id)));
      setHasMoreEvents(older.length === 50);
    });
  };
  const visible = useMemo(() => cloud ? items : filterArchive(items, query, "all", "all"), [cloud, items, query]);
  const groups = useMemo(() => {
    const map = new Map<string, CreationSummary[]>();
    visible.forEach(item => { const key = dateGroup(item.updatedAt); map.set(key, [...(map.get(key) || []), item]); });
    return [...map.entries()];
  }, [visible]);
  const versions = selected?.source === "local" ? (selected.versions || []).map(item => ({ id: item.id, label: `Version ${item.version || 1}` }))
    : events.filter(event => event.kind === "image" && event.generationId).map(event => ({ id: event.generationId!, label: event.data.version ? `Version ${event.data.version}` : new Date(event.createdAt).toLocaleString() }));
  const chooseVersion = async (id: string) => action(async () => {
    const full = selected?.source === "cloud" ? await getCloudHistory(id) : await loadHistoryItem(selected!.versions!.find(item => item.id === id)!);
    setCreation(full);
  });

  return <View onLayout={event => setArchiveWidth(event.nativeEvent.layout.width)} style={{ gap: 18 }}>
    <View style={[row, { justifyContent: "space-between" }]}>
      <View style={{ flex: 1 }}><Text accessibilityRole="header" style={{ color: colors.text, fontFamily: headingFont, fontSize: 34 }}>{trash ? "Recycle Bin" : "Your creations"}</Text><Text style={{ color: colors.textMuted, marginTop: 6 }}>{trash ? "Restore deleted creations, or permanently remove them." : "Images, conversations and versions, together."}</Text></View>
      <Pressable accessibilityRole="button" disabled={busy || loading} style={button} onPress={() => { requestVersion.current++; openVersion.current++; setItems([]); setQuery(""); setHasMore(false); setLoading(true); setRenaming(null); setError(null); setTrash(!trash); setSelected(null); setCreation(null); setDeleting(null); setMenu(null); setNotice(null); }}><Text style={text}>{trash ? "Back to creations" : "Recycle Bin"}</Text></Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel="Refresh history" disabled={busy || loading} style={button} onPress={() => void refresh()}><Icon name="refresh" color={colors.text} size={18} /></Pressable>
    </View>
    {error && <View style={shared.error}><Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text><Pressable accessibilityRole="button" style={button} onPress={() => selected ? void open(selected) : void refresh()}><Text style={text}>Retry</Text></Pressable></View>}
    {notice && <Text accessibilityLiveRegion="polite" style={{ color: colors.textMuted }}>{notice}</Text>}
    {deleting && <View style={[shared.card, { gap: 12, borderColor: colors.danger }]}><Text style={text}>{trash ? `Permanently delete “${deleting.title}” and all its images, versions and conversations? This cannot be undone.` : `Move “${deleting.title}” to the Recycle Bin? You can restore its images, versions and conversations later.`}</Text><View style={row}><Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => void remove()}><Text style={{ color: colors.danger }}>{trash ? "Delete permanently" : "Move to Recycle Bin"}</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => setDeleting(null)}><Text style={text}>Cancel</Text></Pressable></View></View>}
    {renaming && <View style={[shared.card, { gap: 12 }]}><Text style={text}>Rename creation</Text><TextInput accessibilityLabel="Creation title" value={title} onChangeText={setTitle} maxLength={80} editable={!busy} style={{ ...text, padding: 12, borderWidth: 1, borderColor: colors.border, borderRadius: 8 }} /><View style={row}><Pressable accessibilityRole="button" disabled={busy || !title.trim()} style={button} onPress={() => void rename()}><Text style={text}>Save title</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => setRenaming(null)}><Text style={text}>Cancel</Text></Pressable></View></View>}
    {selected ? <>
      <Pressable accessibilityRole="button" disabled={busy} style={[button, { alignSelf: "flex-start" }]} onPress={() => { openVersion.current++; setSelected(null); setCreation(null); setMenu(null); setNotice(null); }}><Text style={text}>← Back to creations</Text></Pressable>
      <View style={[shared.card, { gap: 18 }]}>
        <View style={[row, { justifyContent: "space-between" }]}><View style={{ flex: 1 }}><Text accessibilityRole="header" style={{ color: colors.text, fontFamily: headingFont, fontSize: 28 }}>{selected.title}</Text><Text style={{ color: colors.textMuted, marginTop: 5 }}>{modeLabel(selected.mode)} · {new Date(selected.updatedAt).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</Text></View>{creation && onResume && <Pressable accessibilityRole="button" disabled={busy} style={[button, shared.primaryButton]} onPress={() => onResume(creation)}><Text style={shared.buttonText}>Continue</Text></Pressable>}</View>
        {busy && <ActivityIndicator color={colors.primary} />}
        {creation && <>
          <View style={{ width: "100%", maxWidth: 600, alignSelf: "center", aspectRatio: 1, backgroundColor: "white", borderRadius: 8, overflow: "hidden" }}><Image source={{ uri: creation.imageBase64 ? `data:image/png;base64,${creation.imageBase64}` : creation.imageUrl }} resizeMode="contain" style={{ width: "100%", height: "100%" }} /><AnatomyOverlay annotations={(creation.anatomyAnnotations || []) as AnatomyAnnotation[]} /></View>
          <ImageDownloadControls imageBase64={creation.imageBase64} annotations={(creation.anatomyAnnotations || []) as AnatomyAnnotation[]} organ={(creation.anatomy as { organ?: string })?.organ} />
          {creation.glbBase64 && <ThreeDViewer glbBase64={creation.glbBase64} sizeKb={creation.glbSizeKb} />}
          <Text style={text}>{creation.prompt || "Created from a drawing."}</Text>
        </>}
        {selected.versionCount > 1 && <Pressable accessibilityRole="button" accessibilityState={{ expanded: versionsOpen }} style={button} onPress={() => setVersionsOpen(!versionsOpen)}><Text style={text}>{versionsOpen ? "Hide versions" : `Versions (${selected.versionCount})`}</Text></Pressable>}
        {versionsOpen && <View style={{ gap: 8 }}>{hasMoreEvents && <Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => void loadOlderEvents()}><Text style={text}>Load earlier versions</Text></Pressable>}<View style={row}>{versions.map(version => <Pressable key={version.id} accessibilityRole="button" accessibilityState={{ selected: creation?.id === version.id }} disabled={busy} style={[button, creation?.id === version.id && { borderWidth: 1, borderColor: colors.text }]} onPress={() => void chooseVersion(version.id)}><Text style={text}>{version.label}</Text></Pressable>)}</View></View>}
        <Text accessibilityRole="header" style={{ ...text, fontWeight: "600" }}>Conversation</Text>
        {hasMoreEvents && <Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => void loadOlderEvents()}><Text style={text}>Load earlier messages</Text></Pressable>}
        {events.filter(event => ["prompt", "interaction", "error"].includes(event.kind)).map(event => <View key={event.id} style={{ padding: 14, borderRadius: 8, backgroundColor: colors.surfaceSoft, gap: 6 }}><Text style={{ color: colors.textDim, fontSize: 12 }}>{new Date(event.createdAt).toLocaleString()}</Text><Text selectable style={text}>{event.data.question || event.data.prompt || event.data.message}</Text>{event.data.answer && <Text selectable style={text}>{event.data.answer}</Text>}<PdfEvidence sources={event.data.sources} grounding={event.data.grounding} />{event.data.error && <Text style={{ color: colors.danger }}>{event.data.error}</Text>}</View>)}
        {selected.source === "local" && (creation?.interactions || []).map(turn => <View key={turn.id} style={{ padding: 14, borderRadius: 8, backgroundColor: colors.surfaceSoft, gap: 6 }}><Text selectable style={{ ...text, fontWeight: "600" }}>{turn.question || "Explore selected region"}</Text><Text selectable style={text}>{turn.answer || turn.error || "Answer pending"}</Text><PdfEvidence sources={turn.sources} grounding={turn.grounding} /></View>)}
        {!events.some(event => event.kind === "interaction") && !creation?.interactions?.length && <Text style={{ color: colors.textMuted }}>Continue this creation to ask questions or explore its details.</Text>}
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: detailsOpen }} style={button} onPress={() => setDetailsOpen(!detailsOpen)}><Text style={text}>{detailsOpen ? "Hide generation details" : "Generation details"}</Text></Pressable>
        {detailsOpen && <View style={{ gap: 12 }}>
          {creation && <Text selectable style={text}>{creation.enhancedPrompt || creation.prompt}</Text>}
          {creation?.evaluation && <Text style={text}>Visual score {creation.evaluation.visualScore.toFixed(1)} · Educational score {creation.evaluation.pedagogicalScore.toFixed(1)}</Text>}
          {events.filter(event => event.kind === "enhancement").map(event => <View key={event.id} style={{ gap: 8 }}><Text selectable style={text}>{event.data.prompt}</Text>{!creation && onResume && event.data.payload != null && <Pressable accessibilityRole="button" style={button} onPress={() => onResume({ id: event.id, chatId: selected.id, createdAt: event.createdAt, prompt: event.data.originalPrompt || "", enhancedPrompt: event.data.prompt || "", enhancedPayload: event.data.payload, imageBase64: "", mode: selected.mode, speedMode: event.data.speedMode || "pro", anatomy: (event.data.payload as { anatomy_spec?: unknown }).anatomy_spec })}><Text style={text}>Continue from this instruction</Text></Pressable>}</View>)}
        </View>}
      </View>
    </> : <>
      <TextInput accessibilityLabel="Search creations" placeholder="Search your creations…" placeholderTextColor={colors.textDim} value={query} onChangeText={setQuery} maxLength={100} style={{ ...text, padding: 14, minHeight: 48, borderWidth: 1, borderColor: colors.border, borderRadius: 8, backgroundColor: colors.surface }} />
      {loading && <View style={[shared.card, { gap: 12 }]}><ActivityIndicator color={colors.primary} /><Text style={{ color: colors.textMuted }}>Loading your creations…</Text><View style={{ height: 100, backgroundColor: colors.surfaceSoft, borderRadius: 8 }} /></View>}
      {!loading && !visible.length && <View style={[shared.card, { paddingVertical: 40, alignItems: "center", gap: 10 }]}><Icon name="image" color={colors.primary} size={32} /><Text style={{ ...text, fontWeight: "600" }}>{query.trim() ? "No matching creations" : trash ? "Recycle Bin is empty" : "Your ideas belong here"}</Text><Text style={{ color: colors.textMuted, textAlign: "center" }}>{query.trim() ? "Try a different search." : trash ? "Deleted creations stay here until you restore or permanently delete them." : "Create an image or drawing. Its conversation and versions will stay together."}</Text></View>}
      {groups.map(([label, rows]) => <View key={label} style={{ gap: 12 }}><Text accessibilityRole="header" style={{ color: colors.textMuted, fontSize: 13, fontWeight: "600" }}>{label}</Text><View style={{ flexDirection: "row", flexWrap: "wrap", gap: 16 }}>{rows.map(item => <View key={item.id} style={[shared.card, { padding: 14, gap: 12, width: cardWidth ?? "100%", flexGrow: 0, flexShrink: 0 }]}>
        <Pressable accessibilityRole="button" accessibilityLabel={`Open ${item.title}`} disabled={busy || trash} onPress={() => void open(item)} style={{ borderRadius: 8, overflow: "hidden", backgroundColor: colors.surfaceSoft }}>{item.imageUrl ? <Image source={{ uri: item.imageUrl }} resizeMode="contain" style={{ width: "100%", aspectRatio: 1.65 }} /> : <View style={{ aspectRatio: 1.65, alignItems: "center", justifyContent: "center" }}><Icon name={item.mode === "sketch" ? "pencil" : item.mode === "anatomy" ? "heart" : "image"} size={40} color={colors.textDim} /></View>}</Pressable>
        <Text numberOfLines={2} style={{ ...text, height: 44, fontWeight: "600", fontSize: 17 }}>{item.title}</Text><Text numberOfLines={2} style={{ color: colors.textMuted, height: 36, lineHeight: 18, fontSize: 12 }}>{modeLabel(item.mode)} · {new Date(item.updatedAt).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}{item.hasThreeD ? " · 3D" : ""}</Text>
        {trash ? <View style={row}><Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => void restore(item)}><Text style={text}>Restore</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => setDeleting(item)}><Text style={{ ...text, color: colors.danger }}>Delete permanently</Text></Pressable></View> : <View style={row}><Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => void open(item)}><Text style={text}>Open</Text></Pressable>{onResume && <Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => void open(item, true)}><Text style={text}>Continue</Text></Pressable>}<Pressable accessibilityRole="button" disabled={busy} accessibilityLabel={`More actions for ${item.title}`} accessibilityState={{ expanded: menu === item.id }} style={[button, { marginLeft: "auto" }]} onPress={() => setMenu(menu === item.id ? null : item.id)}><Text style={{ ...text, fontSize: 22 }}>⋯</Text></Pressable></View>}
        {menu === item.id && <View style={{ gap: 6, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 }}><Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => { setRenaming(item); setTitle(item.title); setMenu(null); }}><Text style={text}>Rename</Text></Pressable>{item.generationId && <Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => void open(item)}><Text style={text}>Download options</Text></Pressable>}<Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => { setDeleting(item); setMenu(null); }}><Text style={{ color: colors.danger }}>Delete</Text></Pressable></View>}
      </View>)}</View></View>)}
      {hasMore && !loading && !!items.length && <Pressable accessibilityRole="button" style={button} disabled={busy} onPress={() => void refresh(items[items.length - 1])}><Text style={text}>Load older creations</Text></Pressable>}
      <View style={{ gap: 10, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.border }}><Text style={{ color: colors.textDim, fontSize: 12 }}>{cloud ? "Saved privately to your account." : "Saved in this browser. Sign in to sync across devices."}</Text>{cloud && !trash && <Pressable accessibilityRole="button" disabled={busy} style={[button, { alignSelf: "flex-start" }]} onPress={() => void action(async () => { const count = await syncLocalHistory(); await refresh(); setNotice(count ? `${count} local creation${count === 1 ? "" : "s"} synced.` : "Your local creations are already synced."); })}><Text style={text}>Sync local creations</Text></Pressable>}</View>
    </>}
  </View>;
}
