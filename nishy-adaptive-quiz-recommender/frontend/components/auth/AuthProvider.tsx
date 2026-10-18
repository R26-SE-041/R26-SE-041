"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { User } from "@supabase/supabase-js";
import { getSupabase } from "@/lib/supabase";

const Context = createContext<{ user: User | null; loading: boolean }>({ user: null, loading: true });
export const useAuth = () => useContext(Context);

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const path = usePathname();
  const router = useRouter();
  const protectedPage = /^\/(upload|quiz|history|account)(\/|$)/.test(path);
  useEffect(() => {
    try {
      const auth = getSupabase().auth;
      const { data: { subscription } } = auth.onAuthStateChange((event, session) => {
        setUser(session?.user ?? null);
        setLoading(false);
        if (event === "PASSWORD_RECOVERY") router.replace("/reset-password");
      });
      auth.getSession().then(({ data, error }) => {
        if (error) setError(error.message);
        setUser(data.session?.user ?? null);
        setLoading(false);
      }).catch(() => { setError("Unable to load your account. Please refresh."); setLoading(false); });
      return () => subscription.unsubscribe();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Account service unavailable.");
      setLoading(false);
    }
  }, [router]);
  useEffect(() => {
    if (protectedPage && !loading && !user && !error) router.replace("/sign-in?next=" + encodeURIComponent(path));
  }, [protectedPage, loading, user, error, path, router]);
  return <Context.Provider value={{ user, loading }}>
    {protectedPage && (loading || !user) ? <main className="account-loading" role="status">
      <span className="eyebrow">ADAPTIVEIQ</span><p>{error || (loading ? "Opening your learning space…" : "Taking you to sign in…")}</p>
    </main> : <div key={user?.id ?? "public"}>{children}</div>}
  </Context.Provider>;
}
