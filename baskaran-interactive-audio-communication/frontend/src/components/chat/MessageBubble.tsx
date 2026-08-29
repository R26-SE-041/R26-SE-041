'use client'

import { useState } from 'react'
import type { SessionMessage } from '@/types'
import { MarkdownContent } from '@/components/ui/MarkdownContent'

interface MessageBubbleProps {
  message: SessionMessage
}

// ─── Audio Player ─────────────────────────────────────────────────────────────

function AudioPlayer({ src }: { src: string }) {
  const [playing, setPlaying] = useState(false)
  const audioRef = useState(() => typeof window !== 'undefined' ? new Audio(src) : null)[0]

  const toggle = () => {
    if (!audioRef) return
    if (playing) { audioRef.pause() } else { audioRef.play() }
    setPlaying(!playing)
  }

  return (
    <button type="button" onClick={toggle}
      className="mt-2 inline-flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full transition-all"
      style={{ background: 'var(--c-blue-soft)', color: 'var(--c-blue)', border: '1px solid var(--c-blue-border)' }}>
      {playing ? (
        <>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="4" width="4" height="16" rx="1" />
            <rect x="14" y="4" width="4" height="16" rx="1" />
          </svg>
          Pause
        </>
      ) : (
        <>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          Play Answer
        </>
      )}
    </button>
  )
}

// ─── Message Bubble ───────────────────────────────────────────────────────────

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const [showExcerpts, setShowExcerpts] = useState(false)

  return (
    <div className={`flex gap-2.5 animate-fade-up ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-1"
        style={{
          background: isUser ? 'var(--c-blue-soft)' : 'var(--c-inset)',
          border: '1.5px solid',
          borderColor: isUser ? 'var(--c-blue-border)' : 'var(--c-border)',
        }}>
        {isUser ? (
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
            stroke="var(--c-blue)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          </svg>
        ) : (
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
            stroke="var(--c-ink-muted)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24A2.5 2.5 0 0 1 9.5 2" />
            <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24A2.5 2.5 0 0 0 14.5 2" />
          </svg>
        )}
      </div>

      {/* Bubble */}
      <div className={`max-w-[78%] text-sm leading-relaxed rounded-2xl px-4 py-3 ${isUser ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}
        style={{
          background: isUser ? 'var(--c-blue-soft)' : 'var(--c-card)',
          border: '1px solid',
          borderColor: isUser ? 'var(--c-blue-border)' : 'var(--c-border)',
          color: 'var(--c-ink)',
          boxShadow: isUser ? 'none' : 'var(--shadow-card)',
        }}>

        {/* Render plain text for user, markdown for assistant */}
        {isUser
          ? <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{message.content}</p>
          : <MarkdownContent content={message.content} />
        }

        {/* Audio player */}
        {message.audio_url && <AudioPlayer src={message.audio_url} />}
        {!isUser && message.audio_pending && (
          <div className="mt-2 flex items-center gap-1.5 text-xs" style={{ color: 'var(--c-ink-faint)' }}>
            <div className="w-3 h-3 rounded-full border-2 animate-spin"
              style={{ borderColor: 'var(--c-blue-soft)', borderTopColor: 'var(--c-blue)' }} />
            Generating audio…
          </div>
        )}
        {!isUser && message.audio_error && (
          <p className="mt-1.5 text-xs" style={{ color: 'var(--c-red)' }}>{message.audio_error}</p>
        )}

        {/* References */}
        {!isUser && message.references && message.references.length > 0 && (
          <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--c-border)' }}>
            <button onClick={() => setShowExcerpts((v) => !v)}
              className="flex items-center gap-1.5 w-full text-left group mb-2">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                stroke="var(--c-ink-faint)" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <span className="text-[10px] font-semibold tracking-wide uppercase" style={{ color: 'var(--c-ink-faint)' }}>
                Sources ({message.references.length})
              </span>
              <span className="ml-auto text-[10px] transition-colors" style={{ color: 'var(--c-ink-ghost)' }}>
                {showExcerpts ? '▲ hide' : '▼ show'}
              </span>
            </button>

            <div className="space-y-1.5">
              {message.references.map((ref, i) => (
                <div key={i} className="rounded-lg px-3 py-2"
                  style={{ background: 'var(--c-inset)', border: '1px solid var(--c-border)' }}>
                  <div className="flex items-center gap-2 text-[11px]">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                      stroke="var(--c-ink-faint)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <span className="truncate max-w-[160px] font-medium" style={{ color: 'var(--c-ink-muted)' }} title={ref.filename}>
                      {ref.filename}
                    </span>
                    {ref.page && <span style={{ color: 'var(--c-ink-faint)' }} className="flex-shrink-0">p.{ref.page}</span>}
                    <span className="ml-auto flex-shrink-0 font-semibold text-xs" style={{ color: 'var(--c-blue)' }}>
                      {(ref.score * 100).toFixed(0)}%
                    </span>
                  </div>

                  {showExcerpts && ref.excerpt && (
                    <p className="mt-1.5 text-[11px] leading-relaxed border-l-2 pl-2.5 italic"
                      style={{ color: 'var(--c-ink-muted)', borderColor: 'var(--c-border-md)' }}>
                      {ref.excerpt}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

