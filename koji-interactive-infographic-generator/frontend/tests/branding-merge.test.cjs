const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function load(file, dependencies = {}) {
  const module = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, esModuleInterop: true },
  }).outputText;
  vm.runInNewContext(code, { module, exports: module.exports, require: name => dependencies[name] ?? {} });
  return module.exports;
}
const element = (type, props, ...children) => ({ type, props: { ...props, children } });
const react = { createElement: element };

test('studio uses the dashboard wordmark while linking to the shared toolkit home', () => {
  const Brand = load('components/StudioBrand.tsx', {
    react, 'react-native': { Text: 'Text', View: 'View' }, './LearnXHomeLink': 'HomeLink',
    '../theme': { displayFont: 'Studio Display', useAppTheme: () => ({ colors: { text: '#141413' } }) },
  }).default;
  const full = Brand({});
  assert.equal(full.props.children[0].type, 'HomeLink');
  assert.equal(full.props.children[1].props.children[0], 'Visual learning studio');
  assert.equal(Brand({ compact: true }).props.children[1], false);
  const Link = load('components/LearnXHomeLink.web.tsx', { react }).default;
  const link = Link(full.props.children[0].props);
  assert.equal(link.props.href, 'https://biolearnx-dashboard.vercel.app/');
  assert.equal(link.props.draggable, false);
  assert.equal(link.props.style.userSelect, 'none');
  assert.equal(link.props.style.fontFamily, 'Arial, Helvetica, sans-serif');
  assert.equal(link.props.style.fontWeight, 800);
  assert.equal(link.props.children[0], 'LEARN');
  assert.equal(link.props.children[1].props.className, 'lx-toolkit-x');
});

test('merged theme retains toolkit navigation and the studio layout tokens together', () => {
  const tokens = load('designTokens.ts');
  const theme = load('theme.ts', {
    react: { ...react, createContext: () => ({ Provider: 'Provider' }), useEffect() {},
      useMemo: fn => fn(), useState: initial => [typeof initial === 'function' ? initial() : initial, () => {}] },
    'react-native': { Platform: { OS: 'web', select: value => value.web ?? value.default }, StyleSheet: { create: value => value } },
    './designTokens': tokens, './components/ToolkitNavigation': 'ToolkitNavigation', './components/WebInteractionStyles': 'WebInteractionStyles',
  });
  const tree = theme.ThemeProvider({ children: 'Studio content' });
  assert.equal(tree.props.children[0].type, 'WebInteractionStyles');
  assert.equal(tree.props.children[1].type, 'ToolkitNavigation');
  assert.equal(tree.props.children[1].props.componentName, 'Visual Studio');
  assert.equal(tree.props.children[2], 'Studio content');
  assert.equal(theme.layout, tokens.layout);
});
