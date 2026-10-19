const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function canvas({ platform = 'web', disabled = false, previewOnly = false } = {}) {
  const commits = [];
  const captures = new Set();
  const react = {
    createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
    useRef: current => ({ current }), useState: initial => [initial, () => {}],
  };
  const dependencies = {
    react,
    'react-native': { Platform: { OS: platform }, View: 'View', Text: 'Text', Pressable: 'Pressable' },
    'react-native-svg': { default: 'Svg', Circle: 'Circle', Polyline: 'Polyline', Rect: 'Rect' },
    '../theme': { useAppTheme: () => ({ colors: {} }) },
  };
  const module = { exports: {} };
  const source = fs.readFileSync(path.join(__dirname, '../components/SketchCanvas.tsx'), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, esModuleInterop: true,
  } }).outputText, { module, exports: module.exports, require: name => dependencies[name] || {} });
  const tree = module.exports.default({ strokes: [], onChange: strokes => commits.push(strokes), disabled, previewOnly });
  const surface = tree.props.children.find(child => child?.props?.accessibilityLabel === 'Drawing canvas').props;
  surface.onLayout({ nativeEvent: { layout: { width: 400 } } });
  const target = {
    getBoundingClientRect: () => ({ left: 10, top: 20, width: 400, height: 400 }),
    setPointerCapture: id => captures.add(id),
    hasPointerCapture: id => captures.has(id),
    releasePointerCapture: id => captures.delete(id),
  };
  const pointer = (x, y, pointerType = 'touch', pointerId = 1) => ({
    clientX: x + 10, clientY: y + 20, pointerType, pointerId, button: 0, currentTarget: target, preventDefault() {},
  });
  return { surface, commits, captures, pointer };
}

for (const type of ['touch', 'mouse', 'pen']) {
  test(`${type}: a quick short stroke keeps its release endpoint without a move event`, () => {
    const { surface, commits, captures, pointer } = canvas();
    surface.onPointerDown(pointer(100, 100, type));
    assert.equal(captures.has(1), true);
    surface.onPointerUp(pointer(100.5, 100, type));
    assert.equal(commits.length, 1);
    assert.equal(commits[0][0].points.length, 2);
    assert.equal(commits[0][0].points[1][0], 100.5 / 400);
    assert.equal(captures.size, 0);
    surface.onPointerUp(pointer(100.5, 100, type));
    assert.equal(commits.length, 1);
  });

  test(`${type}: a tap saves a visible single-point dot`, () => {
    const { surface, commits, pointer } = canvas();
    surface.onPointerDown(pointer(80, 90, type));
    surface.onPointerUp(pointer(80, 90, type));
    assert.equal(commits[0][0].points.length, 1);
    assert.equal(commits[0][0].tool, 'pen');
  });
}

test('hover never draws, and a second touch cannot extend or finish the active stroke', () => {
  const { surface, commits, pointer } = canvas();
  surface.onPointerMove(pointer(50, 50, 'mouse'));
  assert.equal(commits.length, 0);
  surface.onPointerDown(pointer(100, 100));
  surface.onPointerDown(pointer(200, 200, 'touch', 2));
  surface.onPointerMove(pointer(210, 210, 'touch', 2));
  surface.onPointerUp(pointer(210, 210, 'touch', 2));
  assert.equal(commits.length, 0);
  surface.onPointerUp(pointer(101, 100));
  assert.equal(commits.length, 1);
  assert.equal(commits[0][0].points.length, 2);
});

test('cancellation commits the existing stroke once without adding a spurious endpoint', () => {
  const { surface, commits, pointer } = canvas();
  surface.onPointerDown(pointer(10, 10));
  surface.onPointerMove(pointer(11, 10));
  surface.onPointerCancel(pointer(0, 0));
  surface.onPointerCancel(pointer(0, 0));
  assert.equal(commits.length, 1);
  assert.equal(commits[0][0].points.length, 2);
  assert.equal(commits[0][0].points[1][0], 11 / 400);
});

test('disabled and preview canvases do not accept pointer strokes', () => {
  for (const options of [{ disabled: true }, { previewOnly: true }]) {
    const { surface, commits, captures, pointer } = canvas(options);
    surface.onPointerDown(pointer(10, 10));
    surface.onPointerUp(pointer(11, 10));
    assert.equal(commits.length, 0);
    assert.equal(captures.size, 0);
  }
});

test('native touch keeps a short release endpoint as well', () => {
  const { surface, commits } = canvas({ platform: 'ios' });
  surface.onResponderGrant({ nativeEvent: { locationX: 100, locationY: 100 } });
  surface.onResponderRelease({ nativeEvent: { locationX: 100.5, locationY: 100 } });
  assert.equal(commits[0][0].points.length, 2);
  assert.equal(commits[0][0].points[1][0], 100.5 / 400);
});
