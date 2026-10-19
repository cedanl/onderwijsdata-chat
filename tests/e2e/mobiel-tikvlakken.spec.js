// #606: een lang woord of een URL zonder spaties in een bubbel, en een tabel die breder is dan de bubbel. Gemeten in
// de gebouwde app op 390 px (aanraking) en 1366 px. Draait zonder LLM: de chat-socket is nagebootst en geeft per
// vraag een vast antwoord. Niet in CI. Draaien: `npx playwright test mobiel-tikvlakken` (playwright.config.js).
import { test, expect, devices } from 'playwright/test'
import { handleLoginIfNeeded } from './helpers.js'

const VRAAG_LANG_WOORD = 'Wat betekent dit woord? ' + 'onderwijsdata'.repeat(250)
const VRAAG_URL = 'Waar staat de tabel?'
const VRAAG_TABEL = 'Zet alles in een tabel.'

const LANGE_URL = 'https://opendata.cbs.nl/statline/#/CBS/nl/dataset/85423NED/table?dl=' + '9A3F0C1D'.repeat(50)
// Breder dan een telefoon: zeven kolommen waarin de getallen het breedst zijn.
const BREDE_TABEL = [
  '| Jaar | mbo | hbo | wo | totaal | groei mbo | groei hbo |',
  '|---|---|---|---|---|---|---|',
  '| 2022 | 507.890 | 489.430 | 335.100 | 1.332.420 | 1,2% | 1,9% |',
  '| 2023 | 512.345 | 498.765 | 341.200 | 1.352.310 | 0,9% | 1,9% |',
].join('\n')

function antwoord(content) {
  return [{ type: 'message_start' }, { type: 'text_delta', content }, { type: 'message_end', content }]
}

const ANTWOORDEN = {
  [VRAAG_LANG_WOORD]: antwoord('Dat is geen bestaand woord; het is het woord onderwijsdata vele keren achter elkaar.'),
  [VRAAG_URL]: antwoord(`Je vindt de tabel hier: ${LANGE_URL}\n\nDaar staat ook de toelichting bij de cijfers.`),
  [VRAAG_TABEL]: antwoord(BREDE_TABEL),
}

// Antwoordt op de heartbeat en op elke bekende vraag; de rest van wat de app stuurt, telt niet.
const nabootsSocket = page => page.routeWebSocket(/\/api\/chat/, ws => ws.onMessage(tekst => {
  const bericht = JSON.parse(tekst)
  if (bericht.action === 'ping') ws.send(JSON.stringify({ type: 'pong' }))
  if (bericht.action === 'message') for (const ev of ANTWOORDEN[bericht.content] ?? []) ws.send(JSON.stringify(ev))
}))

async function stuur(page, vraag) {
  const vragen = page.locator('.message.user')
  const eerder = await vragen.count()
  const veld = page.locator('textarea.chat-input')
  await veld.fill(vraag)
  await veld.press('Enter')
  await expect(vragen).toHaveCount(eerder + 1)
  await expect(page.getByRole('button', { name: 'Verstuur bericht' })).toBeVisible()
}

const TOESTELLEN = [
  ['telefoon', (({ defaultBrowserType: _, ...apparaat }) => apparaat)(devices['iPhone 14'])],
  ['desktop', { viewport: { width: 1366, height: 768 } }],
]

for (const [naam, apparaat] of TOESTELLEN) {
  test.describe(`mobiele tikvlakken en bubbels, ${naam} (${apparaat.viewport.width} px)`, () => {
    test.use(apparaat)

    test.beforeEach(async ({ page }) => {
      await nabootsSocket(page)
      await page.goto('/chat')
      await handleLoginIfNeeded(page)
    })

    test('een lang woord zonder spaties blijft binnen de bubbel en de kolom (#606)', async ({ page }) => {
      await stuur(page, VRAAG_LANG_WOORD)
      const maat = await page.locator('.message.user .message-bubble').last().evaluate(bubbel => {
        const kolom = bubbel.closest('.chat-messages')
        const tekst = document.createRange()
        tekst.selectNode([...bubbel.childNodes].find(n => n.nodeType === Node.TEXT_NODE))
        const knop = bubbel.querySelector('.copy-btn-message')
        knop.scrollIntoView({ block: 'center', behavior: 'instant' })
        const rect = el => el.getBoundingClientRect().toJSON()
        return {
          bubbel: rect(bubbel), kolom: rect(kolom), tekst: tekst.getBoundingClientRect().toJSON(), knop: rect(knop),
          scrollWidth: kolom.scrollWidth, clientWidth: kolom.clientWidth, vw: innerWidth, vh: innerHeight,
        }
      })
      expect(maat.bubbel.width).toBeLessThanOrEqual(maat.kolom.width)
      expect(maat.bubbel.left).toBeGreaterThanOrEqual(maat.kolom.left)
      expect(maat.tekst.left).toBeGreaterThanOrEqual(maat.bubbel.left - 1)
      expect(maat.tekst.right).toBeLessThanOrEqual(maat.bubbel.right + 1)
      expect(maat.scrollWidth).toBeLessThanOrEqual(maat.clientWidth + 1)
      expect(maat.knop.left).toBeGreaterThanOrEqual(0)
      expect(maat.knop.top).toBeGreaterThanOrEqual(0)
      expect(maat.knop.right).toBeLessThanOrEqual(maat.vw)
      expect(maat.knop.bottom).toBeLessThanOrEqual(maat.vh)
    })

    test('een lange URL in het antwoord breekt af in plaats van zijwaarts te scrollen (#606)', async ({ page }) => {
      await stuur(page, VRAAG_URL)
      const bubbel = page.locator('.message-bubble-assistant').last()
      await expect(bubbel.locator('a[href^="https://opendata.cbs.nl"]')).toBeVisible()
      const maat = await bubbel.evaluate(el => {
        const kolom = el.closest('.chat-messages')
        const tekst = document.createRange()
        tekst.selectNodeContents(el.querySelector('p'))
        return {
          bubbel: el.getBoundingClientRect().toJSON(), tekst: tekst.getBoundingClientRect().toJSON(),
          scrollWidth: kolom.scrollWidth, clientWidth: kolom.clientWidth,
        }
      })
      expect(maat.tekst.left).toBeGreaterThanOrEqual(maat.bubbel.left - 1)
      expect(maat.tekst.right).toBeLessThanOrEqual(maat.bubbel.right + 1)
      expect(maat.scrollWidth).toBeLessThanOrEqual(maat.clientWidth + 1)
    })

    // Met `anywhere` in de cellen zou een te brede tabel zijn kolommen smaller maken dan een getal (#606).
    test('een tabel breder dan de bubbel breekt geen getal af (#606)', async ({ page }) => {
      await stuur(page, VRAAG_TABEL)
      const cellen = page.locator('.message-bubble-assistant td')
      await expect(cellen).toHaveCount(14)
      const regels = await cellen.evaluateAll(tds => tds.map(td => {
        const tekst = document.createRange()
        tekst.selectNodeContents(td)
        const hoogtes = new Set([...tekst.getClientRects()].map(r => Math.round(r.top)))
        return [td.textContent, hoogtes.size]
      }))
      expect(regels.filter(([tekst, n]) => /^[\d.,%]+$/.test(tekst) && n !== 1)).toEqual([])
    })
  })
}
