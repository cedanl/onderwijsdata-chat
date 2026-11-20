// #1071: een gedeelde link naar Mijn instelling opent bij de ontvanger dezelfde instelling, ook zonder of met een
// ander profiel, en verandert dat profiel niet. #1078: de eerste kerncijfertegel staat op het eerste scherm, op
// mobiel en desktop, voor een hogeschool, een mbo-instelling en een universiteit; de kaart komt erna.
//
// De dashboardladingen en de lijst van instellingen zijn nagebootst (verzonnen getallen, met een kaart), zodat de
// meting niets van DUO nodig heeft. Niet in CI. Draaien: `npx playwright test dashboard-deellink`.
import { test, expect } from 'playwright/test'
import { handleLoginIfNeeded } from './helpers.js'

const MIJN = '__builtin_mijn_instelling__'
const STORAGE_SETTINGS = 'openEDUdata_settings'
const STORAGE_ONBOARDED = 'openEDUdata_onboarded'

const INSTELLINGEN = [
  { naam: 'Hogeschool Rotterdam', type: 'hbo', aliassen: [] },
  { naam: 'ROC Midden Nederland', type: 'mbo', aliassen: [] },
  { naam: 'Universiteit Utrecht', type: 'wo', aliassen: [] },
]

const reeks = basis => Object.fromEntries([2019, 2020, 2021, 2022, 2023].map((j, i) => [String(j), basis + i * 100]))

const kaart = naam => JSON.stringify({
  data: [
    { type: 'scattergeo', mode: 'markers', name: 'Concurrenten', lon: [4.9], lat: [52.37], text: ['Andere instelling'] },
    { type: 'scattergeo', mode: 'markers+text', name: naam, lon: [5.11], lat: [52.09], text: [naam] },
  ],
  layout: {
    height: 340,
    geo: { scope: 'europe', resolution: 50 },
    meta: { data: [{ Instelling: naam, Plaats: 'Utrecht', Rol: 'eigen instelling' }], zonder_locatie: [] },
  },
})

// Een regiolading zoals /api/dashboard/regio die geeft, ingekort tot wat de bovenkant van de pagina gebruikt.
const regio = (naam, type) => ({
  gevonden: true,
  instelling: naam,
  type,
  provincie: 'Utrecht',
  provincie_herkomst: 'adres',
  arbeidsmarktregio: 'Midden-Utrecht',
  ingeschrevenen: reeks(20000),
  eerstejaars: reeks(5000),
  gediplomeerden: reeks(3000),
  geslacht: { VROUW: 11000, MAN: 9400 },
  perioden: { ingeschrevenen: 'schooljaar', eerstejaars: 'schooljaar', gediplomeerden: 'diplomajaar' },
  benchmark: {
    populatie: `${type}-instellingen in provincie Utrecht`,
    label: `${type}-instellingen in provincie Utrecht (4 instellingen)`,
    ingeschrevenen: reeks(15000), eerstejaars: reeks(4000), gediplomeerden: reeks(2500),
  },
  kaart_figure_json: kaart(naam),
  bronnen: [{ naam: 'DUO', url: 'https://duo.nl/open_onderwijsdata/' }],
})

async function nabootsen(page) {
  // De dashboards staan lokaal standaard uit (ENABLE_DASHBOARDS); hun ladingen zijn hier toch nagebootst.
  await page.route(/\/api\/config(\?|$)/, async route => {
    const antwoord = await route.fetch()
    route.fulfill({ response: antwoord, json: { ...(await antwoord.json()), dashboards_enabled: true } })
  })
  await page.route(/\/api\/instellingen(\?|$)/, route => route.fulfill({ json: INSTELLINGEN }))
  await page.route(/\/api\/dashboard\/[a-z_]+\?/, route => {
    const url = new URL(route.request().url())
    const naam = url.searchParams.get('instelling')
    if (url.pathname.endsWith('/regio')) {
      const type = INSTELLINGEN.find(i => i.naam === naam)?.type ?? 'hbo'
      return route.fulfill({ json: regio(naam, type) })
    }
    return route.fulfill({ json: { instelling: naam } })
  })
}

const link = naam => `/dashboards?${new URLSearchParams({ id: MIJN, instelling: naam })}`

test.describe('gedeelde dashboardlink draagt de instelling (#1071)', () => {
  test.use({ viewport: { width: 1280, height: 800 } })

  test('zonder profiel: de instelling uit de link', async ({ page }) => {
    await nabootsen(page)
    await page.goto(link('ROC Midden Nederland'))
    await handleLoginIfNeeded(page)
    await expect(page.locator('.meta-badge.instelling').first()).toHaveText('ROC Midden Nederland')
  })

  test('met een ander profiel: de link wint, het profiel blijft', async ({ page }) => {
    const profiel = JSON.stringify({ instelling: 'Hogeschool Rotterdam' })
    await page.addInitScript(([sleutel, waarde, gezien]) => {
      if (!localStorage.getItem(sleutel)) localStorage.setItem(sleutel, waarde)
      localStorage.setItem(gezien, '1')
    }, [STORAGE_SETTINGS, profiel, STORAGE_ONBOARDED])
    await nabootsen(page)
    await page.goto(link('Universiteit Utrecht'))
    await handleLoginIfNeeded(page)
    await expect(page.locator('.meta-badge.instelling').first()).toHaveText('Universiteit Utrecht')
    expect(await page.evaluate(k => localStorage.getItem(k), STORAGE_SETTINGS)).toBe(profiel)
    // Terug naar de galerij: id en instelling gaan uit de URL.
    await page.locator('.wb-back-btn').click()
    await expect(page).toHaveURL(/\/dashboards$/)
  })
})

for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 800 }]) {
  for (const { naam, type } of INSTELLINGEN) {
    test(`eerste kerncijfer op het eerste scherm, ${type} ${viewport.width}x${viewport.height} (#1078)`, async ({ page }) => {
      await page.setViewportSize(viewport)
      await nabootsen(page)
      await page.goto(link(naam))
      await handleLoginIfNeeded(page)
      const tegel = page.locator('.kpi-card').first()
      await expect(tegel).toBeVisible()
      const boven = await tegel.evaluate(el => el.getBoundingClientRect().top)
      expect(boven).toBeLessThan(viewport.height)
      // De kaart staat na de kerncijfers in de DOM, dus ook op papier.
      const kaartNaKpi = await page.evaluate(() => {
        const kpi = document.querySelector('.kpi-grid')
        const kaartKop = [...document.querySelectorAll('.dashboard-content *')].find(el => el.textContent.trim() === 'Locaties in de regio')
        return Boolean(kpi && kaartKop && (kpi.compareDocumentPosition(kaartKop) & Node.DOCUMENT_POSITION_FOLLOWING))
      })
      expect(kaartNaKpi).toBe(true)
    })
  }
}
