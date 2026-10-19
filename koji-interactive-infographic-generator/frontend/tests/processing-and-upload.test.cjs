const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function load(file, dependencies = {}, extra = '', globals = {}) {
  const module = { exports: {} };
  const source = fs.readFileSync(path.join(__dirname, '..', file), 'utf8') + extra;
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, esModuleInterop: true,
  } }).outputText, { module, exports: module.exports, require: name => dependencies[name] ?? {}, ...globals });
  return module.exports;
}
const processing = load('processing.ts');
const source = load('threeDSource.ts');

test('durations handle minute rollover and clocks that briefly lag behind the start', () => {
  assert.equal(processing.formatDuration(-500), '0 ms');
  assert.equal(processing.formatDuration(1250), '1.3 s');
  assert.equal(processing.formatDuration(119999), '2 min 0 s');
});

test('3D uploads reject unsupported, empty and oversized files before conversion', () => {
  for (const [size, type, name] of [[100, 'image/svg+xml', 'a.svg'], [0, 'image/png', 'a.png'], [source.MAX_THREED_IMAGE_BYTES + 1, 'image/jpeg', 'a.jpg']]) {
    assert.throws(() => source.validateThreeDImage(size, type, name));
  }
  for (const type of source.THREED_IMAGE_TYPES) assert.doesNotThrow(() => source.validateThreeDImage(100, type, 'image'));
  assert.doesNotThrow(() => source.validateThreeDImage(100, undefined, 'PHOTO.JPG'));
});

function studio({ cloud = true, canceled = false, invalid = false, modelLinkFailures = 0 } = {}) {
  let cursor = 0;
  const states = [];
  const calls = [];
  const react = {
    createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
    useState: initial => {
      const slot = cursor++;
      if (!(slot in states)) states[slot] = typeof initial === 'function' ? initial() : initial;
      return [states[slot], next => { states[slot] = typeof next === 'function' ? next(states[slot]) : next; }];
    },
    useMemo: fn => fn(), useEffect: () => {},
    useRef: value => react.useState(() => ({ current: value }))[0],
  };
  const native = new Proxy({
    Platform: { OS: 'web', select: value => value.web ?? value.default }, StyleSheet: { create: value => value },
    useWindowDimensions: () => ({ width: 1200 }),
    Image: { getSize: (_uri, ok) => ok(100, 100) },
  }, { get: (target, name) => target[name] ?? name });
  const dependencies = {
    react, 'react-native': native,
    './processing': processing, './threeDSource': source,
    './usePullToRefresh': () => 0,
    './theme': { useAppTheme: () => ({ colors: {} }), makeSharedStyles: () => ({}), layout: load('designTokens.ts').layout },
    './config': { THREED_AGENT_URL: 'https://test-3d', STUDIO_API_URL: cloud ? '/studio-api' : '' },
    './components/FeedbackControls': { createOutputId: kind => kind + '-fixture' },
    'expo-document-picker': { getDocumentAsync: async () => canceled ? { canceled: true } : {
      canceled: false, assets: [{ name: 'chosen.png', size: invalid ? 0 : 12, mimeType: 'image/png', base64: 'data:image/png;base64,UPLOADED', uri: 'fixture' }],
    } },
    './historyStorage': { saveHistoryItem: async item => calls.push(['save', item]), updateHistoryItem: async () => {} },
    './studioClient': {
      cloudEnabled: () => cloud,
      studioRequest: async (url, init) => { calls.push(['import', JSON.parse(init.body)]); return { id: 'uploaded-cloud-id' }; },
      runJob: async payload => { calls.push(['job', payload]); return { result: { history_id: 'uploaded-cloud-id' } }; },
      getCloudHistory: async () => ({ id: 'uploaded-cloud-id', glbBase64: 'MODEL' }),
      getCloudModel: async () => {
        calls.push(['model-link']);
        if (modelLinkFailures-- > 0) throw new Error('Saved model temporarily unavailable');
        return { id: 'uploaded-cloud-id', modelUrl: 'https://fixture/model.glb', modelKey: 'model-key' };
      },
    },
    './historyActivity': { markHistoryChanged: () => {} },
  };
  const { testHome } = load('App.tsx', dependencies, '\nexports.testHome = Home;', {
    setTimeout: fn => { fn(); return 1; },
    fetch: async (url, init) => {
      if (init) calls.push(['convert', JSON.parse(init.body)]);
      return { ok: true, status: 200, text: async () => JSON.stringify(init ? { call_id: 'call' } : { glb_base64: 'MODEL' }) };
    },
  });
  function render() { cursor = 0; return testHome({}); }
  function find(node, predicate) {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) { for (const child of node) { const found = find(child, predicate); if (found) return found; } return; }
    if (predicate(node)) return node;
    return find(node.props?.children, predicate);
  }
  const button = label => find(render(), node => node.props?.label === label)?.props;
  const resume = item => find(render(), node => node.props?.active !== undefined && typeof node.props?.onResume === 'function').props.onResume(item);
  const changePrompt = text => find(render(), node => node.props?.accessibilityLabel === 'Your prompt').props.onChangeText(text);
  return { button, calls, resume, changePrompt };
}

