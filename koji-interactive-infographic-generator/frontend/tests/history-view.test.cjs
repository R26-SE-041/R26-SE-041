const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const moduleExports = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(require('node:path').join(__dirname, '../historyView.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { module: moduleExports, exports: moduleExports.exports });
const { localSummaries, filterArchive, dateGroup, creationTitle } = moduleExports.exports;
const item = (id, chatId, createdAt, changes = {}) => ({ id, chatId, createdAt, prompt: 'Human heart', enhancedPrompt: 'Anterior heart', imageBase64: 'image', mode: 'anatomy', speedMode: 'promax', ...changes });
test('versions share one creation and retain legacy speed metadata when resumed', () => {
  const rows = localSummaries([item('v2','chat','2026-10-12T12:00:00Z',{version:2,title:'Heart study',glbBase64:'model'}), item('v1','chat','2026-10-11T12:00:00Z',{version:1}), item('other',undefined,'2026-10-10T12:00:00Z')]);
  assert.equal(rows.length,2); assert.equal(rows[0].title,'Heart study'); assert.equal(rows[0].generationId,'v2');
  assert.equal(rows[0].versionCount,2); assert.equal(rows[0].hasThreeD,true); assert.equal(rows[0].versions[0].speedMode,'promax');
});
test('search matches earlier prompts while mode and date filters combine', () => {
  const rows = localSummaries([item('v1','chat','2026-10-11T12:00:00Z'), item('v2','chat','2026-10-12T12:00:00Z',{prompt:'Updated diagram',enhancedPrompt:'Updated',version:2}), item('old',undefined,'2026-08-01T12:00:00Z')]);
  assert.equal(filterArchive(rows,'heart','anatomy','week',new Date('2026-10-13T12:00:00Z')).length,1);
  assert.equal(filterArchive(rows,'heart','general','all').length,0);
});
test('date groups use local calendar days and drawing titles have a useful fallback', () => {
  const now = new Date(2026,9,13,12);
  assert.equal(dateGroup(new Date(2026,9,13,1).toISOString(),now),'Today');
  assert.equal(dateGroup(new Date(2026,9,12,23).toISOString(),now),'Yesterday');
  assert.equal(dateGroup(new Date(2026,9,10).toISOString(),now),'Earlier');
  assert.equal(creationTitle('  ','sketch'),'Untitled drawing');
});
