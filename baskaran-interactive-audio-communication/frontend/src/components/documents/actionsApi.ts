import { createClient } from '@/lib/supabase'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
export type ActionLanguage = 'english' | 'tamil' | 'sinhala'
export type RevisionMode = 'single' | 'sectioned'
export interface RevisionSection {
  id: number; title: string; script: string; script_language: ActionLanguage
  duration: number | null; start_seconds: number | null; end_seconds: number | null
}
export interface ActionCapabilities { enabled: boolean; provider: string; max_document_chars: number; sectioned_enabled?: boolean }

export interface DocumentActionResult {
  action_id: string
  status: string
  summary: string | null
  saved: boolean
  error: string | null
  provider: string | null
  confirmation: string
  intent: string
  trace: string[]
  audio_ready: boolean
  audio_saved: boolean
  audio_duration: number | null
  language: ActionLanguage
  revision_mode?: RevisionMode
  progress?: string
  sections?: RevisionSection[]
  summary_language: ActionLanguage
}

async function request(path: string, init: RequestInit = {}, timeout = 10_000): Promise<Response> {
  const { data } = await createClient().auth.getSession()
  const token = data.session?.access_token
  const controller = new AbortController()
  const abort = () => controller.abort()
  init.signal?.addEventListener('abort', abort, { once: true })
  if (init.signal?.aborted) controller.abort()
  const timer = setTimeout(abort, timeout)
  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      ...init, signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(typeof error.detail === 'string' ? error.detail : 'Document action request failed.')
    }
    return response
  } finally { clearTimeout(timer); init.signal?.removeEventListener('abort', abort) }
}

export async function documentActionCapabilities(): Promise<ActionCapabilities> {
  return (await request('/api/v1/actions/capabilities')).json()
}

export async function startDocumentAction(command: string, documentId: string, sessionId: string, language: ActionLanguage = 'english', revisionMode: RevisionMode = 'single'): Promise<string> {
  const result = await request('/api/v1/actions', {
    method: 'POST', body: JSON.stringify({ command, document_id: documentId, session_id: sessionId, language, revision_mode: revisionMode }),
  }, 30_000)
  return (await result.json()).action_id
}

export async function retryRevisionAudio(id: string): Promise<string> {
  return (await (await request(`/api/v1/actions/${encodeURIComponent(id)}/retry`, { method: 'POST' }, 30_000)).json()).action_id
}

export async function getDocumentAction(id: string, signal?: AbortSignal): Promise<DocumentActionResult> {
  return (await request(`/api/v1/actions/${encodeURIComponent(id)}`, { signal })).json()
}

export async function downloadDocumentAction(id: string): Promise<Blob> {
  return (await request(`/api/v1/actions/${encodeURIComponent(id)}/download`)).blob()
}

export async function downloadRevisionAudio(id: string, signal?: AbortSignal): Promise<Blob> {
  return (await request(`/api/v1/actions/${encodeURIComponent(id)}/audio`, { signal }, 30_000)).blob()
}

export async function getRevisionSource(id: string, sectionId: number, signal?: AbortSignal): Promise<{ filename: string; excerpt: string; start: number; end: number }> {
  return (await request(`/api/v1/actions/${encodeURIComponent(id)}/sections/${sectionId}/source`, { signal })).json()
}
