'use client'

import { useEffect, useState } from 'react'
import { MarkdownContent } from '@/components/ui/MarkdownContent'
import type { LocalHistoryEntry } from '@/lib/historyDb'

const LANGUAGE_LABEL: Record<string, string> = {
  english: 'English',
  tamil: 'Tamil',
  sinhala: 'Sinhala',
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

interface HistoryPanelProps {
  entries: LocalHistoryEntry[]
  loading: boolean
  onDelete: (id: string) => void
  onClearAll: () => void
}

export function HistoryPanel({ entries, loading, onDelete, onClearAll }: HistoryPanelProps) {
  if (loading) {
    return <p className="text-sm" style={{ color: 'var(--text-dim)' }}>Loading history…</p>
  }

  if (entries.length === 0) {
    return (
      <p
        className="rounded-[16px] px-5 py-4 text-sm"
        style={{ background: 'var(--surface-soft)', border: '1px solid var(--border)', color: 'var(--text-dim)' }}
      >
        No questions yet. Your voice chats, transcripts, and answers will appear here — saved privately in this browser.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={onClearAll}
          className="text-xs font-semibold transition-colors"
          style={{ color: 'var(--text-dim)' }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--danger)' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-dim)' }}
        >
          Clear all
        </button>
      </div>
      <ul className="flex flex-col gap-3">
        {entries.map((entry) => (
          <HistoryEntryCard key={entry.id} entry={entry} onDelete={() => onDelete(entry.id)} />
        ))}
      </ul>
    </div>
  )
}

function HistoryEntryCard({ entry, onDelete }: { entry: LocalHistoryEntry; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const [questionAudioUrl, setQuestionAudioUrl] = useState<string | null>(null)
  const [answerAudioUrl, setAnswerAudioUrl] = useState<string | null>(null)

  // Object URLs are created only while a card is expanded and revoked on
  // collapse/unmount, so we never leak blob URLs for entries the user isn't viewing.
  useEffect(() => {
    if (!expanded) return
    const urls: string[] = []
    if (entry.questionAudio) {
      const url = URL.createObjectURL(entry.questionAudio)
      urls.push(url)
      setQuestionAudioUrl(url)
    }
    if (entry.answerAudio) {
      const url = URL.createObjectURL(entry.answerAudio)
      urls.push(url)
      setAnswerAudioUrl(url)
    }
    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url))
      setQuestionAudioUrl(null)
      setAnswerAudioUrl(null)
    }
  }, [expanded, entry.questionAudio, entry.answerAudio])

  return (
    <li
      className="rounded-[16px] px-5 py-4"
      style={{ background: 'var(--surface-soft)', border: '1px solid var(--border)' }}
    >
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="flex w-full items-start justify-between gap-4 text-left"
        aria-expanded={expanded}
      >
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <span
              className="rounded-[8px] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
              style={{ background: 'var(--primary-soft)', color: 'var(--primary)' }}
            >
              {entry.studyMode === 'document' ? 'Document' : 'Muscle Tutor'}
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: 'var(--text-dim)' }}>
              {LANGUAGE_LABEL[entry.language] ?? entry.language}
            </span>
            {(entry.questionAudio || entry.answerAudio) && (
              <span className="text-[10px]" style={{ color: 'var(--text-dim)' }}>🔊 audio saved</span>
            )}
          </div>
          <p className="truncate text-sm font-semibold" style={{ color: 'var(--text)' }}>{entry.transcript}</p>
          <p className="mt-0.5 text-xs" style={{ color: 'var(--text-dim)' }}>{formatTimestamp(entry.createdAt)}</p>
        </div>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            color: 'var(--text-dim)',
            flexShrink: 0,
            marginTop: 2,
            transform: expanded ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.15s',
          }}
          aria-hidden
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {expanded && (
        <div className="mt-4 flex flex-col gap-4 border-t pt-4" style={{ borderColor: 'var(--border)' }}>
          <div>
            <p className="vl-label mb-1.5">Question</p>
            <p className="text-sm" style={{ color: 'var(--text)' }}>{entry.transcript}</p>
            {questionAudioUrl && (
              <audio controls preload="metadata" className="mt-2 h-9 w-full" src={questionAudioUrl}>
                Your browser does not support audio playback.
              </audio>
            )}
          </div>

          <div>
            <p className="vl-label mb-1.5">Answer</p>
            <MarkdownContent content={entry.answer} className="text-sm" />
            {answerAudioUrl && (
              <audio controls preload="metadata" className="mt-2 h-9 w-full" src={answerAudioUrl}>
                Your browser does not support audio playback.
              </audio>
            )}
          </div>

          {entry.references.length > 0 && (
            <div>
              <p className="vl-label mb-1.5">Sources</p>
              <ul className="space-y-1">
                {entry.references.map((reference, index) => (
                  <li key={`${reference.document_id}-${index}`} className="text-xs" style={{ color: 'var(--text-dim)' }}>
                    {reference.filename}{reference.page != null ? ` · page ${reference.page}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            type="button"
            onClick={(event) => { event.stopPropagation(); onDelete() }}
            className="self-start text-xs font-semibold transition-colors"
            style={{ color: 'var(--danger)' }}
          >
            Delete this entry
          </button>
        </div>
      )}
    </li>
  )
}
