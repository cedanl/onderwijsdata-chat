// #648: "Genereer rapport" onder een kaartantwoord geeft voortgang en daarna een rapport met de kaart. Het rapport
// staat in een sandbox zonder eigen origin (#634), waar de worker van maplibre niet start; kaartRapport.js tekent de
// kaart daar als SVG (#642). Dit meet dat in de gebouwde app: viewer (iframe) en de HTML-download van schijf.
// Nagebootste chat-socket, zonder LLM; de echte /api/workbooks bewaart het rapport. Niet in CI.
// Sinds #660 tekent het rapport met een Plotly zonder maplibre (plotlyRapportBouw.js): naast de kaart een staafdiagram,
// de download opent zonder netwerk en vraagt niets op, en de andere sporen van rapporten en dashboards tekenen ook.
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

// Een figuur van één spoor, zoals de figuur-JSON die de server meestuurt.
const figuur = (data, layout = {}) => JSON.stringify({ data, layout })
const STAAF = figuur([{ type: 'bar', x: ['Groningen', 'Utrecht', 'Zeeland'], y: [31000, 52000, 12000] }])
const vis = (titel, figure_json) => ({ titel, toelichting: '', figure_json, bron: null })

// De sporen die rapporten en dashboards tekenen (data/dashboard.py gebruikt scattergeo), met het element dat Plotly
// per getekend punt of vlak maakt.
const SPOREN = [
  ['staaf', STAAF, '.barlayer .point path'],
  ['lijn', figuur([{ type: 'scatter', mode: 'lines+markers', x: [2021, 2022, 2023], y: [3, 5, 4] }]), '.scatterlayer path.js-line'],
  ['histogram', figuur([{ type: 'histogram', x: [1, 2, 2, 3, 3, 3, 4] }]), '.barlayer .point path'],
  ['taart', figuur([{ type: 'pie', labels: ['mbo', 'hbo', 'wo'], values: [5, 3, 2] }]), '.pielayer .slice path'],
  ['heatmap', figuur([{ type: 'heatmap', z: [[1, 2], [3, 4]] }]), '.heatmaplayer image'],
  // Op de wereldkaart die kaartRapport.js leeg aanlevert: een andere scope haalt zijn kaart van cdn.plot.ly.
  ['scattergeo', figuur([{ type: 'scattergeo', lat: [52.1, 53.2], lon: [5.1, 6.6], mode: 'markers' }]), '.geo .scattergeo path.point'],
]

const SPEC = {
  title: 'Mbo-studenten per provincie in 2023/24',
  onderzoeksvraag: VRAAG,
  definities: [],
  beantwoordt: ['Het aantal mbo-studenten per provincie in 2023/24'],
  beantwoordt_niet: ['De ontwikkeling over de jaren'],
  visualisaties: [
    { titel: 'Mbo-studenten per provincie', toelichting: 'Zuid-Holland kleurt het donkerst.', figure_json: FIGUUR, bron: null },
    vis('Mbo-studenten in drie provincies', STAAF),
  ],
  conclusie: 'Zuid-Holland heeft de meeste mbo-studenten.',
  bronnen: [],
  auteur: 'gast',
  datum: '21 oktober 2026',
  manifest: {},
}

const zend = (ws, ev) => ws.send(JSON.stringify(ev))

