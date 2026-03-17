/**
 * UI Integration test — connects to Chrome Canary via CDP (remote debugging).
 *
 * Pre-requisites:
 *   - Chrome Canary launched on host with --remote-debugging-port=9222
 *   - App server running on localhost:3000
 *
 * Run with:  node test/ui.integration.js
 */

const CDP = require('chrome-remote-interface');
const { spawn } = require('child_process');
const http = require('http');

const CDP_HOST   = process.env.CDP_HOST   || 'host.docker.internal';
const CDP_PORT   = parseInt(process.env.CDP_PORT || '9222', 10);
const APP_URL    = process.env.APP_URL    || 'http://localhost:3000';
const SERVER_PORT = parseInt(new URL(APP_URL).port || '3000', 10);

// ── Server lifecycle ──────────────────────────────────────────────────────────
async function isServerUp(url, timeout = 5000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(url + '/health', res => resolve(res));
        req.on('error', reject);
        req.setTimeout(500, () => { req.destroy(); reject(new Error('timeout')); });
      });
      return true;
    } catch { /* retry */ }
    await new Promise(r => setTimeout(r, 200));
  }
  return false;
}

let serverProc = null;

async function ensureServer() {
  if (await isServerUp(APP_URL)) {
    console.log('  App server already running.');
    return;
  }
  console.log('  Starting app server...');
  serverProc = spawn('node', ['src/index.js'], {
    cwd: process.env.SERVER_CWD || require('path').resolve(__dirname, '..'),
    env: { ...process.env, PORT: String(SERVER_PORT), NODE_ENV: 'test' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  serverProc.stdout.on('data', d => process.stdout.write('  [server] ' + d));
  serverProc.stderr.on('data', d => process.stderr.write('  [server] ' + d));
  const up = await isServerUp(APP_URL, 10000);
  if (!up) throw new Error('App server did not start within 10s');
  console.log('  App server ready.');
}

function stopServer() {
  if (serverProc) { serverProc.kill(); serverProc = null; }
}

let passed = 0, failed = 0;
function pass(msg)  { console.log(`  ✓ ${msg}`); passed++; }
function fail(msg)  { console.error(`  ✗ ${msg}`); failed++; }
function assert(cond, msg) { cond ? pass(msg) : fail(msg); }

async function evaluateJSON(client, expression) {
  const { result } = await client.Runtime.evaluate({
    expression: `(async () => JSON.stringify(await (${expression})))()`,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.type === 'undefined' || result.value == null) return undefined;
  return JSON.parse(result.value);
}

(async () => {
  console.log(`\nUI Integration Tests`);
  try { await ensureServer(); } catch(e) { fail('Server startup: ' + e.message); process.exit(1); }
  console.log(`Connecting to Chrome at ${CDP_HOST}:${CDP_PORT}...`);

  let targets;
  try {
    targets = await CDP.List({ host: CDP_HOST, port: CDP_PORT });
  } catch (e) {
    fail(`Cannot reach Chrome CDP — ${e.message}`);
    process.exit(1);
  }

  let target = targets.find(t => t.type === 'page' && t.url.startsWith(APP_URL));
  if (!target) {
    console.log(`  No tab at ${APP_URL}, opening one...`);
    target = await CDP.New({ host: CDP_HOST, port: CDP_PORT, url: APP_URL });
  }
  console.log(`  Using tab: ${target.title} (${target.url})`);

  const client = await CDP({ host: CDP_HOST, port: CDP_PORT, target: target.id });
  const { Page, Runtime, Network } = client;
  await Promise.all([Network.enable(), Runtime.enable(), Page.enable()]);

  console.log(`  Loading ${APP_URL}...`);
  await Page.navigate({ url: APP_URL });
  // Wait for DOMContentLoaded only — avoids blocking on slow external GSI script
  await Page.domContentEventFired();
  // Poll until the page's own initConfig() has finished fetching /config (max 5s)
  await new Promise(async (resolve) => {
    const deadline = Date.now() + 5000;
    while (Date.now() < deadline) {
      const { result } = await Runtime.evaluate({ expression: 'typeof window._configLoaded !== "undefined"', returnByValue: true });
      if (result.value) break;
      await new Promise(r => setTimeout(r, 200));
    }
    resolve();
  });

  // ── Test 1: /config ───────────────────────────────────────────────────────
  console.log('\n  /config endpoint');
  const config = await evaluateJSON(client,
    `(async () => { const r = await fetch('/config'); return r.json(); })()`);
  console.log('    response:', config);
  assert('googleClientId' in config, '/config returns googleClientId field');
  const hasSso = !!config.googleClientId;
  console.log(`    SSO: ${hasSso ? `REAL (${config.googleClientId})` : 'DEV (no client id set)'}`);

  // ── Test 2: initial UI state ──────────────────────────────────────────────
  console.log('\n  Initial UI state');
  const init = await evaluateJSON(client, `({
    signedOutText:     document.getElementById('signed-out')?.innerText,
    uploaderDisplay:   document.getElementById('uploader')?.style.display,
    downloaderDisplay: document.getElementById('downloader')?.style.display,
    gsiScriptLoaded:   !!document.querySelector('script[src*="accounts.google.com/gsi/client"]'),
    gsiButtonRendered: !!document.querySelector('#google-signin iframe'),
    idToken:           !!window.idToken,
    dummyUser:         window.dummyUser || null,
  })`);
  console.log('    state:', init);
  assert(init.signedOutText !== undefined, 'signed-out element present');
  assert(init.uploaderDisplay === 'none', 'uploader hidden before login');
  if (hasSso) {
    assert(init.gsiScriptLoaded,   'GSI script loaded');
    assert(init.gsiButtonRendered, 'Google sign-in button rendered');
  }

  // ── Test 3: dev sign-in ───────────────────────────────────────────────────
  console.log('\n  Dev sign-in (fake-login button)');
  await Runtime.evaluate({ expression: `document.getElementById('fake-login').click()` });
  await new Promise(r => setTimeout(r, 300));
  const afterLogin = await evaluateJSON(client, `({
    signedOutText:   document.getElementById('signed-out')?.innerText,
    uploaderDisplay: document.getElementById('uploader')?.style.display,
    dummyUser:       window.dummyUser,
  })`);
  console.log('    state:', afterLogin);
  assert(afterLogin.signedOutText?.includes('tester@example.com'), 'status shows tester@example.com');
  assert(afterLogin.uploaderDisplay !== 'none', 'uploader visible after dev login');
  assert(afterLogin.dummyUser === 'tester@example.com', 'dummyUser set');

  // ── Test 4: POST /uploads ─────────────────────────────────────────────────
  console.log('\n  POST /uploads');
  const uploadRes = await evaluateJSON(client, `
    (async () => {
      const h = { 'Content-Type': 'application/json' };
      if (window.dummyUser) h['x-dummy-user'] = window.dummyUser;
      if (window.idToken)   h['Authorization'] = 'Bearer ' + window.idToken;
      const r = await fetch('/uploads', { method:'POST', headers:h,
        body: JSON.stringify({ tenantId:'team-a', filename:'test.pdf' }) });
      return { status: r.status, body: await r.json() };
    })()`);
  console.log('    response:', uploadRes);
  assert(uploadRes.status === 200,     'POST /uploads → 200');
  assert(!!uploadRes.body.id,          'response has id');
  assert(!!uploadRes.body.uploadUrl,   'response has uploadUrl');
  assert(uploadRes.body.expiresIn > 0, 'response has expiresIn');

  // ── Test 5: GET /files/:id/download ──────────────────────────────────────
  console.log('\n  GET /files/:id/download');
  const dlRes = await evaluateJSON(client, `
    (async () => {
      const h = {};
      if (window.dummyUser) h['x-dummy-user'] = window.dummyUser;
      if (window.idToken)   h['Authorization'] = 'Bearer ' + window.idToken;
      const r = await fetch('/files/abc123/download', { headers: h });
      return { status: r.status, body: await r.json() };
    })()`);
  console.log('    response:', dlRes);
  assert(dlRes.status === 200,      'GET /files/:id/download → 200');
  assert(!!dlRes.body.downloadUrl,  'response has downloadUrl');
  assert(dlRes.body.expiresIn > 0,  'response has expiresIn');

  await client.close();
  stopServer();
  console.log(`\n${failed === 0 ? '✅' : '❌'} ${passed} passed, ${failed} failed\n`);
  process.exit(failed > 0 ? 1 : 0);
})();
