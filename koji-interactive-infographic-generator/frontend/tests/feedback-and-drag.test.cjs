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
  vm.runInNewContext(code, { module, exports: module.exports, require: name => dependencies[name] ?? {}, ...globals });
  return module.exports;
}
function find(node, predicate) {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) { for (const child of node) { const value = find(child, predicate); if (value) return value; } return; }
  return predicate(node) ? node : find(node.props?.children, predicate);
}
const element = (type, props, ...children) => ({ type, props: { ...props, children } });
const flush = () => new Promise(setImmediate);
function feedback() {
  let cursor = 0, fail = false;
  const states = [], calls = [];
  const react = { createElement: element, useState: initial => {
    const slot = cursor++;
    if (!(slot in states)) states[slot] = typeof initial === 'function' ? initial() : initial;
    return [states[slot], value => states[slot] = typeof value === 'function' ? value(states[slot]) : value];
  }, useRef: value => react.useState(() => ({ current: value }))[0] };
  const Component = load('components/FeedbackControls.tsx', {
    react, 'react-native': { View: 'View', Text: 'Text', Pressable: 'Pressable', TextInput: 'TextInput', ActivityIndicator: 'ActivityIndicator' },
    './IconButton': 'IconButton', '../theme': { useAppTheme: () => ({ colors: {} }) },
  }, { fetch: async (_url, options) => {
    calls.push({ ...options, body: JSON.parse(options.body) });
    const ok = !fail; fail = false;
    return { ok, status: ok ? 200 : 503, json: async () => ok ? {} : { error: 'Please retry' } };
  } }).default;
  const render = () => { cursor = 0; return Component({ apiUrl: '/studio-api', agentName: 'image-agent', outputId: 'saved-output', sessionId: 'session', accessToken: 'fixture-token', inputContext: {}, outputSnapshot: {}, negativeReasons: [{ code: 'wrong_details', label: 'Wrong details' }] }); };
  const control = label => find(render(), node => node.props?.label === label || node.props?.accessibilityLabel === label)?.props;
  const submit = () => find(render(), node => node.type === 'Pressable' && node.props.children?.some(child => child?.props?.children?.includes('Send feedback')))?.props;
  return { control, submit, calls, fail: () => fail = true, render };
}

test('likes fill only the icon, toggle off persistently, and failed removal restores selection', async () => {
  const app = feedback();
  app.control('Like output').onPress(); await flush();
  assert.equal(app.control('Like output').filled, true);
  assert.equal(app.control('Like output').variant, 'plain');
  assert.equal(app.control('Dislike output').selected, false);
  app.fail(); app.control('Like output').onPress(); await flush();
  assert.equal(app.control('Like output').selected, true);
  app.control('Like output').onPress(); await flush();
  assert.equal(app.control('Like output').selected, false);
  assert.equal(app.calls.at(-1).method, 'DELETE');
  assert.deepEqual(JSON.parse(JSON.stringify(app.calls.at(-1).body)), { agent_name: 'image-agent', output_id: 'saved-output' });
  assert.equal(app.calls.at(-1).headers.Authorization, 'Bearer fixture-token');
});

test('dislikes offer selectable suggestions and comments, save details, and can be deselected', async () => {
  const app = feedback();
  app.control('Dislike output').onPress(); await flush();
  assert.equal(app.control('Dislike output').filled, true);
  assert.equal(app.submit().disabled, true);
  app.control('Wrong details').onPress();
  app.control('Optional feedback comment').onChangeText('The label is incorrect.');
  app.submit().onPress(); await flush();
  assert.equal(app.calls.at(-1).body.rating, -1);
  assert.equal(app.calls.at(-1).body.reason_codes[0], 'wrong_details');
  assert.equal(app.calls.at(-1).body.comment, 'The label is incorrect.');
  assert.equal(app.submit().disabled, true);
  app.control('Dislike output').onPress(); await flush();
  assert.equal(app.control('Optional feedback comment'), undefined);
  assert.equal(app.calls.at(-1).method, 'DELETE');
});

