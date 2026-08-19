'use client'

import { useCallback, useState } from 'react'
import { useSessionStore } from '@/store/sessionStore'
import { useSession } from '@/hooks/useSession'
import { LanguageSelector } from '@/components/voice/LanguageSelector'
import { VoiceRecorder } from '@/components/voice/VoiceRecorder'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import type { TranscribeResponse } from '@/types'
import { askDocument, synthesizeSpeech } from '@/lib/api'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

export default function DashboardPage() {
  const router = useRouter()
  const { user, loading: authLoading, signOut } = useSession()
  const {
    language,
    setLanguage,
    messages,
    addMessage,
    lastTranscript,
    setLastTranscript,
  } = useSessionStore()

  const [error, setError] = useState<string | null>(null)
  const [isQuerying, setIsQuerying] = useState(false)

  // Redirect if not authenticated
  if (!authLoading && !user) {
    router.replace('/login')
    return null
  }

  if (authLoading) {
    return (
      <div className="min-h-screen bg-hero-gradient flex items-center justify-center">
        <LoadingSpinner size="lg" label="Loading…" />
      </div>
    )
  }

  const handleTranscript = useCallback(async (result: TranscribeResponse) => {
    setLastTranscript(result.transcript)
    setError(null)

    // 1. Add user voice message to chat immediately
    addMessage({
      role: 'user',
      content: result.transcript,
      created_at: new Date().toISOString(),
    })

    // 2. Run full pipeline: Prompt Enhance → RAG → Localize
    setIsQuerying(true)
    try {
      const queryResult = await askDocument(
        result.transcript,
        language,
        undefined,
        result.detected_language  // ← pass Whisper's detected language for Tamil/Sinhala
      )

      // 3. Try TTS — get audio URL for the answer (non-blocking)
      let audio_url: string | undefined
      try {
        const audioBlob = await synthesizeSpeech(queryResult.answer, language)
        audio_url = URL.createObjectURL(audioBlob)
      } catch {
        // TTS unavailable — answer still shows as text
      }

      // 4. Add localized assistant answer to chat (with audio if available)
      addMessage({
        role: 'assistant',
        content: queryResult.answer,
        references: queryResult.references ?? [],
        audio_url: audio_url ?? null,
        created_at: new Date().toISOString(),
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Query failed. Check if documents are uploaded.')
    } finally {
      setIsQuerying(false)
    }
  }, [language, addMessage, setLastTranscript])


  const handleError = useCallback((msg: string) => {
    setError(msg)
  }, [])

  const handleSignOut = async () => {
    await signOut()
    router.push('/')
  }

  return (
    <div className="min-h-screen bg-hero-gradient flex flex-col">
      {/* Header */}
      <header className="glass border-b border-white/5 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="glow-dot" />
            <span className="font-bold text-lg">VoiceLearn AI</span>
          </div>
            <nav className="flex items-center gap-4">
              <Link
                href="/dashboard/documents"
                id="nav-documents"
                className="inline-flex items-center gap-1.5 text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                📚 My Documents
              </Link>
              <button
                id="nav-signout"
                onClick={handleSignOut}
                className="text-sm text-white/40 hover:text-white/70 transition-colors"
              >
                Sign out
              </button>
            </nav>
        </div>
      </header>

      <div className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8 grid lg:grid-cols-[380px_1fr] gap-6">

        {/* Left panel — controls */}
        <aside className="flex flex-col gap-6">
          {/* Language selector */}
          <div className="glass rounded-3xl p-6">
            <LanguageSelector value={language} onChange={setLanguage} />
          </div>

          {/* Voice recorder */}
          <div className="glass rounded-3xl p-8 flex flex-col items-center gap-4">
            <div className="text-center mb-2">
              <h2 className="font-semibold text-white">Ask a Question</h2>
              <p className="text-xs text-white/40 mt-1">
                Tap the mic, speak, and release to transcribe
              </p>
            </div>

            <VoiceRecorder
              language={language}
              onTranscript={handleTranscript}
              onError={handleError}
              disabled={isQuerying}
            />

            {/* Pipeline status indicator */}
            {isQuerying && (
              <div className="w-full flex flex-col items-center gap-2">
                <div className="flex items-center gap-2 text-xs text-brand-400 animate-pulse">
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
                  {language === 'english'
                    ? 'Finding answer from your documents…'
                    : language === 'tamil'
                    ? 'தமிழில் பதில் தயாராகிறது…'
                    : language === 'sinhala'
                    ? 'සිංහලෙන් පිළිතුර සකස් කරමින්…'
                    : 'Thanglish-la answer ready pannurom…'}
                </div>
                <div className="w-full bg-white/5 rounded-full h-1">
                  <div className="bg-gradient-to-r from-brand-500 to-accent-500 h-1 rounded-full animate-pulse w-3/4" />
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="w-full bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-sm text-red-400 text-center">
                {error}
              </div>
            )}
          </div>

          {/* Last transcript display */}
          {lastTranscript && (
            <div className="glass rounded-2xl p-5">
              <p className="text-[10px] text-white/30 uppercase tracking-widest mb-2">Last Transcript</p>
              <p className="text-sm text-white/80 leading-relaxed italic">"{lastTranscript}"</p>
            </div>
          )}

          {/* Phase badge */}
          <div className="glass rounded-2xl p-4 border border-indigo-500/20">
            <div className="flex items-center gap-2 mb-3">
              <span className="glow-dot w-2 h-2 flex-shrink-0" />
              <div>
                <p className="text-xs font-semibold text-indigo-300">Phase 2 Active</p>
                <p className="text-[11px] text-white/40 mt-0.5">RAG · Document Intelligence</p>
              </div>
            </div>
            <div className="space-y-1.5">
              {[
                { label: 'STT (Whisper v3)',       done: true },
                { label: 'Prompt Enhancement',      done: true },
                { label: 'RAG Generation',          done: true },
                { label: 'Localization',            done: true },
                { label: 'TTS Synthesis',           done: true },
              ].map((step) => (
                <div key={step.label} className="flex items-center gap-2 text-[11px]">
                  <span className={step.done ? 'text-green-400' : 'text-white/25'}>
                    {step.done ? '✓' : '○'}
                  </span>
                  <span className={step.done ? 'text-white/70' : 'text-white/30'}>
                    {step.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* Right panel — chat */}
        <section className="glass rounded-3xl p-6 flex flex-col min-h-[500px]">
          <div className="flex items-center justify-between mb-4 pb-4 border-b border-white/5">
            <div>
              <h2 className="font-semibold text-white">Conversation</h2>
              <p className="text-xs text-white/40 mt-0.5">{messages.length} message{messages.length !== 1 ? 's' : ''}</p>
            </div>
            {messages.length > 0 && (
              <button
                onClick={() => useSessionStore.getState().clearMessages()}
                className="text-xs text-white/30 hover:text-white/60 transition-colors"
              >
                Clear
              </button>
            )}
          </div>
          <ChatWindow messages={messages} />
        </section>
      </div>
    </div>
  )
}
