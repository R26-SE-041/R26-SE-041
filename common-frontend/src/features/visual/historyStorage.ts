export type HistoryMode = "general" | "anatomy" | "sketch";

export interface SketchStroke {
  points: [number, number][];
  width: number;
  tool: "pen" | "eraser";
}

export interface SketchGenerationMetadata {
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
  id: string;
  createdAt: string;
  prompt: string;
  enhancedPrompt: string;
  imageBase64: string;
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
  id: string;
  createdAt: string;
  mode: "identify" | "explain" | "ask";
  question?: string;
  answer: string;
}

const DATABASE_NAME = "biolearnx-common-visual";
const STORE_NAME = "generation-history";
const DATABASE_VERSION = 1;
const MAX_HISTORY_ITEMS = 50;

async function openDatabase(userId: string): Promise<IDBDatabase | null> {
  if (!userId) throw new Error("Sign in to access visual history.");
  if (typeof indexedDB === "undefined") return Promise.resolve(null);
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(`${DATABASE_NAME}:${userId}`, DATABASE_VERSION);
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

export async function listHistory(userId: string): Promise<GenerationHistoryItem[]> {
  const database = await openDatabase(userId);
  if (!database) return [];
  return new Promise<GenerationHistoryItem[]>((resolve, reject) => {
    const request = database.transaction(STORE_NAME, "readonly").objectStore(STORE_NAME).getAll();
    request.onsuccess = () => resolve(
      (request.result as GenerationHistoryItem[]).sort((a, b) => b.createdAt.localeCompare(a.createdAt)),
    );
    request.onerror = () => reject(request.error);
  }).finally(() => database.close());
}

export async function saveHistoryItem(item: GenerationHistoryItem, userId: string): Promise<void> {
  const database = await openDatabase(userId);
  if (!database) return;
  const transaction = database.transaction(STORE_NAME, "readwrite");
  const store = transaction.objectStore(STORE_NAME);
  store.put(item);
  const allRequest = store.index("createdAt").getAllKeys();
  allRequest.onsuccess = () => {
    const keys = allRequest.result;
    keys.slice(0, Math.max(0, keys.length - MAX_HISTORY_ITEMS)).forEach((key) => store.delete(key));
  };
  await complete(transaction);
  database.close();
}

export async function deleteHistoryItem(id: string, userId: string): Promise<void> {
  const database = await openDatabase(userId);
  if (!database) return;
  const transaction = database.transaction(STORE_NAME, "readwrite");
  transaction.objectStore(STORE_NAME).delete(id);
  await complete(transaction);
  database.close();
}

export async function updateHistoryItem(
  id: string,
  patch: Partial<Omit<GenerationHistoryItem, "id" | "createdAt">>,
  userId: string,
): Promise<void> {
  const database = await openDatabase(userId);
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

export async function appendHistoryInteraction(id: string, interaction: GenerationInteraction, userId: string): Promise<void> {
  const database = await openDatabase(userId);
  if (!database) return;
  const transaction = database.transaction(STORE_NAME, "readwrite");
  const store = transaction.objectStore(STORE_NAME);
  const request = store.get(id);
  request.onsuccess = () => {
    if (request.result) {
      const interactions = Array.isArray(request.result.interactions) ? request.result.interactions : [];
      store.put({ ...request.result, interactions: [...interactions, interaction] });
    }
  };
  await complete(transaction);
  database.close();
}

export async function clearHistory(userId: string): Promise<void> {
  const database = await openDatabase(userId);
  if (!database) return;
  const transaction = database.transaction(STORE_NAME, "readwrite");
  transaction.objectStore(STORE_NAME).clear();
  await complete(transaction);
  database.close();
}
