import { useEffect, useState } from "react";
import { createClient, type Session } from "@supabase/supabase-js";
import { SUPABASE_ANON_KEY, SUPABASE_URL } from "./config";
import { authMessage, createAuthActions } from "./authActions";

const storageKey = "koji:studio-session:" + SUPABASE_URL;
const recoveryKey = storageKey + ":recovery";
const supabase = SUPABASE_URL && SUPABASE_ANON_KEY ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: { storageKey, persistSession: true, autoRefreshToken: true,
    detectSessionInUrl: typeof window !== "undefined" },
}) : null;
function readRecovery() {
  try { return typeof window !== "undefined" && (new URLSearchParams(window.location.hash.slice(1)).get("type") === "recovery" || window.sessionStorage.getItem(recoveryKey) === "true"); }
  catch { return false; }
}
function rememberRecovery(value: boolean) {
  try { if (value) window.sessionStorage.setItem(recoveryKey, "true"); else window.sessionStorage.removeItem(recoveryKey); } catch {}
}
function callbackError() {
  if (typeof window === "undefined") return null;
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const query = new URLSearchParams(window.location.search);
  return fragment.get("error_description") || query.get("error_description");
}
function cleanCallback() {
  if (typeof window !== "undefined" && window.location.pathname === "/auth/callback") {
    window.history.replaceState({}, "", "/");
  }
}
const actions = supabase ? createAuthActions(supabase.auth,
  typeof window !== "undefined" ? window.location.origin + "/auth/callback" : "") : null;

export function useStudioSession(externalToken?: string) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(Boolean(supabase && !externalToken));
  const [error, setError] = useState<string | null>(callbackError);
  const [recovering, setRecovering] = useState(readRecovery);
  useEffect(() => {
    if (!supabase || externalToken) { setLoading(false); return; }
    let active = true;
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, value) => {
      if (!active) return;
      setSession(value);
      if (event === "PASSWORD_RECOVERY") { rememberRecovery(true); setRecovering(true); }
      if (event === "SIGNED_OUT") { rememberRecovery(false); setRecovering(false); }
      // Keep callbacks synchronous: awaiting another SDK auth call here can deadlock.
      setLoading(false);
    });
    supabase.auth.getSession().then(({ data, error: failure }) => {
      if (!active) return;
      if (failure) setError(authMessage(failure));
      setSession(data.session);
      if (!data.session) { rememberRecovery(false); setRecovering(false); }
      setLoading(false); cleanCallback();
    }).catch(failure => {
      if (active) { setError(authMessage(failure)); setLoading(false); cleanCallback(); }
    });
    return () => { active = false; subscription.unsubscribe(); };
  }, [externalToken]);
  async function run<T>(action: () => Promise<T>) {
    setError(null);
    if (!actions) throw new Error("Account services are not configured.");
    try { return await action(); }
    catch (failure) { const message = authMessage(failure); setError(message); throw failure instanceof Error ? failure : new Error(message); }
  }
  return {
    token: externalToken ?? (loading ? undefined : session?.access_token),
    email: session?.user.email, name: session?.user.user_metadata?.full_name as string | undefined,
    loading, recovering, error, configured: Boolean(supabase),
    clearError: () => setError(null),
    signIn: (email: string, password: string) => run(() => actions!.signIn(email, password)),
    signUp: (name: string, email: string, password: string, confirmation: string) => run(() => actions!.signUp(name, email, password, confirmation)),
    resetPassword: (email: string) => run(() => actions!.resetPassword(email)),
    resendVerification: (email: string) => run(() => actions!.resendVerification(email)),
    updatePassword: (password: string, confirmation: string) => run(async () => {
      await actions!.updatePassword(password, confirmation);
      await actions!.signOut();
      rememberRecovery(false); setRecovering(false);
    }),
    signOut: () => run(() => actions!.signOut()),
  };
}
