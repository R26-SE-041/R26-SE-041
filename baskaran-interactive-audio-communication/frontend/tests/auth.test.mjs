import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'

function auth(host) {
  const script = `globalThis.window={location:{hostname:${JSON.stringify(host)}}};
    const m=await import('./src/lib/supabase.ts');
    const c=m.createClient();
    const login=await c.auth.signInWithPassword({email:'demo@example.com',password:'test'});
    const signup=await c.auth.signUp({email:'demo@example.com',password:'test'});
    const session=await c.auth.getSession();
    console.log(JSON.stringify({loginError:login.error,signupError:signup.error,session:session.data.session}));`
  const env = {...process.env}
  delete env.EXPO_PUBLIC_SUPABASE_URL
  delete env.EXPO_PUBLIC_SUPABASE_ANON_KEY
  const result = spawnSync(process.execPath, ['--input-type=module','-e',script], {
    cwd: new URL('..',import.meta.url), env, encoding:'utf8',
  })
  assert.equal(result.status,0,result.stderr)
  return JSON.parse(result.stdout)
}
test('local demo remains available without Supabase configuration', () => {
  assert.deepEqual(auth('localhost'),{loginError:null,signupError:null,session:null})
})
test('public unconfigured builds never report a successful login or signup', () => {
  const result=auth('voicelearn-audio.vercel.app')
  assert.match(result.loginError.message,/Login setup is pending/)
  assert.match(result.signupError.message,/Login setup is pending/)
  assert.equal(result.session,null)
})
