'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { LanguageSelector } from '@/components/voice/LanguageSelector'
import { VoiceRecorder } from '@/components/voice/VoiceRecorder'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { MarkdownContent } from '@/components/ui/MarkdownContent'
import { StudyModeSelector, type StudyMode } from '@/components/ui/StudyModeSelector'
import { MuscleTopicGrid } from '@/components/ui/MuscleTopicGrid'
import { HistoryPanel } from '@/components/history/HistoryPanel'
import {
  askDocument,
  deleteDocument,
  listDocuments,
  synthesizeSpeech,
  uploadDocument,
} from '@/lib/api'
import type { AskResponse, DocumentItem, Language, TranscribeResponse } from '@/types'
import { getMuscleLocale } from '@/lib/muscleLocale'
import {
  addLocalHistoryEntry,
  clearLocalHistory,
  deleteLocalHistoryEntry,
  listLocalHistory,
  updateLocalHistoryAudio,
  type LocalHistoryEntry,
} from '@/lib/historyDb'

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

  // ─── Local history (IndexedDB — this page has no login/backend history) ───
  const [historyEntries, setHistoryEntries] = useState<LocalHistoryEntry[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const lastQuestionAudioRef = useRef<Blob | null>(null)
  const currentHistoryEntryIdRef = useRef<string | null>(null)

  useEffect(() => {
    listLocalHistory()
      .then(setHistoryEntries)
      .catch(() => undefined)
      .finally(() => setHistoryLoading(false))
  }, [])

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
        const historyId = currentHistoryEntryIdRef.current
        if (historyId) {
          void updateLocalHistoryAudio(historyId, blob)
            .then(() => {
              setHistoryEntries((current) =>
                current.map((item) => (item.id === historyId ? { ...item, answerAudio: blob } : item)))
            })
            .catch(() => undefined)
        }
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

  // ─── Local history handlers ────────────────────────────────────────────────
  const handleAudioCaptured = useCallback((blob: Blob) => {
    lastQuestionAudioRef.current = blob
  }, [])

  const persistHistoryEntry = useCallback(async (
    questionText: string,
    answerText: string,
    references: AskResponse['references'],
    documentGrounded: boolean,
  ) => {
    try {
      const entry = await addLocalHistoryEntry({
        studyMode,
        language,
        transcript: questionText,
        answer: answerText,
        references,
        documentGrounded,
        questionAudio: lastQuestionAudioRef.current ?? undefined,
      })
      currentHistoryEntryIdRef.current = entry.id
      setHistoryEntries((current) => [entry, ...current])
    } catch {
      // Local history is a convenience layer — it must never block the Q&A flow.
    }
  }, [studyMode, language])

  const handleDeleteHistoryEntry = useCallback((id: string) => {
    setHistoryEntries((current) => current.filter((item) => item.id !== id))
    void deleteLocalHistoryEntry(id).catch(() => undefined)
  }, [])

  const handleClearHistory = useCallback(() => {
    setHistoryEntries([])
    void clearLocalHistory().catch(() => undefined)
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
    lastQuestionAudioRef.current = null
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
      // Only synthesize if we have a real answer — skip TTS for backend error
      // messages (e.g. "Answer generation is not available right now.") which
      // contain only English and would produce empty audio.
      const isErrorAnswer =
        answer.answer.startsWith('Answer generation is not available') ||
        answer.answer.startsWith('RAG generation is not available') ||
        answer.answer.startsWith("I couldn't generate") ||
        answer.answer.startsWith("I couldn't find relevant content")
      await persistHistoryEntry(question, answer.answer, answer.references, isDocumentGrounded)
      if (!isErrorAnswer) {
        void synthesizeAnswer(answer.answer, language)
      }
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
  }, [detectedLanguage, language, studyMode, synthesizeAnswer, persistHistoryEntry, transcript])

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
    <div className="min-h-screen" style={{ background: 'var(--background)', transition: 'background 0.3s' }}>

      {/* Ambient blobs */}
      <div className="vl-ambient" aria-hidden="true">
        <div className="vl-ambient-top" />
        <div className="vl-ambient-bottom" />
      </div>

      {/* ── Header ── */}
      <header className="nb-header sticky top-0 z-50">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-[13px] flex items-center justify-center" style={{ background: 'var(--primary)' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              </svg>
            </div>
            <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Learning Assistant</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium" style={{ color: 'var(--text-dim)' }}>Voice Interaction</span>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto flex max-w-7xl flex-col gap-6 px-5 py-8 pb-28 sm:px-8 lg:px-10 lg:py-10">

        {/* ── Hero ── */}
        <div className="flex flex-col items-center gap-3 pb-1 pt-4 text-center lg:pt-5">
          <p className="vl-eyebrow">AI Study Assistant</p>
          <h1 className="vl-serif text-5xl font-bold tracking-tight" style={{ color: 'var(--text)', fontSize: 42, lineHeight: 1.1 }}>Learn with your voice</h1>
          <p className="max-w-2xl text-base leading-relaxed" style={{ color: 'var(--text-muted)' }}>
            Study your documents or explore specialized anatomy topics in English, Tamil, and Sinhala.
          </p>
        </div>

        {/* ── Study controls ── */}
        <section className="nb-card flex flex-col gap-6 p-5 sm:p-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between lg:justify-start lg:gap-5">
            <div>
              <p className="vl-label">{loc.ui.studyMode}</p>
              <p className="mt-1 text-xs" style={{ color: 'var(--text-dim)' }}>Choose how you want to learn</p>
            </div>
            <StudyModeSelector
              value={studyMode}
              onChange={handleStudyModeChange}
              disabled={phase === 'asking'}
            />
          </div>

          <div className="hidden h-10 w-px lg:block" style={{ background: 'var(--border)' }} aria-hidden />

          <div className="flex flex-col gap-3 border-t pt-5 sm:flex-row sm:items-center sm:justify-between lg:flex-1 lg:justify-end lg:gap-5 lg:border-0 lg:pt-0" style={{ borderColor: 'var(--border)' }}>
            <div className="lg:text-right">
              <p className="vl-label">{loc.ui.responseLanguage}</p>
              <p className="mt-1 text-xs" style={{ color: 'var(--text-dim)' }}>Answers and audio</p>
            </div>
            <LanguageSelector value={language} onChange={selectLanguage} disabled={phase === 'asking'} />
          </div>
        </section>

        {/* ── Document Study panel ── */}
        {studyMode === 'document' && (
          <SectionWide title="Document Study">
            <p style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 20, lineHeight: 1.6 }}>
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
              className="flex min-h-[210px] w-full flex-col items-center justify-center gap-3 rounded-[20px] px-8 py-12 transition-all disabled:cursor-wait disabled:opacity-60 lg:min-h-[225px]"
              style={{
                border: `2px dashed ${dragOver ? 'var(--primary)' : 'var(--border)'}`,
                background: dragOver ? 'var(--primary-soft)' : 'var(--surface-soft)',
              }}
            >
              <span className="flex h-14 w-14 items-center justify-center rounded-[13px]" style={{ background: 'var(--primary-soft)' }} aria-hidden>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </span>
              <div className="flex flex-col items-center gap-1">
                <span className="text-base font-semibold" style={{ color: 'var(--text)' }}>{uploading ? 'Indexing document…' : 'Upload or drop a document'}</span>
                <span className="text-sm" style={{ color: 'var(--text-dim)' }}>PDF, PowerPoint, Word, Excel, text, or Markdown</span>
              </div>
            </button>

            {/* Indexed document list */}
            <div className="mt-6">
              <p className="vl-label mb-4">Indexed Documents</p>
              {documentsLoading ? (
                <p className="text-sm" style={{ color: 'var(--text-dim)' }}>Loading documents…</p>
              ) : documents.length === 0 ? (
                <p className="rounded-[16px] px-5 py-4 text-sm" style={{ background: 'var(--surface-soft)', border: '1px solid var(--border)', color: 'var(--text-dim)' }}>No documents indexed yet.</p>
              ) : (
                <ul className="space-y-3">
                  {documents.map((document) => (
                    <li key={document.document_id} className="flex items-center gap-4 rounded-[16px] px-5 py-4" style={{ background: 'var(--surface-soft)', border: '1px solid var(--border)' }}>
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] text-xs font-bold uppercase" style={{ background: 'var(--primary-soft)', color: 'var(--primary)' }}>{document.file_type}</span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold" style={{ color: 'var(--text)' }}>{document.filename}</p>
                        <p className="text-xs" style={{ color: 'var(--text-dim)' }}>Ready to search</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleDelete(document.document_id)}
                        className="rounded-[10px] px-3 py-1.5 text-xs font-semibold transition-all"
                        style={{ color: 'var(--text-dim)', background: 'var(--surface-soft)', border: '1px solid var(--border)' }}
                        onMouseEnter={e => { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.borderColor = 'var(--danger-border)'; e.currentTarget.style.background = 'var(--danger-soft)' }}
                        onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-dim)'; e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--surface-soft)' }}
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
          </SectionWide>
        )}

        {/* ── Muscle Tutor panel ── */}
        {studyMode === 'muscle' && (
          <SectionWide title={loc.ui.muscleTutor}>
            <MuscleTopicGrid language={language} onPromptSelect={handlePromptSelect} />
          </SectionWide>
        )}

        {/* ── Ask a Question (shared by both modes) ── */}
        <SectionWide title={loc.ui.askAQuestion}>
          <VoiceRecorder
            language={language}
            onTranscript={handleTranscript}
            onAudioCaptured={handleAudioCaptured}
            onError={handleVoiceError}
            disabled={phase === 'asking'}
          />
          {phase === 'asking' && (
            <div
              className="flex items-center justify-center gap-3 rounded-[13px] px-6 py-4 text-sm animate-fade-up"
              style={{ background: 'var(--primary-soft)', border: '1px solid var(--primary-border)', color: 'var(--primary)', marginTop: 16 }}
            >
              <Spinner />
              {askingText}
            </div>
          )}
          {asrError && <ErrorNotice message={asrError} />}
        </SectionWide>

        {/* ── Transcript / Fix / Ask (shared by both modes) ── */}
        {transcript && (
          <SectionWide title={loc.ui.yourQuestion}>
            <textarea
              value={transcript}
              onChange={(event) => handleTranscriptChange(event.target.value)}
              disabled={phase === 'asking' || correctingTranscript}
              rows={4}
              aria-label={loc.ui.yourQuestion}
              className="nb-input w-full resize-y"
              style={{ minHeight: 110, fontSize: 15, lineHeight: 1.65 }}
            />

            {correctionError && <p className="mt-3 text-sm" style={{ color: 'var(--warning)' }}>{correctionError}</p>}
            {ragError && <ErrorNotice message={ragError} />}

            <div className="mt-5 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void handleFixTranscript()}
                disabled={!transcript.trim() || phase === 'asking' || correctingTranscript}
                className="vl-btn-secondary"
              >
                {correctingTranscript ? loc.ui.fixing : loc.ui.fixTranscript}
              </button>
              <button
                type="button"
                onClick={() => void submitQuestionToRag()}
                disabled={!transcript.trim() || phase === 'asking' || correctingTranscript}
                className="vl-btn-primary"
              >
                {phase === 'asking' ? loc.ui.asking : phase === 'rag-error' ? loc.ui.retryAnswer : loc.ui.askArrow}
              </button>
            </div>
          </SectionWide>
        )}

        {/* ── Answer (shared by both modes) ── */}
        {result && (
          <>
            <SectionWide title={loc.ui.answer}>
              {/* Answer mode badge */}
              <div style={{ marginBottom: 18 }}>
                {result.documentGrounded ? (
                  <span
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      fontSize: 11, fontWeight: 700, padding: '5px 12px', borderRadius: 50,
                      background: 'var(--primary-soft)', color: 'var(--primary)',
                      border: '1px solid var(--primary-border)', letterSpacing: '0.05em', textTransform: 'uppercase',
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
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      fontSize: 11, fontWeight: 700, padding: '5px 12px', borderRadius: 50,
                      background: 'var(--success-soft)', color: 'var(--success)',
                      border: '1px solid var(--success-border)', letterSpacing: '0.05em', textTransform: 'uppercase',
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

              <MarkdownContent content={result.answer} className="text-base" />

              {/* TTS controls */}
              <div className="mt-6 pt-5" style={{ borderTop: '1px solid var(--border)' }}>
                {audioLoading && (
                  <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-dim)' }}><Spinner /> {loc.ui.preparingAudio}</div>
                )}
                {audioUrl && (
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <button
                      type="button"
                      onClick={() => void audioRef.current?.play()}
                      className="vl-btn-primary"
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3" /></svg>
                      {loc.ui.playAnswer}
                    </button>
                    <audio ref={audioRef} src={audioUrl} controls className="h-10 flex-1" preload="metadata" />
                  </div>
                )}
                {audioError && (
                  <div className="flex flex-wrap items-center gap-3">
                    <p className="text-sm" style={{ color: 'var(--warning)' }}>{audioError}</p>
                    <button
                      type="button"
                      onClick={() => void synthesizeAnswer(result.answer, language)}
                      disabled={audioLoading}
                      className="text-sm font-semibold transition-colors disabled:opacity-40"
                      style={{ color: 'var(--primary)' }}
                    >
                      {loc.ui.retryAudio}
                    </button>
                  </div>
                )}
              </div>
            </SectionWide>

            {/* ── Sources ── */}
            {showSources && (
              <SectionWide title={loc.ui.sources}>
                <ol className="space-y-3">
                  {result.references.map((reference, index) => (
                    <li key={`${reference.document_id}-${index}`} className="rounded-[16px] px-5 py-4 nb-inset">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold" style={{ color: 'var(--text-muted)' }}>{reference.filename}</span>
                        {reference.page != null && (
                          <span className="rounded-[8px] px-2.5 py-0.5 text-xs" style={{ background: 'var(--surface-soft)', border: '1px solid var(--border)', color: 'var(--text-dim)' }}>Page {reference.page}</span>
                        )}
                      </div>
                      {reference.excerpt && (
                        <p className="mt-3 line-clamp-3 text-sm leading-relaxed italic" style={{ borderLeft: '2px solid var(--primary-border)', paddingLeft: 12, color: 'var(--text-muted)' }}>
                          {reference.excerpt}
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
              </SectionWide>
            )}
          </>
        )}

        {/* ── Ask another question ── */}
        {(phase === 'answered' || phase === 'rag-error') && (
          <button type="button" onClick={clearAnswer}
            className="self-center vl-btn-secondary" style={{ alignSelf: 'center' }}>
            {loc.ui.askAnother}
          </button>
        )}

        {/* ── History ── */}
        <SectionWide title="History">
          <HistoryPanel
            entries={historyEntries}
            loading={historyLoading}
            onDelete={handleDeleteHistoryEntry}
            onClearAll={handleClearHistory}
          />
        </SectionWide>
      </main>
    </div>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Full-width section card — uses the new design token glass surface */
function SectionWide({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="nb-card p-6 sm:p-8 lg:p-9">
      <h2 className="vl-label" style={{ marginBottom: 20 }}>{title}</h2>
      {children}
    </section>
  )
}

function Spinner() {
  return (
    <span
      className="inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2"
      style={{ borderColor: 'var(--primary-soft)', borderTopColor: 'var(--primary)' }}
      aria-hidden
    />
  )
}

function ErrorNotice({ message }: { message: string }) {
  return (
    <div
      className="mt-4 rounded-[13px] px-5 py-4 text-sm animate-fade-up"
      style={{ background: 'var(--danger-soft)', border: '1px solid var(--danger-border)', color: 'var(--danger)' }}
    >
      {message}
    </div>
  )
}
