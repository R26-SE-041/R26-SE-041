export const extraCommands = [
  'Create an audio revision of this section only and save it',
  'Create a one-minute audio revision and save it',
  'Create a detailed audio revision and save it',
  'Create an audio revision in Tamil and save it',
  'Create an audio revision in Sinhala and save it',
  'Create an audio revision in English and save it',
  'Create flashcards from this document and save them',
  'Delete this saved revision',
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
