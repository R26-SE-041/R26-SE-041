import { useState } from 'react'
import { clsx } from 'clsx'
import type { SessionMessage } from '@/types'

interface MessageBubbleProps {
  message: SessionMessage
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const [showExcerpts, setShowExcerpts] = useState(false)

  return (
    <div className={clsx('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      {/* Avatar */}
      <div className={clsx(
        'w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 mt-1',
        isUser
          ? 'bg-brand-600 text-white'
          : 'bg-gradient-to-br from-accent-500 to-brand-600 text-white'
      )}>
        {isUser ? '🎤' : '🤖'}
      </div>

      {/* Bubble */}
      <div className={clsx(
        'max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
        isUser
          ? 'bg-brand-600/20 border border-brand-500/30 text-white rounded-tr-sm'
          : 'bg-surface-700 border border-white/10 text-white/90 rounded-tl-sm'
      )}>
        <p className="whitespace-pre-wrap">{message.content}</p>

        {/* Audio playback — Phase 3 (TTS) */}
        {message.audio_url && (
          <audio controls className="mt-2 w-full h-8 opacity-70 hover:opacity-100 transition-opacity" src={message.audio_url}>
            Your browser does not support the audio element.
          </audio>
        )}
        {!isUser && message.audio_pending && (
          <p className="mt-2 text-xs text-white/40">Generating audio…</p>
        )}
        {!isUser && message.audio_error && (
          <p className="mt-2 text-xs text-amber-300/80">{message.audio_error}</p>
        )}

        {/* Document references — shown for assistant messages */}
        {!isUser && message.references && message.references.length > 0 && (
          <div className="mt-3 pt-3 border-t border-white/10">
            {/* Header row with toggle */}
            <button
              onClick={() => setShowExcerpts((v) => !v)}
              className="flex items-center gap-1.5 w-full text-left group"
            >
              <span className="text-[10px] text-white/40 uppercase tracking-wide">
                Sources ({message.references.length})
              </span>
              <span className="ml-auto text-[10px] text-white/25 group-hover:text-white/50 transition-colors">
                {showExcerpts ? '▲ hide' : '▼ show excerpts'}
              </span>
            </button>

            <div className="mt-1.5 space-y-1.5">
              {message.references.map((ref, i) => (
                <div key={i} className="rounded-xl bg-white/5 px-3 py-2">
                  {/* File + page + score */}
                  <div className="flex items-center gap-2 text-[11px]">
                    <span>📄</span>
                    <span className="text-white/60 truncate max-w-[160px]" title={ref.filename}>
                      {ref.filename}
                    </span>
                    {ref.page && (
                      <span className="text-white/30 flex-shrink-0">p.{ref.page}</span>
                    )}
                    <span className="ml-auto flex-shrink-0 text-brand-400 font-medium">
                      {(ref.score * 100).toFixed(0)}%
                    </span>
                  </div>

                  {/* Collapsible excerpt */}
                  {showExcerpts && ref.excerpt && (
                    <p className="mt-1.5 text-[11px] text-white/35 leading-relaxed italic border-l border-white/10 pl-2">
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
