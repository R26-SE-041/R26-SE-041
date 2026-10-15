import { useEffect, useRef, useState } from 'react'
import { useHandsFreeRecognition } from '@/hooks/useHandsFreeRecognition'
import { parseVoiceIntent } from './handsFreeCommands'

interface Props {
  active: boolean; busy: boolean; context: string
  validate: (command: string, deleting: boolean) => string | null
  execute: (command: string, deleting: boolean) => Promise<void>
  onEnabled: (enabled: boolean) => void
  playbackInterruptions: number
}

export function HandsFreeControls({ active, busy, context, validate, execute, onEnabled, playbackInterruptions }: Props) {
  const [message, setMessage] = useState('')
  const [pending, setPending] = useState<{ command: string; deleting: boolean; context: string; expires: number } | null>(null)
  const pendingRef = useRef(pending)
  pendingRef.current = pending
  const running = useRef(false)
  // Serialize finals from the same recognition event; confirmation is consumed before awaiting work.
  const recognition = useHandsFreeRecognition(active, busy, text => {
    if (busy || running.current) return
    const intent = parseVoiceIntent(text)
    if (!intent) return
    if (intent.kind === 'disable') { recognition.disable(); return }
    if (intent.kind === 'cancel') { pendingRef.current = null; setPending(null); setMessage('Cancelled.'); return }
    if (intent.kind === 'confirm' || intent.kind === 'confirm-delete') {
      const task = pendingRef.current
      if (!task || task.context !== context || Date.now() > task.expires) { setMessage('No pending command. Say your command again.'); return }
      if (task.deleting !== (intent.kind === 'confirm-delete')) { setMessage(task.deleting ? 'Say “VoiceLearn confirm delete” to delete.' : 'Say “VoiceLearn confirm” to continue.'); return }
      pendingRef.current = null; setPending(null)
      const problem = validate(task.command, task.deleting)
      if (problem) { setMessage(problem); return }
      void run(task.command, task.deleting)
      return
    }
    if (!('command' in intent)) return
    const deleting = intent.kind === 'delete'
    const problem = validate(intent.command, deleting)
    if (problem) { setMessage(problem); return }
    if (intent.kind === 'playback') { void run(intent.command, false); return }
    const task = { command: intent.command, deleting, context, expires: Date.now() + 20_000 }
    pendingRef.current = task; setPending(task)
    setMessage(`${intent.command}. Say “VoiceLearn ${deleting ? 'confirm delete' : 'confirm'}” within 20 seconds, or “VoiceLearn cancel”.`)
  }, playbackInterruptions)
  async function run(command: string, deleting: boolean) {
    running.current = true
    try { await execute(command, deleting); setMessage(`Command sent: ${command}. Check the result below.`) }
    finally { running.current = false }
  }
  useEffect(() => { onEnabled(recognition.enabled) }, [recognition.enabled, onEnabled])
  useEffect(() => {
    if (!pending) return
    if (!recognition.enabled || pending.context !== context) { pendingRef.current = null; setPending(null); setMessage('Pending command cancelled.'); return }
    const timer = setTimeout(() => { pendingRef.current = null; setPending(null); setMessage('Confirmation expired. Say your command again.'); }, Math.max(0, pending.expires - Date.now()))
    return () => clearTimeout(timer)
  }, [pending, context, recognition.enabled])
  return <aside aria-label="Hands-free voice controls" className="mt-5 rounded-2xl border p-4" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="font-semibold">Hands-free controls</h3>
      <button className={recognition.enabled ? 'vl-btn-secondary' : 'vl-btn-primary'} disabled={!recognition.supported || (!recognition.enabled && busy)} onClick={recognition.enabled ? recognition.disable : recognition.enable}>
        {recognition.enabled ? 'Turn off hands-free' : 'Enable hands-free'}
      </button>
    </div>
    <p className="mt-2 text-sm" role="status">{!recognition.supported ? 'Live voice recognition is unavailable in this browser. Use the player or command buttons.' : recognition.enabled ? busy ? 'Listening paused while your task runs.' : recognition.listening ? 'Listening — say “VoiceLearn, pause audio”.' : 'Connecting to voice recognition…' : 'Enable once, then control playing audio with your voice. No Run action needed.'}</p>
    {recognition.error && <p role="alert" className="mt-2 text-sm" style={{ color: 'var(--warning)' }}>{recognition.error}</p>}
    {message && <p role="status" className="mt-2 text-sm">{message}</p>}
    <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold">How to use voice controls</summary>
      <p className="mt-2">Speak English commands: “VoiceLearn, pause audio”, “VoiceLearn, resume audio”, “VoiceLearn, next section”, or any supported command prefixed with “VoiceLearn”. Playback acts immediately after recognition.</p>
      <p className="mt-2">New study tasks need “VoiceLearn confirm”. Deletion needs “VoiceLearn confirm delete”. Say “VoiceLearn cancel” to cancel, or “VoiceLearn stop listening” to turn off.</p>
      <p className="mt-2">Select a document first for new tasks. Open or generate audio before playback commands; section controls need sectioned audio. New materials appear in Saved library when the command includes saving.</p>
      <p className="mt-3 font-semibold">Every command must start with “VoiceLearn”. Unprefixed words from the playing audio are ignored.</p>
      <p className="mt-2">On Android, browser voice recognition can interrupt audio. If playback is interrupted or the browser ends listening, hands-free turns off instead of repeatedly restarting. Normal player controls remain available.</p>
      <p className="mt-2">Headphones help prevent the speaker audio triggering commands. Your browser may send microphone audio to its speech service. Keep this tab open; leaving Study tools or hiding the page turns listening off. Recognition may take a moment or stop when the connection drops.</p>
    </details>
  </aside>
}