test('editing a resumed image creates its next generation inside the original chat', async () => {
  const app = studio();
  const original = { id: 'saved-image', chatId: 'original-chat', mode: 'general', prompt: 'First prompt', enhancedPrompt: 'First prompt', imageBase64: 'SAVED', speedMode: 'fast' };
  app.resume(original);
  app.changePrompt('A revised prompt');
  await app.button('Generate Image').onPress();
  const request = app.calls.find(call => call[0] === 'job')[1];
  assert.equal(request.chat_id, 'original-chat');
  assert.equal(request.prompt, 'A revised prompt');
  assert.equal(original.imageBase64, 'SAVED');
  assert.equal(original.prompt, 'First prompt');
});

test('device image can be converted without first generating an image and uses its own cloud source', async () => {
  const app = studio();
  assert.equal(app.button('Convert to 3D').disabled, true);
  await app.button('Upload image for 3D').onPress();
  assert.equal(app.button('Convert to 3D').disabled, false);
  await app.button('Convert to 3D').onPress();
  assert.equal(app.calls.find(call => call[0] === 'import')[1].image_base64, 'UPLOADED');
  assert.equal(app.calls.find(call => call[0] === 'job')[1].generation_id, 'uploaded-cloud-id');
  // Retrying the same selected image reuses its cloud creation.
  await app.button('Convert to 3D').onPress();
  assert.equal(app.calls.filter(call => call[0] === 'import').length, 1);
});

test('direct 3D conversion sends the chosen device image and saves a separate local creation', async () => {
  const app = studio({ cloud: false });
  await app.button('Upload image for 3D').onPress();
  await app.button('Convert to 3D').onPress();
  assert.equal(app.calls.find(call => call[0] === 'convert')[1].image_base64, 'UPLOADED');
  assert.equal(app.calls.find(call => call[0] === 'save')[1].imageBase64, 'UPLOADED');
});

test('a completed 3D job retries opening its saved model without paying for another generation', async () => {
  const app = studio({ modelLinkFailures: 1 });
  await app.button('Upload image for 3D').onPress();
  await app.button('Convert to 3D').onPress();
  assert.ok(app.button('Open saved model'));
  await app.button('Open saved model').onPress();
  assert.equal(app.calls.filter(call => call[0] === 'job').length, 1);
  assert.equal(app.calls.filter(call => call[0] === 'model-link').length, 2);
});

test('canceling the picker or selecting an invalid image leaves conversion disabled', async () => {
  for (const options of [{ canceled: true }, { invalid: true }]) {
    const app = studio(options);
    await app.button('Upload image for 3D').onPress();
    assert.equal(app.button('Convert to 3D').disabled, true);
    assert.equal(app.calls.length, 0);
  }
});
