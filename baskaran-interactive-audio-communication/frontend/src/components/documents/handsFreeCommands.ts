import { extraCommands, isPlaybackCommand, normalizeCommand } from './audioCommands'

export type VoiceIntent = { kind: 'playback' | 'create' | 'delete'; command: string }
  | { kind: 'confirm' | 'confirm-delete' | 'cancel' | 'disable' }
const creation = new Set<string>([
  ...extraCommands.filter(value => !isPlaybackCommand(value) && value !== 'Delete this saved revision'),
  'Summarize this document', 'Save the summary', 'Summarize this document and save it',
  'Create a short audio revision of this document and save it',
].map(normalizeCommand))
const aliases: Record<string, string> = {
  pause: 'pause the audio', 'pause audio': 'pause the audio',
  play: 'play the audio', 'play audio': 'play the audio',
  resume: 'resume the audio', 'resume audio': 'resume the audio',
  stop: 'stop the audio', 'stop audio': 'stop the audio',
  'next section': 'play the next section', 'previous section': 'play the previous section',
  'replay section': 'replay this section',
}

/** Exact phrases only: narration, negation and compound instructions are ignored. */
export function parseVoiceIntent(transcript: string): VoiceIntent | null {
  let text = normalizeCommand(transcript.replace(/[,;:]/g, ' '))
    .replace(/\b(one|1) minute\b/g, 'one-minute')
  const wake = /^voice\s*learn\s+/.test(text)
  if (!wake) return null
  if (wake) text = text.replace(/^voice\s*learn\s+/, '')
  text = text.replace(/^please /, '')
  if (text === 'confirm delete') return wake ? { kind: 'confirm-delete' } : null
  if (text === 'confirm') return wake ? { kind: 'confirm' } : null
  if (text === 'cancel') return { kind: 'cancel' }
  if (text === 'disable hands free' || text === 'disable hands-free' || text === 'stop listening') return { kind: 'disable' }
  text = aliases[text] || text
  if (isPlaybackCommand(text)) return { kind: 'playback', command: text }
  if (text === 'delete this saved revision') return { kind: 'delete', command: text }
  if (creation.has(text)) return { kind: 'create', command: text }
  return null
}
