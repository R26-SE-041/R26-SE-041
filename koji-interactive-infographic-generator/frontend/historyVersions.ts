import { cloudEnabled, getCloudHistory, studioOwner, studioRequest } from "./studioClient";
import { listHistory, loadHistoryItem, saveHistoryItem, type GenerationHistoryItem } from "./historyStorage";

/** Copy-on-write: an edited image never overwrites a saved version. No GPU call. */
export async function saveAnnotationVersion(id: string, annotations: NonNullable<GenerationHistoryItem["anatomyAnnotations"]>): Promise<GenerationHistoryItem> {
  const owner = studioOwner();
  const cloud = cloudEnabled() && /^[0-9a-f-]{36}$/i.test(id);
  const items = cloud ? [] : await listHistory();
  const local = items.find(item => item.id === id);
  if (!cloud && !local) throw new Error("Saved image not found.");
  const source = cloud ? await getCloudHistory(id) : await loadHistoryItem(local!);
  const chatId = source.chatId ?? source.id;
  const createdAt = new Date().toISOString();
  const newId = typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `edit-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  if (owner !== studioOwner()) throw new Error("Account changed. Please try again.");
  let version: GenerationHistoryItem;
  if (cloud) {
    const { imageBase64, imageUrl: _imageUrl, glbBase64: _glbBase64, glbUrl: _glbUrl, ...metadata } = source;
    const imported = await studioRequest<{ id: string }>("/studio/import", { method: "POST", body: JSON.stringify({
      legacy_id: newId, created_at: createdAt, image_base64: imageBase64,
      metadata: { ...metadata, chatId, anatomyAnnotations: annotations },
    }) });
    version = await getCloudHistory(imported.id);
  } else {
    version = { ...source, id: newId, createdAt, chatId, anatomyAnnotations: annotations,
      version: Math.max(0, ...items.filter(item => (item.chatId ?? item.id) === chatId).map(item => item.version ?? 1)) + 1 };
  }
  if (owner !== studioOwner()) throw new Error("Account changed. Please reopen History.");
  await saveHistoryItem(version);
  return version;
}
