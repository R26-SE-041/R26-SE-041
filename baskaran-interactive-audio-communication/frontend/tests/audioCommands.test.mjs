import test from 'node:test'
import assert from 'node:assert/strict'
import { controlPlayback, isPlaybackCommand, extraCommands } from '../src/components/documents/audioCommands.ts'

const sections = [0, 1, 2].map(id => ({ id, title: `Section ${id + 1}`, start_seconds: id * 20, end_seconds: (id + 1) * 20 }))
function player(time = 0) {
  return { currentTime: time, duration: 60, playbackRate: 1, paused: true,
    pause() { this.paused = true }, async play() { this.paused = false } }
}

test('all 12 requested playback commands are recognized; generation is not', () => {
  const commands = extraCommands.filter(isPlaybackCommand)
  assert.equal(commands.length, 12)
  assert.equal(isPlaybackCommand('Create an audio revision in Tamil and save it'), false)
  assert.equal(isPlaybackCommand('Play the audio and delete all files'), false)
  assert.equal(isPlaybackCommand('Set playback speed to zero point seven five.'), true)
  assert.equal(isPlaybackCommand('Set playback speed to one point two five'), true)
})

test('play, pause, resume, stop and restart at end', async () => {
  const audio = player(60)
  await controlPlayback('Play the audio', audio, sections)
  assert.equal(audio.currentTime, 0); assert.equal(audio.paused, false)
  audio.currentTime = 12
  await controlPlayback('Pause the audio', audio, sections)
  assert.equal(audio.paused, true); assert.equal(audio.currentTime, 12)
  await controlPlayback('Resume the audio', audio, sections)
  assert.equal(audio.paused, false); assert.equal(audio.currentTime, 12)
  await controlPlayback('Stop the audio', audio, sections)
  assert.equal(audio.paused, true); assert.equal(audio.currentTime, 0)
})

test('section navigation, replay bounds, explicit section two and edge errors', async () => {
  const audio = player(21)
  await controlPlayback('Play the next section', audio, sections)
  assert.equal(audio.currentTime, 40)
  await assert.rejects(controlPlayback('Play the next section', audio, sections), /no section/)
  await controlPlayback('Play the previous section', audio, sections)
  assert.equal(audio.currentTime, 20)
  audio.currentTime = 28
  assert.equal((await controlPlayback('Replay this section', audio, sections)).replayEnd, 40)
  assert.equal(audio.currentTime, 20)
  await controlPlayback('Play section two', audio, sections)
  assert.equal(audio.currentTime, 20)
  await assert.rejects(controlPlayback('Play section two', audio, sections.slice(0, 1)), /no section/)
  await assert.rejects(controlPlayback('Replay this section', audio, []), /sectioned/)
})

test('skip clamps to audio duration and beginning, playback rates match commands', async () => {
  const audio = player(55)
  await controlPlayback('Skip forward ten seconds', audio, sections)
  assert.equal(audio.currentTime, 60)
  audio.currentTime = 4
  await controlPlayback('Go back ten seconds', audio, sections)
  assert.equal(audio.currentTime, 0)
  for (const speed of [0.75, 1.25]) {
    await controlPlayback(`Set playback speed to ${speed}`, audio, sections)
    assert.equal(audio.playbackRate, speed)
  }
})
