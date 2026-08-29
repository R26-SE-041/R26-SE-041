'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase'
import { ThemeToggle } from '@/components/ui/ThemeToggle'

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
      email, password, options: { data: { full_name: fullName } },
    })
    if (error) { setError(error.message); setLoading(false) }
    else { setSuccess(true) }
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--c-bg)' }}>
      <div className="fixed top-4 right-4"><ThemeToggle /></div>

      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl mb-4"
            style={{ background: 'var(--c-blue)' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2}
              strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            </svg>
          </div>
          <h1 className="text-2xl font-semibold mb-1" style={{ color: 'var(--c-ink)' }}>Create account</h1>
          <p className="text-sm" style={{ color: 'var(--c-ink-faint)' }}>Start learning with your voice today</p>
        </div>

        {success ? (
          <div className="nb-card rounded-2xl p-8 text-center space-y-4">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto"
              style={{ background: 'var(--c-green-soft)', border: '1px solid var(--c-green-border)' }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
                stroke="var(--c-green)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold" style={{ color: 'var(--c-ink)' }}>Check your email</h2>
              <p className="text-sm mt-1" style={{ color: 'var(--c-ink-faint)' }}>
                We sent a link to <span className="font-medium" style={{ color: 'var(--c-ink)' }}>{email}</span>
              </p>
            </div>
            <Link href="/login" className="inline-block text-sm font-medium hover:underline" style={{ color: 'var(--c-blue)' }}>
              Back to sign in →
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="nb-card rounded-2xl p-8 space-y-5">
            {[
              { id: 'full-name', label: 'Full Name', type: 'text', value: fullName, set: setFullName, placeholder: 'Arun Kumar', required: false },
              { id: 'reg-email', label: 'University Email', type: 'email', value: email, set: setEmail, placeholder: 'you@university.edu', required: true },
              { id: 'reg-password', label: 'Password', type: 'password', value: password, set: setPassword, placeholder: 'Min. 8 characters', required: true },
            ].map(({ id, label, type, value, set, placeholder, required }) => (
              <div key={id}>
                <label htmlFor={id} className="block text-sm font-medium mb-1.5" style={{ color: 'var(--c-ink-soft)' }}>
                  {label}
                </label>
                <input id={id} type={type} required={required} value={value}
                  onChange={(e) => set(e.target.value)} placeholder={placeholder}
                  minLength={type === 'password' ? 8 : undefined} className="nb-input" />
              </div>
            ))}

            {error && (
              <div className="rounded-xl px-4 py-3 text-sm"
                style={{ background: 'var(--c-red-soft)', border: '1px solid var(--c-red-border)', color: 'var(--c-red)' }}>
                {error}
              </div>
            )}

            <button id="register-submit" type="submit" disabled={loading}
              className="nb-btn-primary w-full justify-center py-3 rounded-xl text-sm font-semibold">
              {loading ? (
                <>
                  <div className="w-4 h-4 rounded-full border-2 animate-spin"
                    style={{ borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} />
                  Creating account…
                </>
              ) : 'Create Account'}
            </button>

            <p className="text-center text-sm" style={{ color: 'var(--c-ink-faint)' }}>
              Already have an account?{' '}
              <Link href="/login" className="font-medium hover:underline" style={{ color: 'var(--c-blue)' }}>
                Sign in
              </Link>
            </p>
          </form>
        )}
      </div>
    </main>
  )
}
