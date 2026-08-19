'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'

export default function RegisterPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const supabase = createClient()
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: fullName } },
    })
    if (error) {
      setError(error.message)
      setLoading(false)
    } else {
      setSuccess(true)
    }
  }

  return (
    <main className="min-h-screen bg-hero-gradient flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-2">
            <span className="glow-dot" />
            <span className="font-bold text-xl">VoiceLearn AI</span>
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Create account</h1>
          <p className="text-white/40 text-sm">Start learning with your voice today</p>
        </div>

        {success ? (
          <div className="glass-strong rounded-3xl p-8 text-center space-y-4">
            <div className="text-5xl">📬</div>
            <h2 className="text-xl font-semibold text-white">Check your email</h2>
            <p className="text-white/50 text-sm">We sent a confirmation link to <strong className="text-white">{email}</strong></p>
            <Link href="/login" className="inline-block text-brand-400 hover:text-brand-300 text-sm transition-colors">
              Back to sign in →
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="glass-strong rounded-3xl p-8 space-y-5">
            <div>
              <label htmlFor="full-name" className="block text-sm text-white/60 mb-1.5">Full Name</label>
              <input
                id="full-name"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Arun Kumar"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/50 transition-all"
              />
            </div>

            <div>
              <label htmlFor="reg-email" className="block text-sm text-white/60 mb-1.5">University Email</label>
              <input
                id="reg-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@university.edu"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/50 transition-all"
              />
            </div>

            <div>
              <label htmlFor="reg-password" className="block text-sm text-white/60 mb-1.5">Password</label>
              <input
                id="reg-password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 8 characters"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/50 transition-all"
              />
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-sm text-red-400">
                {error}
              </div>
            )}

            <button
              id="register-submit"
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-brand-600 to-accent-600 hover:from-brand-500 hover:to-accent-500 text-white font-semibold py-3.5 rounded-xl transition-all shadow-brand hover:shadow-brand-lg disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]"
            >
              {loading ? 'Creating account…' : 'Create Account'}
            </button>

            <p className="text-center text-sm text-white/40">
              Already have an account?{' '}
              <Link href="/login" className="text-brand-400 hover:text-brand-300 transition-colors">
                Sign in
              </Link>
            </p>
          </form>
        )}
      </div>
    </main>
  )
}
