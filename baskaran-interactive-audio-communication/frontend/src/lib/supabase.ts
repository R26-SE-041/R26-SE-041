/** Mock Supabase client for Phase 1/2 testing (no real auth needed) */
export function createClient() {
  return {
    auth: {
      getSession: async () => ({
        data: { session: null as { user: { id: string }; access_token: string } | null },
      }),
      onAuthStateChange: (_event: string, _cb: unknown) => ({
        data: { subscription: { unsubscribe: () => {} } },
      }),
      signInWithPassword: async (_creds: { email: string; password: string }) => ({
        data: { session: null },
        error: null as { message: string } | null,
      }),
      signUp: async (_creds: { email: string; password: string; options?: unknown }) => ({
        data: { user: null },
        error: null as { message: string } | null,
      }),
      signOut: async () => {},
    },
  }
}
