/**
 * Playwright-config voor de evals tegen een draaiende omgeving (#169): geen webServer, geen browser.
 * Lokaal: npx playwright test real-questions --config=playwright.eval.config.js
 * met EVAL_BASE_URL, EVAL_USERNAME en EVAL_PASSWORD in de omgeving (zie tests/ijkwaarden/README.md).
 */
import { defineConfig } from 'playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['json', { outputFile: 'eval_results/playwright-eval.json' }]],
  // De verslagen komen uit de runs van alle workers samen: Playwright start na een mislukte test een nieuwe (#753).
  globalSetup: './tests/e2e/eval-setup.js',
  globalTeardown: './tests/e2e/eval-teardown.js',
})
