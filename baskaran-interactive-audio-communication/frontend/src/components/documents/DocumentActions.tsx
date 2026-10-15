'use client'

import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { RevisionNavigator } from './RevisionNavigator'
import { SavedLibrary } from './SavedLibrary'
import { VoiceRecorder } from '@/components/voice/VoiceRecorder'
import { MarkdownContent } from '@/components/ui/MarkdownContent'
import { extraCommands, normalizeCommand, isPlaybackCommand, controlPlayback } from './audioCommands'
import { synthesizeSpeech } from '@/lib/api'
import { documentActionCapabilities, startDocumentAction, getDocumentAction,
  downloadDocumentAction, downloadRevisionAudio, retryRevisionAudio, listSavedActions, deleteSavedAction,
  type SavedAction, type ActionCapabilities, type RevisionMode, type RevisionSection, type ActionLanguage, type DocumentActionResult } from './actionsApi'
import type { DocumentItem } from '@/types'

const labels: Record<string, string> = {
  queued: 'Action queued', processing: 'Processing command', generating: 'Generating summary',
  saving: 'Saving summary', complete: 'Complete', partial: 'Partially completed', failed: 'Action failed',
  synthesizing: 'Generating revision audio',
  localizing: 'Preparing translated transcript',
}
const toolLabels: Record<string, string> = { summarize_document: 'revision transcript',
  create_revision_audio: 'revision audio', save_audio_revision: 'saved transcript and audio' }
const languageLabels = { english: 'English', tamil: 'தமிழ்', sinhala: 'සිංහල' }
const examples: Record<ActionLanguage, { summary: string; save: string; combined: string; audio: string }> = {
  english: { summary: 'Summarize this document', save: 'Save the summary', combined: 'Summarize this document and save it', audio: 'Create a short audio revision of this document and save it' },
  tamil: { summary: 'இந்த ஆவணத்தை சுருக்கவும்', save: 'சுருக்கத்தை சேமிக்கவும்', combined: 'இந்த ஆவணத்தை சுருக்கி சேமிக்கவும்', audio: 'இந்த ஆவணத்தின் ஒலி மீளாய்வை உருவாக்கி சேமிக்கவும்' },
  sinhala: { summary: 'මෙම ලේඛනය සාරාංශ කරන්න', save: 'සාරාංශය සුරකින්න', combined: 'මෙම ලේඛනය සාරාංශ කර සුරකින්න', audio: 'මෙම ලේඛනයේ ශ්‍රව්‍ය පුනරාවලෝකනයක් සාදා සුරකින්න' },
}

