import test from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'
import { readFileSync } from 'node:fs'
import { extraCommands, isPlaybackCommand } from '../src/components/documents/audioCommands.ts'
const source = readFileSync(new URL('../src/components/documents/handsFreeCommands.ts', import.meta.url), 'utf8').replace("'./audioCommands'", JSON.stringify(new URL('../src/components/documents/audioCommands.ts',import.meta.url).href))
const { parseVoiceIntent: parse } = await import('data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText).toString('base64'))
test('all displayed commands have hands-free intents, with a mandatory prefix for new work and delete', () => {
  for (const command of extraCommands) {
    const expected=isPlaybackCommand(command) ? 'playback' : command.startsWith('Delete') ? 'delete' : 'create'
    assert.equal(parse('VoiceLearn, '+command)?.kind, expected, command)
    assert.equal(parse(command),null)
    assert.equal(parse(command,false)?.kind ?? null, expected==='playback' ? 'playback' : null)
  }
})
test('short aliases, spoken decimals, exact matching and explicit voice confirmation', () => {
  assert.equal(parse('Voice learn pause')?.command,'pause the audio')
  assert.equal(parse('pause',false)?.kind,'playback')
  assert.equal(parse('VoiceLearn create a 1 minute audio revision and save it')?.kind,'create')
  assert.equal(parse('VoiceLearn skip forward 10 seconds')?.kind,'playback')
  assert.equal(parse('VoiceLearn set playback speed to one point two five')?.kind,'playback')
  for(const phrase of ['do not pause the audio','VoiceLearn do not pause','VoiceLearn pause and delete','VoiceLearn a story about pause the audio','confirm','confirm delete']) assert.equal(parse(phrase,false),null,phrase)
  assert.equal(parse('VoiceLearn confirm')?.kind,'confirm')
  assert.equal(parse('VoiceLearn confirm delete')?.kind,'confirm-delete')
  assert.equal(parse('VoiceLearn cancel')?.kind,'cancel')
})
