import { STUDIO_API_URL } from "./config";
import type { GenerationHistoryItem } from "./historyStorage";
import { SessionConnectionError } from "./sessionTokens";
import { getHistoryRevision, markHistoryChanged } from "./historyActivity";
import { assetBase64, cachedAsset } from "./assetCache";
let currentToken: string | undefined;
let currentOwner = "anonymous";
type TokenProvider = (refresh?: boolean) => Promise<string | undefined>;
let tokenProvider: TokenProvider | undefined;
function tokenOwner(token?: string) {
  try { return token ? JSON.parse(atob(token.split(".")[1].replace(/-/g,"+").replace(/_/g,"/"))).sub : "anonymous"; }
  catch { return "anonymous"; }
}
export function configureStudio(token?: string, provider?: TokenProvider) {
  if (currentOwner !== tokenOwner(token)) historyCache.clear();
  currentToken = token;
  currentOwner = tokenOwner(token);
  tokenProvider = provider;
}
export function studioOwner() { return currentOwner; }
export function cloudEnabled() { return Boolean(STUDIO_API_URL && currentToken); }
export class StudioRequestError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
async function authenticatedFetch(path: string, init: RequestInit, origin: string): Promise<Response> {
  const owner = studioOwner();
  const provider = tokenProvider;
  const ensureOwner = () => { if (owner !== studioOwner()) throw new Error("Account changed. Please try again."); };
  async function send(refresh = false) {
    let token: string | undefined;
    try { token = provider ? await provider(refresh) : currentToken; }
    catch (error) {
      if (error instanceof SessionConnectionError) throw new StudioRequestError(error.message, 0);
      throw error;
    }
    ensureOwner();
    if (tokenOwner(token) !== owner) throw new Error("Account changed. Please try again.");
    try {
      const response = await fetch(origin.replace(/\/$/, "") + path, {
        signal: typeof AbortSignal !== "undefined" && AbortSignal.timeout ? AbortSignal.timeout(45_000) : undefined,
        ...init, headers: { "Content-Type":"application/json", ...init.headers, ...(token ? { Authorization:"Bearer "+token } : {}) },
      });
      ensureOwner();
      return response;
    } catch (failure) {
      if (failure && typeof failure === "object" && "message" in failure && typeof failure.message === "string" && /fetch|network|load failed|timeout|timed out|aborted/i.test(failure.message)) throw new StudioRequestError("Unable to reach your cloud workspace. Check your connection and retry.", 0);
      throw failure;
    }
  }
  let response = await send();
  // Only an authentication rejection is replayed, once, with the same body and
  // request ID. An accepted generation is never submitted again by polling.
  if (response.status === 401 && provider) response = await send(true);
  return response;
}
export async function studioRequest<T>(path: string, init: RequestInit = {}, origin = STUDIO_API_URL): Promise<T> {
  const owner = studioOwner();
  const response = await authenticatedFetch(path, init, origin);
  const contentType = response.headers?.get("content-type");
  if (contentType && !contentType.includes("application/json")) throw new StudioRequestError("Cloud service returned an unexpected response. Please retry.", response.ok ? 502 : response.status);
  const data = await response.json().catch(() => ({}));
  if (owner !== studioOwner()) throw new Error("Account changed. Please try again.");
  if (!response.ok) throw new StudioRequestError(typeof data.detail === "string" ? data.detail : data.error || "Studio request failed ("+response.status+")", response.status);
  if (init.method && !["GET", "HEAD"].includes(init.method.toUpperCase()) && /^\/studio\/(chats|history|jobs|import)(?:[/?]|$)/.test(path)) markHistoryChanged();
  return data as T;
}
export interface StudioJob { id: string; kind: string; status: "queued" | "running" | "completed" | "failed"; stage: string; generation_id?: string; result?: { history_id?: string; chat_id?: string; enhancement?: Record<string, any>; label_job_id?: string | null; interaction_id?: string }; error?: string; created_at: string; updated_at?: string }
export function requestId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => { const r=Math.random()*16|0; return (c==="x"?r:(r&3)|8).toString(16); });
}
export async function waitJob(id: string, onProgress?: (stage: string) => void): Promise<StudioJob> {
  const started = Date.now();
  const owner = studioOwner();
  let maxWaitMs = 60*60*1000;
  while (Date.now()-started < maxWaitMs) {
    if (owner !== studioOwner()) throw new Error("Account changed. Please try again.");
    let job: StudioJob;
    try { job = await studioRequest<StudioJob>("/studio/jobs/"+encodeURIComponent(id)); }
    catch (error) {
      if (!(error instanceof StudioRequestError) || ![0,408,429,500,502,503,504].includes(error.status)) throw error;
      onProgress?.("Reconnecting — your saved task continues in the background");
      await new Promise(resolve => setTimeout(resolve, 5000));
      continue;
    }
    if (job.kind === "threed") maxWaitMs = 75*60*1000;
    onProgress?.(job.stage);
    if (job.status === "completed") return job;
    if (job.status === "failed") throw new Error(job.error || "Job failed. Retry from Jobs.");
    await new Promise(resolve=>setTimeout(resolve,2500));
  }
  throw new Error("The job is still available in Jobs. Open it there to retrieve its result.");
}
export async function runJob(payload: Record<string,unknown>, onProgress?: (stage: string) => void) {
  const job = await studioRequest<StudioJob>("/studio/jobs", { method:"POST",body:JSON.stringify({ request_id:requestId(),...payload }) });
  return waitJob(job.id,onProgress);
}
const historyCache = new Map<string, { at: number; revision: number; promise: Promise<GenerationHistoryItem> }>();
export function getCloudHistory(id: string, modelEvent?: string): Promise<GenerationHistoryItem> {
  const owner = studioOwner(), revision = getHistoryRevision();
  const key = `${owner}:${id}:${modelEvent || ""}`;
  const cached = historyCache.get(key);
  if (cached && cached.revision === revision && Date.now() - cached.at < 60_000) return cached.promise;
  const promise = (async () => {
    const query = new URLSearchParams({ asset_mode: "urls" });
    if (modelEvent) query.set("model_event", modelEvent);
    const item = await studioRequest<GenerationHistoryItem>(`/studio/history/${encodeURIComponent(id)}?${query}`);
    if (!item.imageBase64 && item.imageUrl) item.imageBase64 = assetBase64(await cachedAsset(owner, item.imageKey || id, item.imageUrl));
    if (owner !== studioOwner()) throw new Error("Account changed. Please try again.");
    return item;
  })();
  const entry = { at: Date.now(), revision, promise };
  historyCache.delete(key); historyCache.set(key, entry);
  while (historyCache.size > 12) historyCache.delete(historyCache.keys().next().value!);
  void promise.catch(() => { if (historyCache.get(key) === entry) historyCache.delete(key); });
  return promise;
}
export interface SavedModel { id: string; generationId: string; chatId: string; title: string; createdAt: string; mode?: string; modelKey: string; modelUrl?: string; glbBase64?: string }
export const getCloudModel = (id: string, modelEvent?: string) => studioRequest<{ id: string; modelUrl: string; modelKey: string; sizeKb?: number }>(`/studio/history/${encodeURIComponent(id)}/model${modelEvent ? "?model_event="+encodeURIComponent(modelEvent) : ""}`);
export async function appendChatEvent(chatId: string, kind: "prompt" | "enhancement", data: Record<string, unknown>) {
  if (!cloudEnabled()) return;
  const id = requestId();
  await studioRequest("/studio/chats/" + encodeURIComponent(chatId) + "/events", { method: "POST", body: JSON.stringify({ id, kind, data }) });
  return id;
}
export async function modelRequest(service: "prompt" | "interactive", directUrl: string, path: string, init: RequestInit) {
  if (!cloudEnabled()) return fetch(directUrl+path,init);
  return authenticatedFetch("/agents/"+service+path,init,STUDIO_API_URL);
}
