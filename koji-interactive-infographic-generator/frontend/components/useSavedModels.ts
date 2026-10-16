import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { cloudEnabled, SavedModel, studioOwner, studioRequest } from "../studioClient";
import { getHistoryRevision, HISTORY_FRESH_MS, subscribeHistory } from "../historyActivity";
import { listHistory } from "../historyStorage";

export interface ModelGalleryProps {
  enabled: boolean; active: boolean; query: string; trashed: boolean;
  onOpen: (model: SavedModel) => void;
  onRename: (model: SavedModel) => void;
  onDelete: (model: SavedModel) => void;
  onRestore: (model: SavedModel) => void;
}
export function useSavedModels({ enabled, active, trashed }: ModelGalleryProps) {
  const [models, setModels] = useState<SavedModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const revision = useSyncExternalStore(subscribeHistory, getHistoryRevision, getHistoryRevision);
  const loaded = useRef({ at: 0, revision: -1, trashed });
  const request = useRef(0);
  const refresh = useCallback(async () => {
    const version = ++request.current, owner = studioOwner(), currentRevision = getHistoryRevision();
    setLoading(true); setError(null);
    try {
      let items: SavedModel[] = [];
      if (cloudEnabled()) {
        let cursor: SavedModel | undefined;
        do {
          const params = new URLSearchParams({ trashed: String(trashed) });
          if (cursor) { params.set("before", cursor.createdAt); params.set("before_id", cursor.id); }
          const page = await studioRequest<SavedModel[]>(`/studio/models?${params}`);
          if (version !== request.current || owner !== studioOwner()) return;
          items = [...items, ...page];
          cursor = page.length === 50 ? page[page.length - 1] : undefined;
        } while (cursor);
      } else {
        items = (await listHistory(undefined, trashed)).filter(item => item.glbBase64 || item.glbUrl).map(item => ({
          id: item.id, generationId: item.id, chatId: item.chatId || item.id,
          title: item.title || item.prompt || "3D model", createdAt: item.createdAt, mode: item.mode,
          modelKey: item.modelKey || item.id, modelUrl: item.glbUrl, glbBase64: item.glbBase64,
        }));
      }
      if (version !== request.current) return;
      setModels(items); loaded.current = { at: Date.now(), revision: currentRevision, trashed };
    } catch (failure) { if (version === request.current) setError(failure instanceof Error ? failure.message : "Unable to load models."); }
    finally { if (version === request.current) setLoading(false); }
  }, [trashed]);
  useEffect(() => {
    if (!enabled) return;
    if (loaded.current.revision !== revision || loaded.current.trashed !== trashed || (active && Date.now() - loaded.current.at >= HISTORY_FRESH_MS)) void refresh();
  }, [enabled, active, revision, trashed, refresh]);
  useEffect(() => () => { request.current++; }, []);
  return { models, loading, error, refresh };
}
