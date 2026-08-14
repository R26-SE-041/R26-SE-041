import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  StyleSheet,
  Platform,
  ActivityIndicator,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";
import { Upload, ImageIcon } from "lucide-react-native";

interface Props {
  onImageSelected: (uri: string, name: string, mime: string) => void;
  disabled?: boolean;
  currentUri: string | null;
}

const ACCEPTED_MIME = ["image/jpeg", "image/png", "image/webp", "image/bmp"];

export default function ImageUploader({ onImageSelected, disabled, currentUri }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);

  // ── Mobile: pick from camera roll ──────────────────────────────────────
  const pickFromLibrary = useCallback(async () => {
    if (disabled) return;
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== "granted") return;
    setLoading(true);
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: "images",
      quality: 1,
      allowsEditing: false,
    });
    setLoading(false);
    if (!result.canceled && result.assets[0]) {
      const asset = result.assets[0];
      const mime = asset.mimeType ?? "image/jpeg";
      const name = asset.fileName ?? `image.${mime.split("/")[1] ?? "jpg"}`;
      onImageSelected(asset.uri, name, mime);
    }
  }, [disabled, onImageSelected]);

  // ── Web: use a hidden <input type="file"> ──────────────────────────────
  const handleWebClick = useCallback(() => {
    if (disabled || Platform.OS !== "web") return;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ACCEPTED_MIME.join(",");
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      if (!ACCEPTED_MIME.includes(file.type)) return;
      const uri = URL.createObjectURL(file);
      onImageSelected(uri, file.name, file.type);
    };
    input.click();
  }, [disabled, onImageSelected]);

  const handlePress = Platform.OS === "web" ? handleWebClick : pickFromLibrary;

  // ── Web: drag and drop ─────────────────────────────────────────────────
  const webDragProps =
    Platform.OS === "web"
      ? {
          onDragOver: (e: React.DragEvent) => {
            e.preventDefault();
            setDragOver(true);
          },
          onDragLeave: () => setDragOver(false),
          onDrop: (e: React.DragEvent) => {
            e.preventDefault();
            setDragOver(false);
            const file = e.dataTransfer.files[0];
            if (!file || !ACCEPTED_MIME.includes(file.type)) return;
            const uri = URL.createObjectURL(file);
            onImageSelected(uri, file.name, file.type);
          },
        }
      : {};

  const borderColor = dragOver ? "rgba(139,92,246,0.7)" : "rgba(255,255,255,0.12)";
  const bg = dragOver ? "rgba(139,92,246,0.08)" : "rgba(255,255,255,0.03)";

  return (
    <TouchableOpacity
      activeOpacity={0.8}
      onPress={handlePress}
      disabled={disabled}
      style={[styles.dropZone, { borderColor, backgroundColor: bg }, disabled && styles.disabled]}
      {...(webDragProps as object)}
    >
      {loading ? (
        <ActivityIndicator color="#a78bfa" size="large" />
      ) : currentUri ? (
        <View style={styles.previewWrap}>
          <Image
            source={{ uri: currentUri }}
            style={styles.preview}
            resizeMode="contain"
          />
          <Text style={styles.replaceHint}>Tap to replace</Text>
        </View>
      ) : (
        <View style={styles.emptyState}>
          <View style={styles.iconCircle}>
            {dragOver ? (
              <ImageIcon size={32} color="#c4b5fd" strokeWidth={1.5} />
            ) : (
              <Upload size={32} color="#a78bfa" strokeWidth={1.5} />
            )}
          </View>
          <View style={styles.emptyText}>
            <Text style={styles.emptyTitle}>
              {Platform.OS === "web"
                ? "Drop your Sinhala handwritten image here"
                : "Tap to pick an image"}
            </Text>
            <Text style={styles.emptySubtitle}>
              {Platform.OS === "web"
                ? "or click to browse — JPG, PNG, WEBP, BMP"
                : "JPG, PNG, WEBP, BMP supported"}
            </Text>
          </View>
        </View>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  dropZone: {
    minHeight: 200,
    borderRadius: 16,
    borderWidth: 2,
    borderStyle: "dashed",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  disabled: {
    opacity: 0.5,
  },
  previewWrap: {
    width: "100%",
    padding: 12,
    alignItems: "center",
  },
  preview: {
    width: "100%",
    height: 220,
    borderRadius: 12,
  },
  replaceHint: {
    marginTop: 10,
    fontSize: 12,
    color: "rgba(255,255,255,0.4)",
  },
  emptyState: {
    alignItems: "center",
    gap: 16,
    padding: 32,
  },
  iconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "rgba(139,92,246,0.15)",
    alignItems: "center",
    justifyContent: "center",
  },
  emptyText: {
    alignItems: "center",
    gap: 4,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: "500",
    color: "rgba(255,255,255,0.85)",
    textAlign: "center",
  },
  emptySubtitle: {
    fontSize: 13,
    color: "rgba(255,255,255,0.4)",
    textAlign: "center",
  },
});
