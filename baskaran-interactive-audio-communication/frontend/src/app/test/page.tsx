'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { LanguageSelector } from '@/components/voice/LanguageSelector'
import { VoiceRecorder } from '@/components/voice/VoiceRecorder'
import {
  askDocument,
  deleteDocument,
  listDocuments,
  synthesizeSpeech,
  uploadDocument,
} from '@/lib/api'
import type { AskResponse, DocumentItem, Language, TranscribeResponse } from '@/types'

type Phase = 'idle' | 'transcript-ready' | 'asking' | 'answered' | 'rag-error' | 'asr-error'

interface Result {
  transcript: string
  answer: string
  references: AskResponse['references']
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
  const [language, setLanguage] = useState<Language>('english')
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [documentsLoading, setDocumentsLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [documentError, setDocumentError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [phase, setPhase] = useState<Phase>('idle')
  const [transcript, setTranscript] = useState('')
  const [detectedLanguage, setDetectedLanguage] = useState<string | undefined>()
  const [correctingTranscript, setCorrectingTranscript] = useState(false)
  const [correctionError, setCorrectionError] = useState<string | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [asrError, setAsrError] = useState<string | null>(null)
  const [ragError, setRagError] = useState<string | null>(null)
  const ragRequestActiveRef = useRef(false)

  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [audioLoading, setAudioLoading] = useState(false)
  const [audioError, setAudioError] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const audioRequestRef = useRef(0)

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

  const selectLanguage = useCallback((nextLanguage: Language) => {
    setLanguage(nextLanguage)
    clearAnswer()
  }, [clearAnswer])

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
        setAudioError('Answer audio is unavailable right now. The text answer is complete.')
      }
    } finally {
      if (requestId === audioRequestRef.current) setAudioLoading(false)
    }
  }, [])

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
      setAsrError('No speech was detected. Please try again and speak clearly.')
      return
    }

    setPhase('transcript-ready')
  }, [])

  const submitQuestionToRag = useCallback(async () => {
    const question = transcript.trim()
    if (!question || ragRequestActiveRef.current) return

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
      )
      setResult({ transcript: question, answer: answer.answer, references: answer.references })
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
  }, [detectedLanguage, language, synthesizeAnswer, transcript])

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

  return (
    <div className="min-h-screen bg-page-gradient">
      <header className="glass sticky top-0 z-50 border-b border-white/[0.06]">
        <div className="mx-auto flex h-16 max-w-3xl items-center px-4 sm:px-6">
          <span className="glow-dot" />
          <span className="ml-2.5 text-sm font-semibold tracking-tight text-white">VoiceLearn AI</span>
        </div>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10 pb-24 sm:px-6">
        <div className="flex flex-col items-center gap-3 pb-2 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-brand-300">AI Study Assistant</p>
          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">Learn from your documents, by voice</h1>
          <p className="max-w-xl text-sm leading-relaxed text-white/50">
            Upload your lecture documents, ask by voice, and receive grounded answers in your language.
          </p>
        </div>

        <Section title="Response Language">
          <LanguageSelector value={language} onChange={selectLanguage} disabled={phase === 'asking'} />
        </Section>

        <Section title="Documents">
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
            className={`flex w-full flex-col items-center gap-2 rounded-2xl border border-dashed px-5 py-7 transition-colors disabled:cursor-wait disabled:opacity-60 ${
              dragOver ? 'border-brand-400 bg-brand-500/10' : 'border-white/15 bg-white/[0.025] hover:border-brand-400/60 hover:bg-brand-500/[0.06]'
            }`}
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/15 text-xl text-brand-200" aria-hidden>↑</span>
            <span className="text-sm font-semibold text-white/80">{uploading ? 'Indexing document…' : 'Upload or drop a document'}</span>
            <span className="text-xs text-white/35">PDF, PowerPoint, Word, Excel, text, or Markdown</span>
          </button>

          <div className="mt-5">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-white/35">Indexed Documents</p>
            {documentsLoading ? (
              <p className="text-sm text-white/35">Loading documents…</p>
            ) : documents.length === 0 ? (
              <p className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3 text-sm text-white/35">No documents indexed yet.</p>
            ) : (
              <ul className="space-y-2">
                {documents.map((document) => (
                  <li key={document.document_id} className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.025] px-4 py-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.05] text-xs font-bold uppercase text-brand-300">{document.file_type}</span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-white/80">{document.filename}</p>
                      <p className="text-xs text-white/35">Ready to search</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleDelete(document.document_id)}
                      className="rounded-lg px-2 py-1 text-xs text-white/35 transition-colors hover:bg-red-500/10 hover:text-red-300"
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

        <Section title="Ask a Question">
          <VoiceRecorder
            language={language}
            onTranscript={handleTranscript}
            onError={handleVoiceError}
            disabled={phase === 'asking'}
          />
          {phase === 'asking' && (
            <div className="flex items-center justify-center gap-3 rounded-xl border border-brand-500/20 bg-brand-500/[0.07] px-4 py-3 text-sm text-brand-200">
              <Spinner />
              Searching your documents and preparing an answer…
            </div>
          )}
          {asrError && <ErrorNotice message={asrError} />}
        </Section>

        {transcript && (
          <Section title="Your Question">
            <textarea
              value={transcript}
              onChange={(event) => handleTranscriptChange(event.target.value)}
              disabled={phase === 'asking' || correctingTranscript}
              rows={3}
              aria-label="Your question"
              className="w-full resize-y rounded-2xl border border-white/10 bg-white/[0.035] px-4 py-3 text-[15px] leading-relaxed text-white/90 outline-none transition-colors focus:border-brand-400/60 disabled:cursor-wait disabled:opacity-60"
            />

            {correctionError && <p className="mt-3 text-xs text-amber-300/80">{correctionError}</p>}
            {ragError && <ErrorNotice message={ragError} />}

            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void handleFixTranscript()}
                disabled={!transcript.trim() || phase === 'asking' || correctingTranscript}
                className="inline-flex items-center justify-center rounded-xl border border-white/10 bg-white/[0.05] px-4 py-2.5 text-sm font-semibold text-white/70 transition-colors hover:bg-white/[0.09] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {correctingTranscript ? 'Fixing\u2026' : 'Fix Transcript'}
              </button>
              <button
                type="button"
                onClick={() => void submitQuestionToRag()}
                disabled={!transcript.trim() || phase === 'asking' || correctingTranscript}
                className="inline-flex items-center justify-center rounded-xl bg-brand-gradient px-5 py-2.5 text-sm font-semibold text-white shadow-brand transition-transform hover:scale-[1.02] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
              >
                {phase === 'asking' ? 'Asking\u2026' : phase === 'rag-error' ? 'Retry Answer' : 'Ask'}
              </button>
            </div>
          </Section>
        )}

        {result && (
          <>
            <Section title="Answer">
              <p className="whitespace-pre-wrap text-[15px] leading-7 text-white/90">{result.answer}</p>

              <div className="mt-5 border-t border-white/[0.07] pt-4">
                {audioLoading && (
                  <div className="flex items-center gap-2 text-sm text-white/45"><Spinner /> Preparing answer audio…</div>
                )}
                {audioUrl && (
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <button
                      type="button"
                      onClick={() => void audioRef.current?.play()}
                      className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-gradient px-4 py-2.5 text-sm font-semibold text-white shadow-brand transition-transform hover:scale-[1.02] active:scale-[0.98]"
                    >
                      <span aria-hidden>▶</span> Play Answer
                    </button>
                    <audio ref={audioRef} src={audioUrl} controls className="h-10 w-full sm:max-w-sm" preload="metadata" />
                  </div>
                )}
                {audioError && (
                  <div className="flex flex-wrap items-center gap-3">
                    <p className="text-xs text-amber-300/80">{audioError}</p>
                    <button
                      type="button"
                      onClick={() => void synthesizeAnswer(result.answer, language)}
                      disabled={audioLoading}
                      className="text-xs font-semibold text-brand-300 transition-colors hover:text-brand-200 disabled:opacity-40"
                    >
                      Retry Audio
                    </button>
                  </div>
                )}
              </div>
            </Section>

            <Section title="Sources">
              {result.references.length === 0 ? (
                <p className="text-sm text-white/35">No source references were returned.</p>
              ) : (
                <ol className="space-y-2">
                  {result.references.map((reference, index) => (
                    <li key={`${reference.document_id}-${index}`} className="rounded-xl border border-white/[0.07] bg-white/[0.025] px-4 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-white/75">{reference.filename}</span>
                        {reference.page != null && <span className="rounded bg-white/[0.06] px-2 py-0.5 text-xs text-white/40">Page {reference.page}</span>}
                      </div>
                      {reference.excerpt && <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-white/40">{reference.excerpt}</p>}
                    </li>
                  ))}
                </ol>
              )}
            </Section>
          </>
        )}

        {(phase === 'answered' || phase === 'rag-error') && (
          <button type="button" onClick={clearAnswer} className="self-center text-sm font-medium text-white/45 transition-colors hover:text-white/75">
            Ask another question
          </button>
        )}
      </main>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="glass-card rounded-3xl p-5 sm:p-6">
      <h2 className="mb-5 text-xs font-bold uppercase tracking-[0.16em] text-white/40">{title}</h2>
      {children}
    </section>
  )
}

function Spinner() {
  return <span className="inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden />
}

function ErrorNotice({ message }: { message: string }) {
  return <p className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">{message}</p>
}
