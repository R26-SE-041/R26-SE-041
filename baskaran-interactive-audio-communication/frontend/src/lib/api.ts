/** Typed API client for the VoiceLearn production workflow. */

import axios, { type AxiosInstance } from 'axios'
import type { AskResponse, ChunkReference, DocumentItem, HistoryItem, Language, QueryResponse, TranscribeResponse } from '@/types'
import { createClient } from './supabase'

import { API_URL as BASE_URL, AUTH_REQUIRED, requireBackend } from '@/lib/config'
// A RAG request includes: retrieval (BGE embed + rerank now 120s), plus Gemma A100 cold-start
// (up to 480s server-side). Keep the browser deadline above the full server budget.
const RAG_REQUEST_TIMEOUT_MS = 600_000

function createApiClient(): AxiosInstance {
  const instance = axios.create({ baseURL: BASE_URL, timeout: 540_000 })
  instance.interceptors.request.use(async (config) => {
    requireBackend()
    const supabase = createClient()
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  })
  instance.interceptors.response.use(
    (response) => response,
    (error) => {
      let message: string
      if (error.code === 'ECONNABORTED') {
        const url: string = error.config?.url ?? ''
        message = url.includes('/ask-jobs')
          ? 'Could not check your answer status. Your question is kept. Use Retry Answer to resume the same request.'
          : url.includes('/ask') || url.includes('/query')
          ? 'The search timed out. The AI service may be warming up; please try again shortly.'
          : 'The upload timed out while indexing. Please retry.'
      } else if (error.code === 'ERR_NETWORK' && !error.response) {
        message = 'The connection to the server was interrupted. Your question is kept. Check your connection, then retry.'
      } else {
        message = error.response?.data?.detail ?? error.message ?? 'The request failed.'
      }
      return Promise.reject(Object.assign(new Error(message), { status: error.response?.status }))
    },
  )
  return instance
}

const api = createApiClient()

// Keep only temporary request IDs in memory. A retry resumes the same job;
// questions/history remain persisted through the existing cloud history flow.
const pendingAnswers = new Map<string, { requestId: string; jobId?: string; expires: number }>()
async function pollAnswer(payload: Record<string, unknown>): Promise<AskResponse> {
  const { data } = await createClient().auth.getSession()
  const key = JSON.stringify([data.session?.user?.id, payload])
  for (const [id, value] of pendingAnswers) if (value.expires < Date.now()) pendingAnswers.delete(id)
  let pending = pendingAnswers.get(key)
  if (!pending) {
    if (pendingAnswers.size >= 20) throw new Error('Too many pending questions. Please wait before asking again.')
    pending = { requestId: crypto.randomUUID(), expires: Date.now() + 15 * 60_000 }
    pendingAnswers.set(key, pending)
  }
  try {
    if (!pending.jobId) {
      const started = await api.post<{job_id:string}>('/api/v1/documents/ask-jobs', payload,
        { headers: { 'Idempotency-Key': pending.requestId }, timeout: 15_000 })
      pending.jobId = started.data.job_id
    }
    const deadline = Date.now() + RAG_REQUEST_TIMEOUT_MS
    while (Date.now() < deadline) {
      const { data: job } = await api.get<{status:string;result?:AskResponse;error?:string}>(
        `/api/v1/documents/ask-jobs/${encodeURIComponent(pending.jobId)}`, { timeout: 15_000 })
      if (job.status === 'complete' && job.result) { pendingAnswers.delete(key); return job.result }
      if (job.status === 'failed') { pendingAnswers.delete(key); throw new Error(job.error || 'Answer preparation failed. Please retry.') }
      await new Promise(resolve => setTimeout(resolve, 1500))
    }
    throw new Error('Your answer is still being prepared. Use Retry Answer to check the same request.')
  } catch (error) {
    if ([400, 404, 409, 422].includes((error as {status?:number}).status ?? 0)) pendingAnswers.delete(key)
    throw error
  }
}

export async function prepareVoice(language: Language, purpose: 'answer' | 'command' = 'answer'): Promise<void> {
  await api.post('/api/v1/voice/prepare', { language, purpose }, { timeout: 10_000 })
}

