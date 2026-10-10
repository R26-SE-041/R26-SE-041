import http from 'node:http';
import https from 'node:https';
import { pathToFileURL } from 'node:url';

export function createProxy(targets, allowedOrigin = 'http://localhost:8085') {
  return http.createServer((req, res) => {
    if (req.headers.origin && req.headers.origin !== allowedOrigin) { res.writeHead(403).end(); return; }
    res.setHeader('Access-Control-Allow-Origin', allowedOrigin);
    res.setHeader('Vary', 'Origin');
    res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    if (req.method === 'OPTIONS') { res.writeHead(204).end(); return; }
    if (!['GET', 'POST', 'PUT', 'DELETE'].includes(req.method)) { res.writeHead(405).end(); return; }
    const match = /^\/(visual|quiz|notes|audio|prompt|image|sketch|interactive|evaluation|threed)(\/.*)$/.exec(req.url || '');
    const target = match && targets[match[1]];
    if (!target) { res.writeHead(503, { 'Content-Type': 'application/json' }).end(JSON.stringify({ detail: 'Backend URL is not configured in common-frontend/.env.local.' })); return; }
    let upstream;
    try { upstream = new URL(target); } catch { res.writeHead(503).end(); return; }
    if (!['http:', 'https:'].includes(upstream.protocol)) { res.writeHead(503).end(); return; }
    // Preserve the configured host. Never resolve user paths as absolute URLs.
    upstream.pathname = upstream.pathname.replace(/\/$/, '') + match[2].split('?')[0];
    upstream.search = match[2].includes('?') ? match[2].slice(match[2].indexOf('?')) : '';
    const headers = { ...req.headers, host: upstream.host };
    delete headers.origin; delete headers.connection; delete headers.cookie;
    const out = (upstream.protocol === 'https:' ? https : http).request(upstream, { method: req.method, headers }, incoming => {
      const responseHeaders = { ...incoming.headers };
      for (const name of Object.keys(responseHeaders)) if (name.startsWith('access-control-') || ['set-cookie', 'connection'].includes(name)) delete responseHeaders[name];
      res.writeHead(incoming.statusCode || 502, responseHeaders);
      incoming.pipe(res);
    });
    out.setTimeout(300000, () => out.destroy(new Error('Upstream timed out')));
    out.on('error', () => { if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json' }).end(JSON.stringify({ detail: 'Backend is unreachable. Check the configured URL and start the service.' })); else res.destroy(); });
    req.on('aborted', () => out.destroy());
    res.on('close', () => { if (!res.writableEnded) out.destroy(); });
    req.pipe(out);
  });
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  createProxy({ visual: process.env.VISUAL_API_URL, quiz: process.env.QUIZ_API_URL, notes: process.env.NOTES_API_URL, audio: process.env.AUDIO_API_URL,
    prompt: process.env.PROMPT_API_URL, image: process.env.IMAGE_API_URL, sketch: process.env.SKETCH_API_URL, interactive: process.env.INTERACTIVE_API_URL, evaluation: process.env.EVALUATION_API_URL, threed: process.env.THREED_API_URL,
  }, process.env.WEB_ORIGIN || 'http://localhost:8085')
    .listen(8787, '127.0.0.1', () => console.log('BioLearnX local development proxy: http://localhost:8787'));
}
