"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { getSupabase } from "@/lib/supabase";
import type { ReactNode } from "react";
import { ArrowRightIcon } from "./Icons";

export default function AppHeader({ children, home = false }: { children?: ReactNode; home?: boolean }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function signOut() {
    setBusy(true); setError("");
    try {
      const { error } = await getSupabase().auth.signOut();
      if (error) throw error;
      router.replace("/sign-in");
    } catch { setError("Unable to sign out. Please try again."); }
    finally { setBusy(false); }
  }
  return (
    <header className="app-header">
      <Link href="/" className="app-wordmark" aria-label="AdaptiveIQ home">AdaptiveIQ</Link>
      <nav aria-label="Main navigation" className="account-nav">
        {home && !user && <div className="hidden lg:flex items-center gap-7 text-sm">
          <a className="nav-link" href="#how-it-works">How it works</a>
          <a className="nav-link" href="#features">Features</a>
        </div>}
        {!loading && (user ? <>
          <Link href="/history" className="nav-link">My quizzes</Link>
          <Link href="/account" className="nav-link">Account</Link>
          <button className="nav-link" disabled={busy} onClick={signOut}>{busy ? "Signing out…" : "Sign out"}</button>
        </> : <Link href="/sign-in" className="nav-link">Sign in</Link>)}
        {children ?? <Link href="/upload" className="btn-primary">Start quiz <ArrowRightIcon /></Link>}
        {error && <span role="alert" className="text-xs text-red-600">{error}</span>}
      </nav>
    </header>
  );
}
