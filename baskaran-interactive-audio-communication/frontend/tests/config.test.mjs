import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'

function config(host, api) {
  const script = `globalThis.window={location:{hostname:${JSON.stringify(host)}}};
    const m=await import('./src/lib/config.ts');
    let error=null;try{m.requireBackend()}catch(e){error=e.message}
    console.log(JSON.stringify({url:m.API_URL,ready:m.BACKEND_CONFIGURED,error,authRequired:m.AUTH_REQUIRED}));`
  const env = { ...process.env }
  delete env.EXPO_PUBLIC_API_URL
  if (api !== undefined) env.EXPO_PUBLIC_API_URL = api
  const result = spawnSync(process.execPath, ['--input-type=module', '-e', script], { cwd: new URL('..', import.meta.url), env, encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  return JSON.parse(result.stdout)
}

test('local development still uses the existing localhost backend', () => {
  assert.deepEqual(config('localhost'), {url:'http://localhost:8000',ready:true,error:null,authRequired:false})
})
test('public frontend without backend blocks API calls instead of reading SPA HTML', () => {
  const result = config('voicelearn-audio.vercel.app')
  assert.equal(result.url, '')
  assert.equal(result.ready, false)
  assert.match(result.error, /Backend connection is pending/)
})
test('configured HTTPS backend enables hosted API calls and strips trailing slash', () => {
  assert.deepEqual(config('voicelearn-audio.vercel.app','https://api.example.com/'), {url:'https://api.example.com',ready:true,error:null,authRequired:true})
})

test('localhost connected to a public cloud backend requires account authentication', () => {
  assert.equal(config('localhost','https://api.example.com').authRequired,true)
})
