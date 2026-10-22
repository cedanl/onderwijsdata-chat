// #606, #611, #612: een lang woord of een URL zonder spaties in een bubbel (en een tabel die breder is dan de bubbel),
// het tikvlak van een citaatgetal tussen gestapelde getallen, de laatste kleine tikdoelen op een telefoon en een
// invoerveld dat verspringt door de tekenteller. Gemeten in de gebouwde app op 390 px (aanraking) en 1366 px. Draait
// zonder LLM: de chat-socket is nagebootst en geeft per vraag een vast antwoord. Niet in CI. Draaien:
// `npx playwright test mobiel-tikvlakken` (playwright.config.js).
import { test, expect, devices } from 'playwright/test'
import { handleLoginIfNeeded } from './helpers.js'

const TIK = 44

const VRAAG_LANG_WOORD = 'Wat betekent dit woord? ' + 'onderwijsdata'.repeat(250)
const VRAAG_URL = 'Waar staat de tabel?'
const VRAAG_TABEL = 'Zet alles in een tabel.'
const VRAAG_CIJFERS = 'Hoeveel studenten zijn er per niveau?'
const VRAAG_TABEL_RIJ = 'Zet de studenten per sector in een tabel.'
// #661: kort genoeg om op één regel te passen, lang genoeg dat een extra 30 px naast de bubbel hem opzij duwt.
const VRAAG_KORT = 'Toon de studenten per niveau'
const VRAAG_WACHT = 'Wacht even.'
const VRAAG_KOPIEER = 'Geef alleen de getallen.'
const VRAAG_GRAFIEK = 'Toon de studenten per niveau in een grafiek.'

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

// Eén getal per tabelrij (#662): de rijen staan dichter op elkaar dan een tikvlak, dus elk getal is gestapeld.
const TABEL_RIJ_CIJFERS = [
  ['Economie', '120.450'], ['Techniek', '98.310'], ['Zorg en welzijn', '143.220'], ['Landbouw', '21.004'],
  ['Gedrag en maatschappij', '33.870'],
]
const TABEL_RIJ = [
  '| Sector | Studenten |', '|---|---|', ...TABEL_RIJ_CIJFERS.map(([sector, getal]) => `| ${sector} | ${getal} |`),
].join('\n')
const CIJFERS_RIJ = TABEL_RIJ_CIJFERS.map(([sector, getal]) => citatie(getal, `mbo, ${sector.toLowerCase()}`))

// Een alinea vol getallen: de bovenste regel loopt op desktop onder de kopieerknop van het antwoord door. Op een
// telefoon hangt die knop in de goot naast de tekstkolom (#623), zodat er geen getal meer onder ligt.
const KOPIEER_GETALLEN = Array.from({ length: 60 }, (_, i) => `1.${String(i + 1).padStart(3, '0')}`)

const FIGUUR = {
  data: [{ type: 'bar', name: 'Studenten', x: ['mbo', 'hbo', 'wo'], y: [512345, 498765, 341200] }],
  layout: { title: { text: 'Ingeschreven studenten per niveau' } },
}
// Bewust langer dan twee regels op 390 px: de meting hieronder vraagt dat het onzichtbare vlak van de CSV-knop
// onder de kopieerknop van het antwoord begint (verticale voorwaarde), en bij een antwoord van één regel komt de
// grafiek dichter tegen de eerste regel liggen. Zo'n kort antwoord gaf op main ook een horizontale overlap met die
// knop, zelfde patroon als #623; die is weg zodra de knop van het bericht in de goot naast de kolom hangt.
const GRAFIEK_TEKST = 'In de grafiek staan de ingeschreven studenten per onderwijsniveau, zoals ze in de opgehaalde ' +
  'CBS-tabel staan: het mbo is het grootst, het hbo volgt kort daarna en het wo is het kleinst.'

function antwoord(content, { citaties = [], stap = null, figuur = null } = {}) {
  const events = [{ type: 'message_start' }]
  if (stap) {
    events.push({ type: 'tool_start', name: 'cbs_query', label: 'CBS-data ophalen' })
    events.push({ type: 'tool_end', name: 'cbs_query', snippet: stap })
  }
  if (figuur) events.push({ type: 'figure', label: 'Studenten per niveau', figure_json: JSON.stringify(figuur) })
  events.push({ type: 'text_delta', content }, { type: 'message_end', content, citaties })
  return events
}

