import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: '../tests/ai-browser', tsconfig: '../tests/ai-browser/tsconfig.json',
  workers: 1, retries: 0, timeout: 600000, reporter: 'list',
  use: { baseURL: process.env.FK_AI_BROWSER_BASE_URL ?? 'https://localhost:18455',
    ignoreHTTPSErrors: true, locale: 'ru-RU', timezoneId: 'Europe/Moscow',
    viewport: { width: 1440, height: 900 },
    // No Playwright traces/video: login credentials must not enter shareable artifacts.
    trace: 'off', video: 'off', screenshot: 'off',
    launchOptions: process.env.FK_BROWSER_EXECUTABLE_PATH ? { executablePath: process.env.FK_BROWSER_EXECUTABLE_PATH } : {},
  },
});
