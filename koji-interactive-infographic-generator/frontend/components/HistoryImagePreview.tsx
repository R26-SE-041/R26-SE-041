import React, { useState } from "react";
import { View } from "react-native";
import type { AnatomyAnnotation } from "../App";
import AnatomyOverlay from "./AnatomyOverlay";
import CachedHistoryImage from "./CachedHistoryImage";

export default function HistoryImagePreview({ uri, assetKey, annotations = [] }: { uri: string; assetKey: string; annotations?: AnatomyAnnotation[] }) {
  const [ratio, setRatio] = useState(1);
  return <View style={{ aspectRatio: ratio, width: "100%", backgroundColor: "white" }}>
    <CachedHistoryImage uri={uri} assetKey={assetKey} resizeMode="contain" style={{ width: "100%", height: "100%" }} onLoad={event => {
      const source = event.nativeEvent.source;
      if (source?.width && source?.height) setRatio(source.width / source.height);
    }} />
    {!!annotations.length && <AnatomyOverlay annotations={annotations} />}
  </View>;
}
