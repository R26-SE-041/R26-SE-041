import { Platform } from "react-native";
import { API_BASE_URL } from "./config";

export interface AccountUser { id: string; email: string; display_name: string; }
interface Session { access_token: string; refresh_token: string; expires_at: number; user: AccountUser; }
export interface AccountState { enabled: boolean; loading: boolean; user: AccountUser | null; error: string; }
const STORAGE_KEY = "sarmitha.auth.session.v1";
let session: Session | null = null;
let state: AccountState = { enabled: true, loading: true, user: null, error: "" };
let refreshPromise: Promise<string | null> | null = null;
const listeners = new Set<(value: AccountState) => void>();

function notify() {
  state = { ...state, user: session?.user ?? null };
  listeners.forEach(listener => listener(state));
}

function saveSession(value: Session | null) {
  session = value;
  if (value) state = { ...state, error: "" };
  if (Platform.OS === "web") {
    try {
      if (value) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch { /* In private mode, retain only the current in-memory session. */ }
  }
  notify();
}

export function subscribeAuth(listener: (value: AccountState) => void) {
  listeners.add(listener); listener(state);
  return () => { listeners.delete(listener); };
}

export function invalidateAccessToken(token: string | null) {
  if (token && session?.access_token === token) saveSession(null);
}

async function accountRequest(path: string, body?: object, token?: string) {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/auth/${path}`, {
      method: body ? "POST" : "GET",
      headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  } catch { throw new Error("We could not reach your account. Check your connection and try again."); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : "Please check your account details and try again.") as Error & { status: number };
    error.status = response.status; throw error;
  }
  return data;
}

export const getAccountUserId = () => session?.user.id ?? null;

export async function getAccessToken(expectedUserId: string | null = getAccountUserId()): Promise<string | null> {
  if (getAccountUserId() !== expectedUserId) throw new Error("Your account changed. Please try again.");
  if (!session) return null;
  if (session.expires_at > Date.now() / 1000 + 60) return session.access_token;
  if (!refreshPromise) {
    const previous = session;
    refreshPromise = (async () => {
      try {
        const data = await accountRequest("refresh", { refresh_token: previous.refresh_token });
        // A late refresh may never restore an account that signed out or changed.
        if (session !== previous) throw new Error("Your account changed. Please try again.");
        if (!data.session?.access_token) throw new Error("Please sign in again.");
        saveSession(data.session);
        return data.session.access_token as string;
      } catch (error) {
        if ((error as Error & { status?: number }).status === 401 && session === previous) saveSession(null);
        throw error;
      } finally { refreshPromise = null; }
    })();
  }
  return refreshPromise;
}

export async function initializeAuth() {
  try {
    const config = await accountRequest("config");
    state = { ...state, enabled: config.enabled === true, error: "" };
    if (state.enabled && Platform.OS === "web") {
      // Supabase email confirmations return a session in the URL fragment.
      // Remove it immediately and validate the token before trusting the account.
      const fragment = window.location?.hash;
      if (fragment && /(?:access_token|error_description)=/.test(fragment)) {
        const params = new URLSearchParams(fragment.slice(1));
        window.history.replaceState(null, "", window.location.pathname + window.location.search);
        if (params.get("error_description")) throw new Error("The confirmation link has expired. Please try signing in or request a new confirmation.");
        const access = params.get("access_token"), refresh = params.get("refresh_token");
        if (!access || !refresh) throw new Error("The confirmation link is incomplete. Please sign in again.");
        const user = await accountRequest("me", undefined, access);
        const seconds = Number(params.get("expires_in") || 3600);
        saveSession({ access_token: access, refresh_token: refresh, expires_at: Date.now() / 1000 + (Number.isFinite(seconds) ? Math.max(0, Math.min(seconds, 86400)) : 3600), user });
      }
      try {
        const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
        if (stored?.access_token && stored?.refresh_token && typeof stored.expires_at === "number" && stored.user?.id) session = stored;
      } catch { session = null; }
    }
    if (session && state.enabled) {
      const token = await getAccessToken();
      if (token) {
        const verifying = session;
        const user = await accountRequest("me", undefined, token);
        if (session === verifying && verifying) saveSession({ ...verifying, user });
      }
    }
  } catch (error) {
    if ((error as Error & { status?: number }).status === 401) saveSession(null);
    state = { ...state, error: (error as Error).message };
  } finally { state = { ...state, loading: false }; notify(); }
}

export async function signIn(email: string, password: string) {
  const data = await accountRequest("signin", { email, password });
  if (!data.session?.access_token) throw new Error("Please confirm your email before signing in.");
  saveSession(data.session);
}

export async function signUp(email: string, password: string, displayName: string): Promise<string | null> {
  const data = await accountRequest("signup", { email, password, display_name: displayName });
  if (data.session) { saveSession(data.session); return null; }
  return data.message || "Check your email to confirm your account, then sign in.";
}

export async function signOut() {
  const previous = session;
  saveSession(null);
  if (previous) await accountRequest("signout", {}, previous.access_token);
}

export function clearCrossTabSession(event: StorageEvent) {
  if (event.key === STORAGE_KEY && event.newValue === null) {
    session = null; notify();
  }
}
