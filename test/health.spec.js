const { test, expect } = require('@playwright/test');
const { APP_URL, ensureServer, stopServer } = require('./helpers/server');

test.beforeAll(async () => {
  await ensureServer();
});

test.afterAll(() => {
  stopServer();
});

test('GET /health returns status ok', async ({ request }) => {
  const res = await request.get(`${APP_URL}/health`);
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body).toEqual({ status: 'ok' });
});
