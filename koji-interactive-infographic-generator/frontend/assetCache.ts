const pending = new Map<string, Promise<ArrayBuffer>>();
const MAX_CACHE_BYTES = 200 * 1024 * 1024;

// Stable, account-scoped keys keep rotating private URLs from redownloading
// the same immutable image/model. CacheStorage is optional (private browsing).
export function cachedAsset(owner: string, key: string, url: string): Promise<ArrayBuffer> {
  const id = `${owner}:${key}`;
  const existing = pending.get(id);
  if (existing) return existing;
  const operation = (async () => {
    let cache: Cache | undefined;
    const requestKey = typeof location === "undefined" ? "" : `${location.origin}/__studio_assets/${encodeURIComponent(key)}`;
    try {
      if (typeof caches !== "undefined") cache = await caches.open(`koji-assets:${owner}`);
      const saved = cache && await cache.match(requestKey);
      if (saved) return saved.arrayBuffer();
    } catch { cache = undefined; }
    const response = await fetch(url, { signal: AbortSignal.timeout(90_000) });
    if (!response.ok) throw new Error(`Unable to download the saved asset (HTTP ${response.status}). Please retry.`);
    const bytes = await response.arrayBuffer();
    if (cache && bytes.byteLength <= MAX_CACHE_BYTES) {
      try {
        await cache.put(requestKey, new Response(bytes, { headers: { "Content-Type": "application/octet-stream", "X-Asset-Bytes": String(bytes.byteLength) } }));
        const entries = await cache.keys();
        let total = bytes.byteLength;
        for (const entry of [...entries].reverse()) {
          if (entry.url === requestKey) continue;
          const saved = await cache.match(entry);
          total += Number(saved?.headers.get("X-Asset-Bytes") || 0);
          if (total > MAX_CACHE_BYTES) await cache.delete(entry);
        }
      } catch { /* Rendering must still work when browser storage is full. */ }
    }
    return bytes;
  })();
  pending.set(id, operation);
  void operation.finally(() => { if (pending.get(id) === operation) pending.delete(id); }).catch(() => {});
  return operation;
}

export function assetBase64(bytes: ArrayBuffer): string {
  const data = new Uint8Array(bytes);
  let binary = "";
  for (let offset = 0; offset < data.length; offset += 32768) binary += String.fromCharCode(...data.subarray(offset, offset + 32768));
  return btoa(binary);
}
