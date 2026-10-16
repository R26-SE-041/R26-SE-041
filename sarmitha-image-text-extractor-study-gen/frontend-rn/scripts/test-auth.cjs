const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

const reply = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data });
const session = (id = 'user-a', expires = Date.now() / 1000 + 3600) => ({ access_token: 'access-' + id, refresh_token: 'refresh-' + id, expires_at: expires, user: { id, email: id + '@example.com', display_name: id } });
function setup(fetcher, stored, browser = {}) {
  const storage = new Map(stored ? [['sarmitha.auth.session.v1', JSON.stringify(stored)]] : []);
  const code = ts.transpileModule(fs.readFileSync(require.resolve('../lib/auth.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  const context = { module, exports: module.exports, fetch: fetcher, window: { localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) } }, require: name => name === 'react-native' ? { Platform: { OS: 'web' } } : { API_BASE_URL: 'https://api.example.com' } };
  Object.assign(context.window, browser);
  context.URLSearchParams = URLSearchParams;
  vm.runInNewContext(code, context);
  let state;
  module.exports.subscribeAuth(value => { state = value; });
  return { auth: module.exports, storage, state: () => state };
}

test('restored sessions are verified with the account service', async () => {
  const current = session();
  const app = setup(async url => url.endsWith('/config') ? reply({ enabled: true }) : reply(current.user), current);
  await app.auth.initializeAuth();
  assert.equal(app.state().user.id, 'user-a');
  assert.equal(app.state().loading, false);
});

test('a forged stored session is removed after verification fails', async () => {
  const app = setup(async url => url.endsWith('/config') ? reply({ enabled: true }) : reply({ detail: 'Please sign in again.' }, 401), session());
  await app.auth.initializeAuth();
  assert.equal(app.state().user, null);
  assert.equal(app.storage.size, 0);
});

test('concurrent requests rotate an expired refresh token only once', async () => {
  let count = 0;
  const app = setup(async url => {
    if (url.endsWith('/config')) return reply({ enabled: true });
    if (url.endsWith('/signin')) return reply({ session: session('user-a', 0) });
    if (url.endsWith('/refresh')) { count++; await new Promise(r => setTimeout(r, 10)); return reply({ session: session() }); }
    throw Error('Unexpected request');
  });
  await app.auth.initializeAuth();
  await app.auth.signIn('one@example.com', 'password');
  const tokens = await Promise.all([app.auth.getAccessToken(), app.auth.getAccessToken(), app.auth.getAccessToken()]);
  assert.equal(count, 1);
  assert.ok(tokens.every(value => value === 'access-user-a'));
});

test('signing out during refresh never restores the old account', async () => {
  let resolveRefresh;
  const app = setup(async url => {
    if (url.endsWith('/config')) return reply({ enabled: true });
    if (url.endsWith('/signin')) return reply({ session: session('user-a', 0) });
    if (url.endsWith('/refresh')) return await new Promise(resolve => { resolveRefresh = resolve; });
    if (url.endsWith('/signout')) return reply({ status: 'signed_out' });
    throw Error('Unexpected request');
  });
  await app.auth.initializeAuth(); await app.auth.signIn('one@example.com', 'password');
  const refresh = app.auth.getAccessToken();
  await app.auth.signOut();
  resolveRefresh(reply({ session: session() }));
  await assert.rejects(refresh, /account changed/);
  assert.equal(app.state().user, null);
  assert.equal(app.storage.size, 0);
});

test('a previous account request cannot adopt a different account token', async () => {
  let resolveRefresh;
  const app = setup(async (url, options) => {
    if (url.endsWith('/config')) return reply({ enabled: true });
    if (url.endsWith('/signin')) return reply({ session: JSON.parse(options.body).email === 'a@example.com' ? session('user-a', 0) : session('user-b') });
    if (url.endsWith('/refresh')) return await new Promise(resolve => { resolveRefresh = resolve; });
    throw Error('Unexpected request');
  });
  await app.auth.initializeAuth(); await app.auth.signIn('a@example.com', 'password');
  const oldRequest = app.auth.getAccessToken();
  await app.auth.signIn('b@example.com', 'password');
  resolveRefresh(reply({ session: session('user-a') }));
  await assert.rejects(oldRequest, /account changed/);
  assert.equal(app.state().user.id, 'user-b');
  await assert.rejects(app.auth.getAccessToken('user-a'), /account changed/);
});

test('an old unauthorized response cannot clear a newer account session', async () => {
  const app = setup(async url => url.endsWith('/config') ? reply({ enabled: true }) : reply({ session: session('user-b') }));
  await app.auth.initializeAuth(); await app.auth.signIn('b@example.com', 'password');
  app.auth.invalidateAccessToken('access-user-a');
  assert.equal(app.state().user.id, 'user-b');
  app.auth.clearCrossTabSession({ key: 'sarmitha.auth.session.v1', newValue: null });
  assert.equal(app.state().user, null);
});
test('email confirmation strips URL credentials before verifying and accepting the session', async () => {
  let stripped = false;
  const app = setup(async (url, options) => {
    if (url.endsWith('/config')) return reply({ enabled: true });
    assert.equal(stripped, true);
    assert.equal(options.headers.Authorization, 'Bearer email-access');
    return reply(session().user);
  }, null, { location: { hash: '#access_token=email-access&refresh_token=email-refresh&expires_in=3600', pathname: '/', search: '' }, history: { replaceState: (_state, _title, url) => { assert.equal(url, '/'); stripped = true; } } });
  await app.auth.initializeAuth();
  assert.equal(app.state().user.id, 'user-a');
  assert.equal(await app.auth.getAccessToken(), 'email-access');
});

test('an invalid email confirmation token is removed from the URL and never stored', async () => {
  let stripped = false;
  const app = setup(async url => url.endsWith('/config') ? reply({ enabled: true }) : reply({ detail: 'Invalid session' }, 401), null,
    { location: { hash: '#access_token=forged&refresh_token=forged', pathname: '/', search: '' }, history: { replaceState: () => { stripped = true; } } });
  await app.auth.initializeAuth();
  assert.equal(stripped, true);
  assert.equal(app.state().user, null);
  assert.equal(app.storage.size, 0);
});

test('logout during initial session verification cannot restore the old account', async () => {
  let resolveMe;
  const app = setup(async url => {
    if (url.endsWith('/config')) return reply({ enabled: true });
    if (url.endsWith('/me')) return new Promise(resolve => { resolveMe = resolve; });
    if (url.endsWith('/signout')) return reply({ status: 'signed_out' });
  }, session());
  const initializing = app.auth.initializeAuth();
  while (!resolveMe) await new Promise(r => setImmediate(r));
  await app.auth.signOut();
  resolveMe(reply(session().user));
  await initializing;
  assert.equal(app.state().user, null);
  assert.equal(app.storage.size, 0);
});
