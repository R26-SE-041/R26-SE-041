export type HistoryMode = "general" | "anatomy";

export interface GenerationHistoryItem {
  id: string;
  createdAt: string;
  prompt: string;
  enhancedPrompt: string;
  imageBase64: string;
  mode: HistoryMode;
  speedMode: "normal" | "pro" | "promax";
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

const DATABASE_NAME = "eduvision-local";
const STORE_NAME = "generation-history";
const DATABASE_VERSION = 1;
const MAX_HISTORY_ITEMS = 50;

function openDatabase(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === "undefined") return Promise.resolve(null);
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
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

export async function listHistory(): Promise<GenerationHistoryItem[]> {
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

export async function saveHistoryItem(item: GenerationHistoryItem): Promise<void> {
  const database = await openDatabase();
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

export async function deleteHistoryItem(id: string): Promise<void> {
  const database = await openDatabase();
  if (!database) return;
  const transaction = database.transaction(STORE_NAME, "readwrite");
  transaction.objectStore(STORE_NAME).delete(id);
  await complete(transaction);
  database.close();
}

export async function updateHistoryItem(
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

export async function appendHistoryInteraction(id: string, interaction: GenerationInteraction): Promise<void> {
  const database = await openDatabase();
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

export async function clearHistory(): Promise<void> {
  const database = await openDatabase();
  if (!database) return;
  const transaction = database.transaction(STORE_NAME, "readwrite");
  transaction.objectStore(STORE_NAME).clear();
  await complete(transaction);
  database.close();
}
