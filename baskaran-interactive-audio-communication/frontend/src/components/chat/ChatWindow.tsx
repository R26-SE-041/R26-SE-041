import type { SessionMessage } from '@/types'
import { MessageBubble } from './MessageBubble'

interface ChatWindowProps {
  messages: SessionMessage[]
}

export function ChatWindow({ messages }: ChatWindowProps) {
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center py-16">
        <div className="text-center">
          <div className="text-5xl mb-4">💬</div>
          <p className="text-white/30 text-sm">Your conversation will appear here</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto space-y-4 py-4 pr-1 scrollbar-thin scrollbar-thumb-white/10">
      {messages.map((msg, i) => (
        <MessageBubble key={i} message={msg} />
      ))}
    </div>
  )
}