export async function transcribeAudio(audioBlob: Blob, language: Language, filename = 'recording.webm', prepareAnswer = false): Promise<TranscribeResponse> {
  const form = new FormData()
  form.append('audio_file', audioBlob, filename)
  form.append('language', language)
  form.append('prepare_answer', String(prepareAnswer))
  const { data } = await api.post<TranscribeResponse>('/api/v1/voice/transcribe', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function voiceQuery(audioBlob: Blob, language: Language, sessionId?: string, filename = 'recording.webm'): Promise<QueryResponse> {
  const form = new FormData()
  form.append('audio_file', audioBlob, filename)
  form.append('language', language)
  if (sessionId) form.append('session_id', sessionId)
  const { data } = await api.post<QueryResponse>('/api/v1/voice/query', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<DocumentItem>('/api/v1/documents/upload', form)
  return data
}

export async function listDocuments(): Promise<DocumentItem[]> {
  const { data } = await api.get<DocumentItem[]>('/api/v1/documents/')
  return data
}

export async function deleteDocument(documentId: string): Promise<void> {
  await api.delete(`/api/v1/documents/${documentId}`)
}

export async function askDocument(
  transcript: string,
  language: Language,
  correctedTranscript?: string,
  detectedLanguage?: string,
  documentGrounded = true,
): Promise<AskResponse> {
  const payload = {
    transcript,
    language,
    corrected_transcript: correctedTranscript ?? null,
    detected_language: detectedLanguage ?? language,
    document_grounded: documentGrounded,
  }
  if (AUTH_REQUIRED) return pollAnswer(payload)
  const { data } = await api.post<AskResponse>('/api/v1/documents/ask', payload, { timeout: RAG_REQUEST_TIMEOUT_MS })
  return data
}

/** Synthesize through the backend's final language router. */
export async function synthesizeSpeech(text: string, language: Language): Promise<Blob> {
  const supabase = createClient()
  const { data: sessionData } = await supabase.auth.getSession()
  const token = sessionData.session?.access_token
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 180_000)
  try {
    requireBackend()
    const response = await fetch(`${BASE_URL}/api/v1/voice/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ text, language }),
      signal: controller.signal,
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(body?.detail ?? 'Answer audio is unavailable.')
    }
    return response.blob()
  } finally {
    clearTimeout(timeoutId)
  }
}

export async function saveHistory(question: string, answer: string, language: Language,
  references: ChunkReference[], audio?: Blob,
  options?: { questionAudio?: Blob; documentGrounded?: boolean; sourceId?: string; createdAt?: string }): Promise<HistoryItem> {
  const form = new FormData()
  form.append('question', question)
  form.append('answer', answer)
  form.append('language', language)
  form.append('references', JSON.stringify(references))
  if (audio) form.append('audio_file', audio, 'answer.wav')
  if (options?.questionAudio) form.append('question_audio', options.questionAudio, 'question.audio')
  form.append('document_grounded', String(options?.documentGrounded ?? true))
  if (options?.sourceId) form.append('source_id', options.sourceId)
  if (options?.createdAt) form.append('created_at', options.createdAt)
  const { data } = await api.post<HistoryItem>('/api/v1/history', form)
  return data
}

export async function listHistory(): Promise<HistoryItem[]> {
  const { data } = await api.get<HistoryItem[]>('/api/v1/history')
  return data
}

export async function saveHistoryAudio(historyId: string, audio: Blob): Promise<HistoryItem> {
  const form = new FormData()
  form.append('audio_file', audio, 'answer.wav')
  const { data } = await api.put<HistoryItem>(`/api/v1/history/${historyId}/audio`, form)
  return data
}

export async function getHistoryAudio(historyId: string): Promise<Blob> {
  const { data } = await api.get<Blob>(`/api/v1/history/${historyId}/audio`, { responseType: 'blob' })
  return data
}

export async function getHistoryQuestionAudio(id: string): Promise<Blob> {
  const { data } = await api.get<Blob>(`/api/v1/history/${id}/question-audio`, { responseType: 'blob' })
  return data
}
export async function editHistoryAnswer(id: string, answer: string) {
  await api.patch(`/api/v1/history/${id}`, { answer })
}
export async function deleteCloudHistory(id?: string) {
  await api.delete('/api/v1/history' + (id ? `/${id}` : ''), { data: { confirmed: true } })
}

export async function login(email: string, password: string) {
  const { data } = await api.post('/api/v1/auth/login', { email, password })
  return data
}

export async function register(email: string, password: string, fullName?: string) {
  const { data } = await api.post('/api/v1/auth/register', { email, password, full_name: fullName })
  return data
}
