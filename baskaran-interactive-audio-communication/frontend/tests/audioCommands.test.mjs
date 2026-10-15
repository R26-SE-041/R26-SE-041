import test from 'node:test'
import assert from 'node:assert/strict'
import { isPlaybackCommand, extraCommands } from '../src/components/documents/audioCommands.ts'

test('legacy playback phrases are intercepted instead of becoming backend generation tasks', () => {
  for(const command of ['Play the audio','Pause the audio','Resume the audio','Stop the audio','Play the next section','Play the previous section','Replay this section','Play section two','Skip forward ten seconds','Go back ten seconds','Set playback speed to 0.75','Set playback speed to one point two five']) assert.equal(isPlaybackCommand(command),true,command)
  for(const command of extraCommands) assert.equal(isPlaybackCommand(command),false,command)
  assert.equal(isPlaybackCommand('Create a short audio revision of this document and save it'),false)
})
