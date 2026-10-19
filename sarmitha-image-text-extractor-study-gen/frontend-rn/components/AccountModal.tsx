import React, { useEffect, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { ArrowRight, X } from "lucide-react-native";
import { useAccount } from "./AuthProvider";
import { signIn, signOut, signUp } from "@/lib/auth";
import { fonts } from "@/theme";
import ToolkitBrand from "./ToolkitBrand";
import { loadAccountActivity, type AccountEvent } from "@/lib/history";

export default function AccountModal({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const account = useAccount();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [events, setEvents] = useState<AccountEvent[]>([]);
  const [activityError, setActivityError] = useState("");
  useEffect(() => {
    let active = true;
    setEvents([]); setActivityError("");
    if (visible && account.user) void loadAccountActivity().then(value => { if (active) setEvents(value); }).catch(() => { if (active) setActivityError("Account activity is temporarily unavailable."); });
    return () => { active = false; };
  }, [visible, account.user?.id]);
  useEffect(() => { if (!visible) { setPassword(""); setError(""); setMessage(""); } }, [visible]);
  const submit = async () => {
    setError(""); setMessage("");
    if (!email.trim() || !password || (mode === "signup" && !name.trim())) { setError("Please fill in all the fields."); return; }
    if (mode === "signup" && password.length < 8) { setError("Choose a password with at least 8 characters."); return; }
    setBusy(true);
    try {
      if (mode === "signin") { await signIn(email.trim(), password); onClose(); }
      else {
        const notice = await signUp(email.trim(), password, name.trim());
        if (notice) { setMessage(notice); setMode("signin"); }
        else onClose();
      }
      setPassword("");
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  };
  const logout = async () => {
    setBusy(true); setError("");
    try { await signOut(); onClose(); }
    catch { setError("You are signed out on this device. We could not confirm the server sign-out; please try again when connected."); }
    finally { setBusy(false); }
  };
  return <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
    <View style={styles.backdrop}>
      <View accessibilityViewIsModal style={styles.card}>
        <Pressable accessibilityRole="button" accessibilityLabel="Close account dialog" onPress={onClose} style={styles.close}><X size={22} color="#141413" /></Pressable>
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content}>
          <View style={{ alignItems: "flex-start", paddingBottom: 28 }}><ToolkitBrand /></View>
          <Text style={styles.overline}>YOUR SINHALA OCR ACCOUNT</Text>
          <Text accessibilityRole="header" style={styles.title}>{account.user ? "Your account." : mode === "signin" ? "Welcome back." : "A place for your words."}</Text>
          {account.user ? <>
            <Text style={styles.description}>{account.user.display_name || "Your account"}</Text>
            <Text selectable style={styles.email}>{account.user.email}</Text>
            <Text style={styles.description}>Your documents and translations are saved privately in your history.</Text>
            <Text style={[styles.label, { marginTop: 28 }]}>RECENT ACCOUNT ACTIVITY</Text>
            {events.map(event => <Text key={event.id} style={styles.activity}>{event.event_type === "sign_up" ? "Account created" : event.event_type === "sign_in" ? "Signed in" : "Signed out"} · {new Date(event.created_at).toLocaleString()}</Text>)}
            {activityError ? <Text style={styles.error}>{activityError}</Text> : null}
            <Pressable accessibilityRole="button" disabled={busy} onPress={logout} style={[styles.primary, busy && styles.disabled]}><Text style={styles.primaryText}>{busy ? "Signing out…" : "Sign out"}</Text></Pressable>
          </> : <>
            <Text style={styles.description}>Sign in to keep your notes, extracted text, and translations together.</Text>
            <View style={styles.tabs}>
              {(["signin", "signup"] as const).map(tab => <Pressable key={tab} accessibilityRole="tab" accessibilityState={{ selected: mode === tab }} disabled={busy} onPress={() => { setMode(tab); setError(""); setMessage(""); }} style={[styles.tab, mode === tab && styles.activeTab]}><Text style={styles.tabText}>{tab === "signin" ? "Sign in" : "Create account"}</Text></Pressable>)}
            </View>
            {mode === "signup" && <><Text style={styles.label}>YOUR NAME</Text><TextInput accessibilityLabel="Your name" style={styles.input} value={name} onChangeText={setName} maxLength={100} autoComplete="name" editable={!busy} /></>}
            <Text style={styles.label}>EMAIL ADDRESS</Text>
            <TextInput accessibilityLabel="Email address" style={styles.input} value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" autoCorrect={false} autoComplete="email" maxLength={254} editable={!busy} />
            <Text style={styles.label}>PASSWORD</Text>
            <TextInput accessibilityLabel="Password" style={styles.input} value={password} onChangeText={setPassword} secureTextEntry autoCapitalize="none" autoCorrect={false} autoComplete={mode === "signup" ? "new-password" : "current-password"} maxLength={128} editable={!busy} onSubmitEditing={submit} />
            {mode === "signup" && <Text style={styles.hint}>Use at least 8 characters.</Text>}
            <Pressable accessibilityRole="button" disabled={busy || account.loading || !account.enabled} onPress={submit} style={[styles.primary, (busy || account.loading || !account.enabled) && styles.disabled]}>{busy ? <ActivityIndicator color="#FAF9F5" /> : <><Text style={styles.primaryText}>{mode === "signin" ? "Sign in" : "Create your account"}</Text><ArrowRight size={17} color="#FAF9F5" /></>}</Pressable>
          </>}
          {error || (!account.user && account.error) ? <Text accessibilityRole="alert" style={styles.error}>{error || account.error}</Text> : null}
          {message ? <Text accessibilityLiveRegion="polite" style={styles.notice}>{message}</Text> : null}
        </ScrollView>
      </View>
    </View>
  </Modal>;
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(20,20,19,.35)", alignItems: "center", justifyContent: "center", padding: 20 },
  card: { width: "100%", maxWidth: 500, maxHeight: "92%", backgroundColor: "#FAF9F5", borderRadius: 24 },
  close: { alignSelf: "flex-end", padding: 18 }, content: { paddingHorizontal: 32, paddingBottom: 36 },
  overline: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1, color: "#5E5D59", marginBottom: 18 },
  title: { fontFamily: fonts.serif, fontSize: 38, lineHeight: 42, letterSpacing: -1, color: "#141413" },
  description: { fontFamily: fonts.serif, fontSize: 18, lineHeight: 26, color: "#5E5D59", marginTop: 16 },
  email: { fontFamily: fonts.sans, fontSize: 15, color: "#141413", marginTop: 12 },
  tabs: { flexDirection: "row", borderBottomWidth: 1, borderColor: "#D1CFC5", marginTop: 24, marginBottom: 24 },
  tab: { borderBottomWidth: 2, borderColor: "transparent", paddingVertical: 12, paddingHorizontal: 14 }, activeTab: { borderColor: "#141413" }, tabText: { fontFamily: fonts.sans, fontSize: 14, color: "#141413" },
  label: { fontFamily: fonts.mono, fontSize: 10, color: "#5E5D59", letterSpacing: .8, marginBottom: 8, marginTop: 16 },
  input: { borderWidth: 1, borderColor: "#B0AEA5", borderRadius: 8, minHeight: 46, paddingHorizontal: 13, fontFamily: fonts.sans, fontSize: 16, color: "#141413", backgroundColor: "#F0EEE6" },
  primary: { marginTop: 26, minHeight: 46, borderRadius: 8, backgroundColor: "#141413", flexDirection: "row", gap: 18, alignItems: "center", justifyContent: "center", paddingHorizontal: 20 }, primaryText: { fontFamily: fonts.sans, fontSize: 15, color: "#FAF9F5", fontWeight: "500" },
  hint: { fontFamily: fonts.sans, fontSize: 12, color: "#5E5D59", marginTop: 8 }, disabled: { opacity: .45 },
  activity: { fontFamily: fonts.sans, fontSize: 12, lineHeight: 19, color: "#5E5D59", marginTop: 8 },
  error: { fontFamily: fonts.sans, fontSize: 14, lineHeight: 21, color: "#A44735", marginTop: 20 }, notice: { fontFamily: fonts.serif, fontSize: 17, lineHeight: 24, color: "#4D6B50", marginTop: 20 },
});
