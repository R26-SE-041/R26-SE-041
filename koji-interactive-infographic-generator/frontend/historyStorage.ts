import { cloudEnabled, studioOwner, studioRequest, getCloudHistory } from "./studioClient";
import type { PdfSource } from "./pdfSources";
export type HistoryMode = "general" | "anatomy" | "sketch";

export interface SketchStroke {
  points: [number, number][];
  width: number;
  tool: "pen" | "eraser";
}

export interface SketchGenerationMetadata {
  subject?: string;
  requested_control_strength?: number;
  control_guidance_end?: number;
  vision_model?: string;
  quality_status?: "passed" | "needs_review" | "unverified";
  attempts?: number;
  recognition?: Record<string, unknown>;
  quality?: Record<string, unknown> | null;
  base_model: string;
  control_model: string;
  seed: number;
  control_strength: number;
  steps: number;
  guidance_scale: number;
  width: number;
  height: number;
}

export interface GenerationHistoryItem {
  deletedAt?: string | null;
  id: string;
  title?: string;
  createdAt: string;
  prompt: string;
  enhancedPrompt: string;
  imageBase64: string;
  imageUrl?: string;
  hasThreeD?: boolean;
  sketchStrength?: number;
  enhancedPayload?: unknown;
  evaluationRetries?: number;
  evaluationWarning?: string | null;
  labelingError?: string | null;
  mode: HistoryMode;
  speedMode: "normal" | "pro" | "promax";
  sketchStrokes?: SketchStroke[];
  sketchMetadata?: SketchGenerationMetadata;
  threeDJob?: { status: "converting" | "done" | "failed"; requestId: string; callId?: string; error?: string };
  /** One user-submitted prompt. Regenerations are versions of the same chat. */
  chatId?: string;
  version?: number;
  interactions?: GenerationInteraction[];
  anatomy?: unknown;
  anatomyAnnotations?: Array<{
    structure_id: string;
    label: string;
    anchor_x: number;
    anchor_y: number;
    label_x: number;
    label_y: number;
    confidence: number;
    verified: boolean;
    user_edited?: boolean;
    source?: "automatic" | "manual";
  }>;
  glbBase64?: string;
  glbSizeKb?: number;
  evaluation?: {
    visualScore: number;
    pedagogicalScore: number;
    feedback: string;
  } | null;
}

export interface GenerationInteraction {
  documentIds?: string[];
  sources?: PdfSource[];
  grounding?: "image" | "pdf" | "no_match";
  id: string;
  createdAt: string;
  mode: "identify" | "explain" | "ask";
  question?: string;
  answer: string;
  selection?: { type: "point" | "box"; coords: number[] };
  structureId?: string | null;
  status?: "queued" | "completed" | "failed";
  error?: string | null;
}

const DATABASE_NAME = "eduvision-local";
const STORE_NAME = "generation-history";
const DATABASE_VERSION = 1;
const MAX_HISTORY_ITEMS = 50;

function openDatabase(owner = studioOwner()): Promise<IDBDatabase | null> {
  if (typeof indexedDB === "undefined") return Promise.resolve(null);
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(owner === "anonymous" ? DATABASE_NAME : DATABASE_NAME + ":" + owner, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: "id" });
        store.createIndex("createdAt", "createdAt");
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function complete(transaction: IDBTransaction): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error);
  });
}

async function localListHistory(): Promise<GenerationHistoryItem[]> {
  const database = await openDatabase();
  if (!database) return [];
  return new Promise<GenerationHistoryItem[]>((resolve, reject) => {
    const request = database.transaction(STORE_NAME, "readonly").objectStore(STORE_NAME).getAll();
    request.onsuccess = () => resolve(
      (request.result as GenerationHistoryItem[]).sort((a, b) => b.createdAt.localeCompare(a.createdAt)),
    );
    request.onerror = () => reject(request.error);
  }).finally(() => database.close());
}

