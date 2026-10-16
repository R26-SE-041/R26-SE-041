import React from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { headingFont, useAppTheme } from "../theme";

export default function ArchiveDialog({ title, busy, onClose, children }: { title: string; busy: boolean; onClose: () => void; children: React.ReactNode }) {
  const { colors } = useAppTheme();
  return <Modal transparent visible animationType="fade" onRequestClose={() => { if (!busy) onClose(); }}>
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: 24 }}>
      <Pressable accessibilityRole="button" accessibilityLabel="Dismiss dialog" disabled={busy} onPress={onClose} style={[StyleSheet.absoluteFill, { backgroundColor: "rgba(0,0,0,.45)" }]} />
      <View accessibilityViewIsModal style={{ width: "100%", maxWidth: 460, padding: 24, gap: 18, borderRadius: 14, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border }}>
        <Text accessibilityRole="header" style={{ color: colors.text, fontFamily: headingFont, fontSize: 28 }}>{title}</Text>
        {children}
      </View>
    </View>
  </Modal>;
}
