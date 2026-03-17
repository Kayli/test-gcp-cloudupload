/**
 * Custom Playwright fixtures
 *
 * When the env var USE_HOST_BROWSER=1 is set the `browser` fixture connects to
 * the host's Chrome Canary instance via Chrome DevTools Protocol (CDP) instead
 * of launching a headless browser inside the container.
 *
 * To use the host browser:
 *   1. Start Chrome Canary on the host with --remote-debugging-port=9222
 *      (see host-start-browser.sh)
 *   2. Set USE_HOST_BROWSER=1 in your shell or in .devcontainer/devcontainer.json
 *   3. Run: npm run test:e2e:host
 *
 * The CDP endpoint defaults to http://host.docker.internal:9222 which is set via
 * CHROME_REMOTE_DEBUGGING_URL in devcontainer.json.
 */

const { test: base, chromium, expect } = require('@playwright/test');

const USE_HOST_BROWSER = process.env.USE_HOST_BROWSER === '1';
const CDP_URL =
  process.env.CHROME_REMOTE_DEBUGGING_URL || 'http://host.docker.internal:9222';

const test = base.extend({
  /**
   * Override the worker-scoped `browser` fixture.
   *
   * • USE_HOST_BROWSER=1 → connect to the already-running Chrome Canary on the
   *   host via CDP.  We intentionally do NOT call browser.close() so the host
   *   browser keeps running after the tests finish.
   *
   * • default → launch a normal headless Chromium inside the container.
   */
  browser: [
    async ({}, use) => {
      if (USE_HOST_BROWSER) {
        console.log(`\n[fixtures] USE_HOST_BROWSER=1 → connecting via CDP at ${CDP_URL}\n`);
        const browser = await chromium.connectOverCDP(CDP_URL);
        await use(browser);
        // Do NOT call browser.close() — Chrome Canary on the host stays running.
        // The CDP socket is released when the Node.js process exits.
      } else {
        const browser = await chromium.launch({ headless: true });
        await use(browser);
        await browser.close();
      }
    },
    { scope: 'worker' },
  ],
});

module.exports = { test, expect };