async function localSaveHistoryItem(item: GenerationHistoryItem): Promise<void> {
  const database = await openDatabase();
  if (!database) return;
  const transaction = database.transaction(STORE_NAME, "readwrite");
  const store = transaction.objectStore(STORE_NAME);
  store.put(item);
  const allRequest = store.index("createdAt").getAll();
  allRequest.onsuccess = () => {
    if (!cloudEnabled()) return; // Only the cloud cache is capped; local-only history is retained.
    const cached = (allRequest.result as GenerationHistoryItem[]).filter(item => !item.deletedAt && /^[0-9a-f-]{36}$/i.test(item.id));
    cached.slice(0, Math.max(0, cached.length - MAX_HISTORY_ITEMS)).forEach(item => store.delete(item.id));
  };
  await complete(transaction);
  database.close();
}

async function localUpdateHistoryItem(
  id: string,
  patch: Partial<Omit<GenerationHistoryItem, "id" | "createdAt">>,
): Promise<void> {
  const database = await openDatabase();
  if (!database) return;
  const transaction = database.transaction(STORE_NAME, "readwrite");
  const store = transaction.objectStore(STORE_NAME);
  const request = store.get(id);
  request.onsuccess = () => {
    if (request.result) store.put({ ...request.result, ...patch, id });
  };
  await complete(transaction);
  database.close();
}

async function localAppendHistoryInteraction(id: string, interaction: GenerationInteraction): Promise<void> {
  const database = await openDatabase();
  if (!database) return;
  const transaction = database.transaction(STORE_NAME, "readwrite");
  const store = transaction.objectStore(STORE_NAME);
  const request = store.get(id);
  request.onsuccess = () => {
    if (request.result) {
      const interactions = Array.isArray(request.result.interactions) ? request.result.interactions : [];
      store.put({ ...request.result, interactions: [...interactions.filter((turn: GenerationInteraction) => turn.id !== interaction.id), interaction] });
    }
  };
  await complete(transaction);
  database.close();
}

export async function listHistory(before?: string, trashed = false): Promise<GenerationHistoryItem[]> {
  if (trashed) return (await localListHistory()).filter(item => Boolean(item.deletedAt));
  if (before && cloudEnabled()) return studioRequest<GenerationHistoryItem[]>("/studio/history?before=" + encodeURIComponent(before));
  const local = (await localListHistory()).filter(item => !item.deletedAt);
  if (!cloudEnabled()) return local;
  const remote = await studioRequest<GenerationHistoryItem[]>("/studio/history");
  const cached = new Map(local.map(item => [item.id,item]));
  const byId = new Map(local.filter(item => !/^[0-9a-f-]{36}$/i.test(item.id)).map(item => [item.id,item]));
  for (const item of remote) byId.set(item.id,{...cached.get(item.id),...item,imageBase64:cached.get(item.id)?.imageBase64 || ""});
  return [...byId.values()].sort((a,b)=>b.createdAt.localeCompare(a.createdAt));
}
export async function loadHistoryItem(item: GenerationHistoryItem): Promise<GenerationHistoryItem> {
  if (!cloudEnabled() || !/^[0-9a-f-]{36}$/i.test(item.id)) return item;
  const full = await getCloudHistory(item.id);
  await localSaveHistoryItem(full);
  return full;
}
export const saveHistoryItem = localSaveHistoryItem;
export async function deleteHistoryItem(id: string) {
  if(cloudEnabled() && /^[0-9a-f-]{36}$/i.test(id)) await studioRequest("/studio/history/"+id,{method:"DELETE"});
  const item = (await localListHistory()).find(item => item.id === id);
  if (item) await localConversationAction(item.chatId ?? item.id, "trash");
}
async function persistHistoryPatch(id: string, patch: Partial<Omit<GenerationHistoryItem,"id"|"createdAt">>) {
  if(cloudEnabled() && /^[0-9a-f-]{36}$/i.test(id)) {
    const {anatomyAnnotations,interactions} = patch;
    const allowed={...(anatomyAnnotations!==undefined?{anatomyAnnotations}:{}),...(interactions!==undefined?{interactions}:{})};
    if(Object.keys(allowed).length) await studioRequest("/studio/history/"+id,{method:"PATCH",body:JSON.stringify(allowed)});
  }
  await localUpdateHistoryItem(id,patch);
}
const pendingPatches = new Map<string, Promise<void>>();
export function updateHistoryItem(id: string, patch: Partial<Omit<GenerationHistoryItem, "id" | "createdAt">>): Promise<void> {
  const owner = studioOwner();
  const key = owner + ":" + id;
  const pending = (pendingPatches.get(key) ?? Promise.resolve()).catch(() => undefined).then(() => {
    if (owner !== studioOwner()) throw new Error("Account changed. Please try again.");
    return persistHistoryPatch(id, patch);
  });
  pendingPatches.set(key, pending);
  void pending.finally(() => { if (pendingPatches.get(key) === pending) pendingPatches.delete(key); }).catch(() => undefined);
  return pending;
}
export async function appendHistoryInteraction(id: string, interaction: GenerationInteraction, alreadySaved = false) {
  if(!alreadySaved && cloudEnabled() && /^[0-9a-f-]{36}$/i.test(id)) await studioRequest("/studio/history/"+id+"/interactions",{method:"POST",body:JSON.stringify(interaction)});
  await localAppendHistoryInteraction(id,interaction);
}
export async function deleteConversation(chatId: string) {
  return trashConversation(chatId, true);
}

