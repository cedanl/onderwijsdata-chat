import { expect } from 'playwright/test'

export async function handleLoginIfNeeded(page) {
  const passwordField = page.locator('input[type="password"]')
  if (await passwordField.isVisible({ timeout: 3000 }).catch(() => false)) {
    await page.fill('input[type="text"]', 'admin')
    await page.fill('input[type="password"]', 'admin')
    await page.click('button[type="submit"]')
    await page.waitForTimeout(3000)
  }

  const skipBtn = page.locator('button', { hasText: 'Overslaan' })
  if (await skipBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await skipBtn.click()
    await page.waitForTimeout(500)
  }
}

// Zet "Geavanceerd" aan zoals een gebruiker dat doet, via Instellingen (#1269). De modelkiezer, de code per stap en
// de CSV-downloads staan erachter, standaard uit: een spec die een model kiest, roept dit eerst aan. Zonder login houdt
// de browser de keuze, met login de server per account; via de schakelaar werkt het in beide gevallen.
export async function zetGeavanceerdAan(page) {
  await page.locator('button[title="Instellingen"]').click()
  const dialoog = page.getByRole('dialog', { name: 'Instellingen' })
  const schakelaar = dialoog.getByRole('switch', { name: 'Geavanceerd' })
  if ((await schakelaar.getAttribute('aria-checked')) !== 'true') await schakelaar.click()
  await expect(schakelaar).toHaveAttribute('aria-checked', 'true')
  await dialoog.getByRole('button', { name: 'Opslaan' }).click()
  await expect(dialoog).toHaveCount(0)
}
