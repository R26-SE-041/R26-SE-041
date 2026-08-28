import type { SessionMessage } from '@/types'
import { MessageBubble } from './MessageBubble'

interface ChatWindowProps {
  messages: SessionMessage[]
}

export function ChatWindow({ messages }: ChatWindowProps) {
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 py-12 animate-fade-in">
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
          style={{ background: 'var(--c-blue-soft)', border: '1px solid var(--c-blue-border)' }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
            stroke="var(--c-blue)" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <div className="text-center">
          <p className="text-sm font-medium" style={{ color: 'var(--c-ink-soft)' }}>No messages yet</p>
          <p className="text-xs mt-1" style={{ color: 'var(--c-ink-faint)' }}>Use the mic on the left to ask a question</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 pb-4">
      {messages.map((msg, i) => (
        <MessageBubble key={`${msg.created_at}-${i}`} message={msg} />
      ))}
    </div>
  )
}
