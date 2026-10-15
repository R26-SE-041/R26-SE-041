import { useEffect, useRef, useState } from 'react'

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
  const [open, setOpen] = useState(false)
  const navigation = useRef<HTMLElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const current = workspaceSections.find(section => section.id === active) || workspaceSections[0]
  useEffect(() => {
    if (!open) return
    const dismiss = (event: PointerEvent) => {
      if (!navigation.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', dismiss)
    return () => document.removeEventListener('pointerdown', dismiss)
  }, [open])
  function select(section: WorkspaceSection) {
    onSelect(section)
    setOpen(false)
    if (window.matchMedia('(max-width: 900px), (hover: none) and (pointer: coarse)').matches) trigger.current?.focus({ preventScroll: true })
  }
  return <nav ref={navigation} aria-label="Workspace navigation" className="vl-workspace-nav" data-open={open}
    onKeyDown={event => {
      if (event.key === 'Escape' && open) { event.preventDefault(); setOpen(false); trigger.current?.focus() }
    }}>
    <p>Your workspace</p>
    <button ref={trigger} type="button" className="vl-workspace-switch" aria-expanded={open} aria-controls="workspace-sections"
      aria-label={`Change workspace section. Current: ${current.title}`} onClick={() => setOpen(value => !value)}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={current.path} /></svg>
      <span><small>Workspace</small><strong>{current.title}</strong></span>
      <span className="vl-workspace-change" aria-hidden="true">Change</span>
      <svg className="vl-workspace-chevron" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
    </button>
    <div id="workspace-sections" role="tablist" aria-label="Study workspace" aria-orientation="vertical">
    {workspaceSections.map((section, index) => <button key={section.id} type="button" role="tab"
      id={`tab-${section.id}`} aria-controls={`panel-${section.id}`} aria-selected={active === section.id}
      tabIndex={active === section.id ? 0 : -1} onClick={() => select(section.id)}
      onKeyDown={event => {
        const offset = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0
        if (!offset && event.key !== 'Home' && event.key !== 'End') return
        event.preventDefault()
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? workspaceSections.length - 1 : (index + offset + workspaceSections.length) % workspaceSections.length
        onSelect(workspaceSections[next].id)
        document.getElementById(`tab-${workspaceSections[next].id}`)?.focus()
      }}>
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={section.path} /></svg>
      <span><span className="vl-nav-title">{section.title}</span><span className="vl-nav-detail" aria-hidden="true">{section.detail}</span></span>
    </button>)}
    </div>
  </nav>
}
