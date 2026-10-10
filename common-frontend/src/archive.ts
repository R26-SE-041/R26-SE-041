import AsyncStorage from '@react-native-async-storage/async-storage';
export interface ArchiveItem { id: string; createdAt: string; title: string }
const key = (module: string, userId: string) => `biolearnx-common:${module}:${userId}`;
export async function readSmall<T>(module: string, userId: string): Promise<T | null> {
  const raw = await AsyncStorage.getItem(key(module, userId));
  if (!raw) return null;
  try { return JSON.parse(raw) as T; } catch { throw new Error('Saved workspace data could not be read.'); }
}
export async function writeSmall<T>(module: string, userId: string, value: T) { await AsyncStorage.setItem(key(module, userId), JSON.stringify(value)); }
async function database(module: string, userId: string) {
  if (typeof indexedDB === 'undefined') throw new Error('Local archives require a browser with IndexedDB enabled.');
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(key(module, userId), 1);
    request.onupgradeneeded = () => request.result.createObjectStore('items', { keyPath: 'id' });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('Local archive storage is unavailable.'));
    request.onblocked = () => reject(new Error('Close other tabs using this archive and retry.'));
  });
}
export async function listArchive<T extends ArchiveItem>(module: string, userId: string): Promise<T[]> {
  const db = await database(module, userId);
  try { return await new Promise<T[]>((resolve, reject) => { const req = db.transaction('items').objectStore('items').getAll(); req.onsuccess = () => resolve((req.result as T[]).sort((a,b) => b.createdAt.localeCompare(a.createdAt))); req.onerror = () => reject(req.error); }); }
  finally { db.close(); }
}
export async function saveArchive<T extends ArchiveItem>(module: string, userId: string, item: T) {
  const db = await database(module, userId);
  try { await new Promise<void>((resolve, reject) => {
    const tx = db.transaction('items', 'readwrite'), store = tx.objectStore('items'); store.put(item);
    const all = store.getAll(); all.onsuccess = () => { const items = (all.result as T[]).sort((a,b) => b.createdAt.localeCompare(a.createdAt)); items.slice(30).forEach(v => store.delete(v.id)); };
    tx.oncomplete = () => resolve(); tx.onerror = () => reject(new Error('The local archive could not be saved. Storage may be full.')); tx.onabort = () => reject(new Error('The local archive could not be saved.'));
  }); } finally { db.close(); }
}
export async function removeArchive(module: string, userId: string, id: string) {
  const db = await database(module, userId);
  try { await new Promise<void>((resolve, reject) => { const tx = db.transaction('items','readwrite'); tx.objectStore('items').delete(id); tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error); }); } finally { db.close(); }
}
