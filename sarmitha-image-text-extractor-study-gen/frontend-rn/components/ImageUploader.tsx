import React, { useCallback, useState } from "react";
import { ActivityIndicator, Image, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { ArrowUpRight, ImagePlus, Upload } from "lucide-react-native";
import { fonts, useAppTheme } from "@/theme";

interface Props {
  onImageSelected: (uri: string, name: string, mime: string) => void;
  disabled?: boolean;
  currentUri: string | null;
}

const ACCEPTED_MIME = ["image/jpeg", "image/png", "image/webp"];

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
        { backgroundColor: dragOver ? colors.canvas : colors.surfaceSoft, borderColor: colors.text },
        dragOver && { borderColor: colors.primary },
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
          <View style={[styles.replaceLink, { backgroundColor: colors.text }]}>
            <ImagePlus size={15} color={colors.background} />
            <Text style={[styles.replaceHint, { color: colors.background }]}>Replace image</Text>
          </View>
        </View>
      ) : (
        <View style={styles.emptyState}>
          <View style={[styles.emptyTop, { borderColor: colors.border }]}>
            <View style={[styles.iconBox, { backgroundColor: colors.primary }]}>
              <Upload size={26} color={colors.background} strokeWidth={1.7} />
            </View>
            <Text style={[styles.fileLabel, { color: colors.textDim }]}>01 / ADD A DOCUMENT</Text>
          </View>
          <View style={styles.emptyCopy}>
            <Text style={[styles.emptyTitle, { color: colors.text }]}>{Platform.OS === "web" ? "Drop your image into the workspace." : "Choose an image from your device."}</Text>
            <Text style={[styles.emptySubtitle, { color: colors.textMuted }]}>Use the clearest available photograph or scan for the best recognition result.</Text>
          </View>
          <View style={[styles.browseButton, { borderColor: colors.text }]}>
            <Text style={[styles.browseButtonText, { color: colors.text }]}>Browse files</Text>
            <ArrowUpRight size={17} color={colors.text} />
          </View>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  dropZone: { minHeight: 430, borderWidth: 1, borderRadius: 20, alignItems: "stretch", justifyContent: "center", overflow: "hidden" },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.82 },
  previewWrap: { width: "100%", padding: 18, alignItems: "flex-start" },
  preview: { width: "100%", height: 350, borderRadius: 14 },
  replaceLink: { marginTop: 14, minHeight: 46, borderRadius: 10, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16 },
  replaceHint: { fontSize: 12, fontWeight: "700", fontFamily: fonts.sans },
  emptyState: { flex: 1, padding: 28, justifyContent: "space-between" },
  emptyTop: { borderBottomWidth: 1, paddingBottom: 18, flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 16 },
  iconBox: { width: 52, height: 52, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  fileLabel: { fontSize: 9, fontWeight: "700", letterSpacing: 1.2, fontFamily: fonts.sans },
  emptyCopy: { paddingVertical: 34 },
  emptyTitle: { fontSize: 34, lineHeight: 39, maxWidth: 580, fontWeight: "700", letterSpacing: -1.1, fontFamily: fonts.display },
  emptySubtitle: { fontSize: 16, lineHeight: 24, maxWidth: 500, marginTop: 15, fontFamily: fonts.serif },
  browseButton: { minHeight: 50, alignSelf: "flex-start", borderWidth: 1, borderRadius: 10, paddingHorizontal: 18, flexDirection: "row", alignItems: "center", gap: 30 },
  browseButtonText: { fontSize: 13, fontWeight: "700", fontFamily: fonts.sans },
});
