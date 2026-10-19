import React, { useState } from "react";
import { View, ViewProps } from "react-native";
import { imageSurfaceSize } from "./imageSurfaceSize";

/** Image, overlays and responders share one explicitly sized coordinate space. */
export default function ImageCoordinateSurface({ aspectRatio, children, style, ...props }: ViewProps & { aspectRatio: number }) {
  const [availableWidth, setAvailableWidth] = useState(0);
  const size = imageSurfaceSize(availableWidth, aspectRatio);
  return <View style={{ width: "100%", alignItems: "center" }} onLayout={event => setAvailableWidth(event.nativeEvent.layout.width)}>
    {availableWidth > 0 && <View {...props} style={[style, size]}>{children}</View>}
  </View>;
}
