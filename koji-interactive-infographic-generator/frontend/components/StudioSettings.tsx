import React from "react";
import { Modal, Pressable, ScrollView, Text, View } from "react-native";
import { headingFont, useAppTheme } from "../theme";
import PersonalMemoryPanel from "./PersonalMemoryPanel";
import Icon from "./Icon";

export default function StudioSettings({ open, onClose, accessToken, apiUrl }: { open: boolean; onClose: () => void; accessToken?: string; apiUrl: string }) {
  const { colors, mode, toggleTheme } = useAppTheme();
  return <Modal visible={open} transparent animationType="fade" onRequestClose={onClose}>
    <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,.35)", padding: 20, justifyContent: "center", alignItems: "center" }}>
      <Pressable accessibilityRole="button" accessibilityLabel="Dismiss settings" onPress={onClose} style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0 }} />
      <View accessibilityViewIsModal style={{ width: "100%", maxWidth: 600, maxHeight: "90%", borderRadius: 12, backgroundColor: colors.background, borderWidth: 1, borderColor: colors.border }}>
        <ScrollView contentContainerStyle={{ padding: 24, gap: 22 }} keyboardShouldPersistTaps="handled">
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}><Text accessibilityRole="header" style={{ fontFamily: headingFont, fontSize: 30, color: colors.text }}>Studio settings</Text><Pressable accessibilityRole="button" accessibilityLabel="Close settings" onPress={onClose} style={{ padding: 12 }}><Icon name="close" color={colors.text} /></Pressable></View>
          <View style={{ gap: 10 }}><Text style={{ color: colors.text, fontSize: 16, fontWeight: "600" }}>Appearance</Text><Pressable accessibilityRole="button" onPress={toggleTheme} style={{ minHeight: 48, backgroundColor: colors.surfaceSoft, borderRadius: 8, padding: 14 }}><Text style={{ color: colors.text }}>{mode === "light" ? "Light theme · Switch to dark" : "Dark theme · Switch to light"}</Text></Pressable><Text style={{ color: colors.textMuted, lineHeight: 21 }}>Your theme preference is remembered on this device.</Text></View>
          {accessToken ? <PersonalMemoryPanel accessToken={accessToken} apiUrl={apiUrl} /> : <View style={{ gap: 8 }}><Text style={{ color: colors.text, fontSize: 16, fontWeight: "600" }}>Learning preferences</Text><Text style={{ color: colors.textMuted, lineHeight: 22 }}>Sign in to remember your preferences across anatomy creations.</Text></View>}
          <View style={{ gap: 8 }}><Text style={{ color: colors.text, fontSize: 16, fontWeight: "600" }}>About generation speed</Text><Text style={{ color: colors.textMuted, lineHeight: 22 }}>Standard and Fast follow the same generation workflow. Fast selects a higher-performance GPU for images and analysis. Wait times depend on model startup and demand; speed does not guarantee higher quality.</Text></View>
        </ScrollView>
      </View>
    </View>
  </Modal>;
}
