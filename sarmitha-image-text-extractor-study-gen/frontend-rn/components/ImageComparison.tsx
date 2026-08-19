import React from "react";
import { View, Text, Image, ScrollView, StyleSheet, useWindowDimensions } from "react-native";

interface Props {
  originalB64: string;
  enhancedB64: string;
}

export default function ImageComparison({ originalB64, enhancedB64 }: Props) {
  const { width } = useWindowDimensions();
  // Stack vertically on narrow screens, side-by-side on wide
  const isWide = width >= 640;

  return (
    <View style={[styles.container, isWide && styles.containerRow]}>
      {/* Original */}
      <View style={styles.imageBlock}>
        <View style={styles.labelWrap}>
          <Text style={styles.labelText}>Original</Text>
        </View>
        <View style={styles.imageBorder}>
          <Image
            source={{ uri: `data:image/png;base64,${originalB64}` }}
            style={styles.image}
            resizeMode="contain"
          />
        </View>
      </View>

      {/* Enhanced */}
      <View style={styles.imageBlock}>
        <View style={[styles.labelWrap, styles.labelWrapAccent]}>
          <Text style={[styles.labelText, styles.labelTextAccent]}>Enhanced (4×)</Text>
        </View>
        <View style={[styles.imageBorder, styles.imageBorderAccent]}>
          <Image
            source={{ uri: `data:image/png;base64,${enhancedB64}` }}
            style={styles.image}
            resizeMode="contain"
          />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "column",
    gap: 20,
  },
  containerRow: {
    flexDirection: "row",
  },
  imageBlock: {
    flex: 1,
    gap: 8,
  },
  labelWrap: {
    alignSelf: "flex-start",
    borderRadius: 6,
    backgroundColor: "rgba(255,255,255,0.08)",
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  labelWrapAccent: {
    backgroundColor: "rgba(139,92,246,0.2)",
  },
  labelText: {
    fontSize: 13,
    fontWeight: "500",
    color: "rgba(255,255,255,0.8)",
  },
  labelTextAccent: {
    color: "#c4b5fd",
  },
  imageBorder: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.1)",
    backgroundColor: "rgba(0,0,0,0.2)",
    overflow: "hidden",
  },
  imageBorderAccent: {
    borderColor: "rgba(139,92,246,0.3)",
  },
  image: {
    width: "100%",
    height: 240,
  },
});
