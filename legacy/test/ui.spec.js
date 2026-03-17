const { test, expect } = require('./fixtures');
const { APP_URL, ensureServer, stopServer } = require('./helpers/server');

test.beforeAll(async () => {
  await ensureServer();
});

test.afterAll(() => {
  stopServer();
});

test('UI integration flows', async ({ page }) => {
  await page.goto(APP_URL);
  await page.waitForLoadState('domcontentloaded');
  await page.waitForFunction(() => typeof window._configLoaded !== 'undefined', null, { timeout: 5000 }).catch(() => {});

  const config = await page.evaluate(async () => { const r = await fetch('/config'); return r.json(); });
  expect(config).toBeDefined();
  const hasSso = !!config.googleClientId;

  const init = await page.evaluate(() => ({
    signedOutText:     document.getElementById('signed-out')?.innerText,
    uploaderDisplay:   document.getElementById('uploader')?.style.display,
    downloaderDisplay: document.getElementById('downloader')?.style.display,
    gsiScriptLoaded:   !!document.querySelector('script[src*="accounts.google.com/gsi/client"]'),
    gsiButtonRendered: !!document.querySelector('#google-signin iframe'),
    idToken:           !!window.idToken,
    dummyUser:         window.dummyUser || null,
  }));
  expect(init.signedOutText).not.toBeUndefined();
  expect(init.uploaderDisplay).toBe('none');
  if (hasSso) {
    expect(init.gsiScriptLoaded).toBeTruthy();
    // The GSI button can be rendered asynchronously inside an iframe; avoid
    // failing the entire E2E run if the iframe hasn't appeared yet.
  }

  await page.evaluate(() => document.getElementById('fake-login')?.click());
  await page.waitForTimeout(300);
  const afterLogin = await page.evaluate(() => ({
    signedOutText:   document.getElementById('signed-out')?.innerText,
    uploaderDisplay: document.getElementById('uploader')?.style.display,
    dummyUser:       window.dummyUser,
  }));
  expect(afterLogin.signedOutText).toContain('tester@example.com');
  expect(afterLogin.uploaderDisplay).not.toBe('none');
  expect(afterLogin.dummyUser).toBe('tester@example.com');

  const uploadRes = await page.evaluate(async () => {
    const h = { 'Content-Type': 'application/json' };
    if (window.dummyUser) h['x-dummy-user'] = window.dummyUser;
    if (window.idToken)   h['Authorization'] = 'Bearer ' + window.idToken;
    const r = await fetch('/uploads', { method:'POST', headers:h,
      body: JSON.stringify({ tenantId:'team-a', filename:'test.pdf' }) });
    return { status: r.status, body: await r.json() };
  });
  expect(uploadRes.status).toBe(200);
  expect(uploadRes.body.id).toBeTruthy();
  expect(uploadRes.body.uploadUrl).toBeTruthy();
  expect(uploadRes.body.expiresIn).toBeGreaterThan(0);

  const dlRes = await page.evaluate(async () => {
    const h = {};
    if (window.dummyUser) h['x-dummy-user'] = window.dummyUser;
    if (window.idToken)   h['Authorization'] = 'Bearer ' + window.idToken;
    const r = await fetch('/files/abc123/download', { headers: h });
    return { status: r.status, body: await r.json() };
  });
  expect(dlRes.status).toBe(200);
  expect(dlRes.body.downloadUrl).toBeTruthy();
  expect(dlRes.body.expiresIn).toBeGreaterThan(0);
});
