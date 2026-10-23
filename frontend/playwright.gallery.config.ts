import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: '../tests/ui-gallery',
  tsconfig: '../tests/ui-gallery/tsconfig.json',
  workers: 1,
  retries: 0,
  timeout: 180000,
  reporter: 'list',
  use: {
    baseURL: process.env.FK_E2E_BASE_URL ?? 'https://localhost:8443',
    ignoreHTTPSErrors: true,
    locale: 'ru-RU',
    timezoneId: 'Europe/Moscow',
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
    launchOptions: process.env.FK_BROWSER_EXECUTABLE_PATH ? { executablePath: process.env.FK_BROWSER_EXECUTABLE_PATH } : {},
  },
});
