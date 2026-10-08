import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Image, Pressable, Text, TextInput, View } from "react-native";
import { studioRequest, getCloudHistory } from "../studioClient";
import { syncLocalHistory, deleteConversation, GenerationHistoryItem } from "../historyStorage";
import { useAppTheme } from "../theme";
import ThreeDViewer from "./ThreeDViewer";
import SketchCanvas from "./SketchCanvas";
import AnatomyOverlay from "./AnatomyOverlay";
import type { AnatomyAnnotation } from "../App";

interface Chat { id: string; title: string; updated_at: string; event_count: number }
interface Event {
  id: string; kind: string; generationId?: string; createdAt: string;
  imageUrl?: string; hasThreeD?: boolean;
  data: { prompt?: string; question?: string; answer?: string; mode?: string;
    status?: string; error?: string; message?: string; enhancedPrompt?: string;
    speedMode?: "normal" | "pro" | "promax"; jobId?: string; originalPrompt?: string; payload?: unknown; selection?: { type: string; coords: number[] } };
}
interface Props { onResume?: (item: GenerationHistoryItem) => void }

export default function ConversationHistory({ onResume }: Props) {
  const { colors } = useAppTheme();
  const [chats, setChats] = useState<Chat[]>([]);
  const [chat, setChat] = useState<Chat | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [creation, setCreation] = useState<GenerationHistoryItem | null>(null);
  const [query, setQuery] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasOlder, setHasOlder] = useState(false);
  const [hasOlderChats, setHasOlderChats] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const box = { borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 16, gap: 12 };
  const action = { paddingVertical: 10, paddingHorizontal: 12, borderRadius: 10, backgroundColor: colors.surfaceSoft };

  const refreshVersion = useRef(0);
  const refresh = useCallback(async () => {
    const version = ++refreshVersion.current;
    try {
      const rows = await studioRequest<Chat[]>("/studio/chats?query=" + encodeURIComponent(query.trim()));
      if (version !== refreshVersion.current) return;
      setChats(rows); setHasOlderChats(rows.length === 50); setError(null);
    } catch (e) { if (version === refreshVersion.current) setError(e instanceof Error ? e.message : "Unable to load conversations"); }
  }, [query]);
  useEffect(() => { const timer = setTimeout(() => void refresh(), 300); return () => { clearTimeout(timer); refreshVersion.current++; }; }, [refresh]);

  const openChat = async (item: Chat, older = false) => {
    setBusy(true); setError(null);
    try {
      const first = events[0];
      const cursor = older && first ? "?before=" + encodeURIComponent(first.createdAt) + "&before_id=" + encodeURIComponent(first.id) : "";
      const rows = await studioRequest<Event[]>("/studio/chats/" + encodeURIComponent(item.id) + "/events" + cursor);
      setEvents(previous => [...new Map([...(older ? previous : []), ...rows].map(event => [event.id, event])).values()]
        .sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id)));
      setHasOlder(rows.length === 50);
      if (!older) { setCreation(null); setTitle(item.title); setConfirmDelete(false); }
      setChat(item);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to open conversation"); }
    finally { setBusy(false); }
  };
  const openCreation = async (id: string, modelEvent?: string) => {
    setBusy(true); setError(null);
    try { setCreation(await getCloudHistory(id, modelEvent)); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to open saved creation"); }
    finally { setBusy(false); }
  };
  const rename = async () => {
    if (!chat || !title.trim()) return;
    setBusy(true);
    try {
      await studioRequest("/studio/chats/" + encodeURIComponent(chat.id), { method: "PATCH", body: JSON.stringify({ title: title.trim() }) });
      setChat({ ...chat, title: title.trim() }); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to rename conversation"); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    if (!chat) return;
    setBusy(true);
    try {
      await deleteConversation(chat.id);
      setChat(null); setEvents([]); setCreation(null); setConfirmDelete(false); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to delete conversation"); }
    finally { setBusy(false); }
  };
  const loadOlderChats = async () => {
    const last = chats[chats.length - 1]; if (!last) return;
    setBusy(true);
    try {
      const older = await studioRequest<Chat[]>("/studio/chats?before=" + encodeURIComponent(last.updated_at) + "&before_id=" + encodeURIComponent(last.id) + "&query=" + encodeURIComponent(query.trim()));
      setChats(previous => [...new Map([...previous, ...older].map(item => [item.id, item])).values()]);
      setHasOlderChats(older.length === 50);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load older conversations"); }
    finally { setBusy(false); }
  };
  const sync = async () => {
    setBusy(true);
    try { await syncLocalHistory(); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to sync local history"); }
    finally { setBusy(false); }
  };

  return <View style={{ gap: 18 }}>
    <Text style={{ color: colors.text, fontSize: 30, fontWeight: "800" }}>Your conversations</Text>
    <Text style={{ color: colors.textMuted }}>Prompts, enhanced instructions, image versions, questions and 3D models stay together.</Text>
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      <Pressable accessibilityRole="button" disabled={busy} style={action} onPress={() => void refresh()}><Text style={{ color: colors.primaryBright }}>Refresh conversations</Text></Pressable>
      <Pressable accessibilityRole="button" disabled={busy} style={action} onPress={() => void sync()}><Text style={{ color: colors.primaryBright }}>Sync local creations</Text></Pressable>
    </View>
    {error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}
    {busy && <ActivityIndicator color={colors.primary} />}
    <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "flex-start", gap: 18 }}>
      <View style={[box, { flexBasis: 260, flexGrow: 1, maxWidth: 360 }]}>
        <TextInput accessibilityLabel="Search conversations" placeholder="Search conversations" placeholderTextColor={colors.textDim} value={query} onChangeText={setQuery} maxLength={100} style={{ color: colors.text, padding: 10, borderColor: colors.border, borderWidth: 1, borderRadius: 10 }} />
        {!chats.length && <Text style={{ color: colors.textMuted }}>Your next prompt will start a saved conversation.</Text>}
        {chats.map(item =>
          <Pressable accessibilityRole="button" key={item.id} disabled={busy} onPress={() => void openChat(item)} style={[action, { borderWidth: 1, borderColor: chat?.id === item.id ? colors.primaryBright : colors.border }]}>
            <Text style={{ color: colors.text, fontWeight: "700" }}>{item.title}</Text>
            <Text style={{ color: colors.textMuted, fontSize: 11, marginTop: 5 }}>{new Date(item.updated_at).toLocaleString()} · {item.event_count} entries</Text>
          </Pressable>)}
        {hasOlderChats && <Pressable accessibilityRole="button" disabled={busy} onPress={() => void loadOlderChats()}><Text style={{ color: colors.primaryBright }}>Load older conversations</Text></Pressable>}
      </View>
      <View style={[box, { flexBasis: 420, flexGrow: 3, minWidth: 260 }]}>
        {!chat ? <Text style={{ color: colors.textMuted }}>Choose a conversation to see its complete learning workflow.</Text> : <>
          <Text style={{ color: colors.text, fontSize: 22, fontWeight: "700" }}>{chat.title}</Text>
          <TextInput accessibilityLabel="Conversation title" value={title} onChangeText={setTitle} maxLength={80} style={{ color: colors.text, padding: 10, borderWidth: 1, borderColor: colors.border, borderRadius: 10 }} />
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
            <Pressable accessibilityRole="button" disabled={busy} style={action} onPress={() => void rename()}><Text style={{ color: colors.primaryBright }}>Save title</Text></Pressable>
            <Pressable accessibilityRole="button" disabled={busy} style={action} onPress={() => void openChat(chat)}><Text style={{ color: colors.primaryBright }}>Refresh conversation</Text></Pressable>
            <Pressable accessibilityRole="button" disabled={busy} style={action} onPress={() => setConfirmDelete(true)}><Text style={{ color: colors.danger }}>Delete conversation</Text></Pressable>
          </View>
          {confirmDelete && <View style={{ gap: 10 }}>
            <Text style={{ color: colors.danger }}>Delete this conversation and its saved images and 3D models? This cannot be undone.</Text>
            <View style={{ flexDirection: "row", gap: 16 }}>
              <Pressable accessibilityRole="button" disabled={busy} onPress={() => void remove()}><Text style={{ color: colors.danger }}>Confirm deletion</Text></Pressable>
              <Pressable accessibilityRole="button" onPress={() => setConfirmDelete(false)}><Text style={{ color: colors.text }}>Cancel</Text></Pressable>
            </View>
          </View>}
          {hasOlder && <Pressable accessibilityRole="button" disabled={busy} onPress={() => void openChat(chat, true)}><Text style={{ color: colors.primaryBright }}>Load earlier messages</Text></Pressable>}
          {events.map(event => <View key={event.id} style={{ gap: 8, paddingVertical: 14, borderBottomWidth: 1, borderColor: colors.border }}>
            <Text style={{ color: colors.textDim, fontSize: 11 }}>{new Date(event.createdAt).toLocaleString()}</Text>
            {event.kind === "prompt" && <>
              <Text style={{ color: colors.primaryBright, fontWeight: "700" }}>You · Original prompt</Text>
              <Text selectable style={{ color: colors.text, lineHeight: 22 }}>{event.data.prompt || "Drawing without additional instruction"}</Text>
            </>}
            {event.kind === "enhancement" && <>
              <Text style={{ color: colors.success, fontWeight: "700" }}>Assistant · Enhanced prompt</Text>
              <Text selectable style={{ color: colors.text, lineHeight: 22 }}>{event.data.prompt}</Text>
              {onResume && event.data.payload && <Pressable accessibilityRole="button" disabled={busy} onPress={() => onResume({ id: event.id, chatId: chat.id, createdAt: event.createdAt, prompt: event.data.originalPrompt || "", enhancedPrompt: event.data.prompt || "", enhancedPayload: event.data.payload, imageBase64: "", mode: event.data.mode === "anatomy" ? "anatomy" : "general", speedMode: event.data.speedMode || "pro", anatomy: (event.data.payload as { anatomy_spec?: unknown }).anatomy_spec })}><Text style={{ color: colors.primaryBright }}>Continue from enhanced prompt</Text></Pressable>}
            </>}
            {event.kind === "interaction" && <>
              <Text style={{ color: colors.primaryBright, fontWeight: "700" }}>You: {event.data.question}</Text>
              {event.data.selection && <Text style={{ color: colors.textMuted, fontSize: 11 }}>{event.data.selection.type === "box" ? "Image region" : "Image point"} · {event.data.selection.coords.map(value => value.toFixed(3)).join(", ")}</Text>}
              {event.generationId && <Pressable accessibilityRole="button" disabled={busy} onPress={() => void openCreation(event.generationId!)}><Text style={{ color: colors.primaryBright }}>Show source image</Text></Pressable>}
              <Text selectable style={{ color: event.data.status === "failed" ? colors.danger : colors.text, lineHeight: 22 }}>{event.data.status === "failed" ? event.data.error : event.data.answer || "Answer pending. Refresh this conversation to check progress."}</Text>
            </>}
            {event.kind === "image" && <>
              <Text style={{ color: colors.success, fontWeight: "700" }}>Assistant · Generated 2D image</Text>
              {event.imageUrl && <Image source={{ uri: event.imageUrl }} resizeMode="contain" style={{ width: "100%", aspectRatio: 1, maxHeight: 360, backgroundColor: "white", borderRadius: 12 }} />}
              <Text selectable style={{ color: colors.textMuted }}>Before: {event.data.prompt || "Drawing only"}</Text>
              <Text selectable style={{ color: colors.text }}>After: {event.data.enhancedPrompt}</Text>
              {event.generationId && <Pressable accessibilityRole="button" disabled={busy} style={action} onPress={() => void openCreation(event.generationId!)}><Text style={{ color: colors.primaryBright }}>Open image, labels and saved Q&A{event.hasThreeD ? " + 3D" : ""}</Text></Pressable>}
            </>}
            {event.kind === "threed" && <>
              <Text style={{ color: colors.success, fontWeight: "700" }}>Assistant · 3D model created from the saved 2D image</Text>
              {event.generationId && <Pressable accessibilityRole="button" disabled={busy} onPress={() => void openCreation(event.generationId!, event.id)}><Text style={{ color: colors.primaryBright }}>Open 3D model</Text></Pressable>}
            </>}
            {event.kind === "labels" && <Text style={{ color: colors.text }}>Saved label edits</Text>}
            {event.kind === "error" && <Text style={{ color: colors.danger }}>{event.data.message}</Text>}
          </View>)}
          {creation && <View style={[box, { backgroundColor: colors.surfaceSoft }]}>
            <Text style={{ color: colors.text, fontSize: 20, fontWeight: "700" }}>Saved creation · Version {creation.version ?? 1}</Text>
            {creation.sketchStrokes && <SketchCanvas strokes={creation.sketchStrokes} onChange={() => undefined} disabled previewOnly />}
            <View style={{ width: "100%", aspectRatio: 1, backgroundColor: "white" }}>
              <Image source={{ uri: "data:image/png;base64," + creation.imageBase64 }} resizeMode="contain" style={{ position: "absolute", width: "100%", height: "100%" }} />
              <AnatomyOverlay annotations={(creation.anatomyAnnotations ?? []) as AnatomyAnnotation[]} />
            </View>
            <Text selectable style={{ color: colors.primaryBright }}>Original: {creation.prompt || "Drawing only"}</Text>
            <Text selectable style={{ color: colors.text }}>Enhanced / generation prompt: {creation.enhancedPrompt}</Text>
            {(creation.interactions ?? []).map(turn => <View key={turn.id} style={{ gap: 6 }}>
              <Text style={{ color: colors.primaryBright, fontWeight: "700" }}>You: {turn.question || turn.mode}</Text>
              <Text selectable style={{ color: colors.text }}>{turn.answer || turn.error || "Pending answer"}</Text>
            </View>)}
            {creation.glbBase64 && <ThreeDViewer glbBase64={creation.glbBase64} sizeKb={creation.glbSizeKb} />}
            {onResume && <Pressable accessibilityRole="button" disabled={busy} style={action} onPress={() => onResume(creation)}><Text style={{ color: colors.primaryBright }}>Continue this conversation</Text></Pressable>}
          </View>}
        </>}
      </View>
    </View>
  </View>;
}
