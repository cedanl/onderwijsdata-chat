// #606, #611: een lang woord of een URL zonder spaties in een bubbel (en een tabel die breder is dan de bubbel), en
// het tikvlak van een citaatgetal tussen gestapelde getallen. Gemeten in de gebouwde app op 390 px (aanraking) en
// 1366 px. Draait zonder LLM: de chat-socket is nagebootst en geeft per vraag een vast antwoord. Niet in CI.
// Draaien: `npx playwright test mobiel-tikvlakken` (playwright.config.js).
import { test, expect, devices } from 'playwright/test'
import { handleLoginIfNeeded } from './helpers.js'

const TIK = 44

const VRAAG_LANG_WOORD = 'Wat betekent dit woord? ' + 'onderwijsdata'.repeat(250)
const VRAAG_URL = 'Waar staat de tabel?'
const VRAAG_TABEL = 'Zet alles in een tabel.'
const VRAAG_CIJFERS = 'Hoeveel studenten zijn er per niveau?'
const VRAAG_KOPIEER = 'Geef alleen de getallen.'

const LANGE_URL = 'https://opendata.cbs.nl/statline/#/CBS/nl/dataset/85423NED/table?dl=' + '9A3F0C1D'.repeat(50)
// Breder dan een telefoon: zeven kolommen waarin de getallen het breedst zijn.
const BREDE_TABEL = [
  '| Jaar | mbo | hbo | wo | totaal | groei mbo | groei hbo |',
  '|---|---|---|---|---|---|---|',
  '| 2022 | 507.890 | 489.430 | 335.100 | 1.332.420 | 1,2% | 1,9% |',
  '| 2023 | 512.345 | 498.765 | 341.200 | 1.352.310 | 0,9% | 1,9% |',
].join('\n')

// Getallen met hun herkomst, zoals de server ze na de controle meestuurt (agent/citaties.py).
const citatie = (getal, selectie) => ({
  getal, vastgesteld: true, label: 'CBS-data ophalen', stap: 1, bron: 'CBS StatLine 85423NED', selectie,
  maat: 'Ingeschreven studenten', data_key: `cbs:85423NED:${getal}`,
})

// Eén getal midden in een alinea met gewone tekst eromheen, twee getallen ver uit elkaar op een regel, en gestapelde
// getallen: een lijst en een tabel met één getal per regel.
const CIJFERS_TEKST = [
  'Hieronder staan de aantallen ingeschreven studenten uit de CBS-tabel, per onderwijsniveau en per jaar, zoals ze ' +
    'in de opgehaalde data staan.',
  'Het mbo telde in dat jaar 512.345 ingeschreven studenten, iets meer dan het jaar ervoor; de groei zat vooral in ' +
    'de bol-opleidingen, terwijl de bbl-opleidingen ongeveer gelijk bleven. Over de hele periode zijn de verschillen ' +
    'klein gebleven.',
  'De regionale spreiding is vrijwel hetzelfde als in eerdere jaren.',
  'Het hbo kwam uit op 498.765 studenten en het wo op 341.200.',
  'Per sector in het mbo:',
  '- Economie: 120.450\n- Techniek: 98.310\n- Zorg en welzijn: 143.220',
  '| Jaar | mbo | hbo |\n|---|---|---|\n| 2021 | 501.230 | 480.110 |\n| 2022 | 507.890 | 489.430 |\n' +
    '| 2023 | 511.002 | 497.001 |',
  'Dit is de laatste zin, zonder getallen, zodat de onderste regel gewone tekst is.',
].join('\n\n')
const CIJFERS = [
  ['512.345', 'mbo'], ['498.765', 'hbo'], ['341.200', 'wo'], ['120.450', 'mbo, economie'], ['98.310', 'mbo, techniek'],
  ['143.220', 'mbo, zorg en welzijn'], ['501.230', 'mbo, 2021'], ['480.110', 'hbo, 2021'], ['507.890', 'mbo, 2022'],
  ['489.430', 'hbo, 2022'], ['511.002', 'mbo, 2023'], ['497.001', 'hbo, 2023'],
].map(([getal, selectie]) => citatie(getal, selectie))

// Een alinea vol getallen: de bovenste regel loopt onder de kopieerknop van het antwoord door.
const KOPIEER_GETALLEN = Array.from({ length: 60 }, (_, i) => `1.${String(i + 1).padStart(3, '0')}`)

function antwoord(content, { citaties = [] } = {}) {
  return [{ type: 'message_start' }, { type: 'text_delta', content }, { type: 'message_end', content, citaties }]
}

