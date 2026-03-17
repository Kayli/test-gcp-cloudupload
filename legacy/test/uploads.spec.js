const { test, expect } = require('./fixtures');
const { APP_URL, ensureServer, stopServer } = require('./helpers/server');

test.beforeAll(async () => {
  await ensureServer();
});

test.afterAll(() => {
  stopServer();
});

test('POST /uploads returns uploadUrl and id', async ({ request }) => {
  const payload = { tenantId: 'team-a', filename: 'doc.pdf' };
  const res = await request.post(`${APP_URL}/uploads`, {
    data: JSON.stringify(payload),
    headers: { 'content-type': 'application/json', 'x-dummy-user': 'tester@example.com' },
  });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.id).toBeTruthy();
  expect(body.uploadUrl).toBeTruthy();
  expect(body.expiresIn).toBeTruthy();
});

test('POST /uploads without required fields returns 400', async ({ request }) => {
  const res = await request.post(`${APP_URL}/uploads`, {
    data: JSON.stringify({}),
    headers: { 'content-type': 'application/json', 'x-dummy-user': 'tester@example.com' },
  });
  expect(res.status()).toBe(400);
  const body = await res.json();
  expect(body).toHaveProperty('error');
});

test('GET /files/:id/download returns downloadUrl', async ({ request }) => {
  const res = await request.get(`${APP_URL}/files/abc123/download`, {
    headers: { 'x-dummy-user': 'tester@example.com' },
  });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body).toHaveProperty('downloadUrl');
  expect(body).toHaveProperty('expiresIn');
});
