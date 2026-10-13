import React, { useState } from "react";
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native";
import Icon from "./Icon";
import { useAppTheme } from "../theme";

interface Props {
  changePassword: (current: string, password: string, confirmation: string) => Promise<void>;
  busy: boolean;
  setBusy: (busy: boolean) => void;
}

export default function ChangePasswordForm({ changePassword, busy, setBusy }: Props) {
  const { colors } = useAppTheme();
  const [passwords, setPasswords] = useState({ current: "", next: "", confirmation: "" });
  const [visible, setVisible] = useState({ current: false, next: false, confirmation: false });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const submit = async () => {
    if (busy) return;
    setBusy(true); setError(null);
    try {
      await changePassword(passwords.current, passwords.next, passwords.confirmation);
      setPasswords({ current: "", next: "", confirmation: "" });
      setVisible({ current: false, next: false, confirmation: false });
      setSaved(true);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to change your password."); }
    finally { setBusy(false); }
  };
  if (saved) return <Text accessibilityRole="alert" style={{ color: colors.success, lineHeight: 22 }}>Password updated. Use your new password next time you sign in.</Text>;
  return <View style={{ gap: 14 }}>
    <Text style={{ color: colors.text, fontSize: 18, fontWeight: "600" }}>Change password</Text>
    {([
      ["current", "Current password"], ["next", "New password"], ["confirmation", "Confirm new password"],
    ] as const).map(([key, label]) => <View key={key} style={{ gap: 7 }}>
      <Text style={{ color: colors.text, fontSize: 13, fontWeight: "600" }}>{label}</Text>
      <View style={{ position: "relative" }}>
        <TextInput accessibilityLabel={label} value={passwords[key]}
          onChangeText={value => { setPasswords(current => ({ ...current, [key]: value })); setError(null); }}
          autoComplete={key === "current" ? "current-password" : "new-password"}
          autoCapitalize="none" autoCorrect={false} secureTextEntry={!visible[key]} editable={!busy}
          maxLength={key === "current" ? undefined : 128} placeholder={key === "next" ? "At least 8 characters" : label}
          placeholderTextColor={colors.textDim} onSubmitEditing={() => { if (key === "confirmation") void submit(); }}
          style={{ color: colors.text, backgroundColor: colors.surfaceSoft, borderColor: colors.border, borderWidth: 1, borderRadius: 8, height: 50, paddingLeft: 12, paddingRight: 48 }} />
        <Pressable accessibilityRole="button" accessibilityLabel={`${visible[key] ? "Hide" : "Show"} ${label.toLowerCase()}`}
          disabled={busy} onPress={() => setVisible(current => ({ ...current, [key]: !current[key] }))}
          style={{ position: "absolute", right: 3, top: 3, width: 44, height: 44, alignItems: "center", justifyContent: "center" }}>
          <Icon name={visible[key] ? "eye-off" : "eye"} color={colors.textMuted} />
        </Pressable>
      </View>
    </View>)}
    {error && <Text accessibilityRole="alert" style={{ color: colors.danger, lineHeight: 22 }}>{error}</Text>}
    <Pressable accessibilityRole="button" accessibilityLabel="Save new password" accessibilityState={{ disabled: busy, busy }}
      disabled={busy} onPress={() => void submit()} style={{ minHeight: 48, borderRadius: 8, padding: 12, alignItems: "center", justifyContent: "center", backgroundColor: colors.buttonBackground, opacity: busy ? .6 : 1 }}>
      {busy ? <ActivityIndicator color={colors.onButton} /> : <Text style={{ color: colors.onButton, fontWeight: "600" }}>Save new password</Text>}
    </Pressable>
  </View>;
}