const ANTWOORDEN = {
  [VRAAG_LANG_WOORD]: antwoord('Dat is geen bestaand woord; het is het woord onderwijsdata vele keren achter elkaar.'),
  [VRAAG_URL]: antwoord(`Je vindt de tabel hier: ${LANGE_URL}\n\nDaar staat ook de toelichting bij de cijfers.`),
  [VRAAG_TABEL]: antwoord(BREDE_TABEL),
  [VRAAG_CIJFERS]: antwoord(CIJFERS_TEKST, { citaties: CIJFERS }),
  [VRAAG_KOPIEER]: antwoord(KOPIEER_GETALLEN.join(' '), { citaties: KOPIEER_GETALLEN.map(g => citatie(g, 'mbo')) }),
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
  ['telefoon', (({ defaultBrowserType: _, ...apparaat }) => apparaat)(devices['iPhone 14']), true],
  ['desktop', { viewport: { width: 1366, height: 768 } }, false],
]

for (const [naam, apparaat, aanraking] of TOESTELLEN) {
  test.describe(`mobiele tikvlakken en bubbels, ${naam} (${apparaat.viewport.width} px)`, () => {
    test.use(apparaat)
    const tik = locator => (aanraking ? locator.tap() : locator.click())

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

    // Op een telefoon is het onzichtbare vlak rond een getal 44 px (#598), op desktop 24 px (#517 A2).
    const bereik = aanraking ? 20 : 10

    test(`een tik binnen het eigen getal raakt dat getal, ook tussen gestapelde getallen (#611)`, async ({ page }) => {
      await stuur(page, VRAAG_CIJFERS)
      await expect(page.locator('.citatie-getal')).toHaveCount(CIJFERS.length)
      const uitslag = await page.evaluate(meetCitaten, { bereik, tik: TIK })
      // Beide soorten moeten erin zitten, anders bewijst de meting niets.
      expect(uitslag.vrij.length, JSON.stringify(uitslag)).toBeGreaterThanOrEqual(2)
      expect(uitslag.gestapeld.length, JSON.stringify(uitslag)).toBeGreaterThanOrEqual(6)
      // Getallen met ruimte eromheen: het hele bereik vanaf het midden is van het getal (#598; regressievangnet).
      expect(uitslag.missersBereik).toEqual([])
      // Gestapelde getallen: de bewuste ondergrens is het eigen vak van het getal, onderste helft inbegrepen.
      expect(uitslag.missersEigenVak).toEqual([])
    })

    test('een open herkomst blijft liggen over de getallen eronder (#611)', async ({ page }) => {
      await stuur(page, VRAAG_CIJFERS)
      const knop = page.getByRole('button', { name: '501.230, herkomst tonen' })
      await tik(knop)
      await expect(knop).toHaveAttribute('aria-expanded', 'true')
      const uitleg = page.locator('.citatie-uitleg')
      await expect(uitleg).toBeVisible()
      const uitslag = await uitleg.evaluate(bovenGetallen)
      expect(uitslag.onder).toBeGreaterThan(0)
      expect(uitslag.mis, JSON.stringify(uitslag)).toEqual([])
    })

    test('het getal blijft een knop: tikken, Enter, spatie en Escape (#611)', async ({ page }) => {
      await stuur(page, VRAAG_CIJFERS)
      const knop = page.getByRole('button', { name: '120.450, herkomst tonen' })
      await tik(knop)
      await expect(knop).toHaveAttribute('aria-expanded', 'true')
      await tik(knop)
      await expect(knop).toHaveAttribute('aria-expanded', 'false')
      await knop.focus()
      await page.keyboard.press('Enter')
      await expect(knop).toHaveAttribute('aria-expanded', 'true')
      await page.keyboard.press('Escape')
      await expect(knop).toHaveAttribute('aria-expanded', 'false')
      await expect(knop).toBeFocused()
      await page.keyboard.press('Space')
      await expect(knop).toHaveAttribute('aria-expanded', 'true')
      await page.keyboard.press('Escape')
      await expect(knop).toHaveAttribute('aria-expanded', 'false')
    })

    test('de kopieerknop blijft boven een getal dat eronder doorloopt (#611)', async ({ page }) => {
      await stuur(page, VRAAG_KOPIEER)
      await expect(page.locator('.citatie-getal')).toHaveCount(KOPIEER_GETALLEN.length)
      const uitslag = await page.locator('.message-bubble-assistant .copy-btn-message').last().evaluate(bovenGetallen)
      // Op een telefoon is de knop 44 px en ligt hij over de eerste twee regels; op desktop ligt er geen getal onder.
      if (aanraking) expect(uitslag.onder).toBeGreaterThan(0)
      expect(uitslag.mis, JSON.stringify(uitslag)).toEqual([])
    })
  })
}

