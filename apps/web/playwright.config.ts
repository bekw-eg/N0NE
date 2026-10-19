import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 90000,
  workers: 1,
  use: {
    baseURL: process.env.FRONTEND_URL || 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 1000 },
    launchOptions: { channel: process.env.PLAYWRIGHT_CHANNEL || 'chromium' },
    screenshot: 'only-on-failure',
  },
  webServer: [
    { command: 'uv run --project ../api python e2e/failure_api.py unreachable 8001', port: 8001, reuseExistingServer: false },
    { command: 'uv run --project ../api python e2e/failure_api.py ors_failure 8002', port: 8002, reuseExistingServer: false },
  ],
});
