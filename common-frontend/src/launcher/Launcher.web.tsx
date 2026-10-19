import React, { useEffect, useRef, useState } from 'react';
import { components, type ComponentId } from './components';
import { dashboardCss } from './styles';

function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={diagonal ? 'M6 18 18 6M6 6h12v12' : 'M4 12h16m-6-6 6 6-6 6'}/></svg>;
}

function Illustration({ kind = 'visual' }: { kind?: ComponentId }) {
  return <svg className="tool-drawing" viewBox="0 0 440 300" fill="none" aria-hidden="true" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
    {kind === 'visual' ? <>
      <path d="M106 73C145 24 264 31 322 77c65 52 63 133-2 175-49 31-147 22-203-11C51 202 55 127 106 73Z"/>
      <path d="M115 82c48-43 137-36 194 2 57 38 58 115 3 154-54 33-136 15-184-11-54-32-63-99-13-145Z" opacity=".45"/>
      <path d="M183 110c22-16 58-10 75 12 16 24 4 48-17 58-29 12-60-1-67-25-5-16-5-31 9-45Z" fill="currentColor" fillOpacity=".06"/>
      <path d="M189 117c22-14 49-7 61 12 13 20 2 37-16 45-21 6-45-2-50-21-5-12-5-25 5-36Z"/>
      <path d="M202 135c7-8 21-6 27 3 9 16-4 29-19 21-10-4-12-16-8-24Z" fill="currentColor" fillOpacity=".13"/>
      {[[130,113,-25],[284,111,36],[290,204,-31],[155,213,22]].map(([x,y,angle],i)=><g key={i} transform={`translate(${x} ${y}) rotate(${angle})`}><path d="M-17-8c11-10 34-6 35 6 1 15-25 18-35 9-5-4-4-11 0-15Z"/><path d="m-9-6 3 12 5-13 5 12 4-11"/></g>)}
      <path d="M163 159c-23-9-42 4-31 15 12 13 45 1 44 18-1 8-17 9-25 4M248 206c-15-16-39-2-26 8 15 12 45-2 41 12M265 146c12-5 25-3 25 5s-22 6-21 14c0 8 23 5 28-2"/>
      <path d="m319 75 39-35h49M109 205l-34 35H27M228 101l43-76h33" opacity=".55"/>
      <circle cx="319" cy="75" r="3" fill="currentColor"/><circle cx="109" cy="205" r="3" fill="currentColor"/>
      {[[154,85],[288,173],[187,233],[113,155],[260,80],[317,148]].map(([x,y],i)=><g key={i}><circle cx={x} cy={y} r="2" fill="currentColor"/><circle cx={x+9} cy={y+5} r="1.5" fill="currentColor"/></g>)}
      <text x="361" y="32" stroke="none" fill="currentColor" fontFamily="Arial, sans-serif" fontSize="9" letterSpacing="1.3">EXPLORE</text><text x="27" y="255" stroke="none" fill="currentColor" fontFamily="Arial, sans-serif" fontSize="9" letterSpacing="1.3">UNDERSTAND</text>
    </> : kind === 'audio' ? <>
      <circle cx="220" cy="150" r="79" strokeOpacity=".35"/><circle cx="220" cy="150" r="105" strokeOpacity=".15"/>
      {[14,35,60,39,92,121,77,42,100,83,48,23,50,30,12].map((h,i)=><path key={i} d={`M${122+i*14} ${150-h/2}v${h}`} strokeWidth="3"/>)}<path d="M98 242h244" strokeOpacity=".4"/><text x="159" y="265" stroke="none" fill="currentColor" fontFamily="Arial, sans-serif" fontSize="10" letterSpacing="2">ASK. LISTEN. LEARN.</text>
    </> : kind === 'quiz' ? <g transform="rotate(-6 220 150)">
      <rect x="125" y="40" width="190" height="220" rx="3"/><path d="M147 66h88m-88 12h140"/>{[0,1,2,3].map(i=><g key={i}><rect x="146" y={104+i*33} width="148" height="24" rx="3" fill="currentColor" fillOpacity={i===1?'.08':'0'}/><circle cx="159" cy={116+i*33} r="4"/><path d={`M174 ${116+i*33}h${i===2?58:91}`}/></g>)}<circle cx="309" cy="217" r="27" fill="#f0eee6"/><path d="m296 217 9 9 17-20" strokeWidth="2"/>
    </g> : <>
      <g transform="rotate(-9 170 160)"><rect x="90" y="52" width="148" height="209" rx="2"/>{[0,1,2,3,4,5].map(i=><path key={i} d={`M108 ${84+i*25}q12-12 27 0t27 0t30 0t25 0`} strokeOpacity=".55"/>)}</g><g transform="rotate(7 277 143)"><rect x="218" y="34" width="135" height="201" rx="2" fill="#f0eee6"/><path d="M236 61h45m-45 21h99m-99 28h99m-99 28h76m-76 28h99m-99 28h63"/></g><circle cx="217" cy="152" r="22" fill="#f0eee6"/><path d="M204 152h26m-9-9 9 9-9 9"/>
    </>}
  </svg>;
}

