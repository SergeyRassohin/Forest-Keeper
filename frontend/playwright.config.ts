import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '../tests/e2e',
  tsconfig: '../tests/e2e/tsconfig.json',
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: process.env.FK_E2E_BASE_URL ?? 'https://localhost:8443',
    // Local development uses a freshly generated self-signed certificate only.
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
    launchOptions: process.env.FK_BROWSER_EXECUTABLE_PATH
      ? { executablePath: process.env.FK_BROWSER_EXECUTABLE_PATH }
      : {},
  },
});
