/**
 * Playwright-config voor de chat met het nepmodel (#1065): de echte app en toollaag, zonder providersleutel.
 * Start uvicorn met MODEL=mock/default op MOCK_PORT (standaard 8765) en serveert de gebouwde frontend (frontend/dist):
 * eerst `cd frontend && npm run build`. Draaien: npx playwright test --config=playwright.mock.config.js
 * Draait ook in CI (job e2e:nepmodel in .gitlab-ci.yml), zonder secrets.
 */
import { defineConfig } from 'playwright/test'

const PORT = process.env.MOCK_PORT || '8765'

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'mock-llm.spec.js',
  timeout: 120_000,
  retries: 0,
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    headless: true,
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `uv run --frozen --no-sync uvicorn server:app --host 127.0.0.1 --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/health`,
    timeout: 120_000,
    // Lokaal mag een al gestarte server met het nepmodel op MOCK_PORT blijven; in CI start de config hem zelf.
    reuseExistingServer: !process.env.CI,
    env: {
      MODEL: 'mock/default',
      APP_ENV: 'local',
      // Een eigen SQLite-bestand per run, niet de onderwijsdata.db van `make dev`.
      DATABASE_PATH: process.env.MOCK_DATABASE_PATH || '/tmp/onderwijsdata-nepmodel.db',
    },
  },
})
