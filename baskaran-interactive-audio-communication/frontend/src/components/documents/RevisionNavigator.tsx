'use client'

import { useEffect, useRef, useState } from 'react'
import { getRevisionSource, type RevisionSection } from './actionsApi'

export function RevisionNavigator({ actionId, sections, currentTime, onPlay, audioReady }: {
  actionId: string; sections: RevisionSection[]; currentTime: number; audioReady: boolean
  onPlay: (section: RevisionSection, replayOnly: boolean) => void
}) {
  const [source, setSource] = useState<{ section: number; filename: string; excerpt: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<number | null>(null)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  async function showSource(section: RevisionSection) {
    controller.current?.abort()
    const abort = new AbortController(); controller.current = abort
    setLoading(section.id); setError(null); setSource(null)
    try {
      const value = await getRevisionSource(actionId, section.id, abort.signal)
      if (!abort.signal.aborted) setSource({ section: section.id, ...value })
    } catch (err) {
      if (!abort.signal.aborted) setError(err instanceof Error ? err.message : 'Source passage unavailable.')
    } finally { if (!abort.signal.aborted) setLoading(null) }
  }
  return <div className="mt-4">
    <h3 className="font-semibold">Revision sections</h3>
    <p className="mt-2 text-sm">Jump to a section or replay it. Supporting passages are from the original document and may be in a different language. Check that they support the revision.</p>
    <div className="mt-3 space-y-3">
      {sections.map(section => {
        const active = section.start_seconds !== null && section.end_seconds !== null && currentTime >= section.start_seconds && currentTime < section.end_seconds
        return <article key={section.id} aria-current={active ? 'true' : undefined} className="rounded-xl border p-4"
          style={{ borderColor: active ? 'var(--accent, #cb5b2c)' : 'var(--border)', background: active ? 'var(--surface-soft)' : 'transparent' }}>
          <h4 className="font-semibold">{section.id + 1}. {section.title}</h4>
          <p className="mt-1 text-sm">{section.duration === null ? 'Audio not ready' : Math.round(section.duration) + ' seconds'}{active ? ' · Current section' : ''}</p>
          <p className="mt-1 text-sm">Transcript language: {section.script_language === 'tamil' ? 'தமிழ்' : section.script_language === 'sinhala' ? 'සිංහල' : 'English'}</p>
          <p className="mt-2 whitespace-pre-wrap text-sm">{section.script}</p>
          <button className="vl-btn-secondary mt-3" disabled={!audioReady || section.start_seconds === null} onClick={() => onPlay(section, false)}>Play from here</button>
          <button className="vl-btn-secondary ml-2 mt-3" disabled={!audioReady || section.start_seconds === null} onClick={() => onPlay(section, true)}>Replay section</button>
          <button className="vl-btn-secondary ml-2 mt-3" disabled={loading === section.id} onClick={() => void showSource(section)}>{loading === section.id ? 'Loading source…' : 'View source'}</button>
        </article>
      })}
    </div>
    {error && <p className="mt-3 text-sm" role="alert">{error}</p>}
    {source && <aside className="mt-4 rounded-xl border p-4" aria-label="Supporting source passage">
      <div className="flex items-center justify-between"><h4 className="font-semibold">Source for section {source.section + 1}: {source.filename}</h4>
        <button className="vl-btn-secondary ml-2" onClick={() => setSource(null)}>Close source</button></div>
      <p className="mt-3 max-h-80 overflow-y-auto whitespace-pre-wrap text-sm">{source.excerpt}</p>
    </aside>}
  </div>
}
