// #649: op een telefoon verschoof de pagina rond de eerste vraag drie keer (CLS 0,27 in de mobiel-audit van 20-10):
// de verbindingsregel bij het laden, elke regel van een lange vraag, en het leegmaken bij versturen (de composer
// sprong 76 px). Nu heeft de pil een vaste plek van één regel en groeit hij daarboven over de berichten. Gemeten in de
// gebouwde app op 390x844 en 390x664 (iPhone 14, aanraking) en 1366x768, met dezelfde methode als de audit: een
// PerformanceObserver vóór de navigatie die alle layout-shifts optelt, ook die met hadRecentInput.
//
// Draait zonder LLM: de chat-socket is nagebootst en speelt een beurt van ongeveer 3 s. Dat is dus geen echte vraag;
// de meting met een echte vraag hoort bij de MR. Niet in CI. Draaien: `npx playwright test mobiel-welkom-cls`
// (playwright.config.js), of tegen een app op een eigen poort met een config die `baseURL` daarop zet.
// VOOR_DIST=<map met een andere frontend-build> meet die build tegen dezelfde backend (zo is main gemeten);
// METING_UIT=<bestand> schrijft per sessie de ruwe meting als JSON-regel weg, voor de tabellen in de MR.
import { test, expect, devices } from 'playwright/test'
import { appendFileSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { handleLoginIfNeeded } from './helpers.js'

const HALVE_PX = 0.5
const VENSTER_MS = 15_000
const TELEFOON = (({ defaultBrowserType: _, ...apparaat }) => apparaat)(devices['iPhone 14'])

// Rond de 175 tekens: vijf regels in het veld op 390 px.
const VRAAG = 'Hoe heeft het aantal ingeschreven studenten in het mbo, het hbo en het wo zich de afgelopen vijf ' +
  'jaar ontwikkeld, per provincie en per niveau, en waar groeit of krimpt het het sterkst?'
const VERVOLG = 'En hoe verhoudt die ontwikkeling zich tot de UWV-vacatures in dezelfde provincies, per brede ' +
  'sector, en welke sectoren hebben in mijn provincie de grootste tekorten aan gediplomeerden?'

// Lang genoeg om de berichtenlijst op 390x664 te laten scrollen (criterium 7).
const ANTWOORD = [
  'Het aantal ingeschreven studenten is de afgelopen vijf jaar in alle drie de sectoren gegroeid, maar niet overal ',
  'even hard. Het mbo groeide het minst en kromp in een paar provincies zelfs licht, vooral in het noorden en in ',
  'Zeeland, waar de jongere bevolking afneemt.\n\n',
  'Het hbo groeide in de Randstad het sterkst: in Utrecht, Zuid-Holland en Noord-Holland kwamen er elk jaar enkele ',
  'procenten studenten bij. Buiten de Randstad bleef het aantal hbo-studenten ongeveer gelijk.\n\n',
  'Het wo groeide landelijk het hardst, mede door internationale studenten. In Groningen, Limburg en Gelderland zie ',
  'je die groei duidelijk terug; daar ligt het aandeel internationale studenten hoger dan gemiddeld.\n\n',
  'Waar het krimpt, gaat het vooral om opleidingen op niveau 2 en 3 in het mbo. Niveau 4 houdt beter stand, ',
  'omdat meer studenten daarna doorstromen naar het hbo.\n\n',
  'Kortom: groei in het hoger onderwijs, vooral in de Randstad en de universiteitssteden, en een licht dalend mbo in ',
  'de krimpregio\'s. De cijfers komen uit de CBS-tabel met inschrijvingen per provincie en niveau.',
]
const BEURT = [
  [0, { type: 'message_start' }],
  [150, { type: 'tool_start', name: 'cbs_query', label: 'CBS-data ophalen' }],
  [1000, { type: 'tool_end', name: 'cbs_query', snippet: "df = cbs.get_data('85423NED')" }],
  ...ANTWOORD.map((deel, i) => [1200 + i * 150, { type: 'text_delta', content: deel }]),
  [3000, { type: 'message_end', content: ANTWOORD.join(''), citaties: [] }],
]

// De socket: open (antwoordt op de heartbeat en speelt per vraag de beurt) of dicht (sluit elke poging meteen, dan
// staat de verbindingsregel in beeld).
function nabootsSocket(page, staat) {
  return page.routeWebSocket(/\/api\/chat/, ws => {
    if (staat.dicht) {
      ws.close()
      return
    }
    ws.onMessage(tekst => {
      const bericht = JSON.parse(tekst)
      if (bericht.action === 'ping') ws.send(JSON.stringify({ type: 'pong' }))
      if (bericht.action !== 'message') return
      for (const [ms, ev] of BEURT) {
        setTimeout(() => {
          try { ws.send(JSON.stringify(ev)) } catch { /* de test is al klaar */ }
        }, ms)
      }
    })
  })
}

// Een andere build tegen dezelfde backend: de app-shell met de headers van de server, de bundels uit VOOR_DIST.
async function andereBuild(page, dist) {
  if (!dist) return
  const index = readFileSync(join(dist, 'index.html'), 'utf8')
  await page.route(url => !url.pathname.startsWith('/api') && !url.pathname.startsWith('/assets/'), async route => {
    if (route.request().resourceType() !== 'document') return route.fallback()
    await route.fulfill({ response: await route.fetch(), body: index })
  })
  await page.route('**/assets/**', route => route.fulfill({ path: join(dist, new URL(route.request().url()).pathname) }))
}

// In de pagina, vóór de navigatie: elke layout-shift met zijn bronnen. `verboden`: de bron is het welkomstscherm (of
// iets erin), het invoergebied of de berichtenlijst zelf (criterium 4).
function observeerShifts() {
  const elementVan = node => (node?.nodeType === 1 ? node : node?.parentElement ?? null)
  const naam = el => {
    if (!el) return '(verwijderd)'
    const eigen = el.tagName.toLowerCase() + [...el.classList].map(k => `.${k}`).join('')
    if (el.classList.length || el.id) return eigen
    const ouder = el.parentElement?.closest('[class]')
    return ouder ? `${ouder.tagName.toLowerCase()}.${[...ouder.classList].join('.')} ${eigen}` : eigen
  }
  const vak = r => r && [r.x, r.y, r.width, r.height].map(Math.round)
  window.__cls = []
  new PerformanceObserver(lijst => {
    for (const e of lijst.getEntries()) {
      window.__cls.push({
        t: e.startTime, waarde: e.value, invoer: e.hadRecentInput,
        bronnen: e.sources.map(s => {
          const el = elementVan(s.node)
          return {
            node: naam(el), van: vak(s.previousRect), naar: vak(s.currentRect),
            verboden: !!el?.matches('.chat-welcome, .chat-welcome *, .chat-input-area, .chat-messages'),
          }
        }),
      })
    }
  }).observe({ type: 'layout-shift', buffered: true })
}

// Elk animatieframe: de top van het invoergebied en van de delen van het welkomstscherm (null als ze er niet zijn).
function startMonsters() {
  const top = s => document.querySelector(s)?.getBoundingClientRect().top ?? null
  window.__monsters = []
  const tik = () => {
    window.__monsters.push({
      t: performance.now(), area: top('.chat-input-area'), icoon: top('.chat-welcome-icon'),
      kop: top('.chat-welcome h2'), suggesties: top('.chat-welcome-suggestions'),
    })
    window.__monsterFrame = requestAnimationFrame(tik)
  }
  tik()
}

const nu = page => page.evaluate(() => performance.now())
const volgendFrame = page =>
  page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))))

