import React, { useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, View } from "react-native";
import ChangePasswordForm from "./ChangePasswordForm";
import Icon from "./Icon";
import { useAppTheme } from "../theme";
interface Props { email?: string; name?: string; signOut: () => Promise<void>; changePassword: (current: string, password: string, confirmation: string) => Promise<void> }
export default function StudioSessionPanel({ email, name, signOut, changePassword }: Props) {
  const { colors } = useAppTheme();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [changingPassword, setChangingPassword] = useState(false);
  const displayName = name || email || "Your account";
  const close = () => { if (!busy) { setOpen(false); setChangingPassword(false); setError(null); } };
  return <>
    <Pressable accessibilityRole="button" accessibilityLabel="Open account menu" accessibilityState={{ expanded: open }} onPress={() => setOpen(true)}
      style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: colors.buttonBackground, alignItems: "center", justifyContent: "center" }}>
      <Text style={{ color: colors.onButton, fontSize: 16, fontWeight: "700" }}>{displayName.slice(0, 1).toUpperCase()}</Text>
    </Pressable>
    <Modal transparent visible={open} animationType="fade" onRequestClose={close}>
      <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,.25)", justifyContent: "flex-start", alignItems: "flex-end", padding: 20 }}>
        <Pressable accessibilityRole="button" accessibilityLabel="Dismiss account menu" focusable={false} disabled={busy} onPress={close} style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0 }} />
        <ScrollView keyboardShouldPersistTaps="handled" style={{ width: 360, maxWidth: "100%", flexGrow: 0, backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: 8, boxShadow: `0 16px 48px ${colors.shadow}` }} contentContainerStyle={{ padding: 20, gap: 12 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={{ color: colors.textDim, fontSize: 11, fontWeight: "700", letterSpacing: 1 }}>YOUR ACCOUNT</Text>
            <Pressable accessibilityRole="button" accessibilityLabel="Close account menu" disabled={busy} onPress={close} style={{ padding: 10 }}><Icon name="close" color={colors.textMuted} /></Pressable>
          </View>
          <Text style={{ color: colors.text, fontWeight: "700", fontSize: 18 }}>{displayName}</Text>
          {email && <Text style={{ color: colors.textMuted, fontSize: 13 }}>{email}</Text>}
          <View style={{ flexDirection: "row", alignItems: "center", gap: 7 }}><Icon name="check" size={14} color={colors.success} /><Text style={{ color: colors.textMuted, fontSize: 12 }}>Signed in</Text></View>
          {open && changingPassword ? <ChangePasswordForm changePassword={changePassword} busy={busy} setBusy={setBusy} /> : <Pressable accessibilityRole="button" disabled={busy} onPress={() => { setError(null); setChangingPassword(true); }} style={{ padding: 12, borderRadius: 8, backgroundColor: colors.surfaceSoft }}><Text style={{ color: colors.primaryBright, fontWeight: "600" }}>Change password</Text></Pressable>}
          <Pressable accessibilityRole="button" disabled={busy} onPress={async () => {
            setBusy(true); setSigningOut(true); setError(null);
            try { await signOut(); setOpen(false); } catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to sign out."); }
            finally { setBusy(false); setSigningOut(false); }
          }} style={{ flexDirection: "row", alignItems: "center", gap: 10, padding: 12, borderRadius: 8, backgroundColor: colors.surfaceSoft, marginTop: 4 }}>
            {signingOut ? <ActivityIndicator color={colors.primaryBright} size="small" /> : <Icon name="log-out" color={colors.primaryBright} />}<Text style={{ color: colors.primaryBright, fontWeight: "600" }}>{signingOut ? "Signing out..." : "Sign out"}</Text>
          </Pressable>
          {error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}
        </ScrollView>
      </View>
    </Modal>
  </>;
}