test('switching votes keeps one selected and rapid repeated clicks never duplicate writes', async () => {
  const app = feedback();
  const like = app.control('Like output'); like.onPress(); like.onPress(); await flush();
  assert.equal(app.calls.length, 1);
  app.control('Dislike output').onPress(); await flush();
  assert.equal(app.control('Like output').selected, false);
  assert.equal(app.control('Dislike output').selected, true);
});

test('plain selected thumb controls have transparent backgrounds and filled SVG paths', () => {
  const colors = { text: '#141413', textMuted: '#555' };
  const button = load('components/IconButton.tsx', { react: { createElement: element }, 'react-native': { Platform: { OS: 'web' }, Pressable: 'Pressable' }, './Icon': 'Icon', '../theme': { useAppTheme: () => ({ colors }) } }).default;
  const tree = button({ label: 'Like output', icon: 'thumb-up', selected: true, filled: true, variant: 'plain', onPress() {} });
  assert.equal(tree.props.style({ pressed: false }).backgroundColor, 'transparent');
  assert.equal(tree.props.style({ pressed: false }).borderWidth, 0);
  const icon = load('components/Icon.tsx', { react: { createElement: element }, 'react-native-svg': { Path: 'Path' } }).default;
  for (const name of ['thumb-up', 'thumb-down']) {
    assert.equal(find(icon({ name, color: '#141413', filled: true }), node => node.type === 'Path').props.fill, '#141413');
    assert.equal(find(icon({ name, color: '#141413' }), node => node.type === 'Path').props.fill, 'none');
  }
});

function dragGuard() {
  const listeners = {}, attributes = {};
  const doc = { documentElement: { setAttribute: (key, value) => attributes[key] = value, removeAttribute: key => delete attributes[key] }, addEventListener: (key, fn) => listeners[key] = fn, removeEventListener: key => delete listeners[key] };
  const win = { addEventListener: (key, fn) => listeners[key] = fn, removeEventListener: key => delete listeners[key] };
  const cleanup = load('dragSelection.ts').installDragSelectionGuard(doc, win);
  const event = (surface = true, editable = false, id = 1) => ({ pointerId: id, target: { closest: selector => selector.includes('data-drag-surface') ? surface : editable }, preventDefault() { this.prevented = true; } });
  return { listeners, attributes, event, cleanup };
}

test('model drag blocks text selection beyond its box and restores normal selection on release', () => {
  const app = dragGuard();
  app.listeners.pointerdown(app.event());
  const outside = app.event(false); app.listeners.selectstart(outside);
  assert.equal(outside.prevented, true);
  app.listeners.pointerup(outside);
  assert.equal(app.attributes['data-studio-dragging'], undefined);
  const normal = app.event(false); app.listeners.selectstart(normal);
  assert.equal(normal.prevented, undefined);
});

test('multi-touch, cancellation, blur and unmount release the guard; inputs and ordinary text stay selectable', () => {
  const app = dragGuard();
  app.listeners.pointerdown(app.event(true, true));
  assert.equal(app.attributes['data-studio-dragging'], undefined);
  app.listeners.pointerdown(app.event(false));
  assert.equal(app.attributes['data-studio-dragging'], undefined);
  app.listeners.pointerdown(app.event(true, false, 1)); app.listeners.pointerdown(app.event(true, false, 2));
  app.listeners.pointerup(app.event(false, false, 1));
  assert.equal(app.attributes['data-studio-dragging'], 'true');
  app.listeners.pointercancel(app.event(false, false, 2));
  assert.equal(app.attributes['data-studio-dragging'], undefined);
  app.listeners.pointerdown(app.event()); app.listeners.blur();
  assert.equal(app.attributes['data-studio-dragging'], undefined);
  app.listeners.pointerdown(app.event()); app.cleanup();
  assert.equal(app.attributes['data-studio-dragging'], undefined);
  assert.equal(Object.keys(app.listeners).length, 0);
});