const storageKey = 'biolearnx.launch-history.v1';
type History = Partial<Record<ComponentId, number>>;
function readHistory(): History {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(storageKey) || '{}');
    if (!raw || typeof raw !== 'object') return {};
    return Object.fromEntries(components.flatMap(({ id }) => {
      const value = (raw as Record<string, unknown>)[id];
      return typeof value === 'number' && Number.isFinite(value) && value > 0 && value <= Date.now() ? [[id, value]] : [];
    }));
  } catch { return {}; }
}

export default function Launcher() {
  const [query, setQuery] = useState('');
  const [history, setHistory] = useState<History>({});
  const [menuOpen, setMenuOpen] = useState(false);
  const page = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.title = 'LearnX — A deeper understanding';
    setHistory(readHistory());
    const sync = () => setHistory(readHistory());
    window.addEventListener('storage', sync);
    const nodes = page.current?.querySelectorAll<HTMLElement>('[data-reveal]');
    const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer?.unobserve(entry.target); }
      });
    }, { threshold: 0.08 }) : null;
    nodes?.forEach(node => { if (observer) { node.classList.add('will-reveal'); observer.observe(node); } });
    return () => { window.removeEventListener('storage', sync); observer?.disconnect(); };
  }, []);

  const record = (id: ComponentId) => {
    const next = { ...readHistory(), [id]: Date.now() };
    setHistory(next);
    try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* Navigation does not depend on browser storage. */ }
  };
  const link = (c: typeof components[number]) => ({ href: c.url, target: '_blank', rel: 'noopener noreferrer', onClick: () => record(c.id) });
  const visible = components.filter(c => `${c.name} ${c.mode} ${c.description} ${c.features.join(' ')}`.toLowerCase().includes(query.trim().toLowerCase()));
  const recent = [...components].filter(c => history[c.id]).sort((a,b) => history[b.id]! - history[a.id]!)[0];
  const closeMenu = () => setMenuOpen(false);

  return <div className="bio-site" ref={page}>
    <style>{dashboardCss}</style>
    <a className="skip-link" href="#main">Skip to main content</a>
    <header className="site-header"><div className="header-inner">
      <a className="wordmark" href="#overview" aria-label="LearnX home" onClick={closeMenu}>LEARN<span className="wordmark-x">X</span></a>
      <button className="menu-toggle" aria-expanded={menuOpen} aria-controls="primary-nav" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} onClick={()=>setMenuOpen(!menuOpen)}><span/ ><span/></button>
      <nav id="primary-nav" className={menuOpen ? 'header-nav is-open' : 'header-nav'} aria-label="Main navigation" onKeyDown={e=>{if(e.key==='Escape') { closeMenu(); page.current?.querySelector<HTMLButtonElement>('.menu-toggle')?.focus(); }}}>
        <a href="#toolkit" onClick={closeMenu}>Learning tools</a><a href="#approach" onClick={closeMenu}>Our approach</a><a href="https://learnx-research.vercel.app/" target="_blank" rel="noopener noreferrer" onClick={closeMenu}>Research <Arrow diagonal/></a><a className="button button-dark" href="#toolkit" onClick={closeMenu}>Start learning <Arrow/></a>
      </nav>
    </div></header>

    <main id="main">
      <section id="overview" className="introduction page-width">
        <div className="intro-title"><p className="eyebrow intro-eyebrow">BIOLOGY, IN EVERY DIMENSION</p><h1>Tools for <a href="#toolkit">curious minds</a>.<br/>A deeper understanding.</h1></div>
        <div className="intro-copy"><p>There is more than one way to understand biology. Explore it visually, talk it through, put it into practice, and make it your own.</p><span className="project-caption">LearnX · G.C.E. A/L Biology</span></div>
      </section>

      <section id="toolkit" className="toolkit page-width" data-reveal>
        <div className="section-heading"><div><span className="eyebrow">THE LEARNX TOOLKIT</span><h2>Four ways to follow your curiosity.</h2></div><label className="tool-search"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/></svg><input type="search" aria-label="Find a learning tool" placeholder="Find a learning tool" value={query} onChange={e=>setQuery(e.target.value)}/>{query && <button aria-label="Clear search" onClick={()=>setQuery('')}>×</button>}</label></div>
        <p className="search-result-count" role="status">{query ? `${visible.length} ${visible.length===1?'tool':'tools'} found` : 'Choose where you would like to begin.'}</p>
        <div className="tool-grid">{visible.map(c=><a className={`tool-card tool-${c.id}`} key={c.id} {...link(c)} aria-label={`Open ${c.name} in a new tab`}>
          <div className="card-top"><span className="eyebrow">{c.number} / {c.mode}</span><Arrow diagonal/></div><div className="card-illustration"><Illustration kind={c.id}/></div><div className="card-content"><h3>{c.name}</h3><p>{c.description}</p><ul className="capabilities">{c.features.map(f=><li key={f}>{f}</li>)}</ul></div><div className="card-bottom"><span>Open workspace <Arrow diagonal/></span><small>{history[c.id] ? 'Previously opened' : 'Opens in a new tab'}</small></div>
        </a>)}</div>
        {!visible.length && <div className="empty-state"><h3>No tools found for “{query}”</h3><p>Try visual, voice, quiz, notes, or translation.</p><button className="button button-dark" onClick={()=>setQuery('')}>View all tools <Arrow/></button></div>}
        <p className="account-note"><span aria-hidden="true">↗</span> Each component opens in its own workspace, with its own sign-in.</p>
      </section>

      <section id="approach" className="approach" data-reveal><div className="page-width approach-grid"><div><span className="eyebrow">LEARNING THAT MEETS YOU WHERE YOU ARE</span><h2>A little curiosity.<br/>A deeper understanding.</h2><p>You do not have to learn everything in the same way. Start with a question, choose a tool, and build your understanding one discovery at a time.</p></div><div className="journey-list">{components.map(c=><a key={c.id} {...link(c)} aria-label={`${c.verb}: open ${c.name} in a new tab`}><span className="journey-number">{c.number}</span><div><h3>{c.step}</h3><p>{c.detail}</p></div><Arrow diagonal/></a>)}</div></div></section>

      <section className="closing page-width" data-reveal><span className="eyebrow">{recent ? 'PICK UP YOUR CURIOSITY' : 'YOUR NEXT DISCOVERY'}</span><h2>{recent ? `A little more ${recent.verb.toLowerCase()==='practice'?'practice':recent.id==='notes'?'clarity':recent.id==='audio'?'conversation':'perspective'}?` : 'Understanding starts with a question.'}</h2><p>{recent ? `Your most recently opened workspace is ${recent.name}.` : 'Four complementary tools. One place to begin.'}</p>{recent ? <a className="button button-dark" {...link(recent)}>Return to {recent.name} <Arrow diagonal/></a> : <a className="button button-dark" href="#toolkit">Explore the toolkit <Arrow/></a>}</section>
    </main>

    <footer id="footer" className="site-footer"><div className="page-width"><div className="footer-grid"><div className="footer-intro"><a className="wordmark" href="#overview" aria-label="LearnX home">LEARN<span className="wordmark-x">X</span></a><p>Learning, in every dimension.</p></div><div><h2>Learning tools</h2>{components.map(c=><a key={c.id} {...link(c)}>{c.name}<Arrow diagonal/></a>)}</div><div><h2>Explore</h2><a href="#approach">Our approach</a><a href="https://learnx-research.vercel.app/" target="_blank" rel="noopener noreferrer">Research project<Arrow diagonal/></a><a href="#toolkit">Start learning</a></div><div className="footer-project"><h2>LearnX</h2><p>A multimodal framework for personalized biology learning.</p><span>R26-SE-041<br/>SLIIT Research Project</span></div></div><div className="footer-base"><span>LearnX · {new Date().getFullYear()}</span><span>Built for curiosity. Designed for understanding.</span><a href="#overview">Back to top ↑</a></div></div></footer>
  </div>;
}
