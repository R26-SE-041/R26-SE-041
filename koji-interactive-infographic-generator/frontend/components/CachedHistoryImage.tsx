import React from "react";
import { Image, ImageProps } from "react-native";
export default function CachedHistoryImage({ uri, assetKey: _assetKey, ...props }: Omit<ImageProps, "source"> & { uri: string; assetKey: string }) {
  return <Image {...props} source={{ uri }} />;
}