// De server van de chat. Op generate_report komen report_generating en een stap; report_ready pas als de test
// `rapportKlaar()` aanroept, zodat de voortgang eerst te zien is.
async function nabootsSocket(page, spec = SPEC) {
  const server = { rapportKlaar: null }
  await page.routeWebSocket(/\/api\/chat/, ws => ws.onMessage(tekst => {
    const bericht = JSON.parse(tekst)
    if (bericht.action === 'ping') zend(ws, { type: 'pong' })
    if (bericht.action === 'message') for (const ev of ANTWOORD) zend(ws, ev)
    if (bericht.action === 'generate_report') {
      zend(ws, { type: 'report_generating' })
      zend(ws, { type: 'tool_start', name: 'create_choropleth_map', label: 'Kaart maken' })
      server.rapportKlaar = () => zend(ws, { type: 'report_ready', spec })
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

// Elk spoor in de lijst heeft getekende elementen, in de volgorde van de grafieken in het rapport.
async function getekend(scope, sporen) {
  const plots = scope.locator('.js-plotly-plot')
  await expect(plots).toHaveCount(sporen.length + 1, { timeout: 20_000 })
  for (const [i, [naam, , selector]] of sporen.entries()) {
    await expect(plots.nth(i + 1).locator(selector).first(), naam).toBeAttached({ timeout: 20_000 })
  }
}

// Verzoeken die de pagina (met het rapportframe) buiten de eigen origin doet; voor een bestand: buiten file:.
function volgVerzoeken(page) {
  const verzoeken = []
  page.on('request', r => verzoeken.push(r.url()))
  return toegestaan => verzoeken.filter(u => !/^(data|blob|about):/.test(u) && !u.startsWith(toegestaan))
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
        const vreemd = volgVerzoeken(page)
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
        await getekend(frame.contentFrame(), [SPOREN[0]])
        // Het beeld voor de MR: de kaart in beeld, niet de kop van het rapport.
        await frame.contentFrame().locator('.js-plotly-plot').first().scrollIntoViewIfNeeded()
        await page.screenshot({ path: testInfo.outputPath(`viewer-${breedte}-${thema}.png`) })

        const pad = testInfo.outputPath('rapport.html')
        await (await downloadRapport(page, smal)).saveAs(pad)
        expect(vreemd(new URL(page.url()).origin)).toEqual([])

        // Van schijf, zonder netwerk (#405): Plotly zit erin en de kaart heeft geen tegels of worker nodig.
        await context.setOffline(true)
        const bestand = await context.newPage()
        const bestandRegels = volgConsole(bestand)
        const bestandVreemd = volgVerzoeken(bestand)
        await bestand.goto(pathToFileURL(pad).href)
        await svgKaart(bestand)
        await getekend(bestand, [SPOREN[0]])
        expect(bestandVreemd('file:')).toEqual([])

        expect([...regels, ...bestandRegels].filter(r => KAART_FOUT.test(r))).toEqual([])
      })
    })
  }
}

// #660: de sporen van rapporten en dashboards tekenen met de Plotly zonder maplibre, in de viewer en van schijf.
test.describe('alle sporen van rapporten en dashboards, 1280 px (#660)', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('viewer en download tekenen de kaart en elk ander spoor', async ({ page, context }, testInfo) => {
    const regels = volgConsole(page)
    const server = await nabootsSocket(page, { ...SPEC, visualisaties: [SPEC.visualisaties[0], ...SPOREN.map(([naam, f]) => vis(naam, f))] })
    await page.goto('/chat')
    await handleLoginIfNeeded(page)
    await page.locator('textarea.chat-input').fill(VRAAG)
    await page.locator('textarea.chat-input').press('Enter')
    await expect(page.locator('.plotly-figure-wrap')).toBeVisible()
    await page.locator('.make-rapport-btn').click()
    await expect.poll(() => typeof server.rapportKlaar).toBe('function')
    server.rapportKlaar()

    const frame = page.locator('iframe.wb-iframe').contentFrame()
    await svgKaart(frame)
    await getekend(frame, SPOREN)

    const pad = testInfo.outputPath('rapport-sporen.html')
    await (await downloadRapport(page, false)).saveAs(pad)
    await context.setOffline(true)
    const bestand = await context.newPage()
    const bestandRegels = volgConsole(bestand)
    await bestand.goto(pathToFileURL(pad).href)
    await svgKaart(bestand)
    await getekend(bestand, SPOREN)

    expect([...regels, ...bestandRegels].filter(r => KAART_FOUT.test(r) || r.startsWith('pageerror'))).toEqual([])
  })
})
