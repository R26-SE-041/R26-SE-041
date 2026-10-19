const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

test('coordinate surface preserves image ratio and normalized targets at every viewport', () => {
  const module = { exports: {} };
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../components/imageSurfaceSize.ts'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText, { module, exports: module.exports });
  const { imageSurfaceSize } = module.exports;
  for (const viewport of [320, 650, 978, 1304]) {
    for (const ratio of [0.5, 1, 2]) {
      const { width, height } = imageSurfaceSize(viewport, ratio);
      assert.equal(width / height, ratio);
      assert.ok(width <= viewport && height <= 720);
      // Contain rendering fills these bounds exactly, so there is no offset
      // between a saved target, its SVG anchor and its tap/edit coordinates.
      const scale = Math.min(width / (512 * ratio), height / 512);
      assert.ok(Math.abs((width - 512 * ratio * scale) / 2) < 1e-9);
      assert.ok(Math.abs((height - 512 * scale) / 2) < 1e-9);
      const target = { x: 0.25, y: 0.6 };
      assert.equal((target.x * width) / width, target.x);
      assert.equal((target.y * height) / height, target.y);
    }
  }
  assert.equal(imageSurfaceSize(1304, 1).width, 720);
});

test('source dimensions stay aligned across portrait, landscape and stale loads', () => {
  let state, effect, previousUri, cleanup;
  const pending = [];
  const module = { exports: {} };
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../components/useImageAspectRatio.ts'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText, { module, exports: module.exports, require: name => name === 'react' ? {
    useState: initial => [state ??= initial, value => { state = value; }],
    useEffect: (callback, [uri]) => {
      if (uri !== previousUri) { cleanup?.(); previousUri = uri; effect = callback; }
    },
  } : { Image: { getSize: (uri, success) => pending.push({ uri, success }) } } });
  const render = uri => { const ratio = module.exports.default(uri); if (effect) { cleanup = effect(); effect = null; } return ratio; };
  assert.equal(render('portrait'), 1);
  pending[0].success(600, 1200);
  assert.equal(render('portrait'), 0.5);
  assert.equal(render('landscape'), 1);
  pending[0].success(900, 900);
  pending[1].success(1200, 600);
  assert.equal(render('landscape'), 2);
  cleanup();
  pending[1].success(400, 800);
  assert.equal(render('landscape'), 2);
});
