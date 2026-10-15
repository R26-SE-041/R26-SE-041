'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { LanguageSelector } from '@/components/voice/LanguageSelector'
import { VoiceRecorder } from '@/components/voice/VoiceRecorder'
import { DocumentActions } from '@/components/documents/DocumentActions'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { WorkspaceNavigation, workspaceSectionFromHash, type WorkspaceSection } from '@/components/ui/WorkspaceNavigation'
import { MarkdownContent } from '@/components/ui/MarkdownContent'
import { HistoryPanel } from '@/components/history/HistoryPanel'
import {
  askDocument,
  deleteDocument,
  listDocuments,
  synthesizeSpeech,
  uploadDocument,
} from '@/lib/api'
import type { AskResponse, DocumentItem, Language, TranscribeResponse } from '@/types'
import { getStudyLocale } from '@/lib/studyLocale'
import {
  addHistoryEntry,
  CLOUD_HISTORY, deviceHistoryCount, importDeviceHistory,
  clearStudyHistory,
  deleteHistoryEntry,
  listStudyHistory,
  updateHistoryAnswer,
  updateHistoryAudio,
  type HistoryEntry,
} from '@/lib/studyHistory'

type Phase = 'idle' | 'transcript-ready' | 'asking' | 'answered' | 'rag-error' | 'asr-error'
const workspaceCopy: Record<WorkspaceSection, { title: string; description: string }> = {
  'study-documents': { title: 'Learn with your voice', description: 'Study your documents in English, Tamil, and Sinhala.' },
  'study-question': { title: 'Ask a question', description: 'Ask about your documents, then listen to the answer.' },
  'study-actions': { title: 'Study tools', description: 'Create summaries, audio revisions, and flashcards from your documents.' },
  'saved-library-title': { title: 'Saved library', description: 'Find and reopen your saved study materials.' },
  'study-history': { title: 'History', description: 'Revisit your questions, answers, and audio.' },
}

interface Result {
  transcript: string
  answer: string
  references: AskResponse['references']
  /** Whether the answer was produced in document-grounded mode. */
  documentGrounded: boolean
}

const ACCEPTED_DOCUMENTS = '.pdf,.pptx,.docx,.xlsx,.txt,.md'
import { API_URL, BACKEND_CONFIGURED, requireBackend } from '@/lib/config'
import { createClient } from '@/lib/supabase'

