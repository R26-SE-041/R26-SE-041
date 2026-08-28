import React, { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import type { AnatomyAnnotation } from "../App";
import { ColorPalette, useAppTheme } from "../theme";
import Icon from "./Icon";
import { buildLabeledSvg, exportFileStem } from "./anatomyExport";

interface Props { annotations: AnatomyAnnotation[]; imageBase64: string; organ?: string }

export default function ImageDownloadControls({ annotations, imageBase64, organ }: Props) {
  const { colors } = useAppTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [error, setError] = useState<string | null>(null);
  const stem = exportFileStem(organ);

  const save = async (withLabels: boolean) => {
    try {
      setError(null);
      const extension = withLabels ? "svg" : "png";
      const uri = `${FileSystem.cacheDirectory}${stem}${withLabels ? "-labels" : ""}.${extension}`;
      if (withLabels) {
        await FileSystem.writeAsStringAsync(uri, buildLabeledSvg(imageBase64, annotations));
      } else {
        await FileSystem.writeAsStringAsync(uri, imageBase64, { encoding: FileSystem.EncodingType.Base64 });
      }
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, { mimeType: withLabels ? "image/svg+xml" : "image/png", dialogTitle: "Save or share educational image" });
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save image");
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <Pressable onPress={() => void save(false)} style={styles.button}><Icon color="#fff" name="download" size={15} /><Text style={styles.text}>Image only (PNG)</Text></Pressable>
        <Pressable disabled={!annotations.length} onPress={() => void save(true)} style={[styles.button, styles.secondary, !annotations.length && styles.disabled]}><Icon color={colors.primaryBright} name="download" size={15} /><Text style={[styles.text, styles.secondaryText]}>Image + SVG labels</Text></Pressable>
      </View>
      {!!error && <Text style={styles.error}>{error}</Text>}
    </View>
  );
}

const makeStyles = (colors: ColorPalette) => StyleSheet.create({
  container: { gap: 7 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  button: { flexDirection: "row", alignItems: "center", gap: 7, backgroundColor: colors.primary, borderRadius: 10, paddingHorizontal: 13, paddingVertical: 9 },
  secondary: { backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.primaryBright },
  text: { color: "#fff", fontSize: 12, fontWeight: "800" },
  secondaryText: { color: colors.primaryBright },
  disabled: { opacity: 0.45 },
  error: { color: colors.danger, fontSize: 11 },
});
