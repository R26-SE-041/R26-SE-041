import Link from 'next/link'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'VoiceLearn AI — Voice-Powered Study Assistant',
  description: 'Upload your lecture documents and ask questions using your voice. Get grounded answers in English, Tamil, or Sinhala.',
}

const features = [
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="22" />
        <line x1="9"  y1="22" x2="15" y2="22" />
      </svg>
    ),
    title: 'Voice Queries',
    desc: 'Ask questions naturally with your microphone. Whisper Large V3 transcribes your speech in real time.',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24A2.5 2.5 0 0 1 9.5 2" />
        <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24A2.5 2.5 0 0 0 14.5 2" />
      </svg>
    ),
    title: 'RAG Answers',
    desc: 'Llama 3.1 8B answers only from your uploaded documents — grounded, no hallucinations.',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M2 12h20" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    ),
    title: 'Multilingual',
    desc: 'Get answers in English, Tamil, or Sinhala — automatically detected from your voice.',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      </svg>
    ),
    title: 'Voice Responses',
    desc: 'Listen to answers with natural neural speech synthesis in your chosen language.',
  },
]

export default function HomePage() {
  return (
    <main className="min-h-screen relative" style={{ background: 'var(--background)' }}>

      {/* ── Ambient background blobs ─────────────────────────────────────── */}
      <div className="vl-ambient" aria-hidden="true">
        <div className="vl-ambient-top" />
        <div className="vl-ambient-bottom" />
      </div>

      {/* ── Nav ───────────────────────────────────────────────────────────── */}
      <nav className="nb-header sticky top-0 z-20" style={{ position: 'relative', zIndex: 20 }}>
        <div className="vl-page h-16 flex items-center justify-between" style={{ maxWidth: 1040 }}>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-[13px] flex items-center justify-center flex-shrink-0"
              style={{ background: 'var(--primary)' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              </svg>
            </div>
            <span className="font-semibold text-base tracking-tight" style={{ color: 'var(--text)' }}>VoiceLearn AI</span>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className="text-sm font-medium px-4 py-2 rounded-[13px] transition-colors"
              style={{ color: 'var(--text-muted)' }}
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="vl-btn-primary text-sm"
              id="nav-get-started"
              style={{ minHeight: 38, padding: '0 18px', borderRadius: 13 }}
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <section className="vl-page pt-20 pb-16 text-center relative z-10" style={{ maxWidth: 900, margin: '0 auto' }}>
        {/* Eyebrow badge */}
        <div className="inline-flex items-center gap-2 rounded-[50px] px-4 py-1.5 mb-8"
          style={{
            background: 'var(--primary-soft)',
            border: '1px solid var(--primary-border)',
            fontSize: 11, fontWeight: 800, letterSpacing: 2.2,
            textTransform: 'uppercase', color: 'var(--primary)',
          }}>
          <span className="vl-dot animate-pulse-slow" />
          Whisper · Llama 3.1 · Kokoro-82M
        </div>

        <h1 className="vl-hero-title mb-5" style={{ fontSize: 'clamp(38px, 6vw, 58px)', lineHeight: '1.08', letterSpacing: '-1.5px' }}>
          Your AI-powered<br />
          <span style={{ color: 'var(--primary)' }}>Study Notebook</span>
        </h1>

        <p className="text-lg max-w-2xl mx-auto mb-10 leading-relaxed" style={{ color: 'var(--text-muted)' }}>
          Upload lecture slides, PDFs, and notes — then ask questions in your voice.
          Get spoken answers in English, Tamil, or Sinhala, grounded in your own materials.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/register"
            id="cta-register"
            className="vl-btn-primary inline-flex items-center justify-center gap-2 text-base"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            </svg>
            Start for Free
          </Link>
          <Link
            href="/login"
            id="cta-login"
            className="vl-btn-secondary inline-flex items-center justify-center text-base"
          >
            Sign In →
          </Link>
        </div>

        {/* Demo links */}
        <div className="flex items-center justify-center gap-4 mt-6">
          <Link href="/test" className="text-xs transition-colors" style={{ color: 'var(--text-dim)' }}>
            → Voice Studio
          </Link>
          <span style={{ color: 'var(--text-dim)' }}>·</span>
          <Link href="/documents" className="text-xs transition-colors" style={{ color: 'var(--text-dim)' }}>
            → Document Library
          </Link>
        </div>
      </section>

      {/* ── Features ──────────────────────────────────────────────────────── */}
      <section className="vl-page pb-24 relative z-10" style={{ maxWidth: 1040, margin: '0 auto' }}>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {features.map((f) => (
            <div key={f.title} className="nb-card p-[22px] hover:-translate-y-1 transition-transform duration-200">
              <div
                className="w-10 h-10 rounded-[13px] flex items-center justify-center mb-4"
                style={{ background: 'var(--primary-soft)', color: 'var(--primary)' }}
              >
                {f.icon}
              </div>
              <h3 className="font-bold text-sm mb-2" style={{ color: 'var(--text)', fontFamily: 'Georgia, serif' }}>{f.title}</h3>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>{f.desc}</p>
            </div>
          ))}
        </div>

        {/* Language pills */}
        <div className="mt-14 text-center">
          <p className="vl-eyebrow mb-4">Supported Languages</p>
          <div className="flex flex-wrap justify-center gap-3">
            {[
              { flag: '🇬🇧', name: 'English' },
              { flag: '🇮🇳', name: 'Tamil · தமிழ்' },
              { flag: '🇱🇰', name: 'Sinhala · සිංහල' },
            ].map((l) => (
              <span key={l.name} className="nb-card px-5 py-2.5 text-sm font-medium flex items-center gap-2"
                style={{ color: 'var(--text-muted)', borderRadius: 20 }}>
                <span>{l.flag}</span>
                <span>{l.name}</span>
              </span>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="mt-16 pt-8 flex flex-wrap justify-center gap-x-6 gap-y-1 text-xs"
          style={{ borderTop: '1px solid var(--border)', color: 'var(--text-dim)' }}>
          <span>Llama 3.1 8B</span>
          <span>·</span>
          <span>Whisper Large V3</span>
          <span>·</span>
          <span>Kokoro-82M TTS</span>
          <span>·</span>
          <span>ChromaDB · MiniLM</span>
          <span>·</span>
          <span>Supabase</span>
        </div>
      </section>
    </main>
  )
}
