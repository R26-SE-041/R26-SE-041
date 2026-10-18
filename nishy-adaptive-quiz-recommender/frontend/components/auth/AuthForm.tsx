"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { getSupabase } from "@/lib/supabase";
import { useAuth } from "./AuthProvider";
import AppHeader from "@/components/ui/AppHeader";

type Mode = "sign-in" | "sign-up" | "forgot-password" | "reset-password" | "account";
const copy = {
  "sign-in": ["Welcome back.", "Your next breakthrough starts here.", "Sign in"],
  "sign-up": ["Make room for growth.", "A personal space for your Biology learning journey.", "Create account"],
  "forgot-password": ["Let’s get you back in.", "We’ll email you a secure link to reset your password.", "Send reset link"],
  "reset-password": ["A fresh start.", "Choose a strong new password for your account.", "Save new password"],
  account: ["Your account.", "Keep your learning space secure.", "Change password"],
};
export default function AuthForm({ mode }: { mode: Mode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [visible, setVisible] = useState(false);
  const [done, setDone] = useState(false);
  const passwordMode = mode !== "forgot-password";
  const newPassword = mode !== "sign-in";
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setError(""); setMessage(""); setBusy(true);
    const form = new FormData(e.currentTarget);
    const email = String(form.get("email") ?? user?.email ?? "").trim();
    const password = String(form.get("password") ?? "");
    try {
      if (passwordMode && newPassword && (password.length < 8 || !/[a-zA-Z]/.test(password) || !/[0-9]/.test(password))) {
        throw new Error("Use at least 8 characters, including a letter and a number.");
      }
      if (passwordMode && newPassword && password !== form.get("confirm")) throw new Error("The passwords do not match.");
      const auth = getSupabase().auth;
      const origin = window.location.origin;
      if (mode === "sign-in") {
        const result = await auth.signInWithPassword({ email, password });
        if (result.error) throw result.error;
        const next = new URLSearchParams(window.location.search).get("next") ?? "/history";
        router.replace(/^\/(upload|quiz|history|account)(\/|$)/.test(next) && !next.includes("\\") ? next : "/history");
      } else if (mode === "sign-up") {
        const result = await auth.signUp({ email, password, options: {
          data: { display_name: String(form.get("name") ?? "").trim() }, emailRedirectTo: origin + "/auth/callback",
        } });
        if (result.error) throw result.error;
        if (result.data.session) router.replace("/history");
        else { setDone(true); setMessage("Check your inbox to confirm your email, then sign in. If you already have an account, sign in or reset your password."); }
      } else if (mode === "forgot-password") {
        const result = await auth.resetPasswordForEmail(email, { redirectTo: origin + "/reset-password" });
        if (result.error) throw result.error;
        setDone(true); setMessage("If an account exists for this email, a reset link is on its way. Check your inbox and spam folder.");
      } else {
        if (mode === "account") {
          const verified = await auth.signInWithPassword({ email, password: String(form.get("current") ?? "") });
          if (verified.error) throw new Error("Your current password is incorrect.");
        }
        const result = await auth.updateUser({ password });
        if (result.error) throw result.error;
        // Revoke sessions on other devices after changing credentials.
        const logout = await auth.signOut({ scope: "others" });
        setDone(true); setMessage(logout.error ? "Password updated. You can manage other sessions by signing out of all devices." : "Password updated successfully. Other devices have been signed out.");
      }
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong. Please try again."); }
    finally { setBusy(false); }
  }
  return <><AppHeader /><main className="auth-layout">
    <aside className="auth-story"><span className="eyebrow">YOUR LEARNING, CONNECTED</span><h2>Small steps.<br /><em>Lasting progress.</em></h2>
      <p>Practise at your pace. Pick up where you left off. See how far you’ve come.</p>
      <div className="auth-orbit" aria-hidden="true"><span>learn</span><span>reflect</span><span>grow</span><i>↗</i></div>
      <p className="auth-note">A personal quiz library. Thoughtful feedback. A little more confidence, every time.</p>
    </aside>
    <section className="auth-panel"><span className="eyebrow">{mode === "account" ? "ACCOUNT SETTINGS" : "WELCOME TO ADAPTIVEIQ"}</span>
      <h1>{copy[mode][0]}</h1><p className="muted">{copy[mode][1]}</p>
      {mode === "account" && <p className="account-email">{user?.email}</p>}
      {error && <div className="form-alert error" role="alert">{error}</div>}
      {message && <div className="form-alert success" role="status">{message}</div>}
      {mode === "reset-password" && loading ? <div className="form-alert" role="status">Verifying your recovery link…</div> : mode === "reset-password" && !user ? <div className="form-alert">Open the latest reset link from your email. <Link href="/forgot-password">Request a new link</Link></div> : !done && <form onSubmit={submit} className="account-form">
        {mode === "sign-up" && <label>Your name<input name="name" autoComplete="name" required maxLength={80} placeholder="How should we call you?" /></label>}
        {!["account", "reset-password"].includes(mode) && <label>Email address<input name="email" type="email" autoComplete="email" required maxLength={254} placeholder="you@example.com" /></label>}
        {mode === "account" && <label>Current password<input name="current" type="password" autoComplete="current-password" required /></label>}
        {passwordMode && <><label>{newPassword ? "New password" : "Password"}<div className="password-input"><input name="password" aria-label={newPassword ? "New password" : "Password"} type={visible ? "text" : "password"} autoComplete={newPassword ? "new-password" : "current-password"} minLength={newPassword ? 8 : 1} required maxLength={128} /><button type="button" onClick={() => setVisible(!visible)} aria-label={visible ? "Hide password" : "Show password"}>{visible ? "Hide" : "Show"}</button></div></label>
          {newPassword && <><p className="field-help">At least 8 characters, with a letter and a number.</p><label>Confirm new password<input name="confirm" type="password" autoComplete="new-password" required maxLength={128} /></label></>}
        </>}
        {mode === "sign-in" && <Link href="/forgot-password" className="forgot-link">Forgot password?</Link>}
        <button className="btn-primary account-submit" disabled={busy || (mode === "reset-password" && (loading || !user))} type="submit">{busy ? "Please wait…" : copy[mode][2]} <span aria-hidden="true">↗</span></button>
      </form>}
      <div className="auth-footer">{mode === "sign-in" ? <>New here? <Link href="/sign-up">Create an account</Link></> : mode === "sign-up" ? <>Already have an account? <Link href="/sign-in">Sign in</Link></> : <Link href={user ? "/history" : "/sign-in"}>← {user ? "Back to my quizzes" : "Back to sign in"}</Link>}</div>
    </section></main></>;
}
