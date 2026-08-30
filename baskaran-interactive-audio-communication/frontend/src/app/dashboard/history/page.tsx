'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { getHistoryAudio, listHistory } from '@/lib/api'
import { useSession } from '@/hooks/useSession'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { MarkdownContent } from '@/components/ui/MarkdownContent'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import type { HistoryItem } from '@/types'

export default function HistoryPage() {
  const router = useRouter()
  const { user, loading: authLoading } = useSession()
  const [items, setItems] = useState<HistoryItem[]>([])
  const [audioUrls, setAudioUrls] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (authLoading) return
    if (!user) { router.replace('/login'); return }
    let active = true
    const createdUrls: string[] = []
    listHistory().then(async (history) => {
      if (!active) return
      setItems(history)
      const withAudio = history.filter((item) => item.has_audio)
      const pairs = await Promise.all(withAudio.map(async (item) => {
        try {
          const url = URL.createObjectURL(await getHistoryAudio(item.id))
          createdUrls.push(url)
          return [item.id, url] as const
        } catch { return null }
      }))
      if (active) setAudioUrls(Object.fromEntries(pairs.filter((pair) => pair !== null)))
    }).catch((e) => setError(e instanceof Error ? e.message : 'Could not load history.'))
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false; createdUrls.forEach((url) => URL.revokeObjectURL(url)) }
  }, [authLoading, user, router])

  if (authLoading || loading) return <div className="min-h-screen flex items-center justify-center"><LoadingSpinner size="lg" label="Loading history…" /></div>

  return (
    <div className="min-h-screen" style={{ background: 'var(--background)' }}>
      <header className="nb-header sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-5 h-14 flex items-center justify-between">
          <div>
            <h1 className="text-sm font-semibold" style={{ color: 'var(--c-ink)' }}>Question History</h1>
            <p className="text-xs" style={{ color: 'var(--c-ink-faint)' }}>Saved answers and voice previews</p>
          </div>
          <div className="flex items-center gap-2"><ThemeToggle /><Link href="/dashboard" className="text-xs font-medium px-3 py-2 rounded-lg" style={{ color: 'var(--c-blue)' }}>← Back to Q&amp;A</Link></div>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-5 py-8">
        {error && <div className="rounded-xl p-4" style={{ background: 'var(--c-red-soft)', color: 'var(--c-red)' }}>{error}</div>}
        {!error && items.length === 0 && <div className="nb-inset p-10 text-center"><p className="font-medium" style={{ color: 'var(--c-ink)' }}>No saved questions yet</p><p className="text-sm mt-1" style={{ color: 'var(--c-ink-faint)' }}>Your next completed Q&amp;A will appear here automatically.</p></div>}
        <div className="space-y-5">
          {items.map((item) => <article key={item.id} className="nb-inset p-5">
            <div className="flex items-center justify-between gap-3 mb-4">
              <span className="text-[10px] uppercase tracking-wide font-semibold" style={{ color: 'var(--c-blue)' }}>{item.language}</span>
              <time className="text-xs" style={{ color: 'var(--c-ink-faint)' }}>{new Date(item.created_at).toLocaleString()}</time>
            </div>
            <p className="nb-label mb-1">Question</p>
            <p className="text-sm mb-4" style={{ color: 'var(--c-ink)' }}>{item.question}</p>
            <p className="nb-label mb-1">Answer</p>
            <div className="text-sm" style={{ color: 'var(--c-ink)' }}><MarkdownContent content={item.answer} /></div>
            {audioUrls[item.id] && <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--c-border)' }}><p className="nb-label mb-2">Voice Preview</p><audio controls preload="metadata" className="w-full" src={audioUrls[item.id]}>Your browser does not support audio playback.</audio></div>}
          </article>)}
        </div>
      </main>
    </div>
  )
}
