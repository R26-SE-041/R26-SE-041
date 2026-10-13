import type { RevisionSection } from './actionsApi'

export const extraCommands = [
  'Create an audio revision of this section only and save it',
  'Create a one-minute audio revision and save it',
  'Create a detailed audio revision and save it',
  'Create an audio revision in Tamil and save it',
  'Create an audio revision in Sinhala and save it',
  'Create an audio revision in English and save it',
  'Create flashcards from this document and save them',
  'Play the audio', 'Pause the audio', 'Resume the audio', 'Stop the audio',
  'Play the next section', 'Play the previous section', 'Replay this section',
  'Play section two', 'Skip forward ten seconds', 'Go back ten seconds',
  'Set playback speed to 0.75', 'Set playback speed to 1.25', 'Delete this saved revision',
] as const

export function normalizeCommand(command: string): string {
  return command.trim().toLowerCase().replace(/\s+/g, ' ').replace(/[.!?]+$/, '').replace(/^please /, '')
    .replace(/zero point (seven five|seventy[- ]five)/g, '0.75')
    .replace(/one point (two five|twenty[- ]five)/g, '1.25')
}

export function isPlaybackCommand(command: string): boolean {
  const text = normalizeCommand(command)
  return /^(play|pause|resume|stop) the audio$/.test(text) ||
    /^(play the (next|previous) section|replay this section|play section (one|two|three|\d+))$/.test(text) ||
    /^(skip forward|go back) (ten|10) seconds$/.test(text) ||
    /^set playback speed to (0\.75|1\.25)$/.test(text)
}

export interface Player {
  currentTime: number; duration: number; playbackRate: number
  pause(): void; play(): Promise<void>
}

export async function controlPlayback(command: string, player: Player, sections: RevisionSection[]): Promise<{ message: string; replayEnd?: number }> {
  const text = normalizeCommand(command)
  if (/^(play|resume) the audio$/.test(text)) {
    if (Number.isFinite(player.duration) && player.currentTime >= player.duration) player.currentTime = 0
    await player.play(); return { message: 'Playing audio' }
  }
  if (text === 'pause the audio') { player.pause(); return { message: 'Audio paused' } }
  if (text === 'stop the audio') { player.pause(); player.currentTime = 0; return { message: 'Audio stopped' } }
  if (text.startsWith('set playback speed')) {
    player.playbackRate = Number(text.split(' ').at(-1)); return { message: `Playback speed: ${player.playbackRate}×` }
  }
  if (/^(skip forward|go back)/.test(text)) {
    const duration = Number.isFinite(player.duration) ? player.duration : player.currentTime + 10
    player.currentTime = Math.min(duration, Math.max(0, player.currentTime + (text.startsWith('skip') ? 10 : -10)))
    return { message: `Playback at ${Math.round(player.currentTime)} seconds` }
  }
  if (!sections.length) throw new Error('Load a sectioned audio revision before using section commands.')
  let index = sections.findIndex(s => s.start_seconds !== null && s.end_seconds !== null && player.currentTime >= s.start_seconds && player.currentTime < s.end_seconds)
  if (index < 0) index = player.currentTime >= (sections.at(-1)?.end_seconds ?? Infinity) ? sections.length - 1 : 0
  if (text === 'play the next section') index++
  else if (text === 'play the previous section') index--
  else if (text.startsWith('play section ')) {
    const number = text.split(' ').at(-1)!
    index = ({ one: 1, two: 2, three: 3 }[number as 'one' | 'two' | 'three'] ?? Number(number)) - 1
  }
  if (index < 0 || index >= sections.length) throw new Error('There is no section in that direction or with that number.')
  const section = sections[index]
  if (section.start_seconds === null || section.end_seconds === null) throw new Error('Section audio is not ready yet.')
  player.currentTime = section.start_seconds
  await player.play()
  return { message: `Playing section ${index + 1}: ${section.title}`, ...(text === 'replay this section' ? { replayEnd: section.end_seconds } : {}) }
}
