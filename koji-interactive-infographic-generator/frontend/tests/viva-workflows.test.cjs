const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function load(file, dependencies = {}, globals = {}) {
  const module = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(code, { module, exports: module.exports, require: name => dependencies[name] ?? {}, ...globals });
  return module.exports;
}

test('answer hierarchy preserves source wording, order, numbered steps and citations', () => {
  const { answerBlocks } = load('answerBlocks.ts');
  const blocks = answerBlocks('## Answer\nBlood enters the atrium. [2]\n\nWhat it does: Receives blood.\n1. First step\n2. Second step\n- A cited fact [3]');
  assert.deepEqual(JSON.parse(JSON.stringify(blocks)), [
    { kind: 'heading', text: 'Answer' }, { kind: 'paragraph', text: 'Blood enters the atrium. [2]' },
    { kind: 'heading', text: 'What it does' }, { kind: 'paragraph', text: 'Receives blood.' },
    { kind: 'list', marker: '1.', text: 'First step' }, { kind: 'list', marker: '2.', text: 'Second step' },
    { kind: 'list', marker: '•', text: 'A cited fact [3]' },
  ]);
});

test('label edits append a new cloud version and never patch or replace the saved original', async () => {
  const original = Object.freeze({ id: '11111111-1111-4111-8111-111111111111', chatId: 'demo-chat',
    mode: 'anatomy', prompt: 'heart', enhancedPrompt: 'heart', imageBase64: 'ORIGINAL-IMAGE', version: 3,
    anatomyAnnotations: [], interactions: [{ id: 'old-question', answer: 'saved answer' }] });
  const calls = [], saved = [];
  const importedId = '22222222-2222-4222-8222-222222222222';
  const { saveAnnotationVersion } = load('historyVersions.ts', {
    './studioClient': { cloudEnabled: () => true, studioOwner: () => 'same-owner',
      getCloudHistory: async id => id === original.id ? original : { ...original, id, version: 4 },
      studioRequest: async (route, options) => { calls.push({ route, method: options.method, body: JSON.parse(options.body) }); return { id: importedId }; } },
    './historyStorage': { saveHistoryItem: async value => saved.push(value) },
  }, { crypto: { randomUUID: () => 'new-edit' } });
  const result = await saveAnnotationVersion(original.id, [{ label: 'Edited label' }]);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].route, '/studio/import');
  assert.equal(calls[0].method, 'POST');
  assert.equal(calls[0].body.metadata.chatId, original.chatId);
  assert.equal(calls[0].body.image_base64, original.imageBase64);
  assert.equal(calls[0].body.snapshot_interactions, true);
  assert.equal(calls[0].body.metadata.imageBase64, undefined);
  assert.equal(calls[0].body.metadata.interactions[0].answer, 'saved answer');
  assert.equal(original.version, 3);
  assert.equal(original.anatomyAnnotations.length, 0);
  assert.equal(result.id, importedId);
  assert.equal(saved[0].version, 4);
});

test('pull to refresh only triggers a deliberate downward gesture in a saved idle workspace', () => {
  for (const [enabled, interactive, horizontal, expected] of [[true, false, false, 1], [false, false, false, 0], [true, true, false, 0], [true, false, true, 0]]) {
    const listeners = {};
    let reloads = 0;
    const node = { scrollTop: 0, style: {}, addEventListener: (name, fn) => listeners[name] = fn, removeEventListener() {} };
    const usePullToRefresh = load('usePullToRefresh.ts', {
      react: { useState: () => [0, () => {}], useEffect: fn => fn() }, 'react-native': { Platform: { OS: 'web' } },
    }, { window: { location: { reload: () => reloads++ } } }).default;
    usePullToRefresh({ current: { getScrollableNode: () => node } }, enabled);
    const event = (x, y) => ({ target: { closest: () => interactive }, touches: [{ clientX: x, clientY: y }], cancelable: true, preventDefault() {} });
    listeners.touchstart(event(10, 10)); listeners.touchmove(event(horizontal ? 160 : 10, 100)); listeners.touchend();
    assert.equal(reloads, expected);
  }
});
