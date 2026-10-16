import React, { useCallback, useState } from "react";
import { ActivityIndicator, Image, Platform, Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";
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
  const { width } = useWindowDimensions();
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fileError, setFileError] = useState("");
  const acceptFile = (file: File) => {
    if (disabled) return;
    if (!ACCEPTED_MIME.includes(file.type) || file.size > 10 * 1024 * 1024) {
      setFileError("Choose a JPG, PNG or WEBP image under 10 MB.");
      return;
    }
    setFileError("");
    onImageSelected(URL.createObjectURL(file), file.name, file.type);
  };

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
      if (file) acceptFile(file);
    };
    input.click();
  }, [disabled, onImageSelected]);

  const webDragProps = Platform.OS === "web" ? {
    onDragOver: (event: React.DragEvent) => { event.preventDefault(); if (!disabled) setDragOver(true); },
    onDragLeave: () => setDragOver(false),
    onDrop: (event: React.DragEvent) => {
      event.preventDefault();
      setDragOver(false);
      const file = event.dataTransfer.files[0];
      if (file) acceptFile(file);
    },
  } : {};

  return (
    <Pressable
      nativeID="image-dropzone"
      accessibilityRole="button"
      accessibilityLabel={currentUri ? "Replace your selected image" : "Choose a handwritten image, JPG, PNG or WEBP, up to 10 megabytes"}
      onPress={Platform.OS === "web" ? handleWebClick : pickFromLibrary}
      disabled={disabled}
      style={({ pressed }) => [
        styles.dropZone,
        { backgroundColor: dragOver ? colors.canvas : colors.surfaceSoft, borderColor: colors.border },
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
          <Image accessibilityLabel="Selected handwritten document" source={{ uri: currentUri }} style={[styles.preview, { backgroundColor: colors.canvas }]} resizeMode="contain" />
          <View style={[styles.replaceLink, { backgroundColor: colors.text }]}>
            <ImagePlus size={15} color={colors.background} />
            <Text style={[styles.replaceHint, { color: colors.background }]}>Replace image</Text>
          </View>
        </View>
      ) : (
        <View style={styles.emptyState}>
          <View style={[styles.emptyTop, { borderColor: colors.border }]}>
            <View style={[styles.iconBox, { borderColor: colors.text }]}>
              <Upload size={23} color={colors.text} strokeWidth={1.4} />
            </View>
            <Text style={[styles.fileLabel, { color: colors.textMuted }]}>YOUR NEXT CLEAR IDEA</Text>
          </View>
          <View style={styles.emptyCopy}>
            <Text style={[styles.emptyTitle, { color: colors.text }, width < 680 && { fontSize: 28, lineHeight: 33 }]}>{Platform.OS === "web" ? "Drop a page.\nDiscover its possibilities." : "Choose a page.\nDiscover its possibilities."}</Text>
            <Text style={[styles.emptySubtitle, { color: colors.textMuted }]}>Drag your image here, or choose a photograph or scan from your device.</Text>
          </View>
          {fileError ? <Text accessibilityRole="alert" style={[styles.fileError, { color: colors.danger }]}>{fileError}</Text> : null}
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
  dropZone: { minHeight: 380, borderWidth: 1, borderRadius: 14, alignItems: "stretch", justifyContent: "center", overflow: "hidden" },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.82 },
  previewWrap: { width: "100%", padding: 18, alignItems: "flex-start" },
  preview: { width: "100%", height: 300, borderRadius: 8 },
  replaceLink: { marginTop: 14, minHeight: 38, borderRadius: 8, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16 },
  replaceHint: { fontSize: 12, fontWeight: "700", fontFamily: fonts.sans },
  emptyState: { flex: 1, padding: 28, justifyContent: "space-between" },
  emptyTop: { paddingBottom: 8, flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  iconBox: { width: 44, height: 44, borderWidth: 1, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  fileLabel: { fontSize: 9, letterSpacing: .8, fontFamily: fonts.mono, flexShrink: 1 },
  emptyCopy: { paddingVertical: 34 },
  emptyTitle: { fontSize: 36, lineHeight: 40, maxWidth: 580, fontWeight: "400", letterSpacing: -.9, fontFamily: fonts.serif },
  emptySubtitle: { fontSize: 16, lineHeight: 24, maxWidth: 500, marginTop: 15, fontFamily: fonts.serif },
  browseButton: { minHeight: 40, alignSelf: "flex-start", borderWidth: 1, borderRadius: 8, paddingHorizontal: 16, flexDirection: "row", alignItems: "center", gap: 24 },
  browseButtonText: { fontSize: 14, fontWeight: "500", fontFamily: fonts.sans },
  fileError: { fontFamily: fonts.sans, fontSize: 13, lineHeight: 19, marginTop: 16 },
});
