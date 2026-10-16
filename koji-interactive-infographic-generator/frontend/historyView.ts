import type { GenerationHistoryItem, HistoryMode } from "./historyStorage";

export type ArchiveFilter = "all" | HistoryMode;
export type ArchivePeriod = "all" | "week" | "month";
export interface CreationSummary {
  modelEvent?: string;
  annotations?: GenerationHistoryItem["anatomyAnnotations"];
  deletedAt?: string | null;
  id: string;
  title: string;
  updatedAt: string;
  mode: HistoryMode;
  imageUrl?: string;
  imageKey?: string;
  generationId?: string;
  versionCount: number;
  hasThreeD?: boolean;
  source: "cloud" | "local";
  versions?: GenerationHistoryItem[];
}
export function creationTitle(prompt: string, mode: HistoryMode): string {
  const text = prompt.replace(/\s+/g, " ").trim();
  if (!text) return mode === "sketch" ? "Untitled drawing" : mode === "anatomy" ? "Anatomy exploration" : "Untitled image";
  return text.length <= 64 ? text : text.slice(0, 61).trimEnd() + "…";
}
export function localSummaries(items: GenerationHistoryItem[]): CreationSummary[] {
  const groups = new Map<string, GenerationHistoryItem[]>();
  for (const item of items) {
    const id = item.chatId || item.id;
    groups.set(id, [...(groups.get(id) || []), item]);
  }
  return [...groups.entries()].map(([id, versions]) => {
    versions.sort((a, b) => a.createdAt.localeCompare(b.createdAt) || (a.version || 1) - (b.version || 1));
    const latest = versions[versions.length - 1];
    return { id, deletedAt: latest.deletedAt, title: latest.title || creationTitle(versions[0].prompt, latest.mode), updatedAt: latest.createdAt,
      mode: latest.mode, generationId: latest.id, imageUrl: latest.imageBase64 ? `data:image/png;base64,${latest.imageBase64}` : latest.imageUrl,
      versionCount: versions.length, annotations: latest.anatomyAnnotations, hasThreeD: versions.some(v => Boolean(v.glbBase64 || v.glbUrl || v.hasThreeD)), source: "local" as const, versions };
  }).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}
export function filterArchive(items: CreationSummary[], query: string, mode: ArchiveFilter, period: ArchivePeriod, now = new Date()): CreationSummary[] {
  const term = query.trim().toLowerCase();
  const earliest = period === "all" ? 0 : now.getTime() - (period === "week" ? 7 : 30) * 86400000;
  return items.filter(item => (mode === "all" || item.mode === mode) && new Date(item.updatedAt).getTime() >= earliest &&
    (!term || [item.title, ...(item.versions || []).flatMap(v => [v.prompt, v.enhancedPrompt])].some(text => text.toLowerCase().includes(term))));
}
export function dateGroup(value: string, now = new Date()): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Earlier";
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  return date >= today ? "Today" : date >= yesterday ? "Yesterday" : "Earlier";
}
export const modeLabel = (mode: HistoryMode) => mode === "sketch" ? "Drawing" : mode === "anatomy" ? "Anatomy" : "Image";

export function conversationEvents<T extends { kind: string; data: { prompt?: string } }>(events: T[]): T[] {
  let lastPrompt: string | null = null;
  return events.filter(event => {
    if (!["prompt", "interaction", "error"].includes(event.kind)) return false;
    if (event.kind !== "prompt") { lastPrompt = null; return true; }
    const prompt = (event.data.prompt || "").replace(/\s+/g, " ").trim();
    if (!prompt || prompt === lastPrompt) return false;
    lastPrompt = prompt;
    return true;
  });
}
