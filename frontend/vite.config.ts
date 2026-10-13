import react from '@vitejs/plugin-react';
import { readFileSync } from 'node:fs';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  server: {
    https:
      process.env.FK_VITE_HTTPS === '1'
        ? {
            key: readFileSync('../deploy/local/tls/dev.key'),
            cert: readFileSync('../deploy/local/tls/dev.crt'),
          }
        : undefined,
    proxy: {
      '/api': process.env.FK_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.test.tsx'],
    restoreMocks: true,
  },
});