const ANTWOORDEN = {
  [VRAAG_LANG_WOORD]: antwoord('Dat is geen bestaand woord; het is het woord onderwijsdata vele keren achter elkaar.'),
  [VRAAG_URL]: antwoord(`Je vindt de tabel hier: ${LANGE_URL}\n\nDaar staat ook de toelichting bij de cijfers.`),
  [VRAAG_TABEL]: antwoord(BREDE_TABEL),
  [VRAAG_CIJFERS]: antwoord(CIJFERS_TEKST, { citaties: CIJFERS }),
  [VRAAG_KORT]: antwoord('Het mbo is het grootst, het hbo volgt kort daarna en het wo is het kleinst.'),
  // Geen message_end: de app blijft bezig, zoals midden in een antwoord.
  [VRAAG_WACHT]: [{ type: 'message_start' }, { type: 'text_delta', content: 'Een moment' }],
  [VRAAG_TABEL_RIJ]: antwoord(TABEL_RIJ, { citaties: CIJFERS_RIJ }),
  [VRAAG_KOPIEER]: antwoord(KOPIEER_GETALLEN.join(' '), { citaties: KOPIEER_GETALLEN.map(g => citatie(g, 'mbo')) }),
  [VRAAG_GRAFIEK]: antwoord(GRAFIEK_TEKST, {
    stap: "df = cbs.get_data('85423NED')\nprint(df.groupby('niveau').sum())", figuur: FIGUUR,
  }),
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

const volgendFrame = page =>
  page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))))

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

    // #662: in een tabel met één getal per rij liggen de middens minder dan een tikvlak uit elkaar (op een telefoon 26 px,
    // een vlak van 44 px). Een punt 20 px onder een getal ligt dan in het eigen vak van het getal eronder en hoort daar
    // bij; dat is de bewuste ondergrens van #611, geen gemist tikvlak. Wat wel moet: elk punt in het eigen vak, de
    // zijkanten en de boven- en onderrand inbegrepen, raakt dat getal en niet de cel of rij eromheen.
    test('een getal in een tabelrij met één getal per rij blijft in zijn eigen vak te raken (#662)', async ({ page }) => {
      await stuur(page, VRAAG_TABEL_RIJ)
      await expect(page.locator('.tabel-scroll .citatie-getal')).toHaveCount(CIJFERS_RIJ.length)
      const uitslag = await page.evaluate(meetCitaten, { bereik, tik: TIK })
      // Alle getallen zijn gestapeld; zo niet, dan meet deze test niets van wat het issue beschrijft.
      expect(uitslag.vrij, JSON.stringify(uitslag)).toEqual([])
      expect(uitslag.gestapeld, JSON.stringify(uitslag)).toHaveLength(CIJFERS_RIJ.length)
      expect(uitslag.missersEigenVak).toEqual([])
    })

    // #661: de herhaalknop naast een vraag bestond alleen als er geen antwoord liep. Hij verscheen dus bij het eind van
    // elk antwoord, verbreedde elke vraag in het gesprek met 30 px en schoof de bubbel opzij (CLS tot 0,38 bij een korte
    // vraag). Nu staat hij er altijd en is hij tijdens een antwoord alleen verborgen.
    test('een eerdere vraag verspringt niet als er een antwoord loopt (#661)', async ({ page }) => {
      await stuur(page, VRAAG_KORT)
      const eerste = page.locator('.message.user').first()
      const vakken = () => eerste.evaluate(el => {
        const rect = e => { const r = e.getBoundingClientRect(); return [r.left, r.width, r.height] }
        return { bericht: rect(el), bubbel: rect(el.querySelector('.message-bubble')) }
      })
      const rust = await vakken()
      await expect(eerste.locator('.resend-btn')).toBeEnabled()

      const veld = page.locator('textarea.chat-input')
      await veld.fill(VRAAG_WACHT)
      await veld.press('Enter')
      await expect(page.locator('.message.user')).toHaveCount(2)
      await expect(page.locator('.message-bubble-assistant').last()).toContainText('Een moment')
      await expect(eerste.locator('.resend-btn')).toBeDisabled()
      const bezig = await vakken()
      for (const deel of ['bericht', 'bubbel']) {
        bezig[deel].forEach((waarde, i) => expect(waarde, `${deel} ${i}: ${JSON.stringify({ rust, bezig })}`).toBeCloseTo(rust[deel][i], 0))
      }
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

    test('de kopieerknop blijft boven een getal dat eronder doorloopt (#611), en staat op een telefoon naast de kolom (#623)', async ({ page }) => {
      await stuur(page, VRAAG_KOPIEER)
      await expect(page.locator('.citatie-getal')).toHaveCount(KOPIEER_GETALLEN.length)
      const uitslag = await page.locator('.message-bubble-assistant .copy-btn-message').last().evaluate(bovenGetallen)
      // Op een telefoon hangt de 44px-knop in de goot naast de tekstkolom (#623), zodat er geen getal onder ligt;
      // op desktop blijft hij op de rand van die kolom staan en loopt de volle alinea er wel onder door.
      if (aanraking) expect(uitslag.onder).toBe(0)
      expect(uitslag.mis, JSON.stringify(uitslag)).toEqual([])
    })

    test('het invoerveld verspringt niet door de tekenteller (#612)', async ({ page }) => {
      const veld = page.locator('textarea.chat-input')
      const teller = page.locator('#message-counter')
      const top = async () => {
        await volgendFrame(page)
        return page.locator('.chat-input-wrap').evaluate(el => el.getBoundingClientRect().top)
      }
      // Op desktop is het lege veld 22,8 px (1 regel van 14,25 px x 1,6) en zet de auto-grow bij de eerste toets de
      // afgeronde scrollHeight van 23 px: een verschil onder een pixel, geen sprong. Daarom hier op een halve pixel.
      const leeg = await top()
      await veld.fill('a')
      expect(await top()).toBeCloseTo(leeg, 0)
      await veld.fill('')
      expect(await top()).toBeCloseTo(leeg, 0)

      await veld.fill('a'.repeat(3199))
      await expect(teller).toHaveText('')
      const bijna = await top()
      await veld.fill('a'.repeat(3200))
      await expect(teller).toContainText('3200 / 4000')
      expect(await top()).toBe(bijna)

      await veld.fill('a'.repeat(4000))
      const grens = await top()
      await veld.fill('a'.repeat(4001))
      await expect(teller).toContainText('te lang')
      expect(await top()).toBe(grens)

      // De teller staat in beeld en niet over de verstuurknop heen.
      const [tel, knop] = await Promise.all(['#message-counter', '.send-btn'].map(s =>
        page.locator(s).evaluate(el => el.getBoundingClientRect().toJSON())))
      expect(tel.width).toBeGreaterThan(0)
      expect(tel.left).toBeGreaterThanOrEqual(0)
      expect(tel.right).toBeLessThanOrEqual(apparaat.viewport.width)
      const naast = tel.right <= knop.left || tel.left >= knop.right || tel.bottom <= knop.top || tel.top >= knop.bottom
      expect(naast, JSON.stringify({ tel, knop })).toBe(true)
    })

    if (aanraking) {
      test('de laatste kleine tikdoelen zijn 44 px, ook via een ::before (#612)', async ({ page }) => {
        await stuur(page, VRAAG_GRAFIEK)
        await expect(page.locator('.csv-download-btn')).toBeAttached()
        // Alle stappen komen in één keer binnen, dus de redenering kan al dicht zijn; de code staat erin.
        const redenering = page.locator('.reasoning-toggle').first()
        if ((await redenering.getAttribute('aria-expanded')) === 'false') await tik(redenering)
        const maten = {}
        for (const kiezer of ['.csv-download-btn', '.reasoning-toggle', '.reasoning-step-code summary']) {
          maten[kiezer] = await page.locator(kiezer).first().evaluate(tikvlak)
        }
        // Voorwaarde voor de randen hieronder (zie GRAFIEK_TEKST): het vlak van de CSV-knop begint onder de kopieerknop.
        const csv = await page.locator('.csv-download-btn').first().evaluate(el => {
          const r = el.getBoundingClientRect()
          const kopieer = el.closest('.message-bubble').querySelector('.copy-btn-message').getBoundingClientRect()
          return { midden: r.top + r.height / 2, kopieerOnder: kopieer.bottom }
        })
        expect(csv.midden - maten['.csv-download-btn'].hoogte / 2, JSON.stringify(csv))
          .toBeGreaterThanOrEqual(csv.kopieerOnder)

        await tik(page.getByRole('button', { name: 'Meer acties' }))
        await tik(page.getByRole('button', { name: 'Exporteer gesprek' }))
        for (const kiezer of ['.confirm-cancel', '.confirm-primary']) {
          maten[kiezer] = await page.locator(kiezer).evaluate(tikvlak)
        }
        await tik(page.locator('.confirm-cancel'))

        await tik(page.getByRole('button', { name: 'Gesprekken en suggesties' }))
        maten['.history-search'] = await page.locator('.history-search').evaluate(tikvlak)
        // De verwijderknop staat in de lade die nog inschuift; de dialoog is wat telt.
        await page.locator('.history-action-icon-delete').first().dispatchEvent('click')
        maten['.confirm-destructive'] = await page.locator('.confirm-destructive').evaluate(tikvlak)

        for (const [kiezer, maat] of Object.entries(maten)) {
          expect(maat.hoogte, `${kiezer}: ${JSON.stringify(maat)}`).toBeGreaterThanOrEqual(TIK)
          expect(maat.breedte, `${kiezer}: ${JSON.stringify(maat)}`).toBeGreaterThanOrEqual(TIK)
        }
        // Het onzichtbare vlak van de CSV-knop ligt boven de grafiek: een tik aan de rand ervan raakt de knop.
        expect(maten['.csv-download-btn'].randen).toEqual([true, true])
      })
    }
  })
}

// Het tikvlak van een element: zijn eigen vak of zijn ::before, wat groter is. `randen`: raakt een tik 1 px binnen de
// boven- en onderrand van dat vlak (midden horizontaal) het element zelf?
function tikvlak(el) {
  const r = el.getBoundingClientRect()
  const voor = getComputedStyle(el, '::before')
  const absoluut = voor.content !== 'none' && voor.position === 'absolute'
  const hoogte = Math.max(r.height, absoluut ? parseFloat(voor.height) : 0)
  const breedte = Math.max(r.width, absoluut ? parseFloat(voor.width) : 0)
  const x = r.left + r.width / 2, y = r.top + r.height / 2
  const randen = [y - hoogte / 2 + 1, y + hoogte / 2 - 1].map(py => el.contains(document.elementFromPoint(x, py)))
  return { hoogte, breedte, randen }
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
