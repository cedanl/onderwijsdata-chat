import { defineConfig } from 'playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  retries: 0,
  workers: 1,
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'make dev',
    url: 'http://localhost:5173',
    timeout: 30_000,
    reuseExistingServer: true,
  },
})