async function open(page, staat = { dicht: false }) {
  await nabootsSocket(page, staat)
  await andereBuild(page, process.env.VOOR_DIST)
  await page.addInitScript(observeerShifts)
  await page.goto('/chat')
  await handleLoginIfNeeded(page)
  await expect(page.locator('.chat-welcome')).toBeVisible()
}

async function verbonden(page) {
  await expect(page.locator('.ws-reconnecting')).toHaveText('')
  await expect(page.locator('.chat-welcome-suggestions, .chat-welcome p').first()).toBeVisible()
  // Wat bij het laden nog binnenkomt (instellingen, gesprekken) eerst laten landen.
  await page.waitForTimeout(800)
  await volgendFrame(page)
}

const RECTS = ['.chat-messages', '.chat-input-area', '.chat-input-wrap']
const rects = page => page.evaluate(kiezers => Object.fromEntries(kiezers.map(s => {
  const r = document.querySelector(s).getBoundingClientRect()
  return [s, { top: r.top, left: r.left, width: r.width, height: r.height }]
})), RECTS)
const left = page => page.getByRole('button', { name: 'Gesprekken en suggesties' })
  .evaluate(el => el.getBoundingClientRect().left)

function noteer(meting) {
  if (process.env.METING_UIT) appendFileSync(process.env.METING_UIT, `${JSON.stringify(meting)}\n`)
}

