import React from "react";
import { Image, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { Sparkles } from "lucide-react-native";
import { fonts, useAppTheme } from "@/theme";

interface Props { originalB64: string; enhancedB64: string; }

export default function ImageComparison({ originalB64, enhancedB64 }: Props) {
  const { width } = useWindowDimensions();
  return (
    <View style={[styles.container, width >= 680 && styles.containerRow]}>
      <ImageBlock label="Original image" source={`data:image/png;base64,${originalB64}`} />
      <ImageBlock label="SwinSR enhanced · 4×" source={`data:image/png;base64,${enhancedB64}`} enhanced />
    </View>
  );
}

function ImageBlock({ label, source, enhanced = false }: { label: string; source: string; enhanced?: boolean }) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.imageBlock, { backgroundColor: colors.surfaceSoft, borderColor: colors.border }]}>
      <View style={styles.labelRow}>
        {enhanced && <Sparkles size={14} color={colors.primaryBright} />}
        <Text style={[styles.labelText, { color: enhanced ? colors.primaryBright : colors.textMuted }]}>{label}</Text>
      </View>
      <View style={[styles.imageBorder, { backgroundColor: colors.canvas, borderColor: colors.border }]}>
        <Image source={{ uri: source }} style={styles.image} resizeMode="contain" />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: "column", gap: 20 },
  containerRow: { flexDirection: "row" },
  imageBlock: { flex: 1, borderRadius: 20, borderWidth: 1, padding: 12 },
  labelRow: { minHeight: 34, flexDirection: "row", alignItems: "center", gap: 7, paddingHorizontal: 4 },
  labelText: { fontSize: 12, fontWeight: "700", letterSpacing: 1.1, textTransform: "uppercase", fontFamily: fonts.sans },
  imageBorder: { borderRadius: 16, borderWidth: 1, overflow: "hidden" },
  image: { width: "100%", height: 260 },
});
