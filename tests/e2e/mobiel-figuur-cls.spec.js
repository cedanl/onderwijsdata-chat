// #661: op een telefoon schoof het etiket "Antwoord van <model>" onder de bubbel mee met alles wat erboven groeide.
// Een grafiek komt als los, al afgerond bericht binnen terwijl de tekst nog stroomt, dus het etiket stond er al en
// schoof bij elke gestreamde regel omlaag en nog eens bij de landing van de grafiek (CLS 0,034 op een staafgrafiek,
// 0,038 met de composer erbij). Nu komt het etiket pas als elk bericht van de beurt klaar is, en landt de grafiek
// zonder dat er iets in beeld verschuift. Gemeten in de gebouwde app op 390x844 (iPhone 14, aanraking), licht en
// donker, met dezelfde methode als #649: een PerformanceObserver vóór de navigatie die alle layout-shifts optelt, ook
// die met hadRecentInput.
//
// Draait zonder LLM: de chat-socket is nagebootst en speelt een beurt van ongeveer 2,6 s. Niet in CI. Draaien:
// `npx playwright test mobiel-figuur-cls` (playwright.config.js).
//
// De kaart telt alleen tot KAART_VENSTER_MS na de landing. Daarna zet useKaartStatus een kaart die nog niet getekend
// is even op 'mislukt' (#642, 1 s bevestiging); in een headless browser zonder GPU tekent de kaart traag genoeg dat
// de melding kort verschijnt en de blokken eronder 49 px op en neer gaan. Dat is een ander verschijnsel dan hier.
import { readFileSync } from 'node:fs'
import { test, expect, devices } from 'playwright/test'
import { handleLoginIfNeeded } from './helpers.js'

const TELEFOON = (({ defaultBrowserType: _, ...apparaat }) => apparaat)(devices['iPhone 14'])
const VRAAG = 'Toon de studenten per niveau in een grafiek.'
const MAX_CLS = 0.02
const KAART_VENSTER_MS = 1000

const JAREN = [2019, 2020, 2021, 2022, 2023]
const FIGUREN = {
  staaf: {
    data: [{ type: 'bar', name: 'Studenten', x: ['mbo', 'hbo', 'wo'], y: [512345, 498765, 341200] }],
    layout: { title: { text: 'Ingeschreven studenten per niveau' } },
  },
  lijn: {
    data: [
      { type: 'scatter', mode: 'lines', name: 'mbo', x: JAREN, y: [500, 505, 510, 507, 512] },
      { type: 'scatter', mode: 'lines', name: 'hbo', x: JAREN, y: [480, 485, 490, 489, 498] },
    ],
    layout: { title: { text: 'Ingeschreven studenten per jaar' } },
  },
  kaart: JSON.parse(readFileSync(new URL('./fixtures/kaart-provincies.json', import.meta.url), 'utf8')),
}

const TEKST = [
  'Het mbo is met 512.345 ingeschreven studenten het grootst, het hbo volgt met 498.765 en het wo is met 341.200 ',
  'het kleinst.\n\nDe cijfers komen uit de CBS-tabel met inschrijvingen per niveau. In de grafiek zie je de ',
  'verhouding tussen de niveaus, zoals ze in de opgehaalde data staan.\n\n',
  'Let op dat het om voorlopige cijfers gaat; CBS kan ze nog herzien.',
]
const EIND_MS = 2600