const spreiding = waarden => (waarden.length ? Math.max(...waarden) - Math.min(...waarden) : 0)
const binnen = (a, b) => Math.abs(a - b) <= HALVE_PX

// De rusttoestand (leeg, verbonden) op main (1fefddd), opnieuw gemeten met deze spec en VOOR_DIST (criterium 5).
const MAIN = {
  '390x844': {
    '.chat-messages': { top: 52, left: 0, width: 390, height: 723 },
    '.chat-input-area': { top: 775, left: 0, width: 390, height: 69 },
    '.chat-input-wrap': { top: 782, left: 10, width: 370, height: 54 },
  },
  '390x664': {
    '.chat-messages': { top: 52, left: 0, width: 390, height: 543 },
    '.chat-input-area': { top: 595, left: 0, width: 390, height: 69 },
    '.chat-input-wrap': { top: 602, left: 10, width: 370, height: 54 },
  },
  '1366x768': {
    '.chat-messages': { top: 64, left: 280, width: 1086, height: 522.203125 },
    '.chat-input-area': { top: 586.203125, left: 280, width: 1086, height: 181.796875 },
    '.chat-input-wrap': { top: 603.203125, left: 304, width: 1038, height: 127.796875 },
  },
}

function verwachtRects(gemeten, verwacht) {
  for (const s of RECTS) {
    for (const maat of ['top', 'left', 'width', 'height']) {
      const verschil = Math.abs(gemeten[s][maat] - verwacht[s][maat])
      expect(verschil, `${s} ${maat}: ${JSON.stringify(gemeten[s])}`).toBeLessThanOrEqual(HALVE_PX)
    }
  }
}

