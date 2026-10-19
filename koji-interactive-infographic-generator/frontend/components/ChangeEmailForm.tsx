import React, { useState } from "react";
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native";
import { useAppTheme } from "../theme";

export default function ChangeEmailForm({ changeEmail, busy, setBusy }: {
  changeEmail: (email: string, password: string) => Promise<void>;
  busy: boolean; setBusy: (value: boolean) => void;
}) {
  const { colors } = useAppTheme();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const submit = async () => {
    if (busy) return;
    setBusy(true); setError("");
    try { await changeEmail(email, password); setPassword(""); setSent(true); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to change email."); }
    finally { setBusy(false); }
  };
  if (sent) return <Text accessibilityRole="alert" style={{ color: colors.success, lineHeight: 22 }}>Check your email to confirm the change. Your account and saved history stay the same. Depending on account settings, confirmation may be required at both addresses.</Text>;
  const input = { color: colors.text, backgroundColor: colors.surfaceSoft, borderColor: colors.border, borderWidth: 1, borderRadius: 8, minHeight: 48, paddingHorizontal: 12 };
  return <View style={{ gap: 12 }}>
    <Text style={{ color: colors.text, fontSize: 18 }}>Change email</Text>
    <Text style={{ color: colors.textMuted, lineHeight: 21 }}>Update the email on this account. Saved creations remain attached to your account ID.</Text>
    <TextInput accessibilityLabel="New email address" placeholder="New email address" placeholderTextColor={colors.textDim} value={email} onChangeText={setEmail} keyboardType="email-address" autoComplete="email" autoCapitalize="none" autoCorrect={false} editable={!busy} style={input} />
    <TextInput accessibilityLabel="Current password for email change" placeholder="Current password" placeholderTextColor={colors.textDim} value={password} onChangeText={setPassword} secureTextEntry autoComplete="current-password" autoCapitalize="none" editable={!busy} style={input} />
    {error && <Text accessibilityRole="alert" style={{ color: colors.danger }}>{error}</Text>}
    <Pressable accessibilityRole="button" disabled={busy} onPress={() => void submit()} style={{ minHeight: 48, backgroundColor: colors.buttonBackground, borderRadius: 8, justifyContent: "center", alignItems: "center" }}>
      {busy ? <ActivityIndicator color={colors.onButton} /> : <Text style={{ color: colors.onButton }}>Send confirmation</Text>}
    </Pressable>
  </View>;
}
