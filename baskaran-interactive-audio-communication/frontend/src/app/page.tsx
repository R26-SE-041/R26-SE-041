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
    <main className="min-h-screen" style={{ background: '#F5F4EF' }}>

      {/* ── Nav ───────────────────────────────────────────────────────── */}
      <nav className="nb-header sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: '#1A73E8' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              </svg>
            </div>
            <span className="font-semibold text-base text-ink tracking-tight">VoiceLearn AI</span>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className="text-sm font-medium text-ink-muted hover:text-ink transition-colors px-4 py-2 rounded-lg hover:bg-sand-200"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="text-sm font-medium text-white px-5 py-2.5 rounded-lg transition-all hover:shadow-blue"
              style={{ background: '#1A73E8' }}
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="max-w-4xl mx-auto px-6 pt-20 pb-16 text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-semibold mb-8 border"
          style={{ background: '#EEF3FD', borderColor: 'rgba(26,115,232,0.2)', color: '#1A73E8' }}>
          <span className="nb-dot nb-dot-blue animate-pulse-slow" />
          Powered by Whisper · Llama 3.1 · Kokoro-82M
        </div>

        <h1 className="text-5xl sm:text-6xl font-bold tracking-tight mb-5 text-ink leading-tight">
          Your AI-powered<br />
          <span style={{ color: '#1A73E8' }}>Study Notebook</span>
        </h1>

        <p className="text-lg text-ink-muted max-w-2xl mx-auto mb-10 leading-relaxed">
          Upload lecture slides, PDFs, and notes — then ask questions in your voice.
          Get spoken answers in English, Tamil, or Sinhala, grounded in your own materials.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/register"
            id="cta-register"
            className="inline-flex items-center justify-center gap-2 text-white font-semibold px-8 py-3.5 rounded-xl text-base transition-all hover:shadow-blue hover:-translate-y-0.5"
            style={{ background: '#1A73E8' }}
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
            className="nb-btn-ghost inline-flex items-center justify-center px-8 py-3.5 rounded-xl text-base"
          >
            Sign In →
          </Link>
        </div>

        {/* Demo links */}
        <div className="flex items-center justify-center gap-4 mt-5">
          <Link href="/test" className="text-xs text-ink-faint hover:text-blue-500 transition-colors">
            → Voice Studio
          </Link>
          <span className="text-ink-ghost">·</span>
          <Link href="/documents" className="text-xs text-ink-faint hover:text-blue-500 transition-colors">
            → Document Library
          </Link>
        </div>
      </section>

      {/* ── Features ──────────────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-6 pb-24">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {features.map((f) => (
            <div key={f.title} className="nb-card p-6 hover:-translate-y-0.5 transition-transform">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                style={{ background: '#EEF3FD', color: '#1A73E8' }}
              >
                {f.icon}
              </div>
              <h3 className="font-semibold text-ink mb-2 text-sm">{f.title}</h3>
              <p className="text-sm text-ink-muted leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* Language pills */}
        <div className="mt-12 text-center">
          <p className="text-xs text-ink-faint mb-4 nb-label">Supported Languages</p>
          <div className="flex flex-wrap justify-center gap-3">
            {[
              { flag: '🇬🇧', name: 'English' },
              { flag: '🇮🇳', name: 'Tamil · தமிழ்' },
              { flag: '🇱🇰', name: 'Sinhala · සිංහල' },
            ].map((l) => (
              <span key={l.name} className="nb-card px-5 py-2.5 text-sm font-medium text-ink-soft flex items-center gap-2">
                <span>{l.flag}</span>
                <span>{l.name}</span>
              </span>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="mt-16 pt-8 border-t border-sand-200 flex flex-wrap justify-center gap-x-6 gap-y-1 text-xs text-ink-faint">
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