// Of `el` boven de citaatgetallen eronder ligt: een tik op zijn midden en op het midden van elke overlap met een getal
// moet `el` raken. `onder` telt de getallen eronder.
function bovenGetallen(el) {
  el.scrollIntoView({ block: 'center', behavior: 'instant' })
  const vak = el.getBoundingClientRect()
  const punten = [[vak.left + vak.width / 2, vak.top + vak.height / 2]]
  for (const getal of document.querySelectorAll('.citatie-getal')) {
    const r = getal.getBoundingClientRect()
    const links = Math.max(r.left, vak.left), rechts = Math.min(r.right, vak.right)
    const boven = Math.max(r.top, vak.top), beneden = Math.min(r.bottom, vak.bottom)
    if (links < rechts && boven < beneden) punten.push([(links + rechts) / 2, (boven + beneden) / 2])
  }
  return { onder: punten.length - 1, mis: punten.filter(([x, y]) => !el.contains(document.elementFromPoint(x, y))) }
}

// Per citaatgetal: zijn onzichtbare vlak (::before) en zijn eigen vak. Een getal heet gestapeld als het midden van een
// ander getal minder dan `tik` px weg ligt, of het vlak van een ander getal in zijn bereik (midden ± bereik) valt;
// anders moet elk punt in dat bereik het eigen getal raken. Voor elk getal moet elk punt in het eigen vak (1 px binnen
// de randen) het eigen getal raken. Elk getal wordt eerst in het midden van de kolom gescrold, zodat de meetpunten in
// beeld liggen.
function meetCitaten({ bereik, tik }) {
  const knoppen = [...document.querySelectorAll('.message-bubble-assistant .citatie-getal')]
  const raakt = (knop, x, y) => knop.contains(document.elementFromPoint(x, y))
  const vrij = [], gestapeld = [], missersBereik = [], missersEigenVak = []
  for (const knop of knoppen) {
    knop.scrollIntoView({ block: 'center', behavior: 'instant' })
    const vakken = knoppen.map(k => {
      const r = k.getBoundingClientRect()
      const voor = getComputedStyle(k, '::before')
      const b = parseFloat(voor.width), h = parseFloat(voor.height)
      const x = r.left + r.width / 2, y = r.top + r.height / 2
      return { r, x, y, vlak: { left: x - b / 2, right: x + b / 2, top: y - h / 2, bottom: y + h / 2 } }
    })
    const eigen = vakken[knoppen.indexOf(knop)]
    const naam = knop.textContent
    const buren = vakken.filter(v => v !== eigen && (Math.hypot(v.x - eigen.x, v.y - eigen.y) < tik ||
      (v.vlak.left < eigen.x + bereik && v.vlak.right > eigen.x - bereik &&
        v.vlak.top < eigen.y + bereik && v.vlak.bottom > eigen.y - bereik)))
    if (buren.length) gestapeld.push(naam)
    else {
      vrij.push(naam)
      const stappen = [...new Set([10, bereik])]
      const offsets = [[0, 0], ...stappen.flatMap(d => [[0, -d], [0, d], [-d, 0], [d, 0]])]
      for (const [dx, dy] of offsets) {
        if (!raakt(knop, eigen.x + dx, eigen.y + dy)) missersBereik.push(`${naam} (${dx},${dy})`)
      }
    }
    const { r } = eigen
    const xs = [r.left + 1, r.left + r.width / 4, r.left + r.width / 2, r.left + (3 * r.width) / 4, r.right - 1]
    const ys = [r.top + 1, r.top + r.height / 4, r.top + r.height / 2, r.top + (3 * r.height) / 4, r.bottom - 1]
    for (const x of xs) for (const y of ys) {
      if (!raakt(knop, x, y)) {
        const ander = document.elementFromPoint(x, y)?.closest('.citatie-getal')?.textContent
        const plek = `(${Math.round(x - r.left)},${Math.round(y - r.top)})`
        missersEigenVak.push(`${naam} ${plek} -> ${ander ?? 'iets anders'}`)
      }
    }
  }
  return { vrij, gestapeld, missersBereik, missersEigenVak }
}
