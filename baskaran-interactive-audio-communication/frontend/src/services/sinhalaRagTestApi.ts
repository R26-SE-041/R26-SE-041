/** Temporary API client for the isolated Sinhala transcript -> RAG test. */

import { createClient } from '@/lib/supabase'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export interface SinhalaRAGTestResult {
  transcript: string
  answer: string
  sources: Array<{
    document_id: string
    filename: string
    page: number | null
    excerpt: string
    score: number
    retrieval_method: string | null
  }>
  language: 'sinhala'
  retrieval_query: string
  translation_fallback_used: boolean
  timings: {
    retrieval_ms: number
    generation_ms: number
    localization_ms: number
    total_ms: number
  }
  latency_ms: number
}

export async function testSinhalaRAG(transcript: string): Promise<SinhalaRAGTestResult> {
  const supabase = createClient()
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 180_000)
  try {
    const response = await fetch(`${BASE_URL}/api/v1/test/sinhala-rag`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ transcript }),
      signal: controller.signal,
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(body?.detail ?? `Sinhala RAG failed: ${response.status}`)
    }
    return response.json() as Promise<SinhalaRAGTestResult>
  } catch (error: unknown) {
    if (controller.signal.aborted) throw new Error('Sinhala RAG timed out after 3 minutes.')
    throw error
  } finally {
    clearTimeout(timeout)
  }
}
