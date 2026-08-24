/** Shared TypeScript types across the frontend. */

export type Language = 'english' | 'tamil' | 'sinhala'

export type FileType = 'pdf' | 'pptx' | 'docx' | 'xlsx' | 'txt' | 'md'

export interface TranscribeResponse {
  transcript: string
  detected_language: string
  selected_language: Language
  duration_ms: number
}

export interface ChunkReference {
  document_id: string
  filename: string
  chunk_index: number
  page: number | null
  excerpt: string
  score: number
}

export interface QueryResponse {
  session_id: string
  transcript: string
  enhanced_query: string | null
  answer: string
  audio_url: string | null
  language: Language
  references: ChunkReference[]
}

export interface DocumentItem {
  document_id: string
  filename: string
  file_type: FileType
  chunk_count: number
  uploaded_at: string
}

export interface AskResponse {
  answer: string
  enhanced_query: string | null
  references: ChunkReference[]
}

export interface SessionMessage {
  role: 'user' | 'assistant'
  content: string
  audio_url?: string | null
  audio_pending?: boolean
  audio_error?: string | null
  references?: ChunkReference[]
  created_at: string
}

export type RecordingState = 'idle' | 'recording' | 'processing' | 'done' | 'error'
