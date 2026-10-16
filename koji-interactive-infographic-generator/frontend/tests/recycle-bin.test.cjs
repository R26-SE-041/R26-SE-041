const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

// A transactional in-memory IDB adapter exercises the exported storage flows;
// requests and transaction completion run asynchronously as in browser IDB.
function loadStorage(initial, cloud = false) {
  const databases = new Map([['eduvision-local:owner', new Map(initial.map(item => [item.id, structuredClone(item)]))]]);
  const calls = [];
  let owner = 'owner';
  const indexedDB = { open(name) {
    const request = {};
    if (!databases.has(name)) databases.set(name, new Map());
    request.result = {
      close() {},
      transaction() {
        const snapshot = new Map([...databases.get(name)].map(([key, value]) => [key, structuredClone(value)]));
        let aborted = false;
        const transaction = { abort() { aborted = true; queueMicrotask(() => transaction.onabort?.()); } };
        const store = {
          getAll() {
            const read = {};
            queueMicrotask(() => {
              read.result = [...snapshot.values()];
              read.onsuccess?.();
              queueMicrotask(() => {
                if (aborted) return;
                databases.set(name, snapshot);
                transaction.oncomplete?.();
              });
            });
            return read;
          },
          put(item) { snapshot.set(item.id, structuredClone(item)); },
          delete(id) { snapshot.delete(id); },
        };
        transaction.objectStore = () => store;
        return transaction;
      },
    };
    queueMicrotask(() => request.onsuccess?.());
    return request;
  } };
  const source = fs.readFileSync(path.join(__dirname, '../historyStorage.ts'), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(code, { module, exports: module.exports, indexedDB, console,
    require: () => ({ markHistoryChanged: () => {}, cloudEnabled: () => cloud, studioOwner: () => owner,
      studioRequest: async (route, options) => { calls.push({ route, options }); return []; } }),
  });
  return { storage: module.exports, calls, changeOwner(value) { owner = value; },
    rows: () => [...databases.get('eduvision-local:owner').values()] };
}

const versions = () => [
  { id: 'v1', chatId: 'chat', createdAt: '2026-10-12T12:00:00Z', imageBase64: 'original', interactions: [{ answer: 'Saved answer' }] },
  { id: 'v2', chatId: 'chat', createdAt: '2026-10-13T12:00:00Z', imageBase64: 'revised', glbBase64: '3D model', sketchStrokes: [{ points: [[.5, .5]] }] },
  { id: 'other', chatId: 'keep', createdAt: '2026-10-14T12:00:00Z', imageBase64: 'unrelated' },
];

test('moving to bin preserves every version, image, model and answer; restore returns them', async () => {
  const { storage, rows } = loadStorage(versions());
  await storage.trashConversation('chat', false);
  assert.equal(rows().length, 3);
  assert.equal((await storage.listHistory()).length, 1);
  assert.equal((await storage.listHistory(undefined, true)).length, 2);
  assert.ok(rows().find(item => item.id === 'v1').deletedAt);
  assert.equal(rows().find(item => item.id === 'v2').glbBase64, '3D model');
  await storage.restoreConversation('chat', false);
  assert.equal((await storage.listHistory()).length, 3);
  assert.equal((await storage.listHistory(undefined, true)).length, 0);
  assert.equal(rows().find(item => item.id === 'v1').interactions[0].answer, 'Saved answer');
});

test('permanent deletion requires a trashed creation and never removes unrelated data', async () => {
  const { storage, rows } = loadStorage(versions());
  await assert.rejects(storage.purgeConversation('chat', false), /Recycle Bin/);
  assert.equal(rows().length, 3);
  await storage.trashConversation('chat', false);
  await storage.purgeConversation('chat', false);
  assert.deepEqual(rows().map(item => item.id), ['other']);
});

test('bin operations remain isolated to the current account database', async () => {
  const { storage, rows, changeOwner } = loadStorage(versions());
  changeOwner('another-owner');
  await storage.trashConversation('chat', false);
  assert.ok(rows().every(item => !item.deletedAt));
});

test('cloud operations use distinct trash, restore and permanent routes', async () => {
  const { storage, calls } = loadStorage(versions(), true);
  await storage.trashConversation('chat', true);
  await storage.restoreConversation('chat', true);
  // Simulate another device moving the creation back to the cloud bin. Local
  // cache state must not prevent eviction after an authoritative cloud purge.
  await storage.purgeConversation('chat', true);
  assert.deepEqual(calls.map(call => [call.route, call.options.method]), [
    ['/studio/chats/chat', 'DELETE'], ['/studio/chats/chat/restore', 'POST'],
    ['/studio/chats/chat/permanent', 'DELETE'],
  ]);
});