export function DocumentActions({ documents, libraryTarget, onOpenSaved, active: visible = true }: {
  documents: DocumentItem[]; libraryTarget?: HTMLElement | null; onOpenSaved?: () => void; active?: boolean
}) {
  const [capabilities, setCapabilities] = useState<ActionCapabilities | null>(null)
  const [capabilitiesError, setCapabilitiesError] = useState(false)
  const [documentId, setDocumentId] = useState('')
  const [command, setCommand] = useState('')
  const [language, setLanguage] = useState<ActionLanguage>('english')
  const [voiceLanguage, setVoiceLanguage] = useState<ActionLanguage>('english')
  const [revisionMode, setRevisionMode] = useState<RevisionMode>('sectioned')
  const [executionProvider, setExecutionProvider] = useState<'direct' | 'openclaw_mcp'>('openclaw_mcp')
  const [currentTime, setCurrentTime] = useState(0)
  const [showSections, setShowSections] = useState(true)
  const [selectedSection, setSelectedSection] = useState(0)
  const [savedActions, setSavedActions] = useState<SavedAction[]>([])
  const [deletePending, setDeletePending] = useState<string | null>(null)
  const [flipped, setFlipped] = useState<number[]>([])
  const replayEnd = useRef<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [result, setResult] = useState<DocumentActionResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [audioError, setAudioError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [playbackRate, setPlaybackRate] = useState('1')
  const audioPlayer = useRef<HTMLAudioElement | null>(null)
  const resultAnchor = useRef<HTMLDivElement | null>(null)
  const session = useRef('')
  const controller = useRef<AbortController | null>(null)
  const active = useRef(false)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    session.current = sessionStorage.getItem('voicelearn-action-session') || crypto.randomUUID()
    sessionStorage.setItem('voicelearn-action-session', session.current)
    documentActionCapabilities().then(value => { if (mounted.current) { setCapabilities(value); setExecutionProvider(value.provider === 'direct' ? 'direct' : 'openclaw_mcp') } }).catch(() => { if (mounted.current) setCapabilitiesError(true) })
    void refreshSaved()
    return () => { mounted.current = false; controller.current?.abort() }
  }, [])
  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl) }, [audioUrl])

  async function refreshSaved() {
    try { const values = await listSavedActions(); if (mounted.current) setSavedActions(values) }
    catch (err) { if (mounted.current) setError(err instanceof Error ? err.message : 'Saved revisions could not be loaded.') }
  }

  async function openSaved(item: SavedAction) {
    if (active.current) return
    active.current = true; setBusy(true); setError(null); setAudioError(null)
    try {
      const value = await getDocumentAction(item.action_id)
      if (!mounted.current) return
      setResult(value); setDocumentId(documents.some(doc => doc.document_id === item.document_id) ? item.document_id : ''); setLanguage(value.language)
      setAudioUrl(null); setCurrentTime(0); setSelectedSection(0); setFlipped([]); replayEnd.current = null
      setStatus('Saved result opened')
      requestAnimationFrame(() => resultAnchor.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
      if (value.audio_ready) {
        await loadSavedAudio(item.action_id)
      }
    } catch (err) { if (mounted.current) setError(err instanceof Error ? err.message : 'Saved result could not be opened.') }
    finally { active.current = false; if (mounted.current) setBusy(false) }
  }

  async function loadSavedAudio(actionId: string) {
    setAudioError(null)
    try {
      const blob = await downloadRevisionAudio(actionId)
      if (mounted.current) setAudioUrl(URL.createObjectURL(blob))
    } catch {
      if (mounted.current) setAudioError('Saved audio could not be loaded. Your transcript is available. Retry loading the audio.')
    }
  }

  async function retrySavedAudio() {
    if (!result || active.current) return
    active.current = true; setBusy(true)
    try { await loadSavedAudio(result.action_id) }
    finally { active.current = false; if (mounted.current) setBusy(false) }
  }

  async function confirmDelete() {
    if (!deletePending || active.current) return
    active.current = true; setBusy(true); setError(null)
    try {
      await deleteSavedAction(deletePending)
      if (result?.action_id === deletePending) { audioPlayer.current?.pause(); setResult(null); setAudioUrl(null); setCurrentTime(0) }
      setDeletePending(null); setStatus('Saved result deleted'); await refreshSaved()
    } catch (err) { setError(err instanceof Error ? err.message : 'Delete failed.') }
    finally { active.current = false; setBusy(false) }
  }

  async function execute(retryActionId?: string) {
    if (!retryActionId && !active.current) {
      const text = normalizeCommand(command)
      if (text === 'delete this saved revision') {
        if (!result?.saved) { setError('Open a saved revision from the library first.'); return }
        setDeletePending(result.action_id); setError(null); return
      }
      if (isPlaybackCommand(command)) {
        if (!audioPlayer.current || !audioUrl || result?.intent !== 'audio_revision') { setError('Generate or open a saved audio revision first.'); return }
        try {
          const controlled = await controlPlayback(command, audioPlayer.current, result.sections ?? [])
          replayEnd.current = controlled.replayEnd ?? null
          setCurrentTime(audioPlayer.current.currentTime); setPlaybackRate(String(audioPlayer.current.playbackRate))
          setStatus(controlled.message); setError(null)
        } catch (err) { setError(err instanceof Error ? err.message : 'Playback command failed.') }
        return
      }
      if (text === 'create an audio revision of this section only and save it' && !result?.sections?.length) {
        setError('Generate or open a sectioned revision and choose its source section first.'); return
      }
    }
    if (active.current || (!retryActionId && (!command.trim() || !documentId))) return
    const sectioned = retryActionId ? result?.revision_mode === 'sectioned' : capabilities?.sectioned_enabled && revisionMode === 'sectioned'
    active.current = true
    setBusy(true); setError(null); setResult(null); setAudioUrl(null); setAudioError(null)
    setCurrentTime(0); setShowSections(true); replayEnd.current = null
    setStatus('Submitting command')
    const abort = new AbortController()
    controller.current = abort
    try {
      const id = retryActionId ? await retryRevisionAudio(retryActionId) : await startDocumentAction(command.trim(), documentId, session.current, language, capabilities?.sectioned_enabled ? revisionMode : 'single', result?.action_id, selectedSection, executionProvider)
      const deadline = Date.now() + (sectioned ? 1_920_000 : 720_000)
      while (!abort.signal.aborted && Date.now() < deadline) {
        const value = await getDocumentAction(id, abort.signal)
        if (!mounted.current) return
        setStatus(value.progress && !['complete', 'partial', 'failed'].includes(value.status) ? value.progress : labels[value.status] || value.status)
        if (['complete', 'partial', 'failed'].includes(value.status)) {
          setResult(value); setError(value.error); setSelectedSection(0); setFlipped([])
          setLanguage(value.language); void refreshSaved()
          if (value.audio_ready) {
            try {
              const blob = await downloadRevisionAudio(value.action_id, abort.signal)
              if (mounted.current && !abort.signal.aborted) setAudioUrl(URL.createObjectURL(blob))
            } catch {
              if (mounted.current) setAudioError('Revision audio could not be loaded. Your transcript is still available; retry the audio download.')
            }
          } else if (value.status === 'complete' && !['audio_revision', 'flashcards'].includes(value.intent)) {
            try {
              const blob = await synthesizeSpeech(value.confirmation, value.language)
              if (mounted.current && !abort.signal.aborted) setAudioUrl(URL.createObjectURL(blob))
            } catch {
              if (mounted.current) setAudioError('Voice confirmation is unavailable. Your text result is still available.')
            }
          }
          return
        }
        await new Promise<void>(resolve => {
          const finish = () => { clearTimeout(timer); abort.signal.removeEventListener('abort', finish); resolve() }
          const timer = setTimeout(finish, 1500)
          abort.signal.addEventListener('abort', finish, { once: true })
        })
      }
      if (!abort.signal.aborted) throw new Error('The action is taking too long. Check the backend status before retrying.')
    } catch (err) {
      if (mounted.current && !abort.signal.aborted) setError(err instanceof Error ? err.message : 'Action failed.')
    } finally { active.current = false; if (mounted.current) setBusy(false) }
  }

  async function download() {
    if (!result || downloading) return
    setDownloading(true)
    try {
      const blob = await downloadDocumentAction(result.action_id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url; anchor.download = result.intent === 'flashcards' ? `lecture-flashcards-${result.language}.json` : `lecture-${result.intent === 'audio_revision' ? 'revision' : 'summary'}-${result.summary_language}.txt`; anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) { setError(err instanceof Error ? err.message : 'Download failed.') }
    finally { setDownloading(false) }
  }

  async function downloadAudio() {
    if (!result || downloading) return
    setDownloading(true)
    try {
      const blob = await downloadRevisionAudio(result.action_id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url; anchor.download = `lecture-revision-${result.language}.wav`; anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) { setError(err instanceof Error ? err.message : 'Audio download failed.') }
    finally { setDownloading(false) }
  }

  function playSection(section: RevisionSection, replayOnly: boolean) {
    const player = audioPlayer.current
    if (!player || section.start_seconds === null) return
    replayEnd.current = replayOnly ? section.end_seconds : null
    player.currentTime = section.start_seconds
    setSelectedSection(section.id)
    setCurrentTime(section.start_seconds)
    void player.play().catch(() => setAudioError('Press Play in the audio player to begin playback.'))
  }

  const library = libraryTarget && createPortal(<SavedLibrary items={savedActions} busy={busy} selectedId={result?.action_id} onOpen={item => { onOpenSaved?.(); void openSaved(item) }} onDelete={setDeletePending} onRefresh={() => void refreshSaved()} />, libraryTarget)
  if (!capabilities?.enabled) return <>
    <section className="nb-card p-6"><h2 className="vl-section-title">Study tools</h2>
      <p role="status" className="mt-3">{capabilitiesError ? 'Study actions could not be loaded. Check your connection and refresh.' : capabilities ? 'Study actions are currently unavailable.' : 'Loading study actions…'}</p>
    </section>{library}
  </>
  return (
    <section className="rounded-[20px] p-6" style={{ border: '1px solid var(--border)', background: 'var(--surface-soft)' }}>
      <h2 className="text-lg font-semibold">Document actions and audio revision</h2>
      <p className="mt-2 text-sm">Summarize your document or create a short spoken revision with a transcript and audio download. Limit: {capabilities.max_document_chars.toLocaleString()} extracted characters.</p>
      <details className="mt-4 text-sm"><summary className="cursor-pointer font-semibold">Advanced options</summary>
      <label htmlFor="action-provider" className="mt-4 block text-sm">Processing mode</label>
      <select id="action-provider" className="nb-input mt-2 w-full" disabled={busy} value={executionProvider} onChange={event => setExecutionProvider(event.target.value as 'direct' | 'openclaw_mcp')}>
        <option value="openclaw_mcp">Study assistant</option><option value="direct">Standard processing</option>
      </select>
      <p className="mt-2 text-sm">Choose how to run new study tasks. Both modes support generating and saving study materials; the selected mode stays in use until you change it.</p>
      </details>
      <label htmlFor="action-language" className="mt-4 block text-sm">Output language</label>
      <select id="action-language" className="nb-input mt-2 w-full" value={language} disabled={busy}
        onChange={event => {
          const selected = event.target.value as ActionLanguage
          setLanguage(selected)
          setError(null); setAudioError(null); setStatus('')
        }}>
        {(['english', 'tamil', 'sinhala'] as const).map(value => <option key={value} value={value}>{languageLabels[value]}</option>)}
      </select>
      {capabilities.sectioned_enabled && <label className="mt-4 block text-sm" htmlFor="revision-mode">Audio revision format
        <select id="revision-mode" className="nb-input mt-2 w-full" value={revisionMode} disabled={busy}
          onChange={event => setRevisionMode(event.target.value as RevisionMode)}>
          <option value="sectioned">Sectioned audio with supporting source passages</option>
          <option value="single">Single audio (baseline)</option>
        </select>
        <span className="mt-2 block text-sm">Sectioned revision uses up to three source sections. More translation and speech calls can take longer.</span>
      </label>}
      <label className="mt-4 block text-sm" htmlFor="action-document">Document for this action</label>
      <select id="action-document" className="nb-input mt-2 w-full" value={documentId} disabled={busy}
        onChange={event => { setDocumentId(event.target.value); setResult(null); setAudioUrl(null); setError(null); setStatus('') }}>
        <option value="">Select a document</option>
        {documents.filter(doc => /\.(pdf|txt|md)$/i.test(doc.filename)).map(doc => (
          <option key={doc.document_id} value={doc.document_id}>{doc.filename}</option>
        ))}
      </select>
      <label htmlFor="voice-command-language" className="mt-4 block text-sm">Voice command language</label>
      <select id="voice-command-language" className="nb-input mt-2 w-full" value={voiceLanguage} disabled={busy} onChange={event => {
        const selected = event.target.value as ActionLanguage
        setVoiceLanguage(selected); setCommand(examples[selected].audio)
      }}>{(['english', 'tamil', 'sinhala'] as const).map(value => <option key={value} value={value}>{languageLabels[value]}</option>)}</select>
      <p className="mt-2 text-sm">The new listed commands use English. You can speak an English command and generate Tamil or Sinhala audio by selecting a different output language.</p>
      <div className="mt-4"><VoiceRecorder key={voiceLanguage} language={voiceLanguage} disabled={busy} active={visible}
        onTranscript={value => { setCommand(value.transcript); setError(null) }} onError={setError} /></div>
      <label htmlFor="action-command" className="mt-4 block text-sm">{languageLabels[voiceLanguage]} command</label>
      <textarea id="action-command" className="nb-input mt-2 w-full" rows={2} value={command}
        disabled={busy} onChange={event => setCommand(event.target.value)} placeholder={examples[voiceLanguage].audio} />
      <p className="mt-2 text-sm">Supported commands: {examples[voiceLanguage].summary}; {examples[voiceLanguage].save}; {examples[voiceLanguage].combined}; {examples[voiceLanguage].audio}.</p>
      <p className="mt-2 text-sm">Use the displayed phrases. After speaking, check or edit the recognized command before running it.</p>
      <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold">All supported commands</summary>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">{extraCommands.map(value => <button key={value} className="vl-btn-secondary text-left" disabled={busy} onClick={() => setCommand(value)}>{value}</button>)}</div>
        <p className="mt-2">Playback commands control the loaded audio. Commands naming Tamil, Sinhala or English override the output language selection. Section-only generation uses the source section selected below.</p>
      </details>
      {!!result?.sections?.length && <label className="mt-3 block text-sm" htmlFor="source-section">Source section for section-only revision
        <select id="source-section" className="nb-input mt-2 w-full" value={selectedSection} disabled={busy} onChange={event => setSelectedSection(Number(event.target.value))}>
          {result.sections.map(section => <option key={section.id} value={section.id}>{section.id + 1}. {section.title}</option>)}
        </select>
      </label>}
      <button className="vl-btn-primary mt-4" disabled={busy || !command.trim() || (!documentId && !isPlaybackCommand(normalizeCommand(command)) && normalizeCommand(command) !== 'delete this saved revision')} onClick={() => void execute()}>
        {busy ? status : 'Run action'}
      </button>
      <button className="vl-btn-secondary ml-3 mt-4" disabled={busy} onClick={() => setCommand(examples[voiceLanguage].audio)}>Use audio revision command</button>
      <p className="mt-2 text-sm" role="status">{!busy && status}</p>
      {error && <p role="alert" className="mt-3 text-sm" style={{ color: 'var(--warning)' }}>{error}</p>}
      {result && <div ref={resultAnchor} className="mt-5 flex items-center justify-between gap-3 border-t pt-4" style={{ scrollMarginTop: 110 }}>
        <h3 className="font-semibold">Opened study result</h3><a className="vl-btn-secondary" href="#saved-library-title">Back to saved library</a>
      </div>}
      {result?.status === 'partial' && result.revision_mode === 'sectioned' && result.summary_language === result.language
        && !!result.sections?.length && result.sections.every(section => section.script_language === result.language) &&
        <button className="vl-btn-secondary mt-3" disabled={busy} onClick={() => void execute(result.action_id)}>Retry audio using prepared transcript</button>}
      {audioUrl && <audio ref={audioPlayer} className="mt-4 w-full" src={audioUrl} controls onSeeking={() => { const player = audioPlayer.current; if (player && replayEnd.current !== null && player.currentTime >= replayEnd.current) replayEnd.current = null }}
        onTimeUpdate={() => {
          const player = audioPlayer.current
          if (!player) return
          setCurrentTime(player.currentTime)
          if (replayEnd.current !== null && player.currentTime >= replayEnd.current) { player.pause(); replayEnd.current = null }
        }}
        autoPlay={visible && result?.intent !== 'audio_revision'} onLoadedMetadata={() => { if (audioPlayer.current) audioPlayer.current.playbackRate = Number(playbackRate) }} />}
      {audioUrl && result?.intent === 'audio_revision' && <label className="mt-3 block text-sm">Playback speed
        <select className="nb-input ml-3" value={playbackRate} onChange={event => {
          setPlaybackRate(event.target.value)
          if (audioPlayer.current) audioPlayer.current.playbackRate = Number(event.target.value)
        }}><option value="0.75">0.75×</option><option value="1">1×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option></select>
      </label>}
      {result?.summary && result.intent !== 'flashcards' && <div className="mt-5">
        {result.intent === 'audio_revision' && <h3 className="mb-3 font-semibold">Audio revision transcript</h3>}
        <p className="mb-3 text-sm">Transcript language: {languageLabels[result.summary_language]}</p>
        {(!(result.sections?.length) || !showSections) && <MarkdownContent content={result.summary} />}
      </div>}
      {!!result?.flashcards?.length && <div className="mt-5"><h3 className="font-semibold">{result.saved ? 'Saved revision flashcards' : 'Revision flashcards'}</h3>
        <p className="mt-2 text-sm">Flip each card to reveal its answer. Source quotes are from the original document.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">{result.flashcards.map((card, index) => <article key={index} className="rounded-xl border p-4">
          <p className="font-semibold">{index + 1}. {card.question}</p>
          <button className="vl-btn-secondary mt-3" aria-expanded={flipped.includes(index)} onClick={() => setFlipped(values => values.includes(index) ? values.filter(i => i !== index) : [...values, index])}>{flipped.includes(index) ? 'Hide answer' : 'Reveal answer'}</button>
          {flipped.includes(index) && <p className="mt-3 whitespace-pre-wrap">{card.answer}</p>}
          <details className="mt-3 text-sm"><summary>Supporting source</summary><blockquote className="mt-2 whitespace-pre-wrap">{card.source_quote}</blockquote></details>
        </article>)}</div>
      </div>}
      {result?.target_duration && <p className="mt-3 text-sm">Target: about {result.target_duration} seconds. Actual audio: {result.audio_duration ? `${Math.round(result.audio_duration)} seconds` : 'not ready'}. Speaking time varies by language and voice.</p>}
      {!!result?.sections?.length && <div className="mt-4">
        <label className="text-sm"><input type="checkbox" checked={showSections} onChange={event => {
          setShowSections(event.target.checked); replayEnd.current = null
        }} /> Show section navigation and source view</label>
        <p className="mt-1 text-sm">Turn off to compare the same audio and transcript in a single-player view. This does not generate new audio.</p>
      </div>}
      {!!result?.sections?.length && showSections && <RevisionNavigator key={result.action_id} actionId={result.action_id} sections={result.sections}
        currentTime={currentTime} audioReady={!!audioUrl} onPlay={playSection} />}
      {(result?.saved || (result?.intent === 'audio_revision' && result.summary)) && <button className="vl-btn-secondary mt-4" disabled={downloading} onClick={() => void download()}>{downloading ? 'Downloading…' : result?.intent === 'flashcards' ? 'Download flashcards (.json)' : result?.intent === 'audio_revision' ? 'Download transcript (.txt)' : 'Download summary (.txt)'}</button>}
      {result?.audio_saved && <button className="vl-btn-secondary ml-3 mt-4" disabled={downloading} onClick={() => void downloadAudio()}>Download revision audio (.wav)</button>}
      {result?.intent === 'audio_revision' && result.trace.length > 0 && <p className="mt-3 text-sm">Completed: {Array.from(new Set(result.trace)).map(tool => toolLabels[tool] || tool).join(' → ')}</p>}
      {audioError && <div className="mt-2"><p className="text-sm" role="alert">{audioError}</p>
        {result?.audio_ready && !audioUrl && <button className="vl-btn-secondary mt-2" disabled={busy} onClick={() => void retrySavedAudio()}>Retry loading audio</button>}
      </div>}
      {library}
      {deletePending && createPortal(<div role="dialog" aria-modal="true" aria-labelledby="delete-revision-title" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div className="w-full max-w-md rounded-xl p-6" style={{ background: 'var(--surface, #fff)' }}>
          <h3 id="delete-revision-title" className="font-semibold">Delete this saved result?</h3>
          <p className="mt-3 text-sm">{savedActions.find(item => item.action_id === deletePending)?.filename}. This removes this saved result and its unshared files. The original document stays available.</p>
          <button autoFocus className="vl-btn-secondary mt-4" disabled={busy} onClick={() => setDeletePending(null)}>Cancel</button>
          <button className="vl-btn-primary ml-3 mt-4" disabled={busy} onClick={() => void confirmDelete()}>{busy ? 'Deleting…' : 'Confirm delete'}</button>
        </div>
      </div>, document.body)}
    </section>
  )
}
