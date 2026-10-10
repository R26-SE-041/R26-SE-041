import React, { useCallback, useState } from "react";
import { ActivityIndicator, Image, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { ImagePlus, Upload } from "lucide-react-native";
import { fonts, useAppTheme } from "@/theme";

interface Props {
  onImageSelected: (uri: string, name: string, mime: string) => void;
  disabled?: boolean;
  currentUri: string | null;
}

const ACCEPTED_MIME = ["image/jpeg", "image/png", "image/webp", "image/bmp"];

export default function ImageUploader({ onImageSelected, disabled, currentUri }: Props) {
  const { colors } = useAppTheme();
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);

  const pickFromLibrary = useCallback(async () => {
    if (disabled) return;
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== "granted") return;
    setLoading(true);
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: "images", quality: 1, allowsEditing: false });
    setLoading(false);
    if (!result.canceled && result.assets[0]) {
      const asset = result.assets[0];
      const mime = asset.mimeType ?? "image/jpeg";
      onImageSelected(asset.uri, asset.fileName ?? `image.${mime.split("/")[1] ?? "jpg"}`, mime);
    }
  }, [disabled, onImageSelected]);

  const handleWebClick = useCallback(() => {
    if (disabled || Platform.OS !== "web") return;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ACCEPTED_MIME.join(",");
    input.onchange = (event) => {
      const file = (event.target as HTMLInputElement).files?.[0];
      if (!file || !ACCEPTED_MIME.includes(file.type)) return;
      onImageSelected(URL.createObjectURL(file), file.name, file.type);
    };
    input.click();
  }, [disabled, onImageSelected]);

  const webDragProps = Platform.OS === "web" ? {
    onDragOver: (event: React.DragEvent) => { event.preventDefault(); setDragOver(true); },
    onDragLeave: () => setDragOver(false),
    onDrop: (event: React.DragEvent) => {
      event.preventDefault();
      setDragOver(false);
      const file = event.dataTransfer.files[0];
      if (!file || !ACCEPTED_MIME.includes(file.type)) return;
      onImageSelected(URL.createObjectURL(file), file.name, file.type);
    },
  } : {};

  return (
    <Pressable
      onPress={Platform.OS === "web" ? handleWebClick : pickFromLibrary}
      disabled={disabled}
      style={({ pressed }) => [
        styles.dropZone,
        { backgroundColor: colors.surfaceSoft, borderColor: dragOver ? colors.primaryBright : colors.border },
        dragOver && styles.dropZoneActive,
        disabled && styles.disabled,
        pressed && !disabled && styles.pressed,
      ]}
      {...(webDragProps as object)}
    >
      {loading ? (
        <ActivityIndicator color={colors.primary} size="large" />
      ) : currentUri ? (
        <View style={styles.previewWrap}>
          <Image source={{ uri: currentUri }} style={[styles.preview, { backgroundColor: colors.canvas }]} resizeMode="contain" />
          <View style={[styles.replacePill, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            <ImagePlus size={15} color={colors.primaryBright} />
            <Text style={[styles.replaceHint, { color: colors.textMuted }]}>Choose another image</Text>
          </View>
        </View>
      ) : (
        <View style={styles.emptyState}>
          <View style={[styles.iconCircle, { backgroundColor: colors.canvas, borderColor: colors.border }]}>
            <Upload size={25} color={colors.primaryBright} strokeWidth={1.8} />
          </View>
          <Text style={[styles.fileLabel, { color: colors.textDim }]}>HANDWRITTEN IMAGE</Text>
          <Text style={[styles.emptyTitle, { color: colors.text }]}>{Platform.OS === "web" ? "Drop your image here" : "Choose an image from your device"}</Text>
          <Text style={[styles.emptySubtitle, { color: colors.textMuted }]}>{Platform.OS === "web" ? "or browse from your computer" : "JPG, PNG, WEBP or BMP"}</Text>
          <View style={[styles.browseButton, { backgroundColor: colors.primary, borderColor: colors.border }]}>
            <Text style={styles.browseButtonText}>Browse files</Text>
          </View>
          <Text style={[styles.formatText, { color: colors.textDim }]}>JPG · PNG · WEBP · BMP</Text>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  dropZone: { minHeight: 300, borderRadius: 24, borderWidth: 1, borderStyle: "dashed", alignItems: "center", justifyContent: "center", overflow: "hidden" },
  dropZoneActive: { transform: [{ scale: 0.99 }] },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.78, transform: [{ scale: 0.99 }] },
  previewWrap: { width: "100%", padding: 12, alignItems: "center" },
  preview: { width: "100%", height: 290, borderRadius: 20 },
  replacePill: { marginTop: 12, minHeight: 38, borderRadius: 50, borderWidth: 1, flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 14 },
  replaceHint: { fontSize: 12, fontWeight: "600", fontFamily: fonts.sans },
  emptyState: { alignItems: "center", padding: 30, maxWidth: 520 },
  iconCircle: { width: 60, height: 60, borderRadius: 30, borderWidth: 1, alignItems: "center", justifyContent: "center", marginBottom: 18 },
  fileLabel: { fontSize: 12, fontWeight: "700", letterSpacing: 1.1, marginBottom: 11, fontFamily: fonts.sans },
  emptyTitle: { fontSize: 23, lineHeight: 29, fontWeight: "700", textAlign: "center", fontFamily: fonts.serif },
  emptySubtitle: { fontSize: 13, textAlign: "center", marginTop: 6, fontFamily: fonts.sans },
  browseButton: { minHeight: 46, borderRadius: 13, borderWidth: 1, paddingHorizontal: 18, justifyContent: "center", marginTop: 20 },
  browseButtonText: { fontSize: 13, fontWeight: "700", color: "#ffffff", fontFamily: fonts.sans },
  formatText: { fontSize: 10, fontWeight: "700", letterSpacing: 1.1, marginTop: 13, fontFamily: fonts.sans },
});
