import Link from 'next/link'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'VoiceLearn AI — Voice-Powered Study Assistant',
  description: 'Upload your lecture documents and ask questions using your voice. Get grounded answers in English, Tamil, or Sinhala.',
}

const features = [
  { icon: '🎤', title: 'Voice Queries', desc: 'Ask questions naturally using your microphone. Whisper Large V3 transcribes your speech.' },
  { icon: '🧠', title: 'RAG Answers', desc: 'Llama 3.1 8B answers only from your uploaded documents — no hallucinations.' },
  { icon: '🌐', title: 'Multilingual', desc: 'Get answers in English, Tamil, or Sinhala.' },
  { icon: '🔊', title: 'Voice Responses', desc: 'Listen to answers with language-specific neural speech synthesis.' },
]

export default function HomePage() {
  return (
    <main className="min-h-screen bg-hero-gradient relative overflow-hidden">
      {/* Background glow orbs */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[400px] pointer-events-none rounded-full blur-3xl opacity-30"
        style={{ background: 'radial-gradient(ellipse, rgba(99,102,241,0.35) 0%, transparent 70%)' }} />
      <div className="absolute top-3/4 left-1/4 w-[300px] h-[300px] rounded-full bg-accent-600/5 blur-3xl pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between max-w-7xl mx-auto px-6 py-5">
        <div className="flex items-center gap-2">
          <span className="glow-dot" />
          <span className="font-bold text-lg">VoiceLearn AI</span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="text-sm text-white/60 hover:text-white transition-colors px-4 py-2"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="text-sm font-semibold bg-gradient-to-r from-brand-600 to-accent-600 text-white px-5 py-2 rounded-xl hover:from-brand-500 hover:to-accent-500 transition-all shadow-brand"
          >
            Get Started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-10 max-w-4xl mx-auto px-6 pt-24 pb-20 text-center">
        <div className="inline-flex items-center gap-2 bg-brand-500/10 border border-brand-500/20 rounded-full px-4 py-1.5 text-sm text-brand-300 mb-8">
          <span className="glow-dot w-2 h-2" />
          Powered by Whisper · Llama 3.1 · Kokoro-82M
        </div>

        <h1 className="text-5xl sm:text-7xl font-bold leading-tight mb-6">
          Study Smarter{' '}
          <span className="text-gradient">with Your Voice</span>
        </h1>

        <p className="text-xl text-white/50 max-w-2xl mx-auto mb-10 leading-relaxed">
          Upload lecture slides, PDFs, Word docs, and spreadsheets, ask questions in Tamil, Sinhala, or English,
          and get spoken answers — all powered by on-demand AI models.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/register"
            id="cta-register"
            className="inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-600 to-accent-600 hover:from-brand-500 hover:to-accent-500 text-white font-semibold px-8 py-4 rounded-2xl text-lg shadow-brand-lg transition-all hover:scale-105 active:scale-95"
          >
            🎤 Start for Free
          </Link>
          <Link
            href="/login"
            id="cta-login"
            className="inline-flex items-center justify-center gap-2 glass text-white/70 hover:text-white font-semibold px-8 py-4 rounded-2xl text-lg transition-all hover:border-white/20"
          >
            Sign In →
          </Link>
        </div>
        {/* Quick demo links */}
        <div className="flex items-center justify-center gap-4 mt-4">
          <Link href="/test" className="text-xs text-white/30 hover:text-white/60 transition-colors">
            → Phase 1: Voice Studio
          </Link>
          <span className="text-white/15">·</span>
          <Link href="/documents" className="text-xs text-indigo-400/70 hover:text-indigo-400 transition-colors">
            → Phase 2: Document Library
          </Link>
        </div>
      </section>

      {/* Features grid */}
      <section className="relative z-10 max-w-5xl mx-auto px-6 pb-24">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {features.map((f) => (
            <div key={f.title} className="glass rounded-2xl p-6 hover:border-white/15 transition-all group">
              <div className="text-3xl mb-4 group-hover:animate-float">{f.icon}</div>
              <h3 className="font-semibold text-white mb-2">{f.title}</h3>
              <p className="text-sm text-white/50 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* Language pills */}
        <div className="mt-12 text-center">
          <p className="text-white/40 text-sm mb-4">Supports</p>
          <div className="flex flex-wrap justify-center gap-3">
            {['English', 'Tamil · தமிழ்', 'Sinhala · සිංහල'].map((l) => (
              <span key={l} className="glass rounded-full px-4 py-2 text-sm text-white/70">
                {l}
              </span>
            ))}
          </div>
        </div>
      </section>
    </main>
  )
}
