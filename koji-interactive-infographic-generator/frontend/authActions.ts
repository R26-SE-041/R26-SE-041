import type { SupabaseClient } from "@supabase/supabase-js";

type Auth = SupabaseClient["auth"];
export function validateEmail(email: string) {
  const value = email.trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) || value.length > 254) {
    throw new Error("Enter a valid email address.");
  }
  return value;
}
export function validateNewPassword(password: string, confirmation: string) {
  if (password.length < 8) throw new Error("Use at least 8 characters for your password.");
  if (password.length > 128) throw new Error("Use a password with 128 characters or fewer.");
  if (password !== confirmation) throw new Error("Passwords do not match.");
}
export function authMessage(error: unknown): string {
  const value = error as { code?: string; status?: number; message?: string };
  if (value?.status === 429 || value?.code?.includes("rate_limit")) return "Too many attempts. Please wait a few minutes and try again.";
  if (value?.code === "invalid_credentials") return "Email or password is incorrect.";
  if (value?.code === "email_not_confirmed") return "Confirm your email before signing in. You can resend the verification email below.";
  if (value?.code === "signup_disabled") return "New accounts are currently disabled. Contact the project administrator.";
  if (value?.message && /fetch|network/i.test(value.message)) return "Unable to connect. Check your internet connection and try again.";
  return value?.message || "Unable to complete this request. Please try again.";
}
export function authErrorCode(error: unknown): string | null {
  if (!error || typeof error !== "object" || !("code" in error)) return null;
  return typeof error.code === "string" ? error.code : null;
}
class AuthActionError extends Error {
  readonly code: string | null;
  constructor(error: unknown) { super(authMessage(error)); this.code = authErrorCode(error); }
}
function check(error: unknown) { if (error) throw new AuthActionError(error); }

/** Supabase owns passwords/users; EC2 validates its access tokens. */
export function createAuthActions(auth: Auth, redirectTo: string) {
  return {
    async signIn(email: string, password: string) {
      if (!password) throw new Error("Enter your password.");
      const { data, error } = await auth.signInWithPassword({ email: validateEmail(email), password });
      check(error);
      return data.session;
    },
    async signUp(name: string, email: string, password: string, confirmation: string) {
      validateNewPassword(password, confirmation);
      if (!name.trim() || name.trim().length > 80) throw new Error("Enter your name using 80 characters or fewer.");
      const { data, error } = await auth.signUp({ email: validateEmail(email), password,
        options: { emailRedirectTo: redirectTo, data: { full_name: name.trim() } } });
      check(error);
      return { confirmationRequired: !data.session };
    },
    async resetPassword(email: string) {
      const { error } = await auth.resetPasswordForEmail(validateEmail(email), { redirectTo });
      check(error);
    },
    async resendVerification(email: string) {
      const { error } = await auth.resend({ type: "signup", email: validateEmail(email), options: { emailRedirectTo: redirectTo } });
      check(error);
    },
    async updatePassword(password: string, confirmation: string) {
      validateNewPassword(password, confirmation);
      const { error } = await auth.updateUser({ password });
      check(error);
    },
    async signOut() {
      const { error } = await auth.signOut({ scope: "local" });
      check(error);
    },
  };
}
