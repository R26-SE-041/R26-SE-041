import React, { useState } from "react";
import { ActivityIndicator, Modal, Pressable, Text, View } from "react-native";
import Icon from "./Icon";
import { useAppTheme } from "../theme";
interface Props { email?: string; name?: string; signOut: () => Promise<void> }
export default function StudioSessionPanel({ email, name, signOut }: Props) {
  const { colors } = useAppTheme();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const displayName = name || email || "Your account";
  return <>
    <Pressable accessibilityRole="button" accessibilityLabel="Open account menu" accessibilityState={{ expanded: open }} onPress={() => setOpen(true)}
      style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" }}>
      <Text style={{ color: "#fff", fontSize: 16, fontWeight: "700" }}>{displayName.slice(0, 1).toUpperCase()}</Text>
    </Pressable>
    <Modal transparent visible={open} animationType="fade" onRequestClose={() => { if (!busy) setOpen(false); }}>
      <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,.25)", justifyContent: "flex-start", alignItems: "flex-end", padding: 20 }}>
        <Pressable accessibilityRole="button" accessibilityLabel="Close account menu" disabled={busy} onPress={() => setOpen(false)} style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0 }} />
        <View style={{ width: 300, maxWidth: "100%", backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, padding: 20, borderRadius: 20, gap: 12 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={{ color: colors.textDim, fontSize: 11, fontWeight: "700", letterSpacing: 1 }}>YOUR ACCOUNT</Text>
            <Pressable accessibilityRole="button" accessibilityLabel="Close account menu" disabled={busy} onPress={() => setOpen(false)} style={{ padding: 10 }}><Icon name="close" color={colors.textMuted} /></Pressable>
          </View>
          <Text style={{ color: colors.text, fontWeight: "700", fontSize: 18 }}>{displayName}</Text>
          {email && <Text style={{ color: colors.textMuted, fontSize: 13 }}>{email}</Text>}
          <View style={{ flexDirection: "row", alignItems: "center", gap: 7 }}><Icon name="check" size={14} color={colors.success} /><Text style={{ color: colors.textMuted, fontSize: 12 }}>Signed in</Text></View>
          <Pressable accessibilityRole="button" disabled={busy} onPress={async () => {
            setBusy(true); setError(null);
            try { await signOut(); setOpen(false); } catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to sign out."); }
            finally { setBusy(false); }
          }} style={{ flexDirection: "row", alignItems: "center", gap: 10, padding: 12, borderRadius: 10, backgroundColor: colors.surfaceSoft, marginTop: 4 }}>
            {busy ? <ActivityIndicator color={colors.primaryBright} size="small" /> : <Icon name="log-out" color={colors.primaryBright} />}<Text style={{ color: colors.primaryBright, fontWeight: "600" }}>{busy ? "Signing out..." : "Sign out"}</Text>
          </Pressable>
          {error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}
        </View>
      </View>
    </Modal>
  </>;
}
