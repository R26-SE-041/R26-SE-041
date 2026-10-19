import React, { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { getHistoryRevision, isHistoryFresh, subscribeHistory } from "../historyActivity";
import { ActivityIndicator, Image, Pressable, Text, TextInput, View } from "react-native";
import { cloudEnabled, getCloudHistory, SavedModel, studioRequest } from "../studioClient";
import { trashConversation, restoreConversation, purgeConversation, GenerationHistoryItem, listHistory, loadHistoryItem, syncLocalHistory, updateHistoryItem } from "../historyStorage";
import { CreationSummary, creationTitle, conversationEvents, dateGroup, filterArchive, localSummaries, modeLabel } from "../historyView";
import ModelGallery from "./ModelGallery";
import ArchiveDialog from "./ArchiveDialog";
import HistoryCardMenu from "./HistoryCardMenu";
import HistoryImagePreview from "./HistoryImagePreview";
import { headingFont, makeSharedStyles, useAppTheme } from "../theme";
import Icon from "./Icon";
import AnatomyOverlay from "./AnatomyOverlay";
import ThreeDViewer from "./ThreeDViewer";
import ImageDownloadControls from "./ImageDownloadControls";
import PdfEvidence from "./PdfEvidence";
import StructuredAnswer from "./StructuredAnswer";
import type { GenerationInteraction } from "../historyStorage";
import type { AnatomyAnnotation } from "../App";

interface CloudChat { id: string; title: string; updated_at: string; deleted_at?: string | null; mode?: string; latest_generation_id?: string; imageUrl?: string; imageKey?: string; version_count?: number; has_three_d?: boolean; annotations?: GenerationHistoryItem["anatomyAnnotations"] }
interface SavedEvent { id: string; kind: string; generationId?: string; createdAt: string; imageUrl?: string; data: { sources?: GenerationInteraction["sources"]; grounding?: GenerationInteraction["grounding"]; prompt?: string; originalPrompt?: string; question?: string; answer?: string; error?: string; message?: string; enhancedPrompt?: string; payload?: unknown; mode?: string; version?: number; speedMode?: "normal" | "pro" | "promax" } }
interface Props { active?: boolean; onResume?: (item: GenerationHistoryItem) => void }

export default function CreationArchive({ active = true, onResume }: Props) {
  const { colors } = useAppTheme();
  const shared = makeSharedStyles(colors);
  const cloud = cloudEnabled();
  const [items, setItems] = useState<CreationSummary[]>([]);
  const [selected, setSelected] = useState<CreationSummary | null>(null);
  const [creation, setCreation] = useState<GenerationHistoryItem | null>(null);
  const [events, setEvents] = useState<SavedEvent[]>([]);
  const [query, setQuery] = useState("");
  const [trash, setTrash] = useState(false);
  const [category, setCategory] = useState<"images" | "sketch" | "models">("images");
  const [visited, setVisited] = useState(active);
  useEffect(() => { if (active) setVisited(true); }, [active]);
  const [archiveWidth, setArchiveWidth] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [hasMoreEvents, setHasMoreEvents] = useState(false);
  const [deleting, setDeleting] = useState<CreationSummary | null>(null);
  const [renaming, setRenaming] = useState<CreationSummary | null>(null);
  const [title, setTitle] = useState("");
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const requestVersion = useRef(0);
  const openVersion = useRef(0);
  const lastLoaded = useRef<{ key: string; at: number; revision: number } | null>(null);
  const detailLoaded = useRef<{ key: string; at: number; revision: number } | null>(null);
  const revision = useSyncExternalStore(subscribeHistory, getHistoryRevision, getHistoryRevision);
  const viewKey = JSON.stringify([cloud, query.trim(), trash, category]);
  const lists = useRef(new Map<string, { items: CreationSummary[]; hasMore: boolean; loaded: { key: string; at: number; revision: number } }>());
  const requestedView = useRef(viewKey);
  const inFlight = useRef<{ key: string; revision: number; version: number } | null>(null);
  const button = { minHeight: 44, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 8, backgroundColor: colors.surfaceSoft, justifyContent: "center" as const };
  const text = { color: colors.text, fontSize: 14, lineHeight: 22 };
  const row = { flexDirection: "row" as const, flexWrap: "wrap" as const, alignItems: "center" as const, gap: 8 };
  const columns = Math.max(1, Math.floor((archiveWidth + 16) / (280 + 16)));
  const cardWidth = archiveWidth ? (archiveWidth - 16 * (columns - 1)) / columns : undefined;

  const refresh = useCallback(async (older?: CreationSummary) => {
    if (category === "models") return;
    const startedRevision = getHistoryRevision();
    if (inFlight.current?.key === viewKey && inFlight.current.revision === startedRevision && inFlight.current.version === requestVersion.current) return;
    const version = ++requestVersion.current;
    inFlight.current = { key: viewKey, revision: startedRevision, version };
    setLoading(true); setError(null);
    try {
      let rows: CreationSummary[];
      if (cloud) {
        const params = new URLSearchParams({ query: query.trim(), category });
        if (trash) params.set("trashed", "true");
        if (older) { params.set("before", older.updatedAt); params.set("before_id", older.id); }
        const chats = await studioRequest<CloudChat[]>(`/studio/chats?${params}`);
        rows = chats.map(chat => {
          const mode = chat.mode === "anatomy" || chat.mode === "sketch" ? chat.mode : "general";
          return { id: chat.id, deletedAt: chat.deleted_at, title: creationTitle(chat.title, mode), updatedAt: chat.updated_at, mode,
            generationId: chat.latest_generation_id, imageUrl: chat.imageUrl, imageKey: chat.imageKey, versionCount: chat.version_count || 0,
            hasThreeD: chat.has_three_d, annotations: chat.annotations || [], source: "cloud" };
        });
        if (version === requestVersion.current) setHasMore(chats.length === 50);
      } else rows = localSummaries(await listHistory(undefined, trash)).filter(item => category === "sketch" ? item.mode === "sketch" : item.mode !== "sketch");
      if (version !== requestVersion.current) return;
      const loaded = older ? lastLoaded.current || { key: viewKey, at: Date.now(), revision: startedRevision } : { key: viewKey, at: Date.now(), revision: startedRevision };
      lastLoaded.current = loaded;
      setItems(previous => {
        const merged = older ? [...new Map([...previous, ...rows].map(item => [item.id, item])).values()] : rows;
        lists.current.set(viewKey, { items: merged, hasMore: cloud && rows.length === 50, loaded });
        while (lists.current.size > 8) lists.current.delete(lists.current.keys().next().value!);
        return merged;
      });
    } catch (failure) { if (version === requestVersion.current) setError(failure instanceof Error ? failure.message : "Unable to load history."); }
    finally {
      if (inFlight.current?.version === version) inFlight.current = null;
      if (version === requestVersion.current) setLoading(false);
    }
  }, [cloud, query, trash, category, viewKey]);
  const changeCategory = (next: typeof category) => {
    if (next === category) return;
    const cached = lists.current.get(JSON.stringify([cloud, query.trim(), trash, next]));
    requestVersion.current++; openVersion.current++; setBusy(false);
    setSelected(null); setCreation(null); setError(null); setCategory(next);
    setItems(cached?.items || []); setHasMore(cached?.hasMore || false);
    lastLoaded.current = cached?.loaded || null; setLoading(!cached && next !== "models");
  };
  useEffect(() => {
    if (!active || category === "models") return;
    // Cancel reads for a different search/bin, but allow an accepted read to
    // finish while the user visits another workspace.
    if (requestedView.current !== viewKey) { requestVersion.current++; requestedView.current = viewKey; }
    if (isHistoryFresh(lastLoaded.current, viewKey, revision)) return;
    const timer = setTimeout(() => {
      if (!isHistoryFresh(lastLoaded.current, viewKey, getHistoryRevision())) void refresh();
    }, 250);
    return () => clearTimeout(timer);
  }, [active, refresh, revision, viewKey, category]);
  useEffect(() => {
    if (!active || category === "models" || typeof window === "undefined") return;
    const revalidate = () => {
      if (document.hidden || isHistoryFresh(lastLoaded.current, viewKey, getHistoryRevision())) return;
      void refresh();
    };
    window.addEventListener("focus", revalidate);
    document.addEventListener("visibilitychange", revalidate);
    return () => { window.removeEventListener("focus", revalidate); document.removeEventListener("visibilitychange", revalidate); };
  }, [active, refresh, viewKey, category]);
  useEffect(() => () => { openVersion.current++; requestVersion.current++; }, []);

  const open = useCallback(async (item: CreationSummary, resume = false, background = false) => {
    const version = ++openVersion.current;
    const startedRevision = getHistoryRevision();
    setBusy(true); setError(null);
    if (!resume && !background) { setSelected(item); setCreation(null); setEvents([]); setVersionsOpen(false); setDetailsOpen(false); }
    try {
      let [full, turns] = await Promise.all([
        item.generationId ? (item.source === "cloud" ? getCloudHistory(item.generationId, item.modelEvent) : item.versions?.length ? loadHistoryItem(item.versions[item.versions.length - 1]) : listHistory().then(rows => { const stored = rows.find(version => version.id === item.generationId); return stored ? loadHistoryItem(stored) : null; })) : Promise.resolve(null),
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
      detailLoaded.current = { key: item.id, at: Date.now(), revision: startedRevision };
      if (resume && !full) setNotice("Open a saved instruction below to continue this creation.");
    } catch (failure) { if (version === openVersion.current) setError(failure instanceof Error ? failure.message : "Unable to open creation."); }
    finally { if (version === openVersion.current) setBusy(false); }
  }, [onResume]);
  useEffect(() => {
    if (!active || !selected || busy || error || isHistoryFresh(detailLoaded.current, selected.id, revision)) return;
    void open(selected, false, true);
  }, [active, selected, busy, error, revision, open]);
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
      setItems(previous => previous.filter(row => row.id !== item.id)); setDeleting(null);
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
      else {
        const versions = item.versions ?? (await listHistory()).filter(version => (version.chatId || version.id) === item.id);
        for (const version of versions) await updateHistoryItem(version.id, { title: title.trim() });
      }
      setItems(previous => previous.map(row => row.id === item.id ? { ...row, title: title.trim() } : row));
      if (selected?.id === item.id) setSelected({ ...selected, title: title.trim() });
      setRenaming(null); setNotice("Title updated.");
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
  const visible = useMemo(() => category === "models" ? [] : cloud ? items : filterArchive(items, query, "all", "all"), [cloud, items, query, category]);
  const modelSummary = (model: SavedModel): CreationSummary => ({ id: model.chatId, title: model.title, updatedAt: model.createdAt,
    generationId: model.generationId, modelEvent: model.id === model.generationId ? undefined : model.id,
    mode: model.mode === "sketch" || model.mode === "anatomy" ? model.mode : "general", versionCount: 1, hasThreeD: true, source: cloud ? "cloud" : "local" });
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
      <Pressable accessibilityRole="button" disabled={busy || loading} style={button} onPress={() => { requestVersion.current++; openVersion.current++; setItems([]); setQuery(""); setHasMore(false); setLoading(true); setRenaming(null); setError(null); setTrash(!trash); setSelected(null); setCreation(null); setDeleting(null); setNotice(null); }}><Text style={text}>{trash ? "Back to creations" : "Recycle Bin"}</Text></Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel="Refresh history" disabled={busy || loading} style={button} onPress={() => void refresh()}><Icon name="refresh" color={colors.text} size={18} /></Pressable>
    </View>
    {error && <View style={shared.error}><Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text><Pressable accessibilityRole="button" style={button} onPress={() => selected ? void open(selected) : void refresh()}><Text style={text}>Retry</Text></Pressable></View>}
    {notice && <Text accessibilityLiveRegion="polite" style={{ color: colors.textMuted }}>{notice}</Text>}
    {deleting && <ArchiveDialog title={trash ? "Delete permanently?" : "Move to Recycle Bin?"} busy={busy} onClose={() => setDeleting(null)}><Text style={text}>{trash ? `Permanently delete “${deleting.title}” and all its images, models and conversations? This cannot be undone.` : `Move “${deleting.title}” and its images, models and conversations to the Recycle Bin? You can restore them later.`}</Text>{error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}<View style={row}><Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => setDeleting(null)}><Text style={text}>Cancel</Text></Pressable><Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => void remove()}><Text style={{ color: colors.danger }}>{busy ? "Deleting…" : trash ? "Delete permanently" : "Move to Recycle Bin"}</Text></Pressable></View></ArchiveDialog>}
    {renaming && <ArchiveDialog title="Rename creation" busy={busy} onClose={() => setRenaming(null)}><TextInput autoFocus accessibilityLabel="Creation title" value={title} onChangeText={setTitle} onSubmitEditing={() => { if (!busy && title.trim()) void rename(); }} maxLength={80} editable={!busy} style={{ ...text, padding: 12, borderWidth: 1, borderColor: colors.border, borderRadius: 8 }} />{error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}<View style={row}><Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => setRenaming(null)}><Text style={text}>Cancel</Text></Pressable><Pressable accessibilityRole="button" disabled={busy || !title.trim()} style={button} onPress={() => void rename()}><Text style={text}>{busy ? "Saving…" : "Save title"}</Text></Pressable></View></ArchiveDialog>}
    {!selected && <View accessibilityRole="tablist" style={row}>{([['images','Images & labels'],['sketch','Sketches'],['models','3D models']] as const).map(([id,label]) => <Pressable key={id} accessibilityRole="tab" accessibilityState={{ selected: category === id }} onPress={() => changeCategory(id)} style={[button, { borderWidth: 1, borderColor: category === id ? colors.text : colors.border, backgroundColor: category === id ? colors.accentSoft : colors.surface }]}><Text style={{ ...text, fontWeight: category === id ? "700" : "400" }}>{label}</Text></Pressable>)}</View>}
    {!selected && <TextInput accessibilityLabel="Search creations" placeholder="Search your creations…" placeholderTextColor={colors.textDim} value={query} onChangeText={setQuery} maxLength={100} style={{ ...text, padding: 14, minHeight: 48, borderWidth: 1, borderColor: colors.border, borderRadius: 8, backgroundColor: colors.surface }} />}
    <View style={{ display: category === "models" && !selected ? "flex" : "none" }}><ModelGallery enabled={visited || active} active={active && category === "models" && !selected} query={query} trashed={trash} busy={busy}
      onOpen={model => void open(modelSummary(model))} onContinue={onResume ? model => void open(modelSummary(model), true) : undefined} onRename={model => { setRenaming(modelSummary(model)); setTitle(model.title); setError(null); }} onDelete={model => { setDeleting(modelSummary(model)); setError(null); }} onRestore={model => void restore(modelSummary(model))} /></View>
    {selected ? <>
      <Pressable accessibilityRole="button" disabled={busy} style={[button, { alignSelf: "flex-start" }]} onPress={() => { openVersion.current++; setSelected(null); setCreation(null); setNotice(null); }}><Text style={text}>← Back to creations</Text></Pressable>
      <View style={[shared.card, { gap: 18 }]}>
        <View style={[row, { justifyContent: "space-between" }]}><View style={{ flex: 1 }}><Text accessibilityRole="header" style={{ color: colors.text, fontFamily: headingFont, fontSize: 28 }}>{selected.title}</Text><Text style={{ color: colors.textMuted, marginTop: 5 }}>{modeLabel(selected.mode)} · {new Date(selected.updatedAt).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</Text></View>{creation && onResume && <Pressable accessibilityRole="button" disabled={busy} style={[button, shared.primaryButton]} onPress={() => onResume(creation)}><Text style={shared.buttonText}>Continue</Text></Pressable>}</View>
        {busy && <ActivityIndicator color={colors.primary} />}
        {creation && <>
          <View style={{ width: "100%", maxWidth: 600, alignSelf: "center", aspectRatio: 1, backgroundColor: "white", borderRadius: 8, overflow: "hidden" }}><Image source={{ uri: creation.imageBase64 ? `data:image/png;base64,${creation.imageBase64}` : creation.imageUrl }} resizeMode="contain" style={{ width: "100%", height: "100%" }} /><AnatomyOverlay annotations={(creation.anatomyAnnotations || []) as AnatomyAnnotation[]} /></View>
          <ImageDownloadControls imageBase64={creation.imageBase64} annotations={(creation.anatomyAnnotations || []) as AnatomyAnnotation[]} organ={(creation.anatomy as { organ?: string })?.organ} />
          {(creation.glbBase64 || creation.glbUrl) && <ThreeDViewer glbBase64={creation.glbBase64} modelUrl={creation.glbUrl} modelKey={creation.modelKey || creation.id} sizeKb={creation.glbSizeKb} active={active} />}
        </>}
        {selected.versionCount > 1 && <Pressable accessibilityRole="button" accessibilityState={{ expanded: versionsOpen }} style={button} onPress={() => setVersionsOpen(!versionsOpen)}><Text style={text}>{versionsOpen ? "Hide versions" : `Versions (${selected.versionCount})`}</Text></Pressable>}
        {versionsOpen && <View style={{ gap: 8 }}>{hasMoreEvents && <Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => void loadOlderEvents()}><Text style={text}>Load earlier versions</Text></Pressable>}<View style={row}>{versions.map(version => <Pressable key={version.id} accessibilityRole="button" accessibilityState={{ selected: creation?.id === version.id }} disabled={busy} style={[button, creation?.id === version.id && { borderWidth: 1, borderColor: colors.text }]} onPress={() => void chooseVersion(version.id)}><Text style={text}>{version.label}</Text></Pressable>)}</View></View>}
        <Text accessibilityRole="header" style={{ ...text, fontWeight: "600" }}>Conversation</Text>
        {hasMoreEvents && <Pressable accessibilityRole="button" disabled={busy} style={button} onPress={() => void loadOlderEvents()}><Text style={text}>Load earlier messages</Text></Pressable>}
        {!events.some(event => event.kind === "prompt") && creation?.prompt && <Text selectable style={text}>{creation.prompt}</Text>}
        {conversationEvents(events).map(event => <View key={event.id} style={{ padding: 14, borderRadius: 8, backgroundColor: colors.surfaceSoft, gap: 6 }}><Text style={{ color: colors.textDim, fontSize: 12 }}>{new Date(event.createdAt).toLocaleString()}</Text><Text selectable style={text}>{event.data.question || event.data.prompt || event.data.message}</Text>{event.data.answer && <StructuredAnswer answer={event.data.answer} />}<PdfEvidence sources={event.data.sources} grounding={event.data.grounding} />{event.data.error && <Text style={{ color: colors.danger }}>{event.data.error}</Text>}</View>)}
        {selected.source === "local" && (creation?.interactions || []).map(turn => <View key={turn.id} style={{ padding: 14, borderRadius: 8, backgroundColor: colors.surfaceSoft, gap: 6 }}><Text selectable style={{ ...text, fontWeight: "600" }}>{turn.question || "Explore selected region"}</Text><StructuredAnswer answer={turn.answer || turn.error || "Answer pending"} /><PdfEvidence sources={turn.sources} grounding={turn.grounding} /></View>)}
        {!events.some(event => event.kind === "interaction") && !creation?.interactions?.length && <Text style={{ color: colors.textMuted }}>Continue this creation to ask questions or explore its details.</Text>}
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: detailsOpen }} style={button} onPress={() => setDetailsOpen(!detailsOpen)}><Text style={text}>{detailsOpen ? "Hide generation details" : "Generation details"}</Text></Pressable>
        {detailsOpen && <View style={{ gap: 12 }}>
          {creation && <Text selectable style={text}>{creation.enhancedPrompt || creation.prompt}</Text>}
          {creation?.evaluation && <Text style={text}>Visual score {creation.evaluation.visualScore.toFixed(1)} · Educational score {creation.evaluation.pedagogicalScore.toFixed(1)}</Text>}
          {events.filter(event => event.kind === "enhancement").map(event => <View key={event.id} style={{ gap: 8 }}><Text selectable style={text}>{event.data.prompt}</Text>{!creation && onResume && event.data.payload != null && <Pressable accessibilityRole="button" style={button} onPress={() => onResume({ id: event.id, chatId: selected.id, createdAt: event.createdAt, prompt: event.data.originalPrompt || "", enhancedPrompt: event.data.prompt || "", enhancedPayload: event.data.payload, imageBase64: "", mode: selected.mode, speedMode: event.data.speedMode || "pro", anatomy: (event.data.payload as { anatomy_spec?: unknown }).anatomy_spec })}><Text style={text}>Continue from this instruction</Text></Pressable>}</View>)}
        </View>}
      </View>
    </> : <>
      <View style={{ display: category === "models" ? "none" : "flex", gap: 18 }}>
      {loading && !items.length && <View style={[shared.card, { gap: 12 }]}><ActivityIndicator color={colors.primary} /><Text style={{ color: colors.textMuted }}>Loading your creations…</Text><View style={{ height: 100, backgroundColor: colors.surfaceSoft, borderRadius: 8 }} /></View>}
      {loading && !!items.length && <View style={row}><ActivityIndicator size="small" color={colors.primary} /><Text style={{ color: colors.textMuted }}>Updating your creations…</Text></View>}
      {!loading && !visible.length && <View style={[shared.card, { paddingVertical: 40, alignItems: "center", gap: 10 }]}><Icon name="image" color={colors.primary} size={32} /><Text style={{ ...text, fontWeight: "600" }}>{query.trim() ? "No matching creations" : trash ? "Recycle Bin is empty" : "Your ideas belong here"}</Text><Text style={{ color: colors.textMuted, textAlign: "center" }}>{query.trim() ? "Try a different search." : trash ? "Deleted creations stay here until you restore or permanently delete them." : "Create an image or drawing. Its conversation and versions will stay together."}</Text></View>}
      {groups.map(([label, rows]) => <View key={label} style={{ gap: 12 }}><Text accessibilityRole="header" style={{ color: colors.textMuted, fontSize: 13, fontWeight: "600" }}>{label}</Text><View style={{ flexDirection: "row", flexWrap: "wrap", gap: 16 }}>{rows.map(item => <View key={item.id} style={[shared.card, { padding: 14, gap: 12, width: cardWidth ?? "100%", flexGrow: 0, flexShrink: 0 }]}>
        <Pressable accessibilityRole="button" accessibilityLabel={`Open ${item.title}`} disabled={busy || trash} onPress={() => void open(item)} style={{ borderRadius: 8, overflow: "hidden", backgroundColor: colors.surfaceSoft }}>{item.imageUrl ? <HistoryImagePreview uri={item.imageUrl} assetKey={item.imageKey || item.generationId || item.id} annotations={item.annotations as AnatomyAnnotation[]} /> : <View style={{ aspectRatio: 1, alignItems: "center", justifyContent: "center" }}><Icon name={item.mode === "sketch" ? "pencil" : item.mode === "anatomy" ? "heart" : "image"} size={40} color={colors.textDim} /></View>}</Pressable>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}><Text numberOfLines={2} style={{ ...text, height: 44, fontWeight: "600", fontSize: 17, flex: 1 }}>{item.title}</Text>
          <HistoryCardMenu title={item.title} disabled={busy} trashed={trash} onOpen={() => void open(item)} onContinue={onResume ? () => void open(item, true) : undefined}
            onRename={() => { setRenaming(item); setTitle(item.title); setError(null); }} onDelete={() => { setDeleting(item); setError(null); }} onRestore={() => void restore(item)} />
        </View>
        <Text numberOfLines={2} style={{ color: colors.textMuted, height: 36, lineHeight: 18, fontSize: 12 }}>{modeLabel(item.mode)} · {new Date(item.updatedAt).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}{item.hasThreeD ? " · 3D" : ""}</Text>
      </View>)}</View></View>)}
      {hasMore && !loading && !!items.length && <Pressable accessibilityRole="button" style={button} disabled={busy} onPress={() => void refresh(items[items.length - 1])}><Text style={text}>Load older creations</Text></Pressable>}
      </View>
      <View style={{ gap: 10, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.border }}><Text style={{ color: colors.textDim, fontSize: 12 }}>{cloud ? "Saved privately to your account." : "Saved in this browser. Sign in to sync across devices."}</Text>{cloud && !trash && <Pressable accessibilityRole="button" disabled={busy} style={[button, { alignSelf: "flex-start" }]} onPress={() => void action(async () => { const count = await syncLocalHistory(); await refresh(); setNotice(count ? `${count} local creation${count === 1 ? "" : "s"} synced.` : "Your local creations are already synced."); })}><Text style={text}>Sync local creations</Text></Pressable>}</View>
    </>}
  </View>;
}
