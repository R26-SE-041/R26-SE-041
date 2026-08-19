/**
 * Global session store using Zustand.
 * Tracks: selected language, current session ID, messages, recording state.
 */

import { create } from 'zustand'
import type { Language, SessionMessage, RecordingState } from '@/types'

interface SessionStore {
  // Language selection
  language: Language
  setLanguage: (lang: Language) => void

  // Session
  sessionId: string | null
  setSessionId: (id: string) => void

  // Messages
  messages: SessionMessage[]
  addMessage: (msg: SessionMessage) => void
  clearMessages: () => void

  // Recording state
  recordingState: RecordingState
  setRecordingState: (state: RecordingState) => void

  // Latest transcript (Phase 1)
  lastTranscript: string | null
  setLastTranscript: (t: string | null) => void
}

export const useSessionStore = create<SessionStore>((set) => ({
  language: 'english',
  setLanguage: (language) => set({ language }),

  sessionId: null,
  setSessionId: (sessionId) => set({ sessionId }),

  messages: [],
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  clearMessages: () => set({ messages: [] }),

  recordingState: 'idle',
  setRecordingState: (recordingState) => set({ recordingState }),

  lastTranscript: null,
  setLastTranscript: (lastTranscript) => set({ lastTranscript }),
}))
