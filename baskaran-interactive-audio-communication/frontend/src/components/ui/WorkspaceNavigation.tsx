import { useEffect, useState } from 'react'

const sections = [
  { id: 'study-documents', title: 'Documents', detail: 'Your uploaded files', path: 'M6 3h8l4 4v14H6z M14 3v5h5 M9 12h6 M9 16h6' },
  { id: 'study-question', title: 'Ask a question', detail: 'Speak or upload audio', path: 'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0z M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3 M8 22h8' },
  { id: 'study-actions', title: 'Study actions', detail: 'Summaries & revisions', path: 'M4 5h7v14H4z M13 5h7v14h-7 M7 9h1 M7 13h1 M16 9h1 M16 13h1' },
  { id: 'saved-library-title', title: 'Saved library', detail: 'Reopen saved results', path: 'M6 3h12v18l-6-4-6 4z' },
  { id: 'study-history', title: 'History', detail: 'Your past questions', path: 'M3 11a9 9 0 1 1 2 7 M3 4v7h7 M12 7v5l3 2' },
]

export function WorkspaceNavigation() {
  const [active, setActive] = useState('study-documents')
  useEffect(() => {
    let frame = 0
    const update = () => {
      frame = 0
      let current = sections[0].id
      for (const section of sections) {
        if ((document.getElementById(section.id)?.getBoundingClientRect().top ?? Infinity) <= 170) current = section.id
      }
      if (window.scrollY > 0 && window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 4) current = 'study-history'
      setActive(current)
    }
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => { window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll); cancelAnimationFrame(frame) }
  }, [])
  return <nav aria-label="Workspace navigation" className="vl-workspace-nav">
    <p>Your workspace</p>
    {sections.map(section => <a key={section.id} href={`#${section.id}`} aria-current={active === section.id ? 'location' : undefined} onClick={() => setActive(section.id)}>
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={section.path} /></svg>
      <span><span className="vl-nav-title">{section.title}</span><span className="vl-nav-detail" aria-hidden="true">{section.detail}</span></span>
    </a>)}
  </nav>
}
