import React, { useEffect, useState } from "react";
import { Image, ImageProps } from "react-native";
import { assetBase64, cachedAsset } from "../assetCache";
import { studioOwner } from "../studioClient";

const thumbnails = new Map<string, { uri?: string; promise: Promise<string> }>();
export default function CachedHistoryImage({ uri, assetKey, ...props }: Omit<ImageProps, "source"> & { uri: string; assetKey: string }) {
  const owner = studioOwner(), key = `${owner}:${assetKey}`;
  const [cached, setCached] = useState(() => uri.startsWith("data:") ? uri : thumbnails.get(key)?.uri);
  useEffect(() => {
    let live = true;
    if (uri.startsWith("data:")) { setCached(uri); return; }
    let entry = thumbnails.get(key);
    if (!entry) {
      const next: { uri?: string; promise: Promise<string> } = { promise: Promise.resolve("") };
      next.promise = cachedAsset(owner, assetKey, uri).then(bytes => {
        next.uri = `data:image/png;base64,${assetBase64(bytes)}`;
        return next.uri;
      });
      entry = next; thumbnails.set(key, next);
      while (thumbnails.size > 100) thumbnails.delete(thumbnails.keys().next().value!);
    }
    void entry.promise.then(value => { if (live) setCached(value); }).catch(() => {
      thumbnails.delete(key); if (live) setCached(uri);
    });
    return () => { live = false; };
  }, [key, uri, owner, assetKey]);
  return <Image {...props} source={{ uri: cached }} />;
}