// Zoals de server een beurt met een grafiek stuurt: de grafiek komt vóór de eindtekst, de tekst stroomt daarna.
const beurt = figuur => [
  [0, { type: 'message_start' }],
  [100, { type: 'tool_start', name: 'cbs_query', label: 'CBS-data ophalen' }],
  [700, { type: 'tool_end', name: 'cbs_query', snippet: "df = cbs.get_data('85423NED')" }],
  [800, { type: 'tool_start', name: 'create_plot', label: 'Grafiek maken' }],
  [1200, { type: 'tool_end', name: 'create_plot', snippet: 'fig' }],
  [1250, { type: 'figure', label: 'Studenten per niveau', figure_json: JSON.stringify(figuur) }],
  ...TEKST.map((deel, i) => [1500 + i * 250, { type: 'text_delta', content: deel }]),
  [EIND_MS, {
    type: 'message_end', content: TEKST.join(''), citaties: [], bronnen: ['CBS StatLine 85423NED'],
    vervolgvragen: ['Hoe zit dit per provincie?', 'En de afgelopen vijf jaar?'],
  }],
]

const nabootsSocket = (page, figuur) => page.routeWebSocket(/\/api\/chat/, ws => ws.onMessage(tekst => {
  const bericht = JSON.parse(tekst)
  if (bericht.action === 'ping') ws.send(JSON.stringify({ type: 'pong' }))
  if (bericht.action !== 'message') return
  for (const [ms, ev] of beurt(figuur)) {
    setTimeout(() => {
      try { ws.send(JSON.stringify(ev)) } catch { /* de test is al klaar */ }
    }, ms)
  }
}))

// In de pagina, vóór de navigatie: elke layout-shift met zijn bronnen.
function observeerShifts() {
  const elementVan = node => (node?.nodeType === 1 ? node : node?.parentElement ?? null)
  const naam = el => (el ? el.tagName.toLowerCase() + [...el.classList].map(k => `.${k}`).join('') : '(verwijderd)')
  window.__cls = []
  new PerformanceObserver(lijst => {
    for (const e of lijst.getEntries()) {
      window.__cls.push({
        t: e.startTime, waarde: e.value, invoer: e.hadRecentInput,
        bronnen: e.sources.map(s => naam(elementVan(s.node))),
      })
    }
  }).observe({ type: 'layout-shift', buffered: true })
}

for (const kleur of ['light', 'dark']) {
  test.describe(`grafiek in een streamend antwoord, 390x844, ${kleur === 'light' ? 'licht' : 'donker'}`, () => {
    test.use({ ...TELEFOON, colorScheme: kleur })

    for (const soort of Object.keys(FIGUREN)) {
      test(`${soort}: de landing verschuift niets in beeld`, async ({ page }) => {
        await nabootsSocket(page, FIGUREN[soort])
        await page.addInitScript(observeerShifts)
        await page.goto('/chat')
        await handleLoginIfNeeded(page)
        await expect(page.locator('.chat-welcome')).toBeVisible()
        await page.waitForTimeout(1000)

        const veld = page.locator('textarea.chat-input')
        await veld.tap()
        await veld.fill(VRAAG)
        await page.getByRole('button', { name: 'Verstuur bericht' }).tap()
        const tikMoment = await page.evaluate(() => performance.now())

        // Zolang de tekst stroomt, staat het etiket er nog niet (het schoof er elke regel mee omlaag).
        await page.waitForTimeout(EIND_MS - 400)
        await expect(page.locator('.message-model')).toHaveCount(0)
        await expect(page.locator('.plotly-figure-wrap')).toBeVisible({ timeout: 15_000 })
        const grafiekMoment = await page.evaluate(() => performance.now())
        await expect(page.locator('.message-model')).toHaveCount(1)
        await page.waitForTimeout(soort === 'kaart' ? KAART_VENSTER_MS : 3000)

        const tot = soort === 'kaart' ? grafiekMoment + KAART_VENSTER_MS : Infinity
        const shifts = (await page.evaluate(() => window.__cls)).filter(s => s.t >= tikMoment && s.t <= tot)
        const cls = shifts.reduce((som, s) => som + s.waarde, 0)

        expect(cls, JSON.stringify(shifts)).toBeLessThanOrEqual(MAX_CLS)
        expect(shifts.flatMap(s => s.bronnen).filter(b => b.includes('message-model')), JSON.stringify(shifts)).toEqual([])
      })
    }
  })
}
