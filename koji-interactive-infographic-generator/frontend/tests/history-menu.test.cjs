const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function load(file, dependencies = {}, globals = {}) {
  const module = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, esModuleInterop: true },
  }).outputText;
  vm.runInNewContext(code, { module, exports: module.exports, require: name => dependencies[name] ?? {}, URLSearchParams, ...globals });
  return module.exports;
}
function find(node, predicate) {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) { for (const child of node) { const found = find(child, predicate); if (found) return found; } return; }
  return predicate(node) ? node : find(node.props?.children, predicate);
}
function statefulReact() {
  let cursor = 0;
  const states = [];
  const react = { createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
    useState: initial => { const slot = cursor++; if (!(slot in states)) states[slot] = typeof initial === 'function' ? initial() : initial; return [states[slot], value => states[slot] = typeof value === 'function' ? value(states[slot]) : value]; },
    useEffect: () => {}, useMemo: fn => fn(), useCallback: fn => fn, useSyncExternalStore: (_subscribe, get) => get(),
    useRef: value => react.useState(() => ({ current: value }))[0],
  };
  return { react, render: (component, props) => { cursor = 0; return component(props); } };
}
const native = new Proxy({ Platform: { OS: 'web' } }, { get: (target, key) => target[key] || key });
const theme = { useAppTheme: () => ({ colors: {} }), makeSharedStyles: () => ({}) };
const textIs = label => node => node.type === 'Pressable' && node.props.children?.some(child => child?.props?.children?.includes(label));
const flush = () => new Promise(setImmediate);

test('three-dot menu opens every creation action and choosing an action closes it', () => {
  for (const [label, callback] of [['Open','onOpen'],['Continue in chat','onContinue'],['Rename','onRename'],['Delete','onDelete']]) {
    const state = statefulReact(), calls = [];
    const Menu = load('components/HistoryCardMenu.tsx', { react: state.react, 'react-native': native, '../theme': theme, './ArchiveDialog': 'ArchiveDialog' }).default;
    const props = { title: 'Saved creation', ...Object.fromEntries(['onOpen','onContinue','onRename','onDelete'].map(key => [key, () => calls.push(key)])) };
    const render = () => state.render(Menu, props);
    find(render(), node => node.props?.accessibilityLabel === 'More actions for Saved creation').props.onPress();
    for (const option of ['Open','Continue in chat','Rename','Delete']) assert.ok(find(render(), textIs(option)));
    find(render(), textIs(label)).props.onPress();
    assert.deepEqual(calls, [callback]);
    assert.equal(find(render(), node => node.type === 'ArchiveDialog'), undefined);
  }
});

test('dismissal never changes data and the recycle-bin menu offers restore separately from permanent deletion', () => {
  const state = statefulReact(), calls = [];
  const Menu = load('components/HistoryCardMenu.tsx', { react: state.react, 'react-native': native, '../theme': theme, './ArchiveDialog': 'ArchiveDialog' }).default;
  const props = { title: 'Saved model', trashed: true, onOpen: () => calls.push('open'), onRename: () => calls.push('rename'), onDelete: () => calls.push('delete'), onRestore: () => calls.push('restore') };
  const render = () => state.render(Menu, props);
  find(render(), node => node.props?.accessibilityLabel).props.onPress();
  assert.ok(find(render(), textIs('Restore')));
  assert.ok(find(render(), textIs('Delete permanently')));
  assert.equal(find(render(), textIs('Open')), undefined);
  find(render(), node => node.type === 'ArchiveDialog').props.onClose();
  assert.deepEqual(calls, []);
});

function archive() {
  const state = statefulReact(), calls = [], resumed = [];
  const saved = { id: 'generation', chatId: 'chat', mode: 'general', prompt: 'Saved image', enhancedPrompt: 'Saved image', imageBase64: 'SAVED', createdAt: '2026-10-19T10:00:00Z', speedMode: 'normal' };
  const Archive = load('components/CreationArchive.tsx', {
    react: state.react, 'react-native': native, '../theme': theme,
    '../historyView': load('historyView.ts'), '../historyActivity': { getHistoryRevision: () => 0 },
    '../studioClient': { cloudEnabled: () => true, getCloudHistory: async (...args) => { calls.push({ kind: 'read', args }); return saved; },
      studioRequest: async (route, options) => {
        calls.push({ route, options });
        if (route.startsWith('/studio/chats?')) return [{ id: 'chat', title: 'Saved creation', updated_at: saved.createdAt, mode: route.includes('category=sketch') ? 'sketch' : 'general', latest_generation_id: saved.id }];
        return [];
      } },
    './HistoryCardMenu': 'HistoryCardMenu', './ModelGallery': 'ModelGallery', './ArchiveDialog': 'ArchiveDialog',
  }).default;
  const render = () => state.render(Archive, { onResume: item => resumed.push(item) });
  return { render, calls, resumed, saved };
}

test('all three history categories open rename/delete confirmation popups; cancelling never writes data', async () => {
  const app = archive();
  const model = { id: 'model-event', generationId: 'generation', chatId: 'chat', title: 'Saved model', mode: 'general', createdAt: app.saved.createdAt };
  for (const category of ['Images & labels','Sketches','3D models']) {
    const tab = find(app.render(), node => node.props?.accessibilityRole === 'tab' && node.props.children?.some(child => child?.props?.children?.includes(category)));
    tab.props.onPress();
    if (category !== '3D models') {
      // Effects are inert in this fixture, so explicitly drive the archive read.
      find(app.render(), node => node.props?.accessibilityLabel === 'Refresh history').props.onPress(); await flush();
    }
    const callbacks = () => category === '3D models' ? find(app.render(), node => node.type === 'ModelGallery').props : find(app.render(), node => node.type === 'HistoryCardMenu').props;
    callbacks().onRename(model);
    let dialog = find(app.render(), node => node.type === 'ArchiveDialog' && node.props.title === 'Rename creation');
    assert.ok(dialog, category + ' rename popup');
    find(dialog, textIs('Cancel')).props.onPress();
    callbacks().onDelete(model);
    dialog = find(app.render(), node => node.type === 'ArchiveDialog' && node.props.title === 'Move to Recycle Bin?');
    assert.ok(dialog, category + ' delete popup');
    find(dialog, textIs('Cancel')).props.onPress();
    assert.equal(app.calls.some(call => call.options?.method), false);
  }
});

test('3D Continue in chat resumes the chosen saved model version without generation', async () => {
  const app = archive();
  find(app.render(), node => node.type === 'ModelGallery').props.onContinue({ id: 'chosen-model-event', generationId: 'generation', chatId: 'chat', title: 'Saved model', mode: 'general', createdAt: app.saved.createdAt });
  await flush();
  assert.deepEqual(app.calls.find(call => call.kind === 'read').args, ['generation', 'chosen-model-event']);
  assert.equal(app.resumed[0].id, 'generation');
  assert.equal(app.calls.some(call => call.options?.method), false);
});
