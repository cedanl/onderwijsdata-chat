// #1065: de hele chat met het nepmodel (MODEL=mock/default), zonder providersleutel: vraag, toolstappen, antwoord,
// rapport. Anders dan de andere specs hier is de socket niet nagebootst: de echte server, toolloop, catalogus en
// controles draaien; alleen het model is nep (agent/nepmodel.py). Het scenario laadt één kleine CBS-tabel, dus de
// test heeft internet naar CBS nodig, maar geen secrets.
// Draaien: `cd frontend && npm run build`, dan `npx playwright test --config=playwright.mock.config.js`.
// In CI: job e2e:nepmodel (.gitlab-ci.yml).
import { test, expect } from 'playwright/test'
import { handleLoginIfNeeded } from './helpers.js'

const VRAAG = 'Hoeveel mbo-studenten zijn er landelijk?'
// De eerste zin van elk antwoord van het nepmodel (agent/nepmodel.py, KOP).
const KOP = 'Nepmodel (lokaal testen, geen echt taalmodel).'

test('vraag, antwoord en rapport met het nepmodel', async ({ page }) => {
  await page.goto('/chat')
  await handleLoginIfNeeded(page)
  await expect(page.locator('.chat-welcome')).toBeVisible()

  // De modelkiezer hoort bij "Geavanceerd" (#1269), standaard uit; zonder login houdt deze browser de instelling.
  await expect(page.getByRole('combobox', { name: 'Model' })).toHaveCount(0)
  await page.locator('button[title="Instellingen"]').click()
  await page.getByRole('switch', { name: 'Geavanceerd' }).click()
  await page.getByRole('button', { name: 'Opslaan' }).click()

  // De modelkiezer biedt de nepscenario's aan (core/config.py, get_available_models).
  await expect(page.getByRole('combobox', { name: 'Model' }).first()).toContainText('Nepmodel')

  const veld = page.locator('textarea.chat-input')
  await veld.fill(VRAAG)
  await page.getByRole('button', { name: 'Verstuur bericht' }).click()

  const antwoord = page.locator('.message-bubble').filter({ hasText: KOP }).last()
  await expect(antwoord).toBeVisible({ timeout: 60_000 })
  await expect(antwoord).toContainText('In de catalogus vond ik als eerste')
  await expect(antwoord).toContainText('mbo-studenten')

  await page.locator('.make-rapport-btn').click()
  const dialoog = page.getByRole('dialog')
  await expect(dialoog).toBeVisible()
  await dialoog.getByRole('button', { name: 'Maak', exact: true }).click()

  // Het rapport wordt bewaard en opent in de viewer (ChatPage: saveWorkbookWithSync, dan openRapport).
  const frame = page.locator('iframe.wb-iframe')
  await expect(frame).toBeVisible({ timeout: 60_000 })
  await expect(frame.contentFrame().locator('body')).toContainText('Het nepmodel schreef dit rapport', { timeout: 20_000 })

  // En het staat bij de rapporten.
  await page.goto('/rapporten')
  await expect(page.getByText('Mbo-studenten', { exact: false }).first()).toBeVisible()
})
