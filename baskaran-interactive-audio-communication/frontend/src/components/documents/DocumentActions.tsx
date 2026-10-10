'use client'

import { useEffect, useRef, useState } from 'react'
import { RevisionNavigator } from './RevisionNavigator'
import { VoiceRecorder } from '@/components/voice/VoiceRecorder'
import { MarkdownContent } from '@/components/ui/MarkdownContent'
import { synthesizeSpeech } from '@/lib/api'
import { documentActionCapabilities, startDocumentAction, getDocumentAction,
  downloadDocumentAction, downloadRevisionAudio, retryRevisionAudio, type ActionCapabilities, type RevisionMode, type RevisionSection, type ActionLanguage, type DocumentActionResult } from './actionsApi'
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

export function DocumentActions({ documents }: { documents: DocumentItem[] }) {
  const [capabilities, setCapabilities] = useState<ActionCapabilities | null>(null)
  const [documentId, setDocumentId] = useState('')
  const [command, setCommand] = useState('')
  const [language, setLanguage] = useState<ActionLanguage>('english')
  const [revisionMode, setRevisionMode] = useState<RevisionMode>('sectioned')
  const [currentTime, setCurrentTime] = useState(0)
  const [showSections, setShowSections] = useState(true)
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
  const session = useRef('')
  const controller = useRef<AbortController | null>(null)
  const active = useRef(false)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    session.current = sessionStorage.getItem('voicelearn-action-session') || crypto.randomUUID()
    sessionStorage.setItem('voicelearn-action-session', session.current)
    documentActionCapabilities().then(value => { if (mounted.current) setCapabilities(value) }).catch(() => undefined)
    return () => { mounted.current = false; controller.current?.abort() }
  }, [])
  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl) }, [audioUrl])

  async function execute(retryActionId?: string) {
    if (active.current || (!retryActionId && (!command.trim() || !documentId))) return
    const sectioned = retryActionId ? result?.revision_mode === 'sectioned' : capabilities?.sectioned_enabled && revisionMode === 'sectioned'
    active.current = true
    setBusy(true); setError(null); setResult(null); setAudioUrl(null); setAudioError(null)
    setCurrentTime(0); setShowSections(true); replayEnd.current = null
    setStatus('Submitting command')
    const abort = new AbortController()
    controller.current = abort
    try {
      const id = retryActionId ? await retryRevisionAudio(retryActionId) : await startDocumentAction(command.trim(), documentId, session.current, language, capabilities?.sectioned_enabled ? revisionMode : 'single')
      const deadline = Date.now() + (sectioned ? 1_920_000 : 720_000)
      while (!abort.signal.aborted && Date.now() < deadline) {
        const value = await getDocumentAction(id, abort.signal)
        if (!mounted.current) return
        setStatus(value.progress && !['complete', 'partial', 'failed'].includes(value.status) ? value.progress : labels[value.status] || value.status)
        if (['complete', 'partial', 'failed'].includes(value.status)) {
          setResult(value); setError(value.error)
          if (value.audio_ready) {
            try {
              const blob = await downloadRevisionAudio(value.action_id, abort.signal)
              if (mounted.current && !abort.signal.aborted) setAudioUrl(URL.createObjectURL(blob))
            } catch {
              if (mounted.current) setAudioError('Revision audio could not be loaded. Your transcript is still available; retry the audio download.')
            }
          } else if (value.status === 'complete' && value.intent !== 'audio_revision') {
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
      anchor.href = url; anchor.download = `lecture-${result.intent === 'audio_revision' ? 'revision' : 'summary'}-${result.summary_language}.txt`; anchor.click()
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
    setCurrentTime(section.start_seconds)
    void player.play().catch(() => setAudioError('Press Play in the audio player to begin playback.'))
  }

  if (!capabilities?.enabled) return null
  return (
    <section className="mt-6 rounded-[20px] p-6" style={{ border: '1px solid var(--border)', background: 'var(--surface-soft)' }}>
      <h2 className="text-lg font-semibold">Document actions and audio revision</h2>
      <p className="mt-2 text-sm">Summarize your document or create a short spoken revision with a transcript and audio download. Limit: {capabilities.max_document_chars.toLocaleString()} extracted characters.</p>
      <label htmlFor="action-language" className="mt-4 block text-sm">Command and output language</label>
      <select id="action-language" className="nb-input mt-2 w-full" value={language} disabled={busy}
        onChange={event => {
          const selected = event.target.value as ActionLanguage
          setLanguage(selected); setCommand(examples[selected].audio)
          setResult(null); setAudioUrl(null); setError(null); setAudioError(null); setStatus('')
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
      <div className="mt-4"><VoiceRecorder key={language} language={language} disabled={busy}
        onTranscript={value => { setCommand(value.transcript); setError(null) }} onError={setError} /></div>
      <label htmlFor="action-command" className="mt-4 block text-sm">{languageLabels[language]} command</label>
      <textarea id="action-command" className="nb-input mt-2 w-full" rows={2} value={command}
        disabled={busy} onChange={event => setCommand(event.target.value)} placeholder={examples[language].audio} />
      <p className="mt-2 text-sm">Supported commands: {examples[language].summary}; {examples[language].save}; {examples[language].combined}; {examples[language].audio}.</p>
      <p className="mt-2 text-sm">Use the displayed phrases. After speaking, check or edit the recognized command before running it.</p>
      <button className="vl-btn-primary mt-4" disabled={busy || !documentId || !command.trim()} onClick={() => void execute()}>
        {busy ? status : 'Run action'}
      </button>
      <button className="vl-btn-secondary ml-3 mt-4" disabled={busy} onClick={() => setCommand(examples[language].audio)}>Use audio revision command</button>
      <p className="mt-2 text-sm" role="status">{!busy && status} {result?.provider === 'openclaw_mcp' ? 'OpenClaw' : result?.provider === 'direct' ? 'Direct backend' : ''}</p>
      {error && <p role="alert" className="mt-3 text-sm" style={{ color: 'var(--warning)' }}>{error}</p>}
      {result?.status === 'partial' && result.revision_mode === 'sectioned' && result.summary_language === result.language
        && !!result.sections?.length && result.sections.every(section => section.script_language === result.language) &&
        <button className="vl-btn-secondary mt-3" disabled={busy} onClick={() => void execute(result.action_id)}>Retry audio using prepared transcript</button>}
      {result?.summary && <div className="mt-5">
        {result.intent === 'audio_revision' && <h3 className="mb-3 font-semibold">Audio revision transcript</h3>}
        <p className="mb-3 text-sm">Transcript language: {languageLabels[result.summary_language]}</p>
        {(!(result.sections?.length) || !showSections) && <MarkdownContent content={result.summary} />}
      </div>}
      {!!result?.sections?.length && <div className="mt-4">
        <label className="text-sm"><input type="checkbox" checked={showSections} onChange={event => {
          setShowSections(event.target.checked); replayEnd.current = null
        }} /> Show section navigation and source view</label>
        <p className="mt-1 text-sm">Turn off to compare the same audio and transcript in a single-player view. This does not generate new audio.</p>
      </div>}
      {!!result?.sections?.length && showSections && <RevisionNavigator key={result.action_id} actionId={result.action_id} sections={result.sections}
        currentTime={currentTime} audioReady={!!audioUrl} onPlay={playSection} />}
      {(result?.saved || (result?.intent === 'audio_revision' && result.summary)) && <button className="vl-btn-secondary mt-4" disabled={downloading} onClick={() => void download()}>{downloading ? 'Downloading…' : result?.intent === 'audio_revision' ? 'Download transcript (.txt)' : 'Download summary (.txt)'}</button>}
      {result?.audio_saved && <button className="vl-btn-secondary ml-3 mt-4" disabled={downloading} onClick={() => void downloadAudio()}>Download revision audio (.wav)</button>}
      {result?.intent === 'audio_revision' && result.trace.length > 0 && <p className="mt-3 text-sm">Completed: {Array.from(new Set(result.trace)).map(tool => toolLabels[tool] || tool).join(' → ')}</p>}
      {audioUrl && <audio ref={audioPlayer} className="mt-4 w-full" src={audioUrl} controls onSeeking={() => { const player = audioPlayer.current; if (player && replayEnd.current !== null && player.currentTime >= replayEnd.current) replayEnd.current = null }}
        onTimeUpdate={() => {
          const player = audioPlayer.current
          if (!player) return
          setCurrentTime(player.currentTime)
          if (replayEnd.current !== null && player.currentTime >= replayEnd.current) { player.pause(); replayEnd.current = null }
        }}
        autoPlay={result?.intent !== 'audio_revision'} onLoadedMetadata={() => { if (audioPlayer.current) audioPlayer.current.playbackRate = Number(playbackRate) }} />}
      {audioUrl && result?.intent === 'audio_revision' && <label className="mt-3 block text-sm">Playback speed
        <select className="nb-input ml-3" value={playbackRate} onChange={event => {
          setPlaybackRate(event.target.value)
          if (audioPlayer.current) audioPlayer.current.playbackRate = Number(event.target.value)
        }}><option value="0.75">0.75×</option><option value="1">1×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option></select>
      </label>}
      {audioError && <p className="mt-2 text-sm">{audioError}</p>}
    </section>
  )
}
