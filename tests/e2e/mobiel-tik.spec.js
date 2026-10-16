// #584: een tik op 'Verstuur bericht' op een telefoon kwam niet aan. Met focus in het invoerveld is de tabbalk
// verborgen (#527); de tik verplaatste de focus naar de knop, de tabbalk kwam meteen terug en het invoergebied
// sprong 58 px omhoog, dus de mouseup landde op de disclaimer en de klik ging naar het invoergebied eromheen.
// Hetzelfde gold voor de stopknop en voor elke tik buiten het veld. Draait zonder LLM: de chat-socket is
// nagebootst en telt wat de app verstuurt. Draaien: `npx playwright test mobiel-tik` (playwright.config.js).
import { test, expect, devices } from 'playwright/test'
import { handleLoginIfNeeded } from './helpers.js'

const VRAAG = 'Hoeveel mbo-studenten zijn er in Utrecht?'

// De bovenkant van `selector` bij elke pointerdown en click, vanaf nu.
const volgPositie = (page, selector) => page.evaluate(sel => {
  window.__posities = []
  for (const type of ['pointerdown', 'click']) {
    document.addEventListener(type, () => window.__posities.push(Math.round(document.querySelector(sel).getBoundingClientRect().top)), true)
  }
}, selector)

for (const toestel of ['iPhone 14', 'Pixel 7']) {
  test.describe(`tikken op een telefoon, ${toestel} (#584)`, () => {
    const { defaultBrowserType: _, ...apparaat } = devices[toestel]
    test.use(apparaat)

    let verstuurd
    test.beforeEach(async ({ page }) => {
      verstuurd = []
      await page.routeWebSocket(/\/api\/chat/, ws => ws.onMessage(bericht => verstuurd.push(JSON.parse(bericht))))
      await page.goto('/chat')
      await handleLoginIfNeeded(page)
      const veld = page.locator('textarea.chat-input')
      await veld.tap()
      await veld.fill(VRAAG)
      // Met focus in het veld is de tabbalk weg (#527).
      await expect(page.locator('.mobile-tabs')).toBeHidden()
    })

    test('verstuurt de vraag, en de knop blijft staan tussen pointerdown en click', async ({ page }) => {
      await volgPositie(page, '.send-btn')
      await page.getByRole('button', { name: 'Verstuur bericht' }).tap()

      await expect.poll(() => verstuurd.filter(b => b.action === 'message').map(b => b.content)).toEqual([VRAAG])
      await expect(page.locator('textarea.chat-input')).toHaveValue('')
      const [neer, klik] = await page.evaluate(() => window.__posities)
      expect(klik).toBe(neer)
      // Na de tik staat de focus op de knop en komt de tabbalk terug.
      await expect(page.locator('.mobile-tabs')).toBeVisible()
    })

    test('de stopknop in dezelfde voet komt ook aan', async ({ page }) => {
      await page.getByRole('button', { name: 'Verstuur bericht' }).tap()
      await expect.poll(() => verstuurd.some(b => b.action === 'message')).toBe(true)
      await page.locator('textarea.chat-input').tap()
      await page.locator("button.send-btn[title='Stop genereren']").tap()
      await expect.poll(() => verstuurd.some(b => b.action === 'stop')).toBe(true)
    })

    test('een tik buiten het veld komt aan op wat er onder de vinger stond', async ({ page }) => {
      const categorie = page.locator('.chat-welcome .suggested-category-btn').first()
      await volgPositie(page, '.chat-welcome .suggested-category-btn')
      await categorie.tap()
      await expect(page.locator('.chat-welcome .suggested-list')).toHaveCount(1)
      const [neer, klik] = await page.evaluate(() => window.__posities)
      expect(klik).toBe(neer)
    })
  })
}
