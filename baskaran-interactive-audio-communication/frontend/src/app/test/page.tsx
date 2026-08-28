'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { LanguageSelector } from '@/components/voice/LanguageSelector'
import { VoiceRecorder } from '@/components/voice/VoiceRecorder'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { MarkdownContent } from '@/components/ui/MarkdownContent'
import { StudyModeSelector, type StudyMode } from '@/components/ui/StudyModeSelector'
import { MuscleTopicGrid } from '@/components/ui/MuscleTopicGrid'
import {
  askDocument,
  deleteDocument,
  listDocuments,
  synthesizeSpeech,
  uploadDocument,
} from '@/lib/api'
import type { AskResponse, DocumentItem, Language, TranscribeResponse } from '@/types'
import { getMuscleLocale } from '@/lib/muscleLocale'

type Phase = 'idle' | 'transcript-ready' | 'asking' | 'answered' | 'rag-error' | 'asr-error'

interface Result {
  transcript: string
  answer: string
  references: AskResponse['references']
  /** Whether the answer was produced in document-grounded mode. */
  documentGrounded: boolean
}

const ACCEPTED_DOCUMENTS = '.pdf,.pptx,.docx,.xlsx,.txt,.md'
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function correctTranscript(transcript: string, language: Language): Promise<string> {
  const response = await fetch(`${API_URL}/api/v1/documents/enhance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transcript, language }),
  })
  if (!response.ok) throw new Error('Transcript correction is unavailable.')
  const data = await response.json() as { enhanced_query: string }
  return data.enhanced_query
}

export default function StudyAssistantPage() {
  // ─── Study mode ────────────────────────────────────────────────────────────
  const [studyMode, setStudyMode] = useState<StudyMode>('document')

  // ─── Language & document state ─────────────────────────────────────────────
  const [language, setLanguage] = useState<Language>('english')
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [documentsLoading, setDocumentsLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [documentError, setDocumentError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ─── Question / answer state ───────────────────────────────────────────────
  const [phase, setPhase] = useState<Phase>('idle')
  const [transcript, setTranscript] = useState('')
  const [detectedLanguage, setDetectedLanguage] = useState<string | undefined>()
  const [correctingTranscript, setCorrectingTranscript] = useState(false)
  const [correctionError, setCorrectionError] = useState<string | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [asrError, setAsrError] = useState<string | null>(null)
  const [ragError, setRagError] = useState<string | null>(null)
  const ragRequestActiveRef = useRef(false)

  // ─── Audio / TTS state ─────────────────────────────────────────────────────
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [audioLoading, setAudioLoading] = useState(false)
  const [audioError, setAudioError] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const audioRequestRef = useRef(0)

  // ─── Load documents on mount ───────────────────────────────────────────────
  const loadDocuments = useCallback(async () => {
    try {
      setDocuments(await listDocuments())
    } catch {
      setDocumentError('Indexed documents could not be loaded. You can still try uploading a document.')
    } finally {
      setDocumentsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadDocuments()
  }, [loadDocuments])

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl)
    }
  }, [audioUrl])

  // ─── Helpers ───────────────────────────────────────────────────────────────
  const clearAnswer = useCallback(() => {
    audioRequestRef.current += 1
    setPhase('idle')
    setTranscript('')
    setDetectedLanguage(undefined)
    setCorrectingTranscript(false)
    setCorrectionError(null)
    setResult(null)
    setAsrError(null)
    setRagError(null)
    ragRequestActiveRef.current = false
    setAudioUrl((current) => {
      if (current) URL.revokeObjectURL(current)
      return null
    })
    setAudioLoading(false)
    setAudioError(null)
  }, [])

  /** Switch study mode — preserves indexed documents, clears stale answers. */
  const handleStudyModeChange = useCallback((nextMode: StudyMode) => {
    if (nextMode === studyMode) return
    setStudyMode(nextMode)
    clearAnswer()
  }, [studyMode, clearAnswer])

  const selectLanguage = useCallback((nextLanguage: Language) => {
    setLanguage(nextLanguage)
    clearAnswer()
  }, [clearAnswer])

  // ─── Document handlers ─────────────────────────────────────────────────────
  const handleFileUpload = useCallback(async (file: File) => {
    setUploading(true)
    setDocumentError(null)
    try {
      const uploaded = await uploadDocument(file)
      setDocuments((current) => [uploaded, ...current.filter((doc) => doc.document_id !== uploaded.document_id)])
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : 'The document could not be uploaded.')
    } finally {
      setUploading(false)
    }
  }, [])

  const handleDelete = useCallback(async (documentId: string) => {
    setDocumentError(null)
    try {
      await deleteDocument(documentId)
      setDocuments((current) => current.filter((doc) => doc.document_id !== documentId))
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : 'The document could not be removed.')
    }
  }, [])

  // ─── TTS ───────────────────────────────────────────────────────────────────
  const synthesizeAnswer = useCallback(async (answer: string, responseLanguage: Language) => {
    const requestId = ++audioRequestRef.current
    setAudioLoading(true)
    setAudioError(null)
    setAudioUrl((current) => {
      if (current) URL.revokeObjectURL(current)
      return null
    })
    try {
      const blob = await synthesizeSpeech(answer, responseLanguage)
      if (requestId === audioRequestRef.current) {
        setAudioUrl(URL.createObjectURL(blob))
      }
    } catch {
      if (requestId === audioRequestRef.current) {
        const locAudio = getMuscleLocale(responseLanguage).ui.audioUnavailable
        setAudioError(locAudio)
      }
    } finally {
      if (requestId === audioRequestRef.current) setAudioLoading(false)
    }
  }, [])

  // ─── ASR / transcript handlers ─────────────────────────────────────────────
  const handleTranscript = useCallback((asrResult: TranscribeResponse) => {
    const question = asrResult.transcript.trim()
    setTranscript(question)
    setDetectedLanguage(asrResult.detected_language)
    setResult(null)
    setAsrError(null)
    setRagError(null)
    setCorrectionError(null)
    setAudioError(null)

    if (!question) {
      setPhase('asr-error')
      setAsrError(getMuscleLocale(language).ui.noSpeechDetected)
      return
    }

    setPhase('transcript-ready')
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language])

  /** Fill transcript from a quick-prompt chip click (Muscle Tutor mode). */
  const handlePromptSelect = useCallback((prompt: string) => {
    setTranscript(prompt)
    setResult(null)
    setAsrError(null)
    setRagError(null)
    setCorrectionError(null)
    setAudioError(null)
    setPhase('transcript-ready')
  }, [])

  // ─── Submit question ───────────────────────────────────────────────────────
  const submitQuestionToRag = useCallback(async () => {
    const question = transcript.trim()
    if (!question || ragRequestActiveRef.current) return

    const isDocumentGrounded = studyMode === 'document'

    ragRequestActiveRef.current = true
    setPhase('asking')
    setRagError(null)
    setResult(null)
    audioRequestRef.current += 1
    setAudioUrl((current) => {
      if (current) URL.revokeObjectURL(current)
      return null
    })
    setAudioLoading(false)
    setAudioError(null)

    try {
      const answer = await askDocument(
        question,
        language,
        undefined,
        detectedLanguage,
        isDocumentGrounded, // ← dynamic: true for Document Study, false for Muscle Tutor
      )
      setResult({
        transcript: question,
        answer: answer.answer,
        references: answer.references,
        documentGrounded: isDocumentGrounded,
      })
      setPhase('answered')
      void synthesizeAnswer(answer.answer, language)
    } catch (error) {
      setPhase('rag-error')
      setRagError(
        error instanceof Error
          ? error.message
          : 'Couldn\u2019t generate an answer. Please try again.',
      )
    } finally {
      ragRequestActiveRef.current = false
    }
  }, [detectedLanguage, language, studyMode, synthesizeAnswer, transcript])

  // ─── Fix Transcript ────────────────────────────────────────────────────────
  const handleFixTranscript = useCallback(async () => {
    const question = transcript.trim()
    if (!question || correctingTranscript || ragRequestActiveRef.current) return

    setCorrectingTranscript(true)
    setCorrectionError(null)
    try {
      setTranscript((await correctTranscript(question, language)).trim() || question)
      setRagError(null)
      if (phase === 'answered') {
        setResult(null)
        audioRequestRef.current += 1
        setAudioUrl((current) => {
          if (current) URL.revokeObjectURL(current)
          return null
        })
        setAudioLoading(false)
        setAudioError(null)
      }
      setPhase('transcript-ready')
    } catch {
      setCorrectionError('Transcript correction is unavailable right now. You can still edit the question manually.')
    } finally {
      setCorrectingTranscript(false)
    }
  }, [correctingTranscript, language, phase, transcript])

  const handleTranscriptChange = useCallback((value: string) => {
    setTranscript(value)
    setRagError(null)
    setCorrectionError(null)
    if (phase === 'answered') {
      setResult(null)
      audioRequestRef.current += 1
      setAudioUrl((current) => {
        if (current) URL.revokeObjectURL(current)
        return null
      })
      setAudioLoading(false)
      setAudioError(null)
    }
    setPhase('transcript-ready')
  }, [phase])

  const handleVoiceError = useCallback((message: string) => {
    setPhase('asr-error')
    setAsrError(message || 'Your recording could not be transcribed. Please try again.')
  }, [])

  // ─── Derived flags ─────────────────────────────────────────────────────────
  const showSources =
    result !== null &&
    result.documentGrounded &&
    result.references.length > 0

  // Locale strings — recomputed whenever language changes
  const loc = getMuscleLocale(language)

  const askingText =
    studyMode === 'document'
      ? loc.ui.searchingDocs
      : loc.ui.consultingBase

  // ─── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen" style={{ background: 'var(--c-bg)', transition: 'background 0.25s' }}>
      {/* ── Header ── */}
      <header className="nb-header sticky top-0 z-50">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'var(--c-blue)' }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              </svg>
            </div>
            <span className="text-sm font-semibold" style={{ color: 'var(--c-ink)' }}>Learning Assistant</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium" style={{ color: 'var(--c-ink-faint)' }}>Voice Interaction</span>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-8 pb-24 sm:px-6">

        {/* ── Hero ── */}
        <div className="flex flex-col items-center gap-2 pb-2 text-center pt-4">
          <p className="nb-label" style={{ color: '#1A73E8' }}>AI Study Assistant</p>
          <h1 className="text-3xl font-semibold tracking-tight text-ink">Learn with your voice</h1>
          <p className="max-w-xl text-sm leading-relaxed text-ink-muted">
            Study your documents or explore specialized anatomy topics in English, Tamil, and Sinhala.
          </p>
        </div>

        {/* ── Study Mode Selector ── */}
        <div className="flex flex-col items-center gap-3">
          <p className="nb-label">{loc.ui.studyMode}</p>
          <StudyModeSelector
            value={studyMode}
            onChange={handleStudyModeChange}
            disabled={phase === 'asking'}
          />
        </div>

        {/* ── Response Language ── */}
        <Section title={loc.ui.responseLanguage}>
          <LanguageSelector value={language} onChange={selectLanguage} disabled={phase === 'asking'} />
        </Section>

        {/* ── Document Study panel ── */}
        {studyMode === 'document' && (
          <Section title="Document Study">
            <p style={{ fontSize: 13, color: 'var(--c-ink-muted)', marginBottom: 16, lineHeight: 1.55 }}>
              Upload your notes, PDFs, slides, or study files and receive answers grounded in your documents.
            </p>

            {/* Upload zone */}
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_DOCUMENTS}
              className="sr-only"
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ''
                if (file) void handleFileUpload(file)
              }}
            />
            <button
              type="button"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(event) => { event.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(event) => {
                event.preventDefault()
                setDragOver(false)
                const file = event.dataTransfer.files[0]
                if (file) void handleFileUpload(file)
              }}
              className="flex w-full flex-col items-center gap-2 rounded-2xl px-5 py-8 transition-all disabled:cursor-wait disabled:opacity-60"
              style={{
                border: `2px dashed ${dragOver ? '#1A73E8' : 'rgba(0,0,0,0.12)'}`,
                background: dragOver ? '#EEF3FD' : '#F5F4EF',
              }}
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-xl" style={{ background: '#EEF3FD' }} aria-hidden>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1A73E8" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </span>
              <span className="text-sm font-medium text-ink">{uploading ? 'Indexing document…' : 'Upload or drop a document'}</span>
              <span className="text-xs text-ink-faint">PDF, PowerPoint, Word, Excel, text, or Markdown</span>
            </button>

            {/* Indexed document list */}
            <div className="mt-4">
              <p className="nb-label mb-3">Indexed Documents</p>
              {documentsLoading ? (
                <p className="text-sm text-ink-faint">Loading documents…</p>
              ) : documents.length === 0 ? (
                <p className="rounded-xl px-4 py-3 text-sm text-ink-faint" style={{ background: '#F5F4EF', border: '1px solid rgba(0,0,0,0.07)' }}>No documents indexed yet.</p>
              ) : (
                <ul className="space-y-2">
                  {documents.map((document) => (
                    <li key={document.document_id} className="flex items-center gap-3 rounded-xl px-4 py-3" style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.07)' }}>
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold uppercase" style={{ background: '#EEF3FD', color: '#1A73E8' }}>{document.file_type}</span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-ink">{document.filename}</p>
                        <p className="text-xs text-ink-faint">Ready to search</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleDelete(document.document_id)}
                        className="rounded-lg px-2 py-1 text-xs font-medium text-ink-faint transition-colors hover:text-red-600 hover:bg-red-50"
                        aria-label={`Remove ${document.filename}`}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {documentError && <ErrorNotice message={documentError} />}
          </Section>
        )}

        {/* ── Muscle Tutor panel ── */}
        {studyMode === 'muscle' && (
          <Section title={loc.ui.muscleTutor}>
            <MuscleTopicGrid language={language} onPromptSelect={handlePromptSelect} />
          </Section>
        )}

        {/* ── Ask a Question (shared by both modes) ── */}
        <Section title={loc.ui.askAQuestion}>
          <VoiceRecorder
            language={language}
            onTranscript={handleTranscript}
            onError={handleVoiceError}
            disabled={phase === 'asking'}
          />
          {phase === 'asking' && (
            <div
              className="flex items-center justify-center gap-3 rounded-xl px-4 py-3 text-sm animate-fade-up"
              style={{ background: '#EEF3FD', border: '1px solid rgba(26,115,232,0.2)', color: '#1A73E8', marginTop: 12 }}
            >
              <Spinner />
              {askingText}
            </div>
          )}
          {asrError && <ErrorNotice message={asrError} />}
        </Section>

        {/* ── Transcript / Fix / Ask (shared by both modes) ── */}
        {transcript && (
          <Section title={loc.ui.yourQuestion}>
            <textarea
              value={transcript}
              onChange={(event) => handleTranscriptChange(event.target.value)}
              disabled={phase === 'asking' || correctingTranscript}
              rows={3}
              aria-label={loc.ui.yourQuestion}
              className="nb-input w-full resize-y"
              style={{ minHeight: 80 }}
            />

            {correctionError && <p className="mt-3 text-xs text-amber-700">{correctionError}</p>}
            {ragError && <ErrorNotice message={ragError} />}

            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void handleFixTranscript()}
                disabled={!transcript.trim() || phase === 'asking' || correctingTranscript}
                className="nb-btn-ghost rounded-xl px-4 py-2.5 text-sm"
              >
                {correctingTranscript ? loc.ui.fixing : loc.ui.fixTranscript}
              </button>
              <button
                type="button"
                onClick={() => void submitQuestionToRag()}
                disabled={!transcript.trim() || phase === 'asking' || correctingTranscript}
                className="nb-btn-primary rounded-xl px-5 py-2.5 text-sm"
              >
                {phase === 'asking' ? loc.ui.asking : phase === 'rag-error' ? loc.ui.retryAnswer : loc.ui.askArrow}
              </button>
            </div>
          </Section>
        )}

        {/* ── Answer (shared by both modes) ── */}
        {result && (
          <>
            <Section title={loc.ui.answer}>
              {/* Answer mode badge — user-friendly label only */}
              <div style={{ marginBottom: 14 }}>
                {result.documentGrounded ? (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 5,
                      fontSize: 11,
                      fontWeight: 600,
                      padding: '4px 10px',
                      borderRadius: 999,
                      background: 'var(--c-blue-soft)',
                      color: 'var(--c-blue)',
                      border: '1px solid var(--c-blue-border)',
                      letterSpacing: '0.03em',
                    }}
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    {loc.ui.documentGroundedAnswer}
                  </span>
                ) : (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 5,
                      fontSize: 11,
                      fontWeight: 600,
                      padding: '4px 10px',
                      borderRadius: 999,
                      background: 'var(--c-green-soft)',
                      color: 'var(--c-green)',
                      border: '1px solid var(--c-green-border)',
                      letterSpacing: '0.03em',
                    }}
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <path d="M18 20V10" />
                      <path d="M12 20V4" />
                      <path d="M6 20v-6" />
                    </svg>
                    {loc.ui.specializedAnatomyAnswer}
                  </span>
                )}
              </div>

              <MarkdownContent content={result.answer} className="text-sm" />

              {/* TTS controls */}
              <div className="mt-5 pt-4" style={{ borderTop: '1px solid rgba(0,0,0,0.07)' }}>
                {audioLoading && (
                  <div className="flex items-center gap-2 text-sm text-ink-faint"><Spinner /> {loc.ui.preparingAudio}</div>
                )}
                {audioUrl && (
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <button
                      type="button"
                      onClick={() => void audioRef.current?.play()}
                      className="nb-btn-primary rounded-xl px-4 py-2.5 text-sm"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3" /></svg>
                      {loc.ui.playAnswer}
                    </button>
                    <audio ref={audioRef} src={audioUrl} controls className="h-10 w-full sm:max-w-sm" preload="metadata" />
                  </div>
                )}
                {audioError && (
                  <div className="flex flex-wrap items-center gap-3">
                    <p className="text-xs text-amber-700">{audioError}</p>
                    <button
                      type="button"
                      onClick={() => void synthesizeAnswer(result.answer, language)}
                      disabled={audioLoading}
                      className="text-xs font-semibold transition-colors disabled:opacity-40"
                      style={{ color: '#1A73E8' }}
                    >
                      {loc.ui.retryAudio}
                    </button>
                  </div>
                )}
              </div>
            </Section>

            {/* ── Sources — only for document-grounded answers with references ── */}
            {showSources && (
              <Section title={loc.ui.sources}>
                <ol className="space-y-2">
                  {result.references.map((reference, index) => (
                    <li key={`${reference.document_id}-${index}`} className="rounded-xl px-4 py-3 nb-inset">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-ink-soft">{reference.filename}</span>
                        {reference.page != null && (
                          <span className="rounded px-2 py-0.5 text-xs text-ink-faint" style={{ background: '#EAE8E0' }}>Page {reference.page}</span>
                        )}
                      </div>
                      {reference.excerpt && (
                        <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-ink-muted border-l-2 pl-2.5 italic mt-2" style={{ borderColor: '#DBD8CC' }}>
                          {reference.excerpt}
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
              </Section>
            )}
          </>
        )}

        {/* ── Ask another question ── */}
        {(phase === 'answered' || phase === 'rag-error') && (
          <button type="button" onClick={clearAnswer}
            className="self-center text-sm font-medium text-ink-faint transition-colors hover:text-ink">
            {loc.ui.askAnother}
          </button>
        )}
      </main>
    </div>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="nb-card rounded-2xl p-5 sm:p-6">
      <h2 className="mb-5 nb-label">{title}</h2>
      {children}
    </section>
  )
}

function Spinner() {
  return (
    <span className="inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2" style={{ borderColor: 'rgba(26,115,232,0.2)', borderTopColor: '#1A73E8' }} aria-hidden />
  )
}

function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="mt-4 rounded-xl px-4 py-3 text-sm text-red-700 animate-fade-up"
      style={{ background: '#FEF2F2', border: '1px solid rgba(234,67,53,0.2)' }}>
      {message}
    </div>
  )
}
