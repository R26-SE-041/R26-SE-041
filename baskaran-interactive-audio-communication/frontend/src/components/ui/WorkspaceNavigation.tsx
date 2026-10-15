import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from 'react'

export const workspaceSections = [
  { id: 'study-documents', title: 'Documents', detail: 'Your uploaded files', path: 'M6 3h8l4 4v14H6z M14 3v5h5 M9 12h6 M9 16h6' },
  { id: 'study-question', title: 'Ask a question', detail: 'Speak or upload audio', path: 'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0z M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3 M8 22h8' },
  { id: 'study-actions', title: 'Study tools', detail: 'Summaries, audio & flashcards', path: 'M4 5h7v14H4z M13 5h7v14h-7 M7 9h1 M7 13h1 M16 9h1 M16 13h1' },
  { id: 'saved-library-title', title: 'Saved library', detail: 'Reopen saved results', path: 'M6 3h12v18l-6-4-6 4z' },
  { id: 'study-history', title: 'History', detail: 'Your past questions', path: 'M3 11a9 9 0 1 1 2 7 M3 4v7h7 M12 7v5l3 2' },
] as const
export type WorkspaceSection = typeof workspaceSections[number]['id']
export function workspaceSectionFromHash(): WorkspaceSection {
  const hash = window.location.hash.slice(1)
  return workspaceSections.find(section => section.id === hash)?.id || 'study-documents'
}

export function WorkspaceNavigation({ active, onSelect }: { active: WorkspaceSection; onSelect: (section: WorkspaceSection) => void }) {
  const media = '(max-width: 900px), (hover: none) and (pointer: coarse)'
  const [mobile, setMobile] = useState(() => window.matchMedia(media).matches)
  const [preview, setPreview] = useState<number | null>(null)
  const [dragging, setDragging] = useState(false)
  const gesture = useRef<{ id: number; x: number; y: number; moved: boolean } | null>(null)
  const suppressClickUntil = useRef(0)
  const selectedIndex = workspaceSections.findIndex(section => section.id === active)
  useEffect(() => {
    const query = window.matchMedia(media)
    const update = () => setMobile(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    gesture.current = null; setDragging(false); setPreview(null)
  }, [mobile, active])

  function position(event: PointerEvent<HTMLDivElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    const cell = (box.width - 12) / workspaceSections.length
    return Math.max(0, Math.min(workspaceSections.length - 1, (event.clientX - box.left - 6) / cell - 0.5))
  }
  function finish(event: PointerEvent<HTMLDivElement>, commit: boolean) {
    const current = gesture.current
    if (!current || current.id !== event.pointerId) return
    gesture.current = null
    if (current.moved) {
      // Swiping can emit a compatibility click after pointerup. Consume it,
      // while a subsequent intentional tap resets suppression on pointerdown.
      suppressClickUntil.current = Date.now() + 500
      const box = event.currentTarget.getBoundingClientRect()
      if (commit && event.clientY >= box.top - 16 && event.clientY <= box.bottom + 16) {
        const target = workspaceSections[Math.round(position(event))].id
        if (target !== active) onSelect(target)
        document.getElementById(`tab-${target}`)?.focus({ preventScroll: true })
      }
    }
    setDragging(false)
    setPreview(null)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }
  const shortTitles = ['Docs', 'Ask', 'Tools', 'Saved', 'History']
  return <nav aria-label="Workspace navigation" className="vl-workspace-nav" data-dragging={dragging}
    style={{ '--workspace-index': preview ?? selectedIndex } as CSSProperties}>
    <p>Your workspace</p>
    <div id="workspace-sections" role="tablist" aria-label="Study workspace" aria-orientation={mobile ? 'horizontal' : 'vertical'}
      onPointerDown={event => {
        if (!mobile || !event.isPrimary || event.button !== 0 || gesture.current) return
        suppressClickUntil.current = 0
        gesture.current = { id: event.pointerId, x: event.clientX, y: event.clientY, moved: false }
      }}
      onPointerMove={event => {
        const current = gesture.current
        if (!current || current.id !== event.pointerId) return
        if (!current.moved) {
          const dx = Math.abs(event.clientX - current.x), dy = Math.abs(event.clientY - current.y)
          if (Math.max(dx, dy) < 6) return
          if (dy > dx) { finish(event, false); return }
          current.moved = true
          event.currentTarget.setPointerCapture(event.pointerId)
          setDragging(true)
        }
        event.preventDefault()
        setPreview(position(event))
      }}
      onPointerUp={event => finish(event, true)}
      onPointerLeave={event => { if (event.pointerType === 'mouse' && !gesture.current?.moved) finish(event, false) }}
      onPointerCancel={event => finish(event, false)}
      onLostPointerCapture={event => { if (event.target === event.currentTarget) finish(event, false) }}
      onClickCapture={event => {
        if (event.detail > 0 && Date.now() < suppressClickUntil.current) {
          suppressClickUntil.current = 0
          event.preventDefault(); event.stopPropagation()
        }
      }}>
    {workspaceSections.map((section, index) => <button key={section.id} type="button" role="tab"
      id={`tab-${section.id}`} aria-controls={`panel-${section.id}`} aria-selected={active === section.id}
      data-previewed={preview !== null && Math.round(preview) === index}
      aria-label={section.title} tabIndex={active === section.id ? 0 : -1} onClick={() => onSelect(section.id)}
      onKeyDown={event => {
        const offset = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0
        if (!offset && event.key !== 'Home' && event.key !== 'End') return
        event.preventDefault()
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? workspaceSections.length - 1 : (index + offset + workspaceSections.length) % workspaceSections.length
        onSelect(workspaceSections[next].id)
        document.getElementById(`tab-${workspaceSections[next].id}`)?.focus()
      }}>
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={section.path} /></svg>
      <span><span className="vl-nav-title vl-nav-title-full">{section.title}</span><span className="vl-nav-title vl-nav-title-short" aria-hidden="true">{shortTitles[index]}</span><span className="vl-nav-detail" aria-hidden="true">{section.detail}</span></span>
    </button>)}
    </div>
  </nav>
}
