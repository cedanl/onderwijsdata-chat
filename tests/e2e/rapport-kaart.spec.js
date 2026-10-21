// #648: "Genereer rapport" onder een kaartantwoord geeft voortgang en daarna een rapport met de kaart. Het rapport
// staat in een sandbox zonder eigen origin (#634), waar de worker van maplibre niet start; kaartRapport.js tekent de
// kaart daar als SVG (#642). Dit meet dat in de gebouwde app: viewer (iframe) en de HTML-download van schijf.
// Nagebootste chat-socket, zonder LLM; de echte /api/workbooks bewaart het rapport. Niet in CI.
// Draaien: `npx playwright test rapport-kaart` tegen een gebouwde app (zie kaart-csp.spec.js).
//
// fixtures/kaart-provincies.json is de figuur die create_choropleth_map maakt voor "mbo-studenten per provincie"
// (12 provincies, verzonnen aantallen); het rapport krijgt dezelfde figuur als zijn visualisatie.
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { test, expect } from 'playwright/test'
import { handleLoginIfNeeded } from './helpers.js'

const FIGUUR = readFileSync(new URL('./fixtures/kaart-provincies.json', import.meta.url), 'utf8')
const PROVINCIES = JSON.parse(FIGUUR).layout.meta.data.length
const VRAAG = 'Maak een kaart van Nederland met het aantal mbo-studenten in 2023/24 per provincie'
const TEKST = 'Op de kaart staat het aantal mbo-studenten per provincie.'
const KAART_FOUT = /Worker failed|Content Security Policy/

const ANTWOORD = [
  { type: 'message_start' },
  { type: 'tool_start', name: 'create_choropleth_map', label: 'Kaart maken' },
  { type: 'tool_end', name: 'create_choropleth_map' },
  { type: 'figure', label: 'Kaart aangemaakt', figure_json: FIGUUR },
  { type: 'text_delta', content: TEKST },
  { type: 'message_end', content: TEKST, citaties: [], bronnen: [] },
]

const SPEC = {
  title: 'Mbo-studenten per provincie in 2023/24',
  onderzoeksvraag: VRAAG,
  definities: [],
  beantwoordt: ['Het aantal mbo-studenten per provincie in 2023/24'],
  beantwoordt_niet: ['De ontwikkeling over de jaren'],
  visualisaties: [{ titel: 'Mbo-studenten per provincie', toelichting: 'Zuid-Holland kleurt het donkerst.', figure_json: FIGUUR, bron: null }],
  conclusie: 'Zuid-Holland heeft de meeste mbo-studenten.',
  bronnen: [],
  auteur: 'gast',
  datum: '21 oktober 2026',
  manifest: {},
}

const zend = (ws, ev) => ws.send(JSON.stringify(ev))

// De server van de chat. Op generate_report komen report_generating en een stap; report_ready pas als de test
// `rapportKlaar()` aanroept, zodat de voortgang eerst te zien is.
async function nabootsSocket(page) {
  const server = { rapportKlaar: null }
  await page.routeWebSocket(/\/api\/chat/, ws => ws.onMessage(tekst => {
    const bericht = JSON.parse(tekst)
    if (bericht.action === 'ping') zend(ws, { type: 'pong' })
    if (bericht.action === 'message') for (const ev of ANTWOORD) zend(ws, ev)
    if (bericht.action === 'generate_report') {
      zend(ws, { type: 'report_generating' })
      zend(ws, { type: 'tool_start', name: 'create_choropleth_map', label: 'Kaart maken' })
      server.rapportKlaar = () => zend(ws, { type: 'report_ready', spec: SPEC })
    }
  }))
  return server
}

// Alles wat de console en de pagina aan fouten melden, ook uit het iframe van het rapport.
function volgConsole(page) {
  const regels = []
  page.on('console', m => regels.push(`${m.type()}: ${m.text()}`))
  page.on('pageerror', e => regels.push(`pageerror: ${e.message}`))
  return regels
}

// De gebieden van de SVG-kaart en hoeveel verschillende kleuren ze hebben (een kaart, geen grijze vlakken).
async function svgKaart(scope) {
  const gebieden = scope.locator('path.choroplethlocation')
  await expect(gebieden).toHaveCount(PROVINCIES, { timeout: 20_000 })
  const kleuren = await gebieden.evaluateAll(paden => new Set(paden.map(p => getComputedStyle(p).fill)).size)
  expect(kleuren).toBeGreaterThan(1)
  await expect(scope.locator('canvas.maplibregl-canvas')).toHaveCount(0)
}

async function downloadRapport(page, smal) {
  const download = page.waitForEvent('download')
  if (smal) await page.locator('[aria-controls="navbar-meer-rapport"]').click()
  await page.getByRole('button', { name: 'Download als HTML' }).click()
  return download
}

for (const breedte of [390, 1280]) {
  const smal = breedte < 600
  for (const thema of ['light', 'dark']) {
    test.describe(`rapport van een kaartvraag, ${breedte} px, ${thema} (#648)`, () => {
      test.use({
        colorScheme: thema,
        viewport: { width: breedte, height: smal ? 844 : 900 },
        ...(smal && { isMobile: true, hasTouch: true }),
      })

      test('voortgang, dan de viewer en de download met de kaart als SVG', async ({ page, context }, testInfo) => {
        const regels = volgConsole(page)
        const server = await nabootsSocket(page)
        await page.goto('/chat')
        await handleLoginIfNeeded(page)
        const veld = page.locator('textarea.chat-input')
        await veld.fill(VRAAG)
        await veld.press('Enter')
        await expect(page.locator('.plotly-figure-wrap')).toBeVisible()

        const knop = page.locator('.make-rapport-btn')
        await (smal ? knop.tap() : knop.click())
        await expect(page.locator('.report-progress')).toBeVisible()
        await expect(knop).toHaveText('Rapport wordt gegenereerd…')
        await expect.poll(() => typeof server.rapportKlaar).toBe('function')
        server.rapportKlaar()

        const frame = page.locator('iframe.wb-iframe')
        await expect(frame).toHaveAttribute('sandbox', 'allow-scripts')
        await svgKaart(frame.contentFrame())
        // Het beeld voor de MR: de kaart in beeld, niet de kop van het rapport.
        await frame.contentFrame().locator('.js-plotly-plot').first().scrollIntoViewIfNeeded()
        await page.screenshot({ path: testInfo.outputPath(`viewer-${breedte}-${thema}.png`) })

        const pad = testInfo.outputPath('rapport.html')
        await (await downloadRapport(page, smal)).saveAs(pad)
        const bestand = await context.newPage()
        const bestandRegels = volgConsole(bestand)
        await bestand.goto(pathToFileURL(pad).href)
        await svgKaart(bestand)

        expect([...regels, ...bestandRegels].filter(r => KAART_FOUT.test(r))).toEqual([])
      })
    })
  }
}
