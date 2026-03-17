const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './test',
  workers: 1,
  use: {
    // Default: headless Chromium inside the dev container.
    // When USE_HOST_BROWSER=1 the custom fixture in test/fixtures.js
    // connects to the host Chrome Canary via CDP instead; these settings
    // are ignored in that code path.
    headless: true,
  },
});
