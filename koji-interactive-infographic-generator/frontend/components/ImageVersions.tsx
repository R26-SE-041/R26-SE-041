import React, { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Pressable, Text, View } from "react-native";
import { cloudEnabled, getCloudHistory, studioRequest } from "../studioClient";
import { listHistory, loadHistoryItem, type GenerationHistoryItem } from "../historyStorage";
import { getHistoryRevision, subscribeHistory } from "../historyActivity";
import { useAppTheme } from "../theme";

interface Version { id: string; createdAt: string; number?: number; item?: GenerationHistoryItem }
interface Event { id: string; kind: string; generationId?: string; createdAt: string; data: { version?: number } }
export default function ImageVersions({ chatId, currentId, disabled, onSelect }: {
  chatId: string | null; currentId: string | null; disabled: boolean; onSelect: (item: GenerationHistoryItem) => void;
}) {
  const { colors } = useAppTheme();
  const revision = useSyncExternalStore(subscribeHistory, getHistoryRevision, getHistoryRevision);
  const [versions, setVersions] = useState<Version[]>([]);
  const [cursor, setCursor] = useState<Event | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(0);
  useEffect(() => {
    const serial = ++request.current;
    setError(""); setVersions([]); setCursor(null);
    if (!chatId) return;
    void (async () => {
      try {
        if (cloudEnabled()) {
          const events = await studioRequest<Event[]>(`/studio/chats/${encodeURIComponent(chatId)}/events`);
          if (serial !== request.current) return;
          setVersions(events.filter(event => event.kind === "image" && event.generationId).map(event => ({ id: event.generationId!, createdAt: event.createdAt, number: event.data.version })));
          setCursor(events.length === 50 ? events.at(-1)! : null);
        } else {
          const items = await listHistory();
          if (serial !== request.current) return;
          setVersions(items.filter(item => (item.chatId ?? item.id) === chatId).map(item => ({ id: item.id, createdAt: item.createdAt, number: item.version, item })));
        }
      } catch { if (serial === request.current) setError("Versions unavailable. Your saved images are still in History."); }
    })();
    return () => { request.current++; };
  }, [chatId, currentId, revision]);
  const earlier = async () => {
    if (!cursor || !chatId || busy) return;
    const serial = request.current;
    setBusy(true);
    try {
      const events = await studioRequest<Event[]>(`/studio/chats/${encodeURIComponent(chatId)}/events?before=${encodeURIComponent(cursor.createdAt)}&before_id=${encodeURIComponent(cursor.id)}`);
      if (serial !== request.current) return;
      setVersions(current => [...new Map([...current, ...events.filter(event => event.kind === "image" && event.generationId).map(event => ({ id: event.generationId!, createdAt: event.createdAt, number: event.data.version }))].map(version => [version.id, version])).values()]);
      setCursor(events.length === 50 ? events.at(-1)! : null);
    } catch { setError("Could not load earlier versions. Please retry."); }
    finally { setBusy(false); }
  };
  if (!chatId || (!currentId && !versions.length)) return null;
  return <View style={{ gap: 10 }}>
    <Text style={{ color: colors.textMuted, fontSize: 12 }}>SAVED VERSIONS · edits and regenerations stay in this chat</Text>
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
      {versions.map(version => <Pressable key={version.id} accessibilityRole="button" aria-pressed={currentId === version.id} disabled={disabled || busy}
        onPress={async () => {
          const serial = request.current; setBusy(true); setError("");
          try { const item = version.item ? await loadHistoryItem(version.item) : await getCloudHistory(version.id); if (serial === request.current) onSelect(item); }
          catch { setError("Could not open this version. Please retry."); }
          finally { setBusy(false); }
        }} style={{ minHeight: 44, padding: 12, borderRadius: 8, borderWidth: 1, borderColor: currentId === version.id ? colors.text : colors.border, backgroundColor: currentId === version.id ? colors.surfaceSoft : colors.surface }}>
        <Text style={{ color: colors.text, fontSize: 12 }}>{version.number ? `Version ${version.number}` : new Date(version.createdAt).toLocaleString()}{currentId === version.id ? " · current" : ""}</Text>
      </Pressable>)}
      {cursor && <Pressable accessibilityRole="button" disabled={disabled || busy} onPress={() => void earlier()} style={{ padding: 12, minHeight: 44 }}><Text style={{ color: colors.text }}>Earlier versions</Text></Pressable>}
    </View>
    {error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}
  </View>;
}
