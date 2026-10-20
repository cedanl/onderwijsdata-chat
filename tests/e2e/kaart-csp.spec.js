// #632: de kaart van create_choropleth_map tekent in de chat. Maplibre start zijn worker vanaf een blob:-URL; zonder
// `worker-src` in de CSP werd die geblokkeerd en bleef de kaart leeg, met "Kaart aangemaakt" erboven. Gemeten in de
// gebouwde app met een nagebootste chat-socket, zonder LLM. Niet in CI. Draaien: `npx playwright test kaart-csp`.
//
// "Getekend" telt maplibre zelf: de vlakken staan op een WebGL-canvas, niet als `path` in de DOM. De meting vraagt
// de kaart achter de Plotly-grafiek (`gd._fullLayout.map._subplot.map`) welke gebieden ze getekend heeft.
//
// fixtures/kaart-provincies.json is de figuur die create_choropleth_map maakt voor "mbo-studenten per provincie"
// (12 provincies, verzonnen aantallen), met de GeoJSON van cartomap (provincie_2024) als vaste kopie.
import { readFileSync } from 'node:fs'
import { test, expect } from 'playwright/test'
import { handleLoginIfNeeded } from './helpers.js'

const FIGUUR = readFileSync(new URL('./fixtures/kaart-provincies.json', import.meta.url), 'utf8')
const PROVINCIES = JSON.parse(FIGUUR).layout.meta.data.length
const VRAAG = 'Toon het aantal mbo-studenten per provincie op een kaart.'
const KAART_FOUT = /Content Security Policy|Worker failed to load|Map error/

const ANTWOORD = [
  { type: 'message_start' },
  { type: 'tool_start', name: 'create_choropleth_map', label: 'Kaart maken' },
  { type: 'tool_end', name: 'create_choropleth_map' },
  { type: 'figure', label: 'Kaart aangemaakt', figure_json: FIGUUR },
  { type: 'text_delta', content: 'Op de kaart staat het aantal mbo-studenten per provincie.' },
  { type: 'message_end', content: 'Op de kaart staat het aantal mbo-studenten per provincie.', citaties: [] },
]

const nabootsSocket = page => page.routeWebSocket(/\/api\/chat/, ws => ws.onMessage(tekst => {
  const bericht = JSON.parse(tekst)
  if (bericht.action === 'ping') ws.send(JSON.stringify({ type: 'pong' }))
  if (bericht.action === 'message') for (const ev of ANTWOORD) ws.send(JSON.stringify(ev))
}))

// Alles wat de console en de pagina aan fouten melden.
function volgConsole(page) {
  const regels = []
  page.on('console', m => regels.push(`${m.type()}: ${m.text()}`))
  page.on('pageerror', e => regels.push(`pageerror: ${e.message}`))
  return regels
}

// De CSP van vóór #632: zonder worker-src, zodat de worker van maplibre weer geblokkeerd wordt.
async function zonderWorkerSrc(page) {
  await page.route(/\/chat$/, async route => {
    const antwoord = await route.fetch()
    const headers = { ...antwoord.headers() }
    headers['content-security-policy'] = headers['content-security-policy'].replace(/worker-src[^;]*;\s*/, '')
    await route.fulfill({ response: antwoord, headers })
  })
}

async function vraagKaart(page) {
  await page.goto('/chat')
  await handleLoginIfNeeded(page)
  const veld = page.locator('textarea.chat-input')
  await veld.fill(VRAAG)
  await veld.press('Enter')
  await expect(page.locator('.plotly-figure-wrap')).toBeVisible()
}

// Het aantal verschillende gebieden dat maplibre getekend heeft (een gebied over twee tegels telt één keer).
const getekendeGebieden = page => page.locator('.plotly-figure-wrap .js-plotly-plot').evaluate(gd => {
  const map = gd._fullLayout?.map?._subplot?.map
  if (!map) return 0
  const vlakken = map.queryRenderedFeatures().filter(f => f.layer?.type === 'fill')
  // Plotly geeft elk gebied id 0; zijn eigenschappen (midden en kleur) maken het herkenbaar.
  return new Set(vlakken.map(f => JSON.stringify(f.properties))).size
})

for (const thema of ['light', 'dark']) {
  test.describe(`kaart in de chat, ${thema} (#632)`, () => {
    test.use({ colorScheme: thema, viewport: { width: 1366, height: 900 } })

    test('tekent alle provincies, zonder CSP- of kaartfout', async ({ page }) => {
      const regels = volgConsole(page)
      await nabootsSocket(page)
      await vraagKaart(page)
      await expect.poll(() => getekendeGebieden(page), { timeout: 20_000 }).toBe(PROVINCIES)
      expect(PROVINCIES).toBe(12)
      expect(regels.filter(r => KAART_FOUT.test(r))).toEqual([])
      const wrap = page.locator('.plotly-figure-wrap')
      await expect(wrap.getByText('Kaart aangemaakt')).toBeVisible()
      await expect(wrap.getByRole('alert')).toHaveCount(0)
      await expect(wrap.locator('table')).toHaveCount(0)
    })
  })
}

test.describe('kaart in de chat, worker geblokkeerd (#632)', () => {
  test.use({ viewport: { width: 1366, height: 900 } })

  test('toont de melding en de tabel in plaats van een lege kaart', async ({ page }) => {
    const regels = volgConsole(page)
    await zonderWorkerSrc(page)
    await nabootsSocket(page)
    await vraagKaart(page)
    const wrap = page.locator('.plotly-figure-wrap')
    await expect(wrap.getByRole('alert')).toContainText('De kaart kon niet worden getekend', { timeout: 20_000 })
    await expect(wrap.getByRole('alert')).toContainText('tabel')
    await expect(wrap.locator('table tbody tr')).toHaveCount(PROVINCIES)
    await expect(wrap.locator('table th')).toHaveText(['Provincie', 'Studenten'])
    await expect(wrap.getByText('Kaart niet getekend')).toBeVisible()
    await expect(wrap.getByText('Kaart aangemaakt')).toHaveCount(0)
    // De lege kaart is weg, ook voor een schermlezer: haar naam ("12 gebieden") zou niet kloppen.
    await expect(wrap.locator('[role="img"]')).toBeHidden()
    // Bewijs dat de simulatie de oorspronkelijke fout geeft.
    expect(regels.some(r => r.includes("'worker-src' was not explicitly set"))).toBe(true)
  })
})
