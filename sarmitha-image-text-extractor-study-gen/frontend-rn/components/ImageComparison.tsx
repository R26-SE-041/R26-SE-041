import React from "react";
import { Image, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { ArrowRight } from "lucide-react-native";
import { fonts, useAppTheme } from "@/theme";

interface Props { originalB64: string; enhancedB64: string; }

export default function ImageComparison({ originalB64, enhancedB64 }: Props) {
  const { width } = useWindowDimensions();
  const { colors } = useAppTheme();
  const isRow = width >= 680;
  return (
    <View style={[styles.container, isRow && styles.containerRow]}>
      <ImageBlock index="A" label="Original image" source={`data:image/png;base64,${originalB64}`} />
      {isRow && <View style={[styles.arrowBox, { backgroundColor: colors.primary }]}><ArrowRight size={18} color={colors.background} /></View>}
      <ImageBlock index="B" label="SwinSR enhanced · 4×" source={`data:image/png;base64,${enhancedB64}`} />
    </View>
  );
}

function ImageBlock({ index, label, source }: { index: string; label: string; source: string }) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.imageBlock, { borderColor: colors.border }]}>
      <View style={[styles.labelRow, { borderColor: colors.border }]}>
        <Text style={[styles.index, { color: colors.primary }]}>{index}</Text>
        <Text style={[styles.labelText, { color: colors.text }]}>{label}</Text>
      </View>
      <View style={[styles.imageBorder, { backgroundColor: colors.canvas }]}>
        <Image source={{ uri: source }} style={styles.image} resizeMode="contain" />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: "column", gap: 18, position: "relative" },
  containerRow: { flexDirection: "row", gap: 20 },
  imageBlock: { flex: 1, borderWidth: 1, borderRadius: 18, overflow: "hidden" },
  labelRow: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 14, borderBottomWidth: 1 },
  index: { fontSize: 11, fontWeight: "700", fontFamily: fonts.sans },
  labelText: { fontSize: 11, fontWeight: "700", letterSpacing: 0.8, textTransform: "uppercase", fontFamily: fonts.sans },
  imageBorder: { overflow: "hidden" },
  image: { width: "100%", height: 360 },
  arrowBox: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center", position: "absolute", left: "50%", top: "50%", zIndex: 2, transform: [{ translateX: -21 }, { translateY: -21 }] },
});
