import React, { useEffect, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View, useWindowDimensions } from "react-native";
import type { useStudioSession } from "../studioAuth";
import Icon from "./Icon";
import { authErrorCode } from "../authActions";
import { useAppTheme } from "../theme";

type Mode = "signin" | "signup" | "forgot" | "verify" | "password";
const paths: Record<Mode, string> = { signin: "/signin", signup: "/signup", forgot: "/forgot-password", verify: "/verify-email", password: "/reset-password" };
function pageMode(): Mode {
  if (typeof window === "undefined") return "signin";
  return (Object.keys(paths) as Mode[]).find(mode => paths[mode] === window.location.pathname) || "signin";
}
type Props = { session: ReturnType<typeof useStudioSession> };

export default function AuthScreen({ session }: Props) {
  const { colors, mode: theme, toggleTheme } = useAppTheme();
  const wide = useWindowDimensions().width >= 900;
  const [mode, setMode] = useState<Mode>(() => session.recovering ? "password" : pageMode());
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [visible, setVisible] = useState(false);
  const [confirmationVisible, setConfirmationVisible] = useState(false);
  const [needsVerification, setNeedsVerification] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => {
    if (session.recovering) setMode("password");
    else if (!session.loading) setMode(current => current === "password" ? "signin" : current);
  }, [session.recovering, session.loading]);
  useEffect(() => {
    if (typeof window === "undefined" || session.loading) return;
    if (window.location.pathname !== paths[mode]) window.history.replaceState({}, "", paths[mode]);
    document.title = (mode === "signup" ? "Create account" : mode === "signin" ? "Sign in" : mode === "forgot" ? "Forgot password" : mode === "password" ? "Reset password" : "Verify email") + " | learnX";
  }, [mode, session.loading]);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const onBack = () => { setMode(session.recovering ? "password" : pageMode()); setError(null); setMessage(null); setPassword(""); setConfirmation(""); };
    window.addEventListener("popstate", onBack);
    return () => window.removeEventListener("popstate", onBack);
  }, [session.recovering]);
  const disabled = busy || session.loading || !session.configured;
  const switchMode = (value: Mode) => {
    if (busy) return;
    if (typeof window !== "undefined") window.history.pushState({}, "", paths[value]);
    setMode(value); setNeedsVerification(false); setError(null); setMessage(null); session.clearError();
    setPassword(""); setConfirmation(""); setVisible(false); setConfirmationVisible(false);
  };
  const submit = async () => {
    if (disabled) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      if (mode === "signin") { setNeedsVerification(false); await session.signIn(email, password); }
      if (mode === "signup") {
        const result = await session.signUp(name, email, password, confirmation);
        if (result.confirmationRequired) { setMode("verify"); setPassword(""); setConfirmation(""); }
      }
      if (mode === "forgot") {
        await session.resetPassword(email);
        setMessage("If an account exists for this email, a password reset link will arrive shortly. Check your spam folder too.");
      }
      if (mode === "password") {
        await session.updatePassword(password, confirmation);
        setMode("signin"); setPassword(""); setConfirmation("");
        setMessage("Password updated. Sign in with your new password.");
      }
    } catch (failure) {
      if (mode === "signin" && authErrorCode(failure) === "email_not_confirmed") setNeedsVerification(true);
      setError(failure instanceof Error ? failure.message : "Please try again.");
    }
    finally { setBusy(false); }
  };
  const resend = async () => {
    if (disabled) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      await session.resendVerification(email);
      setMessage("If your account is awaiting confirmation, a new verification email will arrive shortly.");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Unable to resend verification."); }
    finally { setBusy(false); }
  };
  const headings = {
    signin: ["Welcome back.", "Sign in to continue your visual learning journey."],
    signup: ["Make room for ideas.", "Create your account. Keep every creation and conversation together."],
    forgot: ["Forgot your password?", "Enter your account email and we'll send you a reset link."],
    verify: ["Check your inbox.", "Confirm your email to start creating."],
    password: ["Choose a new password.", "Set a new password for your account."],
  } as const;
  const label = { color: colors.text, fontSize: 13, fontWeight: "600" as const, marginBottom: 7 };
  const input = { color: colors.text, backgroundColor: colors.surfaceSoft, borderColor: colors.textDim, borderWidth: 1, borderRadius: 12, minHeight: 50, paddingHorizontal: 14, fontSize: 15 };
  const link = { color: colors.primaryBright, fontWeight: "600" as const, fontSize: 13 };
  const button = { padding: 12, minHeight: 44, justifyContent: "center" as const };
  const passwordInput = (confirm = false) => <View style={{ marginTop: 18 }}>
    <Text style={label}>{confirm ? "Confirm password" : mode === "password" ? "New password" : "Password"}</Text>
    <View style={{ position: "relative" }}>
      <TextInput accessibilityLabel={confirm ? "Confirm password" : mode === "password" ? "New password" : "Password"}
        value={confirm ? confirmation : password} onChangeText={confirm ? setConfirmation : setPassword}
        secureTextEntry={!(confirm ? confirmationVisible : visible)} autoCapitalize="none" autoCorrect={false} editable={!disabled}
        autoComplete={mode === "signin" ? "current-password" : "new-password"} maxLength={128}
        placeholder={mode === "signin" ? "Enter your password" : "At least 8 characters"}
        placeholderTextColor={colors.textDim} onSubmitEditing={() => void submit()} style={[input, { width: "100%", height: 50, paddingRight: 52 }]} />
      <Pressable accessibilityRole="button" accessibilityLabel={(confirm ? confirmationVisible : visible) ? (confirm ? "Hide confirm password" : "Hide password") : (confirm ? "Show confirm password" : "Show password")}
        accessibilityState={{ disabled }} disabled={disabled}
        onPress={() => confirm ? setConfirmationVisible(!confirmationVisible) : setVisible(!visible)}
        style={{ position: "absolute", right: 4, top: 3, width: 44, height: 44, justifyContent: "center", alignItems: "center" }}>
        <Icon name={(confirm ? confirmationVisible : visible) ? "eye-off" : "eye"} color={colors.textMuted} size={20} />
      </Pressable>
    </View>
  </View>;
  return <KeyboardAvoidingView style={{ flex: 1, backgroundColor: colors.background }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
    <ScrollView contentContainerStyle={{ flexGrow: 1, padding: wide ? 48 : 22 }} keyboardShouldPersistTaps="handled">
      <View style={{ width: "100%", maxWidth: 1240, alignSelf: "center", flex: 1 }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: wide ? 64 : 30 }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <View style={{ backgroundColor: colors.primary, borderRadius: 12, width: 40, height: 40, alignItems: "center", justifyContent: "center" }}><Text style={{ color: "#fff", fontWeight: "800", fontSize: 22 }}>L</Text></View>
            <Text style={{ color: colors.text, fontWeight: "800", fontSize: 23 }}>learnX</Text>
          </View>
          <Pressable accessibilityRole="button" accessibilityLabel={theme === "light" ? "Switch to dark mode" : "Switch to light mode"} onPress={toggleTheme} style={[button, { width: 44, alignItems: "center" }]}><Icon name={theme === "light" ? "moon" : "sun"} color={colors.textMuted} size={21} /></Pressable>
        </View>
        <View style={{ flexDirection: wide ? "row" : "column", gap: wide ? 80 : 28, alignItems: wide ? "center" : "stretch", flex: 1, paddingBottom: 40 }}>
          <View style={{ flex: 1, gap: 20 }}>
            <Text style={{ color: colors.primaryBright, letterSpacing: 2.5, fontSize: 11, fontWeight: "700" }}>YOUR VISUAL LEARNING STUDIO</Text>
            <Text style={{ color: colors.text, fontSize: wide ? 62 : 36, lineHeight: wide ? 68 : 42, fontWeight: "800", maxWidth: 550 }}>An idea. A drawing.{"\n"}A whole new perspective.</Text>
            <Text style={{ color: colors.textMuted, fontSize: 17, lineHeight: 27, maxWidth: 450 }}>Bring your ideas to life, explore the details, and pick up exactly where you left off.</Text>
            {wide && <View style={{ gap: 12, marginTop: 18 }}>
              {[
                ["01", "Create", "Turn a prompt or sketch into a visual."],
                ["02", "Explore", "Ask questions, edit labels, and discover in 3D."],
                ["03", "Continue", "Your images and conversations, saved together."],
              ].map(([number, title, body]) => <View key={number} style={{ flexDirection: "row", gap: 16, padding: 18, backgroundColor: colors.surface, borderRadius: 18, maxWidth: 450 }}>
                <Text style={{ color: colors.primaryBright, fontSize: 14, fontWeight: "700", paddingTop: 2 }}>{number}</Text>
                <View style={{ flex: 1 }}><Text style={{ color: colors.text, fontSize: 16, fontWeight: "700" }}>{title}</Text><Text style={{ color: colors.textMuted, lineHeight: 21, marginTop: 3 }}>{body}</Text></View>
              </View>)}
            </View>}
          </View>
          <View style={{ width: wide ? 440 : "100%", maxWidth: 520, alignSelf: wide ? "center" : "stretch", backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 28, padding: wide ? 32 : 24 }}>
            <Text accessibilityRole="header" style={{ color: colors.text, fontSize: 29, fontWeight: "800", lineHeight: 35 }}>{headings[mode][0]}</Text>
            <Text style={{ color: colors.textMuted, lineHeight: 22, marginTop: 10, marginBottom: 24 }}>{headings[mode][1]}</Text>
            {session.loading && <View style={{ flexDirection: "row", gap: 10, alignItems: "center", marginBottom: 12 }}><ActivityIndicator color={colors.primary} /><Text style={{ color: colors.textMuted }}>Checking your session…</Text></View>}
            {!session.configured && <Text accessibilityRole="alert" style={{ color: colors.danger }}>Account services are unavailable. Please contact the project administrator.</Text>}
            {mode === "verify" ? <View style={{ gap: 14 }}>
              <Text style={{ color: colors.text, fontWeight: "600" }}>{email.trim()}</Text>
              <Text style={{ color: colors.textMuted, lineHeight: 23 }}>Open the verification link in your email. If you already have an account, you can sign in instead. Check your spam folder if the email hasn't arrived.</Text>
              <Pressable accessibilityRole="button" disabled={disabled} onPress={() => void resend()} style={button}><Text style={link}>{busy ? "Sending…" : "Resend verification email"}</Text></Pressable>
            </View> : <>
              {mode === "signup" && <View style={{ marginBottom: 18 }}><Text style={label}>Your name</Text><TextInput accessibilityLabel="Your name" value={name} onChangeText={setName} editable={!disabled} autoComplete="name" maxLength={80} placeholder="Your name" placeholderTextColor={colors.textDim} style={input} /></View>}
              {mode !== "password" && <View><Text style={label}>Email address</Text><TextInput accessibilityLabel="Email address" value={email} onChangeText={value => { setEmail(value); setNeedsVerification(false); setError(null); session.clearError(); }} editable={!disabled} keyboardType="email-address" autoCapitalize="none" autoCorrect={false} autoComplete="email" maxLength={254} placeholder="you@example.com" placeholderTextColor={colors.textDim} onSubmitEditing={() => { if (mode === "forgot") void submit(); }} style={input} /></View>}
              {(mode === "signin" || mode === "signup" || mode === "password") && passwordInput()}
              {(mode === "signup" || mode === "password") && passwordInput(true)}
              {mode === "signup" && <Text style={{ color: colors.textDim, fontSize: 12, lineHeight: 18, marginTop: 10 }}>Use at least 8 characters. We'll send an email to verify your account.</Text>}
              {mode === "signin" && <Pressable accessibilityRole="button" disabled={busy} onPress={() => switchMode("forgot")} style={[button, { alignSelf: "flex-end" }]}><Text style={link}>Forgot password?</Text></Pressable>}
              <Pressable accessibilityRole="button" accessibilityLabel={mode === "signin" ? "Sign in to studio" : mode === "signup" ? "Create your account" : mode === "forgot" ? "Send reset link" : "Save new password"}
                accessibilityState={{ disabled, busy }} disabled={disabled} onPress={() => void submit()}
                style={{ backgroundColor: colors.primary, minHeight: 52, borderRadius: 12, marginTop: 22, padding: 14, alignItems: "center", justifyContent: "center", opacity: disabled ? .6 : 1 }}>
                {busy ? <ActivityIndicator color="#fff" /> : <Text style={{ color: "#fff", fontWeight: "700", fontSize: 15 }}>{mode === "signin" ? "Sign in to studio" : mode === "signup" ? "Create your account" : mode === "forgot" ? "Send reset link" : "Save new password"}</Text>}
              </Pressable>
            </>}
            {(error || session.error) && <Text accessibilityRole="alert" style={{ color: colors.danger, lineHeight: 22, marginTop: 16 }}>{error || session.error}</Text>}
            {message && <Text accessibilityRole="alert" style={{ color: colors.success, lineHeight: 22, marginTop: 16 }}>{message}</Text>}
            {(mode === "signin" || mode === "signup") && <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", justifyContent: "center", marginTop: 16 }}><Text style={{ color: colors.textMuted }}>{mode === "signin" ? "New to learnX?" : "Already have an account?"}</Text><Pressable accessibilityRole="button" disabled={busy} onPress={() => switchMode(mode === "signin" ? "signup" : "signin")} style={button}><Text style={link}>{mode === "signin" ? "Create account" : "Sign in"}</Text></Pressable></View>}
            {mode === "signin" && needsVerification && <Pressable accessibilityRole="button" disabled={disabled} onPress={() => void resend()} style={[button, { marginTop: 10 }]}><Text style={link}>Resend verification email</Text></Pressable>}
            {mode !== "signin" && mode !== "signup" && <Pressable accessibilityRole="button" disabled={busy} onPress={() => { if (mode === "password") { void session.signOut().then(() => switchMode("signin")).catch(failure => setError(failure.message)); } else switchMode("signin"); }} style={[button, { marginTop: 18 }]}><Text style={link}>Back to sign in</Text></Pressable>}
            <Text style={{ color: colors.textDim, fontSize: 12, lineHeight: 18, marginTop: 24 }}>Your creations and conversations belong to your account.</Text>
          </View>
        </View>
      </View>
    </ScrollView>
  </KeyboardAvoidingView>;
}
