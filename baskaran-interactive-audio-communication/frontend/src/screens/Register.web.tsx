import { useState, type FormEvent } from 'react'
import { useRouter } from '@/web/navigation'
import Link from '@/web/navigation'
import { AUTH_CONFIGURED, createClient } from '@/lib/supabase'
import { ThemeToggle } from '@/components/ui/ThemeToggle'

type Field = 'name' | 'email' | 'password' | 'confirm'
type FieldErrors = Partial<Record<Field, string>>
const ids: Record<Field, string> = { name: 'full-name', email: 'reg-email', password: 'reg-password', confirm: 'confirm-password' }

export default function RegisterPage() {
  const router = useRouter()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [role, setRole] = useState('student')
  const [institution, setInstitution] = useState('')
  const [language, setLanguage] = useState('english')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  // Guidance based on length, without forcing arbitrary character combinations.
  const strength = password.length < 8 ? 0 : password.length >= 16 ? 3 : password.length >= 12 ? 2 : 1
  const strengthLabels = ['Too short', 'Meets the minimum', 'Good length', 'Strong length']

  function clearField(field: Field) {
    setErrors(current => ({ ...current, [field]: undefined }))
    setError('')
  }
  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (loading) return
    setError('')
    const invalid: FieldErrors = {}
    const name = fullName.trim(), address = email.trim()
    if (!name) invalid.name = 'Enter your full name.'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address)) invalid.email = 'Enter a valid email address.'
    if (password.length < 8) invalid.password = 'Use at least 8 characters.'
    if (!confirmPassword) invalid.confirm = 'Confirm your password.'
    else if (password !== confirmPassword) invalid.confirm = 'The passwords do not match.'
    setErrors(invalid)
    const first = Object.keys(invalid)[0] as Field | undefined
    if (first) { document.getElementById(ids[first])?.focus(); return }
    if (!AUTH_CONFIGURED) {
      setError('Account registration is not connected in this preview. Please use the hosted app to create an account.')
      return
    }
    setLoading(true)
    try {
      const { data, error: signupError } = await createClient().auth.signUp({
        email: address, password,
        options: {
          emailRedirectTo: `${window.location.origin}/login`,
          data: { full_name: name, learner_role: role, institution: institution.trim() || null, preferred_language: language },
        },
      })
      if (signupError) throw signupError
      if (data.session) router.push('/study-assistant')
      else { setEmail(address); setSuccess(true) }
      setPassword(''); setConfirmPassword('')
    } catch (cause) {
      const message = cause && typeof cause === 'object' && 'message' in cause ? String(cause.message) : ''
      setError(/fetch|network/i.test(message)
        ? 'We could not connect to the account service. Check your connection and try again.'
        : message || 'Your account could not be created. Please try again.')
    } finally { setLoading(false) }
  }
  function fieldError(field: Field) {
    return errors[field] ? <p id={`${field}-error`} className="mt-2 text-xs" style={{ color: 'var(--c-red)' }}>{errors[field]}</p> : null
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-4 py-12 sm:py-16" style={{ background: 'var(--c-bg)' }}>
      <div className="fixed top-4 right-4 z-10"><ThemeToggle /></div>
      <div className="w-full max-w-2xl">
        <header className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl mb-4" style={{ background: 'var(--c-blue)' }}>
            <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            </svg>
          </div>
          <p className="nb-label mb-2">VoiceLearn AI</p>
          <h1 className="text-3xl font-semibold mb-2" style={{ color: 'var(--c-ink)' }}>{success ? 'One more step' : 'Create your learning account'}</h1>
          <p className="text-sm" style={{ color: 'var(--c-ink-faint)' }}>Study your documents with your voice, in English, Tamil or Sinhala.</p>
        </header>
        {success ? (
          <section className="nb-card p-6 sm:p-10 text-center space-y-5" role="status" aria-live="polite">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'var(--c-green-soft)', border: '1px solid var(--c-green-border)' }}>
              <svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--c-green)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m2 6 10 7 10-7" /></svg>
            </div>
            <h2 className="text-xl font-semibold" style={{ color: 'var(--c-ink)' }}>Check your email</h2>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--c-ink-soft)' }}>Look for a confirmation link at <strong className="break-all">{email}</strong>. Confirm your email, then sign in to start learning.</p>
            <p className="text-xs leading-relaxed" style={{ color: 'var(--c-ink-faint)' }}>Check your spam folder too. If you already have an account, sign in instead.</p>
            <Link href="/login" className="nb-btn-primary inline-flex">Back to sign in</Link>
            <button type="button" onClick={() => { setSuccess(false); setError('') }} className="block mx-auto text-sm hover:underline" style={{ color: 'var(--c-ink-soft)' }}>Use a different email</button>
          </section>
        ) : (
          <form noValidate onSubmit={handleSubmit} className="nb-card p-6 sm:p-9 space-y-7" aria-busy={loading}>
            <fieldset disabled={loading} className="min-w-0">
              <legend className="text-base font-semibold mb-1" style={{ color: 'var(--c-ink)' }}>Account details</legend>
              <p className="text-xs mb-5" style={{ color: 'var(--c-ink-faint)' }}>All account fields are required. A personal or university email works.</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <label htmlFor="full-name" className="block text-sm font-medium mb-1.5" style={{ color: 'var(--c-ink-soft)' }}>Full name</label>
                  <input id="full-name" required autoComplete="name" maxLength={100} value={fullName} onChange={e => { setFullName(e.target.value); clearField('name') }} placeholder="Your full name" className="nb-input" aria-invalid={Boolean(errors.name)} aria-describedby={errors.name ? 'name-error' : undefined} />
                  {fieldError('name')}
                </div>
                <div>
                  <label htmlFor="reg-email" className="block text-sm font-medium mb-1.5" style={{ color: 'var(--c-ink-soft)' }}>Email address</label>
                  <input id="reg-email" type="email" required autoComplete="email" autoCapitalize="none" spellCheck={false} maxLength={254} value={email} onChange={e => { setEmail(e.target.value); clearField('email') }} placeholder="you@example.com" className="nb-input" aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? 'email-error' : undefined} />
                  {fieldError('email')}
                </div>
                <div>
                  <label htmlFor="reg-password" className="block text-sm font-medium mb-1.5" style={{ color: 'var(--c-ink-soft)' }}>Password</label>
                  <input id="reg-password" type={showPassword ? 'text' : 'password'} required autoComplete="new-password" minLength={8} maxLength={128} value={password} onChange={e => { setPassword(e.target.value); clearField('password'); clearField('confirm') }} placeholder="At least 8 characters" className="nb-input" aria-invalid={Boolean(errors.password)} aria-describedby={`password-hint${errors.password ? ' password-error' : ''}`} />
                  {fieldError('password')}
                </div>
                <div>
                  <label htmlFor="confirm-password" className="block text-sm font-medium mb-1.5" style={{ color: 'var(--c-ink-soft)' }}>Confirm password</label>
                  <input id="confirm-password" type={showPassword ? 'text' : 'password'} required autoComplete="new-password" maxLength={128} value={confirmPassword} onChange={e => { setConfirmPassword(e.target.value); clearField('confirm') }} placeholder="Enter your password again" className="nb-input" aria-invalid={Boolean(errors.confirm)} aria-describedby={errors.confirm ? 'confirm-error' : undefined} />
                  {fieldError('confirm')}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <label className="inline-flex items-center gap-2 text-xs cursor-pointer" style={{ color: 'var(--c-ink-soft)' }}><input type="checkbox" checked={showPassword} onChange={e => setShowPassword(e.target.checked)} style={{ accentColor: 'var(--c-blue)' }} />Show passwords</label>
                {password && <span className="text-xs" role="status" style={{ color: strength ? 'var(--c-ink-soft)' : 'var(--c-red)' }}>Password length: {strengthLabels[strength]}</span>}
              </div>
              <p id="password-hint" className="mt-3 text-xs leading-relaxed" style={{ color: 'var(--c-ink-faint)' }}>Use at least 8 characters. A longer, unique passphrase is a good choice.</p>
            </fieldset>
            <fieldset disabled={loading} className="min-w-0 border-t pt-6" style={{ borderColor: 'var(--border)' }}>
              <legend className="text-base font-semibold px-0" style={{ color: 'var(--c-ink)' }}>Study profile <span className="ml-2 text-xs font-normal" style={{ color: 'var(--c-ink-faint)' }}>Optional</span></legend>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <label htmlFor="learner-role" className="block text-sm font-medium mb-1.5" style={{ color: 'var(--c-ink-soft)' }}>I am a</label>
                  <select id="learner-role" value={role} onChange={e => setRole(e.target.value)} className="nb-input"><option value="student">Student</option><option value="educator">Educator</option><option value="independent_learner">Independent learner</option><option value="prefer_not_to_say">Prefer not to say</option></select>
                </div>
                <div>
                  <label htmlFor="preferred-language" className="block text-sm font-medium mb-1.5" style={{ color: 'var(--c-ink-soft)' }}>Preferred study language</label>
                  <select id="preferred-language" value={language} onChange={e => setLanguage(e.target.value)} className="nb-input"><option value="english">English</option><option value="tamil">Tamil</option><option value="sinhala">Sinhala</option></select>
                </div>
                <div className="sm:col-span-2">
                  <label htmlFor="institution" className="block text-sm font-medium mb-1.5" style={{ color: 'var(--c-ink-soft)' }}>Institution or course <span className="font-normal text-xs">(optional)</span></label>
                  <input id="institution" autoComplete="organization" maxLength={150} value={institution} onChange={e => setInstitution(e.target.value)} placeholder="University, school or course name" className="nb-input" />
                </div>
              </div>
              <p className="text-xs mt-3" style={{ color: 'var(--c-ink-faint)' }}>These details are saved to your profile. You can choose any language when studying.</p>
            </fieldset>
            {error && <div role="alert" className="rounded-xl px-4 py-3 text-sm" style={{ background: 'var(--c-red-soft)', border: '1px solid var(--c-red-border)', color: 'var(--c-red)' }}>{error}</div>}
            <div className="space-y-4">
              <button id="register-submit" type="submit" disabled={loading} className="nb-btn-primary w-full justify-center py-3 rounded-xl text-sm font-semibold">{loading ? 'Creating your account…' : 'Create account'}</button>
              <p className="text-center text-xs" style={{ color: 'var(--c-ink-faint)' }}>We will ask you to verify your email before signing in.</p>
              <p className="text-center text-sm" style={{ color: 'var(--c-ink-faint)' }}>Already have an account? <Link href="/login" className="font-medium hover:underline" style={{ color: 'var(--c-blue)' }}>Sign in</Link></p>
            </div>
          </form>
        )}
      </div>
    </main>
  )
}
