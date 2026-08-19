'use client'

import { useCallback, useEffect, useState } from 'react'
import { listDocuments, askDocument } from '@/lib/api'
import { UploadZone } from '@/components/documents/UploadZone'
import { DocumentList } from '@/components/documents/DocumentList'
import type { DocumentItem, Language, AskResponse, ChunkReference } from '@/types'
import Link from 'next/link'

// ── Language options for the ask panel ───────────────────────────────────────
const LANG_OPTIONS: { value: Language; label: string }[] = [
  { value: 'english', label: '🇬🇧 English' },
  { value: 'tamil',   label: '🇮🇳 Tamil' },
  { value: 'sinhala', label: '🇱🇰 Sinhala' },
  { value: 'mixed',   label: '🌐 Mixed' },
]

export default function DocumentsPage() {
  const [documents, setDocuments]   = useState<DocumentItem[]>([])
  const [loading, setLoading]       = useState(true)
  const [question, setQuestion]     = useState('')
  const [language, setLanguage]     = useState<Language>('english')
  const [asking, setAsking]         = useState(false)
  const [response, setResponse]     = useState<AskResponse | null>(null)
  const [askError, setAskError]     = useState<string | null>(null)

  // Load documents on mount
  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch((e) => console.error('Failed to load documents', e))
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
      const res = await askDocument(question.trim(), language)
      setResponse(res)
    } catch (e) {
      setAskError(e instanceof Error ? e.message : 'Failed to get answer')
    } finally {
      setAsking(false)
    }
  }

  const totalChunks = documents.reduce((s, d) => s + d.chunk_count, 0)

  return (
    <div className="min-h-screen" style={{ background: '#080811' }}>

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="glass fixed top-0 left-0 right-0 z-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="glow-dot" />
            <span className="font-semibold text-sm text-white tracking-tight">VoiceLearn AI</span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/test"
              className="text-xs font-medium text-white/40 hover:text-white/70 transition-colors"
            >
              ← Voice Studio
            </Link>
            <span className="inline-flex items-center gap-1.5 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-[11px] font-semibold rounded-full px-3 py-1">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
              Phase 2 · RAG
            </span>
          </div>
        </div>
      </header>

      {/* ── Body ───────────────────────────────────────────────────────── */}
      <main className="pt-14 pb-24">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10 flex flex-col gap-8">

          {/* Hero */}
          <div className="text-center flex flex-col items-center gap-4 pt-4 pb-2">
            <div className="inline-flex items-center gap-2 border border-indigo-500/25 bg-indigo-500/10 rounded-full px-3.5 py-1.5 text-xs font-semibold text-indigo-400">
              Phase 2 — Document Intelligence
            </div>
            <h1 className="text-3xl sm:text-4xl font-bold text-gradient-subtle tracking-tight">
              Your Lecture Library
            </h1>
            <p className="text-sm text-white/40 max-w-sm leading-relaxed">
              Upload your slides, notes, and readings — then ask questions in any language.
            </p>
          </div>

          {/* ── Stats bar ──────────────────────────────────────────────── */}
          <div className="glass-card rounded-2xl px-5 py-4 flex items-center gap-6">
            <Stat label="Documents" value={documents.length} />
            <div className="divider" style={{ width: 1, height: 32, background: 'rgba(255,255,255,0.07)' }} />
            <Stat label="Indexed chunks" value={totalChunks} />
            <div className="divider" style={{ width: 1, height: 32, background: 'rgba(255,255,255,0.07)' }} />
            <Stat label="Formats" value="6" suffix="types" />
          </div>

          {/* ── Two-column layout (upload + list) ─────────────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}
               className="sm:grid-cols-2 grid-cols-1">

            {/* Upload */}
            <div className="glass-card rounded-3xl p-5 flex flex-col gap-4">
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-white/30">
                Upload Document
              </p>
              <UploadZone onUploaded={handleUploaded} />
            </div>

            {/* Document list */}
            <div className="glass-card rounded-3xl p-5 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-white/30">
                  Your Documents
                </p>
                {documents.length > 0 && (
                  <span className="text-[11px] text-white/30 font-medium">
                    {documents.length} file{documents.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>

              {loading ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'rgba(255,255,255,0.25)', fontSize: 13 }}>
                  Loading…
                </div>
              ) : (
                <DocumentList documents={documents} onDeleted={handleDeleted} />
              )}
            </div>
          </div>

          {/* ── Ask panel ──────────────────────────────────────────────── */}
          <div className="glass-card rounded-3xl p-6 sm:p-8 flex flex-col gap-5">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-white/30 mb-1">
                Ask Your Documents
              </p>
              <p className="text-xs text-white/35">
                Type or paste a question — our AI searches your uploaded files and answers.
              </p>
            </div>

            {/* Language select */}
            <div className="flex gap-2 flex-wrap">
              {LANG_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setLanguage(opt.value)}
                  className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-all duration-150 ${
                    language === opt.value
                      ? 'border-indigo-500/50 bg-indigo-500/15 text-indigo-300'
                      : 'border-white/10 bg-white/5 text-white/45 hover:text-white/70 hover:border-white/20'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Input + button */}
            <div style={{ display: 'flex', gap: 10 }}>
              <input
                id="ask-input"
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                placeholder="e.g. What is backpropagation? Explain the law of demand..."
                disabled={asking}
                style={{
                  flex: 1,
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 12,
                  padding: '10px 14px',
                  fontSize: 14,
                  color: 'rgba(255,255,255,0.85)',
                  outline: 'none',
                  transition: 'border-color 0.15s',
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = 'rgba(99,102,241,0.5)'}
                onBlur={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'}
              />
              <button
                id="ask-btn"
                onClick={handleAsk}
                disabled={asking || !question.trim() || documents.length === 0}
                style={{
                  padding: '10px 20px',
                  borderRadius: 12,
                  border: 'none',
                  background: (asking || !question.trim() || documents.length === 0)
                    ? 'rgba(99,102,241,0.25)'
                    : 'linear-gradient(135deg, #6366f1, #a855f7)',
                  color: 'white',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: (asking || !question.trim() || documents.length === 0) ? 'not-allowed' : 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'opacity 0.15s',
                }}
              >
                {asking ? 'Thinking…' : 'Ask →'}
              </button>
            </div>

            {documents.length === 0 && !loading && (
              <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', marginTop: -8 }}>
                Upload at least one document before asking questions.
              </p>
            )}

            {/* Error */}
            {askError && (
              <div style={{
                background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
                borderRadius: 12, padding: '10px 14px',
                fontSize: 13, color: '#f87171',
              }}>
                ⚠ {askError}
              </div>
            )}

            {/* Answer */}
            {response && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div className="divider" />

                {/* Enhanced query */}
                {response.enhanced_query && response.enhanced_query !== question && (
                  <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)' }}>
                    <span style={{ color: 'rgba(99,102,241,0.8)' }}>Optimized query: </span>
                    "{response.enhanced_query}"
                  </div>
                )}

                {/* Answer box */}
                <div style={{
                  background: 'rgba(99,102,241,0.06)',
                  border: '1px solid rgba(99,102,241,0.2)',
                  borderRadius: 14,
                  padding: '16px 18px',
                }}>
                  <p style={{ fontSize: 11, fontWeight: 700, color: 'rgba(99,102,241,0.8)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                    Answer
                  </p>
                  <p style={{ fontSize: 14, lineHeight: 1.7, color: 'rgba(255,255,255,0.85)' }}>
                    {response.answer}
                  </p>
                </div>

                {/* References */}
                {response.references.length > 0 && (
                  <div>
                    <p style={{ fontSize: 11, fontWeight: 700, color: 'rgba(255,255,255,0.25)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                      Sources ({response.references.length})
                    </p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {response.references.map((ref: ChunkReference, i: number) => (
                        <div key={i} style={{
                          background: 'rgba(255,255,255,0.03)',
                          border: '1px solid rgba(255,255,255,0.07)',
                          borderRadius: 10,
                          padding: '8px 12px',
                          fontSize: 12,
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                            <span style={{ color: 'rgba(255,255,255,0.5)', fontWeight: 600 }}>{ref.filename}</span>
                            <span style={{ color: 'rgba(99,102,241,0.7)', fontWeight: 600 }}>
                              {Math.round(ref.score * 100)}% match
                              {ref.page ? ` · p.${ref.page}` : ''}
                            </span>
                          </div>
                          <p style={{ color: 'rgba(255,255,255,0.35)', lineHeight: 1.5 }}>{ref.excerpt}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex flex-wrap justify-center gap-x-5 gap-y-1.5 text-[11px] text-white/25 font-medium">
            <span>Llama 3.1 8B</span>
            <span className="text-white/10">·</span>
            <span>Qwen2.5-3B Prompt Enhancer</span>
            <span className="text-white/10">·</span>
            <span>ChromaDB · MiniLM Embeddings</span>
            <span className="text-white/10">·</span>
            <span>Supabase Storage</span>
          </div>

        </div>
      </main>
    </div>
  )
}

// ── Stat chip ─────────────────────────────────────────────────────────────────
function Stat({ label, value, suffix }: { label: string; value: number | string; suffix?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 20, fontWeight: 700, color: 'rgba(255,255,255,0.85)' }}>
        {value}{suffix ? <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.35)', marginLeft: 4 }}>{suffix}</span> : null}
      </span>
      <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', fontWeight: 500 }}>{label}</span>
    </div>
  )
}