async function localConversationAction(chatId: string, action: "trash" | "restore" | "purge" | "evict") {
  const database = await openDatabase();
  if (!database) {
    if (cloudEnabled()) return;
    throw new Error("Browser storage is unavailable. Please retry in a supported browser.");
  }
  try {
    const transaction = database.transaction(STORE_NAME, "readwrite");
    const store = transaction.objectStore(STORE_NAME);
    const request = store.getAll();
    const deletedAt = new Date().toISOString();
    let failure: Error | undefined;
    request.onsuccess = () => {
      const versions = (request.result as GenerationHistoryItem[]).filter(item => (item.chatId ?? item.id) === chatId);
      if (action === "purge" && versions.some(item => !item.deletedAt)) {
        failure = new Error("Move this creation to the Recycle Bin before deleting permanently.");
        transaction.abort();
        return;
      }
      for (const item of versions) {
        if (action === "purge" || action === "evict") store.delete(item.id);
        else store.put({ ...item, deletedAt: action === "trash" ? item.deletedAt || deletedAt : null });
      }
    };
    await complete(transaction).catch(error => { throw failure ?? error; });
  } finally { database.close(); }
}

export async function trashConversation(chatId: string, remote: boolean) {
  if (remote) await studioRequest("/studio/chats/" + encodeURIComponent(chatId), { method: "DELETE" });
  await localConversationAction(chatId, "trash");
}

export async function restoreConversation(chatId: string, remote: boolean) {
  if (remote) await studioRequest("/studio/chats/" + encodeURIComponent(chatId) + "/restore", { method: "POST" });
  await localConversationAction(chatId, "restore");
}

export async function purgeConversation(chatId: string, remote: boolean) {
  if (remote) await studioRequest("/studio/chats/" + encodeURIComponent(chatId) + "/permanent", { method: "DELETE" });
  await localConversationAction(chatId, remote ? "evict" : "purge");
}
export async function clearHistory() {
  if(cloudEnabled()) {
    while (true) {
      const items = await studioRequest<GenerationHistoryItem[]>("/studio/history");
      if (!items.length) break;
      for (const item of items) await deleteHistoryItem(item.id);
    }
  }
  for (const item of await localListHistory()) if (!item.deletedAt) await localConversationAction(item.chatId ?? item.id, "trash");
}

export async function syncLocalHistory() {
  if(!cloudEnabled()) throw new Error("Sign in to sync local history");
  const database=await openDatabase("anonymous");
  const legacy=database?await new Promise<GenerationHistoryItem[]>((resolve,reject)=>{
    const request=database.transaction(STORE_NAME,"readonly").objectStore(STORE_NAME).getAll();
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
  }).finally(()=>database.close()):[];
  const items=new Map([...legacy,...await localListHistory()].map(item=>[item.id,item]));
  let count=0;
  for(const item of items.values()) {
    if(item.deletedAt) continue;
    if(/^[0-9a-f-]{36}$/i.test(item.id) || !item.imageBase64) continue;
    const {id,createdAt,imageBase64,glbBase64,imageUrl,...metadata}=item;
    await studioRequest("/studio/import",{method:"POST",body:JSON.stringify({legacy_id:id,created_at:createdAt,metadata,image_base64:imageBase64,glb_base64:glbBase64})});
    count++;
  }
  return count;
}
