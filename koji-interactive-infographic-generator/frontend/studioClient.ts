import { STUDIO_API_URL } from "./config";
import type { GenerationHistoryItem } from "./historyStorage";
let currentToken: string | undefined;
let currentOwner = "anonymous";
export function configureStudio(token?: string) {
  currentToken = token;
  try { currentOwner = token ? JSON.parse(atob(token.split(".")[1].replace(/-/g,"+").replace(/_/g,"/"))).sub : "anonymous"; }
  catch { currentOwner = "anonymous"; }
}
export function studioOwner() { return currentOwner; }
export function cloudEnabled() { return Boolean(STUDIO_API_URL && currentToken); }
export async function studioRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const owner = studioOwner();
  let response: Response;
  try { response = await fetch(STUDIO_API_URL.replace(/\/$/, "") + path, {
    ...init, headers: { "Content-Type":"application/json", ...(currentToken ? { Authorization:"Bearer "+currentToken } : {}), ...init.headers },
  }); } catch (failure) {
    if (failure && typeof failure === "object" && "message" in failure && typeof failure.message === "string" && /fetch|network|load failed/i.test(failure.message)) throw new Error("Unable to reach your cloud workspace. Check your connection and retry.");
    throw failure;
  }
  const contentType = response.headers?.get("content-type");
  if (contentType && !contentType.includes("application/json")) throw new Error("Cloud service returned an unexpected response. Please retry.");
  const data = await response.json().catch(() => ({}));
  if (owner !== studioOwner()) throw new Error("Account changed. Please try again.");
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : data.error || "Studio request failed ("+response.status+")");
  return data as T;
}
export interface StudioJob { id: string; kind: string; status: "queued" | "running" | "completed" | "failed"; stage: string; generation_id?: string; result?: { history_id?: string; chat_id?: string; enhancement?: Record<string, any>; label_job_id?: string | null; interaction_id?: string }; error?: string; created_at: string }
export function requestId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => { const r=Math.random()*16|0; return (c==="x"?r:(r&3)|8).toString(16); });
}
export async function waitJob(id: string, onProgress?: (stage: string) => void): Promise<StudioJob> {
  const started = Date.now();
  while (Date.now()-started < 60*60*1000) {
    const job = await studioRequest<StudioJob>("/studio/jobs/"+encodeURIComponent(id));
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
export const getCloudHistory = (id: string, modelEvent?: string) => studioRequest<GenerationHistoryItem>("/studio/history/"+encodeURIComponent(id)+(modelEvent ? "?model_event="+encodeURIComponent(modelEvent) : ""));
export async function appendChatEvent(chatId: string, kind: "prompt" | "enhancement", data: Record<string, unknown>) {
  if (!cloudEnabled()) return;
  const id = requestId();
  await studioRequest("/studio/chats/" + encodeURIComponent(chatId) + "/events", { method: "POST", body: JSON.stringify({ id, kind, data }) });
  return id;
}
export async function modelRequest(service: "prompt" | "interactive", directUrl: string, path: string, init: RequestInit) {
  if (!cloudEnabled()) return fetch(directUrl+path,init);
  return fetch(STUDIO_API_URL.replace(/\/$/, "")+"/agents/"+service+path,{...init,headers:{...init.headers,Authorization:"Bearer "+currentToken}});
}
