'use client'

import { useCallback, useState } from 'react'
import { useSessionStore } from '@/store/sessionStore'
import { useSession } from '@/hooks/useSession'
import { LanguageSelector } from '@/components/voice/LanguageSelector'
import { VoiceRecorder } from '@/components/voice/VoiceRecorder'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import type { TranscribeResponse } from '@/types'
import { askDocument, saveHistory, saveHistoryAudio, synthesizeSpeech } from '@/lib/api'
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
    updateMessage,
    lastTranscript,
    setLastTranscript,
  } = useSessionStore()

  const [error, setError] = useState<string | null>(null)
  const [isQuerying, setIsQuerying] = useState(false)

  const handleTranscript = useCallback(async (result: TranscribeResponse) => {
    setLastTranscript(result.transcript)
    setError(null)

    addMessage({
      role: 'user',
      content: result.transcript,
      created_at: new Date().toISOString(),
    })

    setIsQuerying(true)
    try {
      const queryResult = await askDocument(
        result.transcript,
        language,
        undefined,
        result.detected_language
      )

      const answerCreatedAt = new Date().toISOString()
      addMessage({
        role: 'assistant',
        content: queryResult.answer,
        references: queryResult.references ?? [],
        audio_url: null,
        audio_pending: true,
        created_at: answerCreatedAt,
      })

      // Persist the text immediately; attach the WAV when slower TTS completes.
      const historyItem = saveHistory(result.transcript, queryResult.answer, language,
        queryResult.references ?? []).catch(() => null)

      void synthesizeSpeech(queryResult.answer, language)
        .then((audioBlob) => {
          updateMessage(answerCreatedAt, {
            audio_url: URL.createObjectURL(audioBlob),
            audio_pending: false,
            audio_error: null,
          })
          void historyItem.then((item) => item
            ? saveHistoryAudio(item.id, audioBlob).catch(() => undefined)
            : undefined)
        })
        .catch(() => {
          updateMessage(answerCreatedAt, {
            audio_pending: false,
            audio_error: 'Answer audio is unavailable. The text answer is complete.',
          })
        })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Query failed. Check if documents are uploaded.')
    } finally {
      setIsQuerying(false)
    }
  }, [language, addMessage, setLastTranscript, updateMessage])

  const handleError = useCallback((msg: string) => { setError(msg) }, [])

  if (!authLoading && !user) {
    router.replace('/login')
    return null
  }

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--c-bg)' }}>
        <LoadingSpinner size="lg" label="Loading…" />
      </div>
    )
  }

  const handleSignOut = async () => { await signOut(); router.push('/') }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--background)', transition: 'background 0.3s' }}>

      {/* ── Ambient blobs ─────────────────────────────────────────────────── */}
      <div className="vl-ambient" aria-hidden="true">
        <div className="vl-ambient-top" />
        <div className="vl-ambient-bottom" />
      </div>

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <header className="nb-header sticky top-0 z-20">
        <div className="max-w-full px-5 h-14 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ background: 'var(--c-blue)' }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.2}
                strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              </svg>
            </div>
            <span className="font-semibold text-sm tracking-tight" style={{ color: 'var(--c-ink)' }}>
              VoiceLearn AI
            </span>
          </div>

          {/* Center: Processing badge */}
          {isQuerying && (
            <div className="hidden sm:flex items-center gap-2 text-xs animate-fade-in"
              style={{ background: 'var(--primary-soft)', borderRadius: 999, padding: '5px 14px',
                border: '1px solid var(--primary-border)', color: 'var(--primary)' }}>
              <div className="w-3 h-3 rounded-full border-2 animate-spin"
                style={{ borderColor: 'var(--primary-soft)', borderTopColor: 'var(--primary)' }} />
              Finding answer from your documents…
            </div>
          )}

          {/* Right: Nav + Theme toggle */}
          <nav className="flex items-center gap-1">
            <ThemeToggle />
            <Link href="/dashboard/history" id="nav-history"
              className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-lg transition-all"
              style={{ color: 'var(--c-ink-muted)' }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
                strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 3v6h6" /><path d="M12 7v5l3 2" />
              </svg>
              History
            </Link>
            <Link href="/dashboard/documents" id="nav-documents"
              className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-2 rounded-lg transition-all"
              style={{ color: 'var(--c-ink-muted)' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--c-ink)'; e.currentTarget.style.background = 'var(--c-inset)' }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--c-ink-muted)'; e.currentTarget.style.background = 'transparent' }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
                strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              Documents
            </Link>
            <button id="nav-signout" onClick={handleSignOut}
              className="text-xs font-medium px-3 py-2 rounded-lg transition-all"
              style={{ color: 'var(--c-ink-faint)' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--c-red)'; e.currentTarget.style.background = 'var(--c-red-soft)' }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--c-ink-faint)'; e.currentTarget.style.background = 'transparent' }}>
              Sign out
            </button>
          </nav>
        </div>
      </header>

      {/* ── Body: two-pane ───────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── LEFT SIDEBAR ─────────────────────────────────────────────── */}
        <aside className="nb-sidebar flex flex-col" style={{ width: 320, minWidth: 280, flexShrink: 0 }}>
          <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-5">

            <div className="pt-2 pb-1">
              <p className="nb-label mb-1">Active Session</p>
              <h1 className="text-base font-semibold" style={{ color: 'var(--c-ink)' }}>Voice Q&amp;A</h1>
              <p className="text-xs mt-0.5" style={{ color: 'var(--c-ink-faint)' }}>
                {messages.length} message{messages.length !== 1 ? 's' : ''} in conversation
              </p>
            </div>

            <div className="nb-divider" />

            {/* Language selector */}
            <div>
              <p className="nb-label mb-3">Response Language</p>
              <LanguageSelector value={language} onChange={setLanguage} />
            </div>

            <div className="nb-divider" />

            {/* Voice recorder */}
            <div className="flex flex-col items-center gap-1">
              <div className="text-center mb-1 w-full">
                <p className="nb-label mb-0.5">Ask a Question</p>
                <p className="text-xs" style={{ color: 'var(--c-ink-faint)' }}>Tap the mic, speak, then submit</p>
              </div>

              <VoiceRecorder
                language={language}
                onTranscript={handleTranscript}
                onError={handleError}
                disabled={isQuerying}
              />

              {error && (
                <div className="w-full rounded-xl px-4 py-3 text-xs mt-2 animate-fade-up"
                  style={{ background: 'var(--c-red-soft)', border: '1px solid var(--c-red-border)', color: 'var(--c-red)' }}>
                  ⚠ {error}
                </div>
              )}
            </div>

            {/* Last transcript */}
            {lastTranscript && (
              <div className="nb-inset p-4 animate-fade-up">
                <p className="nb-label mb-2">Last Transcript</p>
                <p className="text-xs leading-relaxed italic" style={{ color: 'var(--c-ink-muted)' }}>
                  &ldquo;{lastTranscript}&rdquo;
                </p>
              </div>
            )}

            {/* Pipeline badge */}
            <div className="nb-inset p-4">
              <p className="nb-label mb-3">Pipeline Status</p>
              <div className="space-y-2">
                {[
                  'STT — Whisper Large V3',
                  'Prompt Enhancement',
                  'RAG Generation',
                  'Localization',
                  'TTS Synthesis',
                ].map((step) => (
                  <div key={step} className="flex items-center gap-2 text-xs">
                    <div className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0"
                      style={{ background: 'var(--c-green-soft)', border: '1px solid var(--c-green-border)' }}>
                      <svg width="8" height="8" viewBox="0 0 24 24" fill="none"
                        stroke="var(--c-green)" strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                    <span style={{ color: 'var(--c-ink-muted)' }}>{step}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </aside>

        {/* ── RIGHT: Chat area ─────────────────────────────────────────── */}
        <main className="flex-1 flex flex-col nb-content overflow-hidden">
          <div className="px-6 py-4 flex items-center justify-between flex-shrink-0"
            style={{ borderBottom: '1px solid var(--c-border)' }}>
            <div>
              <h2 className="text-sm font-semibold" style={{ color: 'var(--c-ink)' }}>Conversation</h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--c-ink-faint)' }}>
                {messages.length === 0 ? 'Ask a question using the microphone' : `${messages.length} message${messages.length !== 1 ? 's' : ''}`}
              </p>
            </div>
            {messages.length > 0 && (
              <button
                onClick={() => useSessionStore.getState().clearMessages()}
                className="text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                style={{ color: 'var(--c-ink-faint)' }}
                onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--c-red)'; e.currentTarget.style.background = 'var(--c-red-soft)' }}
                onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--c-ink-faint)'; e.currentTarget.style.background = 'transparent' }}>
                Clear chat
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col">
            <ChatWindow messages={messages} />
          </div>
        </main>
      </div>
    </div>
  )
}
