"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";

export default function Callback() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [error, setError] = useState("");
  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const message = params.get("error_description") || new URLSearchParams(window.location.search).get("error_description");
    if (message) { setError(message); window.history.replaceState(null, "", window.location.pathname); }
    else if (!loading) {
      if (user) router.replace("/history");
      else setError("This confirmation link has expired or has already been used. Try signing in, or use forgot password to recover your account.");
    }
  }, [user, loading, router]);
  return <main className="account-loading"><span className="eyebrow">ADAPTIVEIQ</span><h1>{error ? "Let’s try again." : "Confirming your email…"}</h1><p role="status">{error}</p>{error && <Link href="/sign-in" className="btn-primary">Go to sign in</Link>}</main>;
}
