import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | undefined;
export function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) throw new Error("Account service is not configured. Please contact support.");
  client ??= createClient(url, key, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });
  return client;
}

export async function accessToken() {
  const { data, error } = await getSupabase().auth.getSession();
  if (error || !data.session) throw new Error("Please sign in to continue.");
  // getSession refreshes expired tokens; refresh proactively at the boundary.
  if (data.session.expires_at && data.session.expires_at * 1000 < Date.now() + 30000) {
    const refreshed = await getSupabase().auth.refreshSession();
    if (refreshed.error || !refreshed.data.session) throw new Error("Your session has expired. Please sign in again.");
    return refreshed.data.session.access_token;
  }
  return data.session.access_token;
}
