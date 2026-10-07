import React, { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type { AnatomyAnnotation } from "../App";
import { ColorPalette, useAppTheme } from "../theme";
import Icon from "./Icon";
import { buildLabeledSvg, exportFileStem } from "./anatomyExport";

interface Props { annotations: AnatomyAnnotation[]; imageBase64: string; organ?: string }

function download(href: string, filename: string) {
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  anchor.click();
}

export default function ImageDownloadControls({ annotations, imageBase64, organ }: Props) {
  const { colors } = useAppTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const stem = exportFileStem(organ);

  const downloadImage = () => download(`data:image/png;base64,${imageBase64}`, `${stem}.png`);
  const downloadLabeled = () => {
    const url = URL.createObjectURL(new Blob([buildLabeledSvg(imageBase64, annotations)], { type: "image/svg+xml" }));
    download(url, `${stem}-labels.svg`);
    setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  return (
    <View style={styles.row}>
      <Pressable onPress={downloadImage} style={styles.button}><Icon color="#fff" name="download" size={15} /><Text style={styles.text}>Image only (PNG)</Text></Pressable>
      <Pressable disabled={!annotations.length} onPress={downloadLabeled} style={[styles.button, styles.secondary, !annotations.length && styles.disabled]}><Icon color={colors.primaryBright} name="download" size={15} /><Text style={[styles.text, styles.secondaryText]}>Image + SVG labels</Text></Pressable>
    </View>
  );
}

const makeStyles = (colors: ColorPalette) => StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  button: { flexDirection: "row", alignItems: "center", gap: 7, backgroundColor: colors.primary, borderRadius: 10, paddingHorizontal: 13, paddingVertical: 9 },
  secondary: { backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.primaryBright },
  text: { color: "#fff", fontSize: 12, fontWeight: "800" },
  secondaryText: { color: colors.primaryBright },
  disabled: { opacity: 0.45 },
});
