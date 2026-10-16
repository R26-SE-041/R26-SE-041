// Invalidate the mounted archive after writes without duplicating image/model data.
let revision = 0;
const listeners = new Set<() => void>();

export const getHistoryRevision = () => revision;
export function subscribeHistory(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
export function markHistoryChanged(): void {
  revision++;
  listeners.forEach(listener => listener());
}

export const HISTORY_FRESH_MS = 60_000;
export function isHistoryFresh(
  loaded: { key: string; at: number; revision: number } | null,
  key: string,
  currentRevision: number,
  now = Date.now(),
): boolean {
  return loaded !== null && loaded.key === key && loaded.revision === currentRevision && now - loaded.at < HISTORY_FRESH_MS;
}
