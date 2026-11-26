// #1065: de hele chat met het nepmodel (MODEL=mock/default), zonder providersleutel: vraag, toolstappen, antwoord,
// rapport. Anders dan de andere specs hier is de socket niet nagebootst: de echte server, toolloop, catalogus en
// controles draaien; alleen het model is nep (agent/nepmodel.py). Het scenario laadt één kleine CBS-tabel, dus de
// test heeft internet naar CBS nodig, maar geen secrets.
// Draaien: `cd frontend && npm run build`, dan `npx playwright test --config=playwright.mock.config.js`.
// In CI: job e2e:nepmodel (.gitlab-ci.yml).
import { test, expect } from 'playwright/test'
import { handleLoginIfNeeded, zetGeavanceerdAan } from './helpers.js'

const VRAAG = 'Hoeveel mbo-studenten zijn er landelijk?'
// De eerste zin van elk antwoord van het nepmodel (agent/nepmodel.py, KOP).
const KOP = 'Nepmodel (lokaal testen, geen echt taalmodel).'

test('vraag, antwoord en rapport met het nepmodel', async ({ page }) => {
  await page.goto('/chat')
  await handleLoginIfNeeded(page)
  await expect(page.locator('.chat-welcome')).toBeVisible()

  // De modelkiezer hoort bij "Geavanceerd" (#1269), standaard uit; zonder login houdt deze browser de instelling.
  await expect(page.getByRole('combobox', { name: 'Model' })).toHaveCount(0)
  await zetGeavanceerdAan(page)

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

// #1254: een getal dat de controle intrekt, staat op geen enkel moment in beeld. Scenario verzonnen (agent/nepmodel.py)
// noemt eerst een getal dat in geen data staat, in twee stukken ("27." en "135"); de getalcontrole trekt het antwoord
// in en de correctieronde noemt het niet. Zonder netwerk naar CBS: het scenario roept geen tools aan. De test leest de
// DOM na elke text_delta (twee frames later, als de delta getekend is) en bij elke mutatie.
test('een ingetrokken getal is bij geen enkele delta zichtbaar (#1254)', async ({ page }) => {
  await page.addInitScript(() => {
    const GEZOCHT = '27135'
    const meting = { deltas: 0, annuleringen: 0, zichtbaar: [], inDom: [], einde: false }
    window.__getal = meting
    const cijfers = t => t.replace(/[.\s\u00a0\u202f]/g, '')
    function kijk(moment) {
      if (!document.body) return
      const loper = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
      for (let n = loper.nextNode(); n; n = loper.nextNode()) {
        if (!cijfers(n.textContent).includes(GEZOCHT)) continue
        if (!meting.einde) meting.inDom.push(moment)
        const el = n.parentElement
        if (el?.checkVisibility({ contentVisibilityAuto: true, opacityProperty: true, visibilityProperty: true })) {
          meting.zichtbaar.push(moment)
        }
      }
    }
    new MutationObserver(() => kijk('mutatie')).observe(document, { subtree: true, childList: true, characterData: true })
    const Echt = window.WebSocket
    window.WebSocket = class extends Echt {
      constructor(...args) {
        super(...args)
        this.addEventListener('message', e => {
          let ev
          try { ev = JSON.parse(e.data) } catch { return }
          if (ev.type === 'text_delta') {
            meting.deltas += 1
            const n = meting.deltas
            requestAnimationFrame(() => requestAnimationFrame(() => kijk(`delta ${n}`)))
          }
          if (ev.type === 'message_cancel') meting.annuleringen += 1
          if (ev.type === 'message_end') meting.einde = true
        })
      }
    }
  })

  await page.goto('/chat')
  await handleLoginIfNeeded(page)
  await expect(page.locator('.chat-welcome')).toBeVisible()
  // Het scenario kiezen kan alleen met "Geavanceerd" aan: de modelkiezer staat erachter (#1269).
  await zetGeavanceerdAan(page)
  await page.getByRole('combobox', { name: 'Model' }).first().selectOption('mock/verzonnen')

  // Een vraag zonder open slot: anders komt er eerst een verduidelijkingskaart in plaats van het model.
  await page.locator('textarea.chat-input').fill(VRAAG)
  await page.getByRole('button', { name: 'Verstuur bericht' }).click()

  const antwoord = page.locator('.message.assistant .message-bubble').filter({ hasText: KOP }).last()
  await expect(antwoord).toContainText('noemt daarom geen aantal', { timeout: 60_000 })
  // De eerste versie is ingetrokken: dat staat er, dichtgeklapt.
  await expect(page.locator('details.message-ingetrokken summary')).toBeVisible()

  const meting = await page.evaluate(() => window.__getal)
  expect(meting.deltas).toBeGreaterThanOrEqual(4)
  expect(meting.annuleringen).toBe(1)
  expect(meting.zichtbaar).toEqual([])
  expect(meting.inDom).toEqual([])
})