async function correctTranscript(transcript: string, language: Language): Promise<string> {
  requireBackend()
  const { data: sessionData } = await createClient().auth.getSession()
  const token = sessionData.session?.access_token
  const response = await fetch(`${API_URL}/api/v1/documents/enhance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ transcript, language }),
  })
  if (!response.ok) throw new Error('Transcript correction is unavailable.')
  const data = await response.json() as { enhanced_query: string }
  return data.enhanced_query
}

export default function StudyAssistantPage() {
  const [libraryTarget, setLibraryTarget] = useState<HTMLDivElement | null>(null)
  const [activeSection, setActiveSection] = useState<WorkspaceSection>(workspaceSectionFromHash)
  const selectSection = useCallback((section: WorkspaceSection) => {
    document.querySelectorAll('audio').forEach(player => player.pause())
    setActiveSection(section)
    if (window.location.hash !== `#${section}`) window.location.hash = section
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [])
  useEffect(() => {
    const sync = () => { document.querySelectorAll('audio').forEach(player => player.pause()); setActiveSection(workspaceSectionFromHash()); window.scrollTo({ top: 0, behavior: 'instant' }) }
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])
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
  const [audioApprovalPending, setAudioApprovalPending] = useState(false)
  const [editingAnswer, setEditingAnswer] = useState(false)
  const [answerDraft, setAnswerDraft] = useState('')
  const audioRef = useRef<HTMLAudioElement>(null)
  const audioRequestRef = useRef(0)

  // Hosted history is account-scoped; local demo history remains available.
  const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [deviceEntries, setDeviceEntries] = useState(0)
  const [importingHistory, setImportingHistory] = useState(false)
  const lastQuestionAudioRef = useRef<Blob | null>(null)
  const currentHistoryEntryIdRef = useRef<string | null>(null)
  const historySaveRef = useRef<Promise<string | null> | null>(null)
  const historyAudioSaveRef = useRef<Promise<void>>(Promise.resolve())

  useEffect(() => {
    let active = true
    const refresh = () => {
      if (document.visibilityState === 'hidden') return
      listStudyHistory().then(items => { if (active) { setHistoryEntries(items); setHistoryError(null) } })
        .catch(() => { if (active) setHistoryError('History could not be loaded. Please check your connection and refresh.') })
        .finally(() => { if (active) setHistoryLoading(false) })
    }
    refresh()
    if (CLOUD_HISTORY) void deviceHistoryCount().then(count => { if (active) setDeviceEntries(count) }).catch(() => undefined)
    window.addEventListener('focus', refresh)
    const timer = CLOUD_HISTORY ? window.setInterval(refresh, 30000) : undefined
    return () => { active = false; window.removeEventListener('focus', refresh); window.clearInterval(timer) }
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
    setAudioApprovalPending(false)
    setEditingAnswer(false)
    setAnswerDraft('')
  }, [])

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
  const synthesizeAnswer = useCallback(async (answer: string, responseLanguage: Language, savingHistory?: Promise<string | null>) => {
    const requestId = ++audioRequestRef.current
    const historyId = currentHistoryEntryIdRef.current
    const pendingHistory = savingHistory ?? historySaveRef.current
    setAudioLoading(true)
    setAudioError(null)
    setAudioApprovalPending(false)
    setAudioUrl((current) => {
      if (current) URL.revokeObjectURL(current)
      return null
    })
    try {
      const blob = await synthesizeSpeech(answer, responseLanguage)
      if (requestId === audioRequestRef.current) {
        setAudioUrl(URL.createObjectURL(blob))
        setAudioLoading(false)
        const savedHistoryId = pendingHistory ? await pendingHistory : historyId
        if (savedHistoryId && requestId === audioRequestRef.current) {
          historyAudioSaveRef.current = updateHistoryAudio(savedHistoryId, blob)
            .then(() => {
              setHistoryEntries((current) =>
                current.map((item) => (item.id === savedHistoryId ? { ...item, answerAudio: blob } : item)))
            })
            .catch(() => setHistoryError('Answer audio could not be saved to your history. Please retry audio generation.'))
        }
      }
    } catch {
      if (requestId === audioRequestRef.current) {
        const locAudio = getStudyLocale(responseLanguage).ui.audioUnavailable
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
    currentHistoryEntryIdRef.current = null
    try {
      const entry = await addHistoryEntry({
        language,
        transcript: questionText,
        answer: answerText,
        references,
        documentGrounded,
        questionAudio: lastQuestionAudioRef.current ?? undefined,
      })
      currentHistoryEntryIdRef.current = entry.id
      setHistoryEntries((current) => [entry, ...current])
      setHistoryError(null)
      return entry.id
    } catch {
      setHistoryError('This answer could not be saved to history. Keep this page open and retry when connected.')
      return null
    }
  }, [language])

  const handleDeleteHistoryEntry = useCallback((id: string) => {
    if (CLOUD_HISTORY && !window.confirm('Delete this history entry and its audio from your account on every device?')) return
    void deleteHistoryEntry(id).then(() => setHistoryEntries(current => current.filter(item => item.id !== id)))
      .catch(() => setHistoryError('History could not be deleted. Please retry.'))
  }, [])

  const handleClearHistory = useCallback(() => {
    if (CLOUD_HISTORY && !window.confirm('Delete all history and history audio from your account on every device? Saved revisions and documents will remain.')) return
    void clearStudyHistory().then(() => setHistoryEntries([]))
      .catch(() => setHistoryError('History could not be cleared. Please retry.'))
  }, [])

  const handleImportHistory = async () => {
    if (!window.confirm('Import this device’s old browser history into the account you are signed in to? Only import entries that belong to you.')) return
    setImportingHistory(true)
    try {
      await importDeviceHistory()
      setHistoryEntries(await listStudyHistory())
      setDeviceEntries(await deviceHistoryCount())
      setHistoryError(null)
    } catch { setHistoryError('Import could not finish. Your remaining local entries are safe; retry to continue without duplicates.') }
    finally { setImportingHistory(false) }
  }

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
      setAsrError(getStudyLocale(language).ui.noSpeechDetected)
      return
    }

    setPhase('transcript-ready')
  }, [language])

  // ─── Submit question ───────────────────────────────────────────────────────
  const submitQuestionToRag = useCallback(async () => {
    const question = transcript.trim()
    if (!question || ragRequestActiveRef.current) return

    const isDocumentGrounded = true

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
        true,
      )
      setResult({
        transcript: question,
        answer: answer.answer,
        references: answer.references,
        documentGrounded: isDocumentGrounded,
      })
      setEditingAnswer(false)
      setAnswerDraft(answer.answer)
      setPhase('answered')
      // Only synthesize if we have a real answer — skip TTS for backend error
      // messages (e.g. "Answer generation is not available right now.") which
      // contain only English and would produce empty audio.
      const isErrorAnswer =
        answer.answer.startsWith('Answer generation is not available') ||
        answer.answer.startsWith('RAG generation is not available') ||
        answer.answer.startsWith("I couldn't generate") ||
        answer.answer.startsWith("I couldn't find relevant content")
      const savingHistory = persistHistoryEntry(question, answer.answer, answer.references, isDocumentGrounded)
      historySaveRef.current = savingHistory
      historyAudioSaveRef.current = Promise.resolve()
      if (!isErrorAnswer) {
        if (language === 'sinhala') {
          setAudioApprovalPending(true)
        } else {
          void synthesizeAnswer(answer.answer, language, savingHistory)
        }
      }
      await savingHistory
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
  }, [detectedLanguage, language, synthesizeAnswer, persistHistoryEntry, transcript])

  const saveEditedAnswer = useCallback(() => {
    const editedAnswer = answerDraft.trim()
    if (!result || !editedAnswer) return

    setResult({ ...result, answer: editedAnswer })
    setEditingAnswer(false)
    audioRequestRef.current += 1
    setAudioLoading(false)
    setAudioUrl((current) => {
      if (current) URL.revokeObjectURL(current)
      return null
    })

    const historyId = currentHistoryEntryIdRef.current
    const pendingHistory = historySaveRef.current ?? Promise.resolve(historyId)
    const pendingAudio = historyAudioSaveRef.current
    historySaveRef.current = pendingHistory.then(async (savedHistoryId) => {
      if (!savedHistoryId) return null
      await pendingAudio
      await updateHistoryAnswer(savedHistoryId, editedAnswer)
      setHistoryEntries((current) => current.map((item) => (
        item.id === savedHistoryId ? { ...item, answer: editedAnswer, answerAudio: undefined, hasAnswerAudio: false } : item
      )))
      return savedHistoryId
    }).catch(() => {
      setHistoryError('Edited answer could not be synced. Please retry saving it.')
      return null
    })
  }, [answerDraft, result])

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
  const loc = getStudyLocale(language)

  const askingText = loc.ui.searchingDocs

  // ─── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen" style={{ background: 'var(--background)', transition: 'background 0.3s' }}>

      {!BACKEND_CONFIGURED && (
        <div role="status" className="relative z-50 px-5 py-3 text-center text-sm" style={{ background: 'var(--surface)', color: 'var(--text)' }}>
          Frontend preview: backend connection is pending. Document uploads and AI actions will be available after the backend is connected.
        </div>
      )}

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
            <span className="hidden text-xs font-medium sm:inline" style={{ color: 'var(--text-dim)' }}>Voice Interaction</span>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <div className="vl-workspace">
        <WorkspaceNavigation active={activeSection} onSelect={selectSection} />
      <main className="relative z-10 mx-auto flex max-w-7xl flex-col gap-6 px-5 py-8 pb-28 sm:px-8 lg:px-10 lg:py-10">

        {/* ── Hero ── */}
        <div className="vl-study-hero flex flex-col gap-3">
          <p className="vl-eyebrow">AI Study Assistant</p>
          <h1 className="vl-serif" style={{ color: 'var(--text)' }}>{workspaceCopy[activeSection].title}</h1>
          <p className="max-w-2xl text-base leading-relaxed" style={{ color: 'var(--text-muted)' }}>
            {workspaceCopy[activeSection].description}
          </p>
        </div>

        <nav hidden={activeSection !== 'study-documents'} className="vl-study-steps" aria-label="Getting started">
          <a href="#study-documents"><span className="vl-step-number">{documents.length ? '✓' : '1'}</span><span><strong>Add a document</strong><small>{documents.length ? `${documents.length} ready to study` : 'Upload your notes or PDF'}</small></span></a>
          <a href="#study-question"><span className="vl-step-number">2</span><span><strong>Ask a question</strong><small>Choose a language, then speak</small></span></a>
          <a href="#study-actions"><span className="vl-step-number">3</span><span><strong>Create a revision</strong><small>Save audio, summaries or flashcards</small></span></a>
        </nav>

        {/* ── Document Study panel ── */}
        <div role="tabpanel" id="panel-study-documents" aria-labelledby="tab-study-documents" hidden={activeSection !== 'study-documents'} className="vl-tab-panel">
          <SectionWide id="study-documents" title="Document Study">
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
              className="vl-document-upload flex w-full items-center justify-center gap-4 rounded-xl px-5 py-6 transition-all disabled:cursor-wait disabled:opacity-60"
              style={{
                border: `2px dashed ${dragOver ? 'var(--primary)' : 'var(--border)'}`,
                background: dragOver ? 'var(--primary-soft)' : 'var(--surface-soft)',
              }}
            >
              <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-[13px]" style={{ background: 'var(--primary-soft)' }} aria-hidden>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </span>
              <div className="flex flex-col gap-1">
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
                    <li key={document.document_id} className="vl-document-row flex items-center gap-4 rounded-[16px] px-5 py-4" style={{ background: 'var(--surface-soft)', border: '1px solid var(--border)' }}>
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] text-xs font-bold uppercase" style={{ background: 'var(--primary-soft)', color: 'var(--primary)' }}>{document.file_type}</span>
                      <div className="min-w-0 flex-1">
                        <p className="vl-document-name truncate text-sm font-semibold" style={{ color: 'var(--text)' }}>{document.filename}</p>
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

        {/* ── Ask a Question ── */}
        </div>
        <div role="tabpanel" id="panel-study-question" aria-labelledby="tab-study-question" hidden={activeSection !== 'study-question'} className="vl-tab-panel">
        <section className="nb-card flex flex-wrap items-center justify-between gap-3 p-5">
          <div>
            <p className="vl-label">{loc.ui.responseLanguage}</p>
            <p className="mt-1 text-xs" style={{ color: 'var(--text-dim)' }}>Answers and audio</p>
          </div>
          <LanguageSelector value={language} onChange={selectLanguage} disabled={phase === 'asking'} />
        </section>
        <SectionWide id="study-question" title={loc.ui.askAQuestion}>
          <VoiceRecorder
            language={language}
            prepareAnswer
            active={activeSection === 'study-question'}
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

        {/* ── Transcript / Fix / Ask ── */}


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

        {/* ── Answer ── */}
        {result && (
          <>
            <SectionWide title={loc.ui.answer}>
              {/* Answer mode badge */}
              <div style={{ marginBottom: 18 }}>
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
              </div>

              {editingAnswer ? (
                <div>
                  <textarea
                    value={answerDraft}
                    onChange={(event) => setAnswerDraft(event.target.value)}
                    rows={7}
                    autoFocus
                    aria-label="Edit Sinhala answer"
                    className="nb-input w-full resize-y"
                    style={{ minHeight: 180, fontSize: 16, lineHeight: 1.75 }}
                  />
                  <div className="mt-4 flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={saveEditedAnswer}
                      disabled={!answerDraft.trim()}
                      className="vl-btn-primary disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Save Changes
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setAnswerDraft(result.answer)
                        setEditingAnswer(false)
                      }}
                      className="vl-btn-secondary"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <MarkdownContent content={result.answer} className="text-base" />
                  {audioApprovalPending && (
                    <button
                      type="button"
                      onClick={() => {
                        setAnswerDraft(result.answer)
                        setEditingAnswer(true)
                      }}
                      className="vl-btn-secondary mt-5"
                    >
                      Edit Answer
                    </button>
                  )}
                </>
              )}

              {/* TTS controls */}
              <div className="mt-6 pt-5" style={{ borderTop: '1px solid var(--border)' }}>
                {audioApprovalPending && !editingAnswer && (
                  <div className="flex flex-wrap items-center gap-3">
                    <p className="text-sm" style={{ color: 'var(--text-dim)' }}>
                      Review the Sinhala answer above. Speech will only be generated after you accept it.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        setAudioApprovalPending(false)
                        void synthesizeAnswer(result.answer, 'sinhala')
                      }}
                      className="vl-btn-primary"
                    >
                      Accept &amp; Generate Speech
                    </button>
                  </div>
                )}
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

        </div>
        <div role="tabpanel" id="panel-study-actions" aria-labelledby="tab-study-actions" hidden={activeSection !== 'study-actions'} className="vl-tab-panel">
          <div id="study-actions"><DocumentActions documents={documents} active={activeSection === 'study-actions'} libraryTarget={libraryTarget} onOpenSaved={() => selectSection('study-actions')} /></div>
        </div>
        <div role="tabpanel" id="panel-saved-library-title" aria-labelledby="tab-saved-library-title" hidden={activeSection !== 'saved-library-title'} className="vl-tab-panel">
          <div ref={setLibraryTarget} />
        </div>
        <div role="tabpanel" id="panel-study-history" aria-labelledby="tab-study-history" hidden={activeSection !== 'study-history'} className="vl-tab-panel">
        <SectionWide id="study-history" title="History">
          {CLOUD_HISTORY && <p className="text-xs mb-3" style={{ color: 'var(--text-dim)' }}>Saved to your account. Available when you sign in on another device.</p>}
          {historyError && <p role="alert" className="text-sm mb-3" style={{ color: 'var(--danger)' }}>{historyError}</p>}
          {CLOUD_HISTORY && deviceEntries > 0 && <div className="mb-4 text-sm">
            <p>{deviceEntries} old history entries are stored on this device.</p>
            <button type="button" className="nb-btn-secondary mt-2" disabled={importingHistory} onClick={() => void handleImportHistory()}>{importingHistory ? 'Importing history…' : 'Import this device’s history'}</button>
          </div>}
          <HistoryPanel
            entries={historyEntries}
            loading={historyLoading}
            onDelete={handleDeleteHistoryEntry}
            onClearAll={handleClearHistory}
          />
        </SectionWide>
        </div>
      </main>
      </div>
    </div>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Full-width section card — uses the new design token glass surface */
function SectionWide({ id, title, children }: { id?: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="nb-card p-6 sm:p-8 lg:p-9">
      <h2 className="vl-section-title" style={{ marginBottom: 20 }}>{title}</h2>
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
