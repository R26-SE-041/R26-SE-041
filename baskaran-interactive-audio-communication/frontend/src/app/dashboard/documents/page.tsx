'use client'

/**
 * /dashboard/documents — Document Library
 * Full light-mode redesign — NotebookLM style
 */

import { useCallback, useEffect, useState } from 'react'
import { UploadZone } from '@/components/documents/UploadZone'
import { DocumentList } from '@/components/documents/DocumentList'
import { listDocuments, askDocument } from '@/lib/api'
import type { DocumentItem, Language, AskResponse, ChunkReference } from '@/types'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import Link from 'next/link'

const LANG_OPTIONS: { value: Language; label: string; flag: string }[] = [
  { value: 'english', label: 'English', flag: '🇬🇧' },
  { value: 'tamil',   label: 'Tamil',   flag: '🇮🇳' },
  { value: 'sinhala', label: 'Sinhala', flag: '🇱🇰' },
]

export default function DashboardDocumentsPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [loading, setLoading]     = useState(true)
  const [question, setQuestion]   = useState('')
  const [language, setLanguage]   = useState<Language>('english')
  const [asking, setAsking]       = useState(false)
  const [response, setResponse]   = useState<AskResponse | null>(null)
  const [askError, setAskError]   = useState<string | null>(null)

  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch(() => {/* handled by api client */})
      .finally(() => setLoading(false))
  }, [])

  const handleUploaded = useCallback((doc: DocumentItem) => {
    setDocuments((prev) => [doc, ...prev])
  }, [])

  const handleDeleted = useCallback((id: string) => {
    setDocuments((prev) => prev.filter((d) => d.document_id !== id))
  }, [])

  const handleAsk = async () => {
    if (!question.trim() || asking) return
    setAsking(true)
    setAskError(null)
    setResponse(null)
    try {
      const res = await askDocument(question.trim(), language, undefined, undefined, true)
      setResponse(res)
    } catch (e) {
      setAskError(e instanceof Error ? e.message : 'Failed to get answer')
    } finally {
      setAsking(false)
    }
  }

  const totalChunks = documents.reduce((s, d) => s + d.chunk_count, 0)

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--c-bg)', transition: 'background 0.25s' }}>

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="nb-header sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-5 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: 'var(--c-blue)' }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.2}
                strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              </svg>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Link href="/dashboard" className="font-medium transition-colors" style={{ color: 'var(--c-ink-faint)' }}>
                Voice Q&amp;A
              </Link>
              <span style={{ color: 'var(--c-ink-ghost)' }}>/</span>
              <span className="font-semibold" style={{ color: 'var(--c-ink)' }}>Documents</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold rounded-full px-3 py-1"
              style={{ background: 'var(--c-blue-soft)', border: '1px solid var(--c-blue-border)', color: 'var(--c-blue)' }}>
              <span className="w-1.5 h-1.5 rounded-full animate-pulse-slow" style={{ background: 'var(--c-blue)' }} />
              RAG Active
            </span>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-5 py-8 flex flex-col gap-6">

        {/* Page title */}
        <div className="pt-2">
          <h1 className="text-2xl font-semibold text-ink tracking-tight">Document Library</h1>
          <p className="text-sm text-ink-faint mt-1">Upload your slides, notes, and readings — then ask questions in any language.</p>
        </div>

        {/* Stats bar */}
        <div className="nb-card px-5 py-4 flex items-center gap-6">
          <StatBadge label="Documents" value={documents.length} />
          <div style={{ width: 1, height: 32, background: 'rgba(0,0,0,0.07)' }} />
          <StatBadge label="Indexed chunks" value={totalChunks} />
          <div style={{ width: 1, height: 32, background: 'rgba(0,0,0,0.07)' }} />
          <StatBadge label="Formats" value="PDF · PPTX · DOCX · XLSX · TXT · MD" small />
        </div>

        {/* Upload + List grid */}
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="nb-card p-5 flex flex-col gap-4">
            <p className="nb-label">Upload Lecture File</p>
            <UploadZone onUploaded={handleUploaded} />
          </div>

          <div className="nb-card p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <p className="nb-label">Your Library</p>
              {documents.length > 0 && (
                <span className="text-xs text-ink-faint font-medium">
                  {documents.length} file{documents.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>
            {loading ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner label="Loading documents…" />
              </div>
            ) : (
              <DocumentList documents={documents} onDeleted={handleDeleted} />
            )}
          </div>
        </div>

        {/* Ask / RAG panel */}
        <div className="nb-card p-6 sm:p-8 flex flex-col gap-5">
          <div>
            <p className="nb-label mb-1">Ask Your Documents</p>
            <p className="text-xs text-ink-faint">
              Type your question — AI searches your library and generates a grounded answer.
            </p>
          </div>

          {/* Language chips */}
          <div className="flex gap-2 flex-wrap">
            {LANG_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setLanguage(opt.value)}
                className={`nb-chip ${language === opt.value ? 'nb-chip-active' : ''}`}
              >
                {opt.flag} {opt.label}
              </button>
            ))}
          </div>

          {/* Input row */}
          <div className="flex gap-3">
            <input
              id="ask-input"
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
              placeholder="e.g. Explain backpropagation, What is the law of supply and demand…"
              disabled={asking}
              className="nb-input flex-1"
            />
            <button
              id="ask-btn"
              onClick={handleAsk}
              disabled={asking || !question.trim() || documents.length === 0}
              className="nb-btn-primary flex-shrink-0"
            >
              {asking ? (
                <>
                  <div className="w-3.5 h-3.5 rounded-full border-2 border-blue-200 border-t-white animate-spin" />
                  Thinking…
                </>
              ) : 'Ask →'}
            </button>
          </div>

          {documents.length === 0 && !loading && (
            <p className="text-xs text-ink-faint -mt-2">↑ Upload at least one document first.</p>
          )}

          {/* Error */}
          {askError && (
            <div className="rounded-xl px-4 py-3 text-sm text-red-700 animate-fade-up"
              style={{ background: '#FEF2F2', border: '1px solid rgba(234,67,53,0.2)' }}>
              ⚠ {askError}
            </div>
          )}

          {/* Answer */}
          {response && (
            <div className="flex flex-col gap-4 animate-fade-up">
              <div className="nb-divider" />

              {response.enhanced_query && response.enhanced_query !== question && (
                <p className="text-xs text-ink-faint">
                  <span className="font-semibold" style={{ color: '#1A73E8' }}>Optimized: </span>
                  &ldquo;{response.enhanced_query}&rdquo;
                </p>
              )}

              <div className="rounded-xl p-5" style={{ background: '#EEF3FD', border: '1px solid rgba(26,115,232,0.15)' }}>
                <p className="nb-label mb-2" style={{ color: '#1A73E8' }}>Answer</p>
                <p className="text-sm text-ink leading-relaxed">{response.answer}</p>
              </div>

              {response.references.length > 0 && (
                <div>
                  <p className="nb-label mb-3">Sources ({response.references.length})</p>
                  <div className="flex flex-col gap-2">
                    {response.references.map((ref: ChunkReference, i: number) => (
                      <div key={i} className="nb-inset p-3">
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-2 text-xs">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                              stroke="#AEAEB2" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                              <polyline points="14 2 14 8 20 8" />
                            </svg>
                            <span className="font-medium text-ink-soft truncate max-w-[200px]">{ref.filename}</span>
                            {ref.page && <span className="text-ink-faint">p.{ref.page}</span>}
                          </div>
                          <span className="text-xs font-semibold flex-shrink-0" style={{ color: '#1A73E8' }}>
                            {Math.round(ref.score * 100)}% match
                          </span>
                        </div>
                        <p className="text-xs text-ink-muted leading-relaxed border-l-2 pl-2.5 italic"
                          style={{ borderColor: '#DBD8CC' }}>
                          {ref.excerpt}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex flex-wrap justify-center gap-x-5 gap-y-1 text-xs text-ink-faint py-4 border-t border-sand-200">
          <span>Llama 3.1 8B</span>
          <span>·</span>
          <span>Qwen2.5-3B Prompt Enhancer</span>
          <span>·</span>
          <span>ChromaDB · MiniLM Embeddings</span>
          <span>·</span>
          <span>Supabase Storage</span>
        </div>
      </main>
    </div>
  )
}

function StatBadge({ label, value, small }: { label: string; value: number | string; small?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className={`font-bold text-ink ${small ? 'text-sm' : 'text-xl'}`}>{value}</span>
      <span className="text-xs text-ink-faint font-medium">{label}</span>
    </div>
  )
}
