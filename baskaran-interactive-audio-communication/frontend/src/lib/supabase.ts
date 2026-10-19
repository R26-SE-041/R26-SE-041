import { createClient as createSupabaseClient, type Session } from '@supabase/supabase-js'

const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim()
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim()
export const AUTH_CONFIGURED = Boolean(url && key)
const local = typeof window !== 'undefined' && ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)
const unavailable = () => local ? null : { message: 'Login setup is pending. Please try again after the backend is connected.' }

// Preserve the local demo while public builds never pretend a login succeeded.
const demo = {
  auth: {
    getSession: async () => ({ data: { session: null as Session | null }, error: null }),
    onAuthStateChange: (_cb: (event: string, session: Session | null) => void) => ({
      data: { subscription: { unsubscribe: () => {} } },
    }),
    signInWithPassword: async (_creds: { email: string; password: string }) => ({
      data: { session: null }, error: unavailable(),
    }),
    signUp: async (_creds: { email: string; password: string; options?: { data?: object; emailRedirectTo?: string } }) => ({
      data: { user: null, session: null }, error: unavailable(),
    }),
    signOut: async () => ({ error: null }),
  },
}

let client: ReturnType<typeof createSupabaseClient> | undefined
export function createClient() {
  if (!url || !key) return demo
  client ??= createSupabaseClient(url, key, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  })
  return client
}
