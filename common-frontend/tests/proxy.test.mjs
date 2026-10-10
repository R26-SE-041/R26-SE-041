import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { createProxy } from '../scripts/proxy.mjs';
async function listen(server) { await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); return `http://127.0.0.1:${server.address().port}`; }

test('sketch jobs route separately and preserve optional instruction and pending results', async t => {
  const seen = [];
  const upstream = http.createServer((req, res) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      seen.push({ url: req.url, body });
      res.writeHead(req.method === 'POST' ? 200 : 202, { 'Content-Type': 'application/json' });
      res.end(req.method === 'POST' ? '{"call_id":"fc-test"}' : '{"status":"generating"}');
    });
  });
  const target = await listen(upstream), proxy = createProxy({ sketch: target }), url = await listen(proxy);
  t.after(() => { proxy.close(); upstream.close(); });
  const payload = { strokes: [{ points: [[0.2, 0.5], [0.8, 0.5]], width: 0.006, tool: 'pen' }], instruction: '' };
  const start = await fetch(url + '/sketch/generate/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  assert.deepEqual(await start.json(), { call_id: 'fc-test' });
  assert.deepEqual(JSON.parse(seen[0].body), payload);
  const result = await fetch(url + '/sketch/generate/result/fc-test');
  assert.equal(result.status, 202);
  assert.equal(seen[1].url, '/generate/result/fc-test');
});
test('forwards paths, query, bearer and multipart body without changing existing APIs', async t => {
  let captured;
  const upstream = http.createServer((req, res) => { let body = ''; req.on('data', chunk => body += chunk); req.on('end', () => { captured = { url: req.url, auth: req.headers.authorization, cookie: req.headers.cookie, body, type: req.headers['content-type'] }; res.setHeader('Content-Type', 'application/json'); res.end('{"status":"ok"}'); }); });
  const target = await listen(upstream), proxy = createProxy({ quiz: target }); const url = await listen(proxy);
  t.after(() => { proxy.close(); upstream.close(); });
  const form = new FormData(); form.append('file', new Blob(['biology']), 'notes.txt');
  const response = await fetch(url + '/quiz/api/v1/documents/upload?lang=ta', { method: 'POST', body: form, headers: { Origin: 'http://localhost:8085', Authorization: 'Bearer test-token', Cookie: 'original=private' } });
  assert.equal(response.status, 200); assert.equal(response.headers.get('access-control-allow-origin'), 'http://localhost:8085');
  assert.equal(captured.url, '/api/v1/documents/upload?lang=ta'); assert.equal(captured.auth, 'Bearer test-token'); assert.equal(captured.cookie, undefined); assert.match(captured.body, /biology/); assert.match(captured.type, /multipart\/form-data/);
});
test('rejects other web origins and arbitrary targets; supports preflight', async t => {
  const proxy = createProxy({}); const url = await listen(proxy); t.after(() => proxy.close());
  assert.equal((await fetch(url + '/quiz/health', { headers: { Origin: 'https://untrusted.example' } })).status, 403);
  assert.equal((await fetch(url + '/https://example.com/')).status, 503);
  assert.equal((await fetch(url + '/quiz/health')).status, 503);
  assert.equal((await fetch(url + '/quiz/health', { method: 'OPTIONS', headers: { Origin: 'http://localhost:8085' } })).status, 204);
});
test('audio PUT uploads and DELETE 204 preserve existing backend methods', async t => {
  const seen=[];
  const upstream=http.createServer((req,res)=>{seen.push({method:req.method,url:req.url});req.resume();res.writeHead(req.method==='DELETE'?204:200,{'Content-Type':'application/json'}).end(req.method==='DELETE'?undefined:'{"has_audio":true}');});
  const target=await listen(upstream),proxy=createProxy({audio:target}),url=await listen(proxy);t.after(()=>{proxy.close();upstream.close();});
  const form=new FormData();form.append('audio_file',new Blob(['wav']),'answer.wav');
  assert.equal((await fetch(url+'/audio/api/v1/history/id/audio',{method:'PUT',body:form})).status,200);
  assert.equal((await fetch(url+'/audio/api/v1/documents/id',{method:'DELETE'})).status,204);
  assert.deepEqual(seen,[{method:'PUT',url:'/api/v1/history/id/audio'},{method:'DELETE',url:'/api/v1/documents/id'}]);
});
