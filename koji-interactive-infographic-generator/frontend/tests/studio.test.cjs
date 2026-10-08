const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function loadModule(file, globals = {}, cache = new Map()) {
  const resolved = path.resolve(__dirname, '..', file);
  if (cache.has(resolved)) return cache.get(resolved);
  const source = fs.readFileSync(resolved, 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  cache.set(resolved, module.exports);
  const context = {
    module, exports: module.exports, process, console, setTimeout, clearTimeout, crypto: global.crypto,
    atob, ...globals,
    require: name => name.startsWith('.') ?
      loadModule(path.relative(path.resolve(__dirname, '..'), path.resolve(path.dirname(resolved), name + '.ts')), globals, cache) : require(name),
  };
  vm.runInNewContext(code, context, { filename: resolved });
  return module.exports;
}
const annotation = {
  structure_id: 'manual.one', label: 'Heart', anchor_x: .5, anchor_y: .5,
  label_x: .05, label_y: .2, verified: false, user_edited: true, confidence: 0,
};

test('SVG export contains edited names and arrowhead at the selected target', () => {
  const exporter = loadModule('components/anatomyExport.ts');
  const svg = exporter.buildLabeledSvg('image', [{ ...annotation, label: 'Left ventricle', anchor_x: .65 }]);
  assert.match(svg, /Left ventricle/);
  assert.match(svg, /<polygon points="650,500 /);
  assert.match(svg, /x1="650"/);
});

test('edited label text is escaped in exported SVG', () => {
  const exporter = loadModule('components/anatomyExport.ts');
  const svg = exporter.buildLabeledSvg('image', [{ ...annotation, label: '<script>&"test"' }]);
  assert.ok(!svg.includes('<script>'));
  assert.ok(svg.includes('&lt;script&gt;&amp;&quot;test&quot;'));
});

test('moving a label beyond image boundaries keeps the complete box inside the export', () => {
  const geometry = loadModule('components/annotationGeometry.ts');
  const box = geometry.annotationGeometry({ ...annotation, label_x: 1, label_y: 1 });
  assert.ok(box.x + box.width <= 1000);
  assert.ok(box.y + geometry.LABEL_HEIGHT / 2 <= 1000);
});

test('cloud requests carry a bearer token and return the completed durable job', async () => {
  const previous = process.env.EXPO_PUBLIC_STUDIO_API_URL;
  process.env.EXPO_PUBLIC_STUDIO_API_URL = 'https://studio.example';
  const calls = [];
  try {
    const client = loadModule('studioClient.ts', {
      fetch: async (url, init = {}) => {
        calls.push({ url, init });
        return {
          ok: true, json: async () => url.endsWith('/studio/jobs') ?
            { id: 'job-one', status: 'queued' } :
            { id: 'job-one', status: 'completed', stage: 'completed', result: { history_id: 'image-one' } },
        };
      },
    });
    const token = 'header.' + Buffer.from(JSON.stringify({ sub: 'user-one' })).toString('base64url') + '.signature';
    client.configureStudio(token);
    const result = await client.runJob({ kind: 'generate', prompt: 'heart' });
    assert.equal(result.result.history_id, 'image-one');
    assert.equal(calls[0].init.headers.Authorization, 'Bearer ' + token);
    assert.equal(calls[1].url, 'https://studio.example/studio/jobs/job-one');
    assert.equal(JSON.parse(calls[0].init.body).kind, 'generate');
    assert.match(JSON.parse(calls[0].init.body).request_id, /^[0-9a-f-]{36}$/i);
  } finally {
    if (previous === undefined) delete process.env.EXPO_PUBLIC_STUDIO_API_URL;
    else process.env.EXPO_PUBLIC_STUDIO_API_URL = previous;
  }
});

test('a failed durable job surfaces its error instead of polling forever', async () => {
  const previous = process.env.EXPO_PUBLIC_STUDIO_API_URL;
  process.env.EXPO_PUBLIC_STUDIO_API_URL = 'https://studio.example';
  try {
    const client = loadModule('studioClient.ts', {
      fetch: async () => ({ ok: true, json: async () => ({ status: 'failed', stage: 'failed', error: 'Sketch service unavailable' }) }),
    });
    await assert.rejects(client.waitJob('failed'), /Sketch service unavailable/);
  } finally {
    if (previous === undefined) delete process.env.EXPO_PUBLIC_STUDIO_API_URL;
    else process.env.EXPO_PUBLIC_STUDIO_API_URL = previous;
  }
});

test('network failures provide an actionable cloud connection error',async()=>{
 const client=loadModule('studioClient.ts',{fetch:async()=>{throw new TypeError('Failed to fetch');}});
 await assert.rejects(client.studioRequest('/studio/jobs'),/cloud workspace.*retry/);
});
test('hosted web requests use the configured same-origin route and keep bearer auth',async()=>{
 const previous={...process.env};const calls=[];
 try{
  process.env.NODE_ENV='production';process.env.EXPO_PUBLIC_STUDIO_API_URL='https://api.example';process.env.EXPO_PUBLIC_STUDIO_PROXY_PATH='/studio-api';
  const client=loadModule('studioClient.ts',{window:{},fetch:async(url,init)=>{calls.push({url,init});return{ok:true,json:async()=>[]};}});
  client.configureStudio('session-token');await client.studioRequest('/studio/jobs');
  assert.equal(calls[0].url,'/studio-api/studio/jobs');assert.equal(calls[0].init.headers.Authorization,'Bearer session-token');
 }finally{for(const key of ['NODE_ENV','EXPO_PUBLIC_STUDIO_API_URL','EXPO_PUBLIC_STUDIO_PROXY_PATH']){if(previous[key]===undefined)delete process.env[key];else process.env[key]=previous[key];}}
});