for (const hoogte of [844, 664]) {
  const maat = `390x${hoogte}`
  test.describe(`welkomstscherm naar eerste bericht zonder verschuiving, ${maat}`, () => {
    test.use({ ...TELEFOON, viewport: { width: 390, height: hoogte } })

    for (const sessie of [1, 2]) {
      test(`sessie ${sessie}: CLS, invoergebied, welkomstscherm, navbar en ruimte bij een lange vraag`, async ({ page }) => {
        test.setTimeout(90_000)
        await open(page)
        await verbonden(page)

        const rust = await rects(page)
        const leftLeeg = await left(page)
        const meerActiesLeeg = await page.getByRole('button', { name: 'Meer acties' }).count()
        await page.evaluate(startMonsters)
        const start = await nu(page)

        const veld = page.locator('textarea.chat-input')
        await veld.tap()
        await veld.pressSequentially(VRAAG, { delay: 10 })
        await volgendFrame(page)
        const laatsteToets = await nu(page)

        await page.getByRole('button', { name: 'Verstuur bericht' }).tap()
        const tikMoment = await nu(page)
        await expect(page.locator('.message.user')).toHaveCount(1)
        await expect(page.locator('.message-bubble-assistant')).toContainText('CBS-tabel', { timeout: 10_000 })
        await page.waitForTimeout(Math.max(0, tikMoment + VENSTER_MS + 200 - (await nu(page))))

        const monsters = await page.evaluate(() => {
          cancelAnimationFrame(window.__monsterFrame)
          return window.__monsters
        })
        const shifts = (await page.evaluate(() => window.__cls)).filter(s => s.t <= tikMoment + VENSTER_MS)
        const cls = shifts.reduce((som, s) => som + s.waarde, 0)
        const leftNa = await left(page)
        const meerActiesNa = await page.getByRole('button', { name: 'Meer acties' }).count()

        // Criterium 7: een lange vervolgvraag in een gesprek van twee berichten.
        const veldHoogtes = []
        await veld.tap()
        for (const teken of VERVOLG) {
          await veld.pressSequentially(teken)
          veldHoogtes.push(await veld.evaluate(el => el.getBoundingClientRect().height))
        }
        const ruimte = await page.evaluate(() => {
          const lijst = document.querySelector('.chat-messages')
          lijst.scrollTop = lijst.scrollHeight
          return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => {
            const berichten = document.querySelectorAll('.message')
            r({
              berichten: berichten.length,
              laatsteOnder: berichten[berichten.length - 1].getBoundingClientRect().bottom,
              pilTop: document.querySelector('.chat-input-wrap').getBoundingClientRect().top,
              scrolt: lijst.scrollHeight > lijst.clientHeight,
            })
          })))
        })

        const naToets = monsters.filter(m => m.t >= laatsteToets && m.t <= tikMoment + VENSTER_MS)
        const totToets = monsters.filter(m => m.t >= start && m.t <= laatsteToets)
        const meting = {
          maat, sessie, build: process.env.VOOR_DIST ? 'voor' : 'na', cls, rust,
          shifts: shifts.map(s => ({ ...s, t: Math.round(s.t - tikMoment) })),
          areaNaToets: {
            min: Math.min(...naToets.map(m => m.area)), max: Math.max(...naToets.map(m => m.area)), n: naToets.length,
          },
          welkom: Object.fromEntries(['icoon', 'kop', 'suggesties'].map(k => [k, spreiding(totToets.map(m => m[k]))])),
          leftLeeg, leftNa, meerActiesLeeg, meerActiesNa,
          veldHoogtes: [...new Set(veldHoogtes.map(h => Math.round(h * 10) / 10))], ruimte,
        }
        noteer(meting)

        // 1: CLS van de navigatie tot 15 s na de tik op versturen.
        expect(cls, JSON.stringify(meting.shifts)).toBeLessThan(0.1)
        // 2: het invoergebied staat stil van de laatste toets tot 15 s na de tik, op zijn plek in de lege staat.
        expect(naToets.length).toBeGreaterThan(100)
        expect(meting.areaNaToets.max - meting.areaNaToets.min, JSON.stringify(meting.areaNaToets))
          .toBeLessThanOrEqual(HALVE_PX)
        expect(binnen(meting.areaNaToets.min, rust['.chat-input-area'].top)).toBe(true)
        // 4: het welkomstscherm staat stil tot de laatste toets, en is nergens een bron van een verschuiving.
        for (const [deel, verschil] of Object.entries(meting.welkom)) expect(verschil, deel).toBeLessThanOrEqual(HALVE_PX)
        expect(totToets.every(m => m.icoon !== null && m.kop !== null && m.suggesties !== null)).toBe(true)
        expect(shifts.flatMap(s => s.bronnen).filter(b => b.verboden)).toEqual([])
        // 5: de rusttoestand is die van main.
        verwachtRects(rust, MAIN[maat])
        // 6: de gesprekkenknop blijft staan, het ⋯-menu komt pas met het gesprek.
        expect(meerActiesLeeg).toBe(0)
        expect(meerActiesNa).toBe(1)
        expect(binnen(leftNa, leftLeeg), `${leftLeeg} -> ${leftNa}`).toBe(true)
        // 7: met een lange vraag scrolt het eind van het gesprek tot boven de pil; het veld groeit als op main.
        expect(ruimte.berichten).toBe(2)
        expect(ruimte.scrolt).toBe(true)
        expect(ruimte.laatsteOnder, JSON.stringify(ruimte)).toBeLessThanOrEqual(ruimte.pilTop)
        expect(meting.veldHoogtes).toEqual([42, 66, 90, 114, 120])
      })
    }

    test('verbindingsregel in beeld of niet: invoergebied en berichtenlijst op dezelfde plek (criterium 3)', async ({ page }) => {
      const staat = { dicht: true }
      await open(page, staat)
      await expect(page.locator('.ws-reconnecting')).toHaveText('Verbinding herstellen...')
      await volgendFrame(page)
      const dicht = await rects(page)

      staat.dicht = false
      await page.reload()
      await verbonden(page)
      const verbondenRects = await rects(page)

      noteer({ maat, build: process.env.VOOR_DIST ? 'voor' : 'na', verbinding: { dicht, open: verbondenRects } })
      expect(binnen(dicht['.chat-input-area'].top, verbondenRects['.chat-input-area'].top), JSON.stringify({ dicht, verbondenRects }))
        .toBe(true)
      expect(binnen(dicht['.chat-messages'].height, verbondenRects['.chat-messages'].height)).toBe(true)
    })
  })
}

test.describe('desktop 1366x768: de rusttoestand is die van main (criterium 5)', () => {
  test.use({ viewport: { width: 1366, height: 768 } })

  test('berichten, invoergebied en invoerkader', async ({ page }) => {
    await open(page)
    await verbonden(page)
    const rust = await rects(page)
    noteer({ maat: '1366x768', build: process.env.VOOR_DIST ? 'voor' : 'na', rust })
    verwachtRects(rust, MAIN['1366x768'])
  })
})
