import React, { useState } from "react";
import { Image, Modal, Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { ArrowRight } from "lucide-react-native";
import { fonts, useAppTheme } from "@/theme";

interface Props { originalB64?: string; enhancedB64?: string; originalUri?: string; enhancedUri?: string; }

export default function ImageComparison({ originalB64, enhancedB64, originalUri, enhancedUri }: Props) {
  const { width } = useWindowDimensions();
  const { colors } = useAppTheme();
  const isRow = width >= 680;
  return (
    <View style={[styles.container, isRow && styles.containerRow]}>
      <ImageBlock index="A" label="Original input image" source={originalUri || (originalB64 ? `data:image/png;base64,${originalB64}` : "")} />
      {isRow && <View style={[styles.arrowBox, { backgroundColor: colors.primary }]}><ArrowRight size={18} color={colors.background} /></View>}
      <ImageBlock index="B" label="Enhanced image · 4×" source={enhancedUri || (enhancedB64 ? `data:image/png;base64,${enhancedB64}` : "")} />
    </View>
  );
}

function ImageBlock({ index, label, source }: { index: string; label: string; source: string }) {
  const { colors } = useAppTheme();
  const [expanded, setExpanded] = useState(false);
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const available = !!source && failedSource !== source;
  return (
    <View style={[styles.imageBlock, { borderColor: colors.border }]}>
      <View style={[styles.labelRow, { borderColor: colors.border }]}>
        <Text style={[styles.index, { color: colors.primary }]}>{index}</Text>
        <Text style={[styles.labelText, { color: colors.text }]}>{label}</Text>
      </View>
      <View style={[styles.imageBorder, { backgroundColor: colors.canvas }]}>
        {available ? <Pressable accessibilityRole="button" accessibilityLabel={`Enlarge ${label}`} onPress={() => setExpanded(true)}>
          <Image accessibilityLabel={label} source={{ uri: source }} style={styles.image} resizeMode="contain" onError={() => setFailedSource(source)} />
          <Text style={[styles.hint, { color: colors.textMuted }]}>Tap to enlarge</Text>
        </Pressable> : <View style={[styles.image, styles.placeholder]}><Text style={{ color: colors.textMuted }}>{source ? "Image could not load. Reopen this document to retry." : "Image was not saved for this document."}</Text></View>}
      </View>
      <Modal visible={expanded && available} transparent animationType="fade" onRequestClose={() => setExpanded(false)}>
        <View style={styles.viewer}><Pressable accessibilityRole="button" accessibilityLabel="Close image preview" onPress={() => setExpanded(false)} style={styles.close}><Text style={styles.closeText}>Close image</Text></Pressable><Image accessibilityLabel={label} source={{ uri: source }} style={styles.expandedImage} resizeMode="contain" /></View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: "column", gap: 18, position: "relative" },
  containerRow: { flexDirection: "row", gap: 20 },
  imageBlock: { flex: 1, borderWidth: 1, borderRadius: 12, overflow: "hidden" },
  labelRow: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 14, borderBottomWidth: 1 },
  index: { fontSize: 11, fontWeight: "700", fontFamily: fonts.sans },
  labelText: { fontSize: 11, fontWeight: "400", letterSpacing: .4, textTransform: "uppercase", fontFamily: fonts.mono },
  imageBorder: { overflow: "hidden" },
  image: { width: "100%", height: 360 },
  hint: { textAlign: "center", fontFamily: fonts.sans, fontSize: 12, padding: 10 },
  placeholder: { alignItems: "center", justifyContent: "center", padding: 24 },
  viewer: { flex: 1, backgroundColor: "rgba(20,20,19,.96)", padding: 20 },
  close: { alignSelf: "flex-end", padding: 16 },
  closeText: { color: "#FAF9F5", fontFamily: fonts.sans, fontSize: 16 },
  expandedImage: { flex: 1, width: "100%" },
  arrowBox: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center", position: "absolute", left: "50%", top: "50%", zIndex: 2, transform: [{ translateX: -21 }, { translateY: -21 }] },
});
