'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { ThemeToggle } from '@/components/ui/ThemeToggle'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const supabase = createClient()
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) { setError(error.message); setLoading(false) }
    else { router.push('/dashboard') }
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--c-bg)' }}>
      {/* Theme toggle */}
      <div className="fixed top-4 right-4">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl mb-4"
            style={{ background: 'var(--c-blue)' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2}
              strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            </svg>
          </div>
          <h1 className="text-2xl font-semibold mb-1" style={{ color: 'var(--c-ink)' }}>Welcome back</h1>
          <p className="text-sm" style={{ color: 'var(--c-ink-faint)' }}>Sign in to continue learning</p>
        </div>

        <form onSubmit={handleSubmit} className="nb-card rounded-2xl p-8 space-y-5">
          <div>
            <label htmlFor="email" className="block text-sm font-medium mb-1.5" style={{ color: 'var(--c-ink-soft)' }}>
              Email
            </label>
            <input id="email" type="email" required value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@university.edu" className="nb-input" />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium mb-1.5" style={{ color: 'var(--c-ink-soft)' }}>
              Password
            </label>
            <input id="password" type="password" required value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••" className="nb-input" />
          </div>

          {error && (
            <div className="rounded-xl px-4 py-3 text-sm"
              style={{ background: 'var(--c-red-soft)', border: '1px solid var(--c-red-border)', color: 'var(--c-red)' }}>
              {error}
            </div>
          )}

          <button id="login-submit" type="submit" disabled={loading}
            className="nb-btn-primary w-full justify-center py-3 rounded-xl text-sm font-semibold">
            {loading ? (
              <>
                <div className="w-4 h-4 rounded-full border-2 animate-spin"
                  style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} />
                Signing in…
              </>
            ) : 'Sign In'}
          </button>

          <p className="text-center text-sm" style={{ color: 'var(--c-ink-faint)' }}>
            No account?{' '}
            <Link href="/register" className="font-medium hover:underline" style={{ color: 'var(--c-blue)' }}>
              Register
            </Link>
          </p>
        </form>
      </div>
    </main>
  )
}
