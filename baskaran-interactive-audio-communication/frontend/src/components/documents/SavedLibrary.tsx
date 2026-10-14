import { useMemo, useState } from 'react'
import type { SavedAction } from './actionsApi'

const PAGE_SIZE = 5
const languageNames = { english: 'English', tamil: 'தமிழ்', sinhala: 'සිංහල' }
function kind(item: SavedAction) {
  return item.intent === 'flashcards' ? 'flashcards' : item.intent === 'audio_revision' ? 'audio' : 'summary'
}

export function SavedLibrary({ items, busy, selectedId, onOpen, onDelete, onRefresh }: {
  items: SavedAction[]; busy: boolean; selectedId?: string
  onOpen: (item: SavedAction) => void; onDelete: (id: string) => void; onRefresh: () => void
}) {
  const [query, setQuery] = useState('')
  const [type, setType] = useState('all')
  const [language, setLanguage] = useState('all')
  const [page, setPage] = useState(1)
  const filtered = useMemo(() => items.filter(item =>
    (type === 'all' || kind(item) === type) && (language === 'all' || item.language === language) &&
    item.filename.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
    .sort((a, b) => (Date.parse(b.created_at ?? '') || 0) - (Date.parse(a.created_at ?? '') || 0)), [items, query, type, language])
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const currentPage = Math.min(page, pages)
  const start = (currentPage - 1) * PAGE_SIZE
  const visible = filtered.slice(start, start + PAGE_SIZE)
  return <section aria-labelledby="saved-library-title" className="mt-6 border-t pt-5">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h3 id="saved-library-title" className="font-semibold" style={{ scrollMarginTop: 110 }}>Saved revisions and flashcards</h3>
        <p className="mt-1 text-sm" style={{ color: 'var(--text-dim)' }}>{items.length} saved items · Find and reopen your study materials</p></div>
      <button className="vl-btn-secondary" disabled={busy} onClick={onRefresh}>Refresh saved library</button>
    </div>
    {!!items.length && <div className="mt-4 grid gap-3 sm:grid-cols-3">
      <label className="text-sm">Search documents
        <input type="search" className="nb-input mt-1 w-full" placeholder="Search by document name" value={query} onChange={event => { setQuery(event.target.value); setPage(1) }} />
      </label>
      <label className="text-sm">Saved item type
        <select className="nb-input mt-1 w-full" value={type} onChange={event => { setType(event.target.value); setPage(1) }}>
          <option value="all">All types</option><option value="audio">Audio revisions</option><option value="summary">Summaries</option><option value="flashcards">Flashcards</option>
        </select>
      </label>
      <label className="text-sm">Saved item language
        <select className="nb-input mt-1 w-full" value={language} onChange={event => { setLanguage(event.target.value); setPage(1) }}>
          <option value="all">All languages</option><option value="english">English</option><option value="tamil">தமிழ்</option><option value="sinhala">සිංහල</option>
        </select>
      </label>
    </div>}
    {!items.length ? <p className="mt-4 text-sm">No saved results yet.</p> : !filtered.length ? <div className="mt-4 rounded-xl border p-4">
      <p className="text-sm">No saved items match your search or filters.</p>
      <button className="vl-btn-secondary mt-3" onClick={() => { setQuery(''); setType('all'); setLanguage('all'); setPage(1) }}>Clear filters</button>
    </div> : <>
      <ul aria-label="Saved study materials" className="mt-4 space-y-2">{visible.map(item => <li key={item.action_id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3" style={{ borderColor: selectedId === item.action_id ? 'var(--primary)' : 'var(--border)' }}>
        <div className="min-w-0 flex-1" style={{ minWidth: 'min(220px, 100%)' }}>
          <p className="break-words text-sm font-semibold">{item.filename}</p>
          <p className="mt-1 text-xs" style={{ color: 'var(--text-dim)' }}>{languageNames[item.language]} · {kind(item) === 'flashcards' ? 'Flashcards' : kind(item) === 'audio' ? `${item.revision_mode} audio revision` : 'Summary'}{item.audio_duration ? ` · ${Math.round(item.audio_duration)} seconds` : ''}
            {item.scope === 'section' ? ' · Selected section only' : item.style === 'one_minute' ? ' · One-minute target' : item.style === 'detailed' ? ' · Detailed revision' : ''}</p>
          {item.created_at && <p className="mt-1 text-xs" style={{ color: 'var(--text-dim)' }}>{new Date(item.created_at).toLocaleString()}{selectedId === item.action_id ? ' · Currently open' : ''}</p>}
        </div>
        <div className="flex items-center gap-2"><button className="vl-btn-secondary" disabled={busy} onClick={() => onOpen(item)}>Open</button>
          <button className="vl-btn-secondary" disabled={busy} onClick={() => onDelete(item.action_id)}>Delete</button></div>
      </li>)}</ul>
      <nav aria-label="Saved library pages" className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p role="status" className="text-sm" style={{ color: 'var(--text-dim)' }}>Showing {start + 1}–{Math.min(start + PAGE_SIZE, filtered.length)} of {filtered.length}</p>
        <div className="flex items-center gap-3"><button className="vl-btn-secondary" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Previous</button>
          <span className="text-sm">Page {currentPage} of {pages}</span>
          <button className="vl-btn-secondary" disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)}>Next</button></div>
      </nav>
    </>}
  </section>
}
