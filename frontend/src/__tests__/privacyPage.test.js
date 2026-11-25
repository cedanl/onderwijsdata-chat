// @vitest-environment jsdom
// #477: privacy-informatie in de app, ook vóór het inloggen, met dezelfde kopjes als docs/privacy.md.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import PrivacyPage, { PRIVACY_KOPJES } from '../pages/PrivacyPage'
import LoginPage from '../pages/LoginPage'
import SettingsModal from '../components/SettingsModal'
import App from '../App'
import { zetBronnenLijst } from '../bronnenLijst'
import { zetTermijnen } from '../termijnen'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
  zetBronnenLijst({})
})

// The privacy information opens as a popup from these places (#572); privacyModal.test.js covers the popup.
const privacyButtons = () => [...container.querySelectorAll('button')].filter(b => b.textContent === 'Privacy-informatie')
const privacyLinks = () => [...container.querySelectorAll('a[href="/privacy"]')]

// One section of the rendered page: the elements between its h2 and the next h2.
function sectionElements(kop) {
  const h2 = [...container.querySelectorAll('h2')].find(h => h.textContent === kop)
  const elements = []
  for (let el = h2.nextElementSibling; el && el.tagName !== 'H2'; el = el.nextElementSibling) elements.push(el)
  return elements
}
const sectionText = kop => sectionElements(kop).map(el => el.textContent).join(' ')

// docs/privacy.md and one of its sections (from its '## ' heading up to the next one).
const readDocs = () => readFileSync(join(__dirname, '..', '..', '..', 'docs', 'privacy.md'), 'utf8')
const docsSection = kop => readDocs().split(/^## /m).find(deel => deel.startsWith(`${kop}\n`)) ?? ''
const oneLine = text => text.replace(/\s+/g, ' ')

describe('PrivacyPage', () => {
  it('names the page in the tab title and carries every section', async () => {
    await render(createElement(PrivacyPage))
    expect(document.title).toBe('Privacy — openEDUdata+')
    expect([...container.querySelectorAll('h2')].map(h => h.textContent)).toEqual(PRIVACY_KOPJES)
    expect(container.querySelector('a[href="/"]').textContent).toBe('Terug naar de startpagina')
  })

  it('has the same sections as docs/privacy.md', () => {
    const kopjes = [...readDocs().matchAll(/^## (.+)$/gm)].map(m => m[1])
    expect(kopjes).toEqual(PRIVACY_KOPJES)
  })

  it('does not present the open points as settled facts', async () => {
    await render(createElement(PrivacyPage))
    const open = sectionText('Open punten')
    expect(open).toContain('Verwerkersovereenkomst')
    expect(open).toMatch(/bewaartermijn van het serverlog/i)
    expect(container.textContent).not.toMatch(/geen persoonsgegevens worden verwerkt/i)
  })

  // #553 point 1, decided 19-10-2026: the controller is no longer an open point, in the app or the docs.
  it('names the deelnemende instelling as verwerkingsverantwoordelijke, in the app and in docs/privacy.md', async () => {
    await render(createElement(PrivacyPage))
    const app = sectionText('Verantwoordelijke en contact')
    const docs = oneLine(docsSection('Verantwoordelijke en contact'))
    for (const tekst of [app, docs]) {
      expect(tekst).toContain('deelnemende instelling')
      expect(tekst).not.toMatch(/vóór de demofase eindigt/)
    }
    const appBullets = sectionElements('Open punten').flatMap(el => [...el.querySelectorAll('li')]).map(li => li.textContent)
    const docsBullets = docsSection('Open punten').split(/^- /m).slice(1)
    expect(appBullets).toHaveLength(3)
    expect(docsBullets).toHaveLength(3)
    for (const bullet of [...appBullets, ...docsBullets]) expect(bullet).not.toMatch(/verwerkingsverantwoordelijke/i)
  })

  // #645 and #646: exporting and deleting everything are both possible, in the app and the docs; what stays after the
  // delete is named. #485: the retention terms are decided and named; only those of logs and back-ups stay open.
  it('says that all data can be exported and deleted, what the delete leaves, and the retention terms', async () => {
    await render(createElement(PrivacyPage))
    const app = [sectionText('Wat je zelf kunt doen'), sectionText('Open punten'), sectionText('Wat de server bewaart')]
    const docs = [oneLine(docsSection('Wat je zelf kunt doen')), oneLine(docsSection('Open punten')), oneLine(docsSection('Wat de server bewaart'))]
    for (const [zelf, open, server] of [app, docs]) {
      expect(zelf).toContain('Exporteer al mijn gegevens')
      expect(zelf).toContain('/api/mijn-gegevens/export')
      expect(zelf).toContain('Verwijder al mijn gegevens')
      expect(zelf).not.toMatch(/kan nog niet/)
      // What goes and what stays.
      for (const tekst of ['kopie in deze browser', 'serverlogs', 'back-ups van de beheerder', 'tot zij verloopt', 'ander apparaat', 'gedeeld account']) {
        expect(zelf).toContain(tekst)
      }
      // Feedback per antwoord (de duimpjes) wordt niet meer bewaard, ook niet losgekoppeld (#983).
      expect(zelf).not.toContain('losgekoppeld')
      expect(server).not.toMatch(/duim|answer_feedback|feedback per antwoord|losgekoppeld/i)
      expect(open).not.toMatch(/alles verwijderen|exporteren/)
      expect(open).toMatch(/bewaartermijn van het (serverlog|logplatform)/i)
      expect(open).not.toContain('bij productie')
      expect(server).toMatch(/al (je|zijn) gegevens verwijdert/)
      // The terms in plain words, and no trace of "nothing is cleaned up".
      expect(server).toMatch(/90 dagen na (je|het) laatste bericht/)
      expect(server).toMatch(/365 dagen/)
      expect(server).toMatch(/90 dagen na(dat je hem gaf| het geven)/)
      expect(server).not.toMatch(/nog geen automatische opschoning|onbepaald|blijft staan tot je al je gegevens/)
    }
  })

  // #1074: the tokengebruik per day belongs to the account: it is in the export and goes with the delete, not in what
  // stays. #1118: without a login of one's own there is no export either.
  it('names the tokengebruik among what is exported and deleted, and no export without a login, in the app and the docs', async () => {
    await render(createElement(PrivacyPage))
    const appBullets = sectionElements('Wat je zelf kunt doen').flatMap(el => [...el.querySelectorAll('li')]).map(li => oneLine(li.textContent))
    const docsBullets = docsSection('Wat je zelf kunt doen').split(/^- /m).map(oneLine)
    for (const bullets of [appBullets, docsBullets]) {
      const exporteren = bullets.find(b => b.includes('Exporteer al mijn gegevens'))
      const verwijderen = bullets.find(b => b.includes('Verwijder al mijn gegevens'))
      expect(exporteren).toMatch(/tokengebruik/)
      expect(exporteren).toMatch(/Zonder eigen login/)
      const [weg, blijft] = verwijderen.split('Wat blijft')
      expect(weg).toMatch(/tokengebruik/)
      expect(blijft).not.toMatch(/tokengebruik|teller/i)
    }
    expect(sectionText('Wat de server bewaart')).toMatch(/zit in de export, en gaat weg als je al je gegevens verwijdert/)
    const rij = readDocs().split('\n').find(regel => regel.includes('| `tokengebruik` |'))
    expect(rij).toMatch(/eerder als de gebruiker al zijn gegevens verwijdert, en in de export/)
  })

  // #1112, #1117: the counters of the budget and the limits are named: what they hold, under what key, how long.
  it('names the counters of the budget and the limits, in the app and the docs', async () => {
    await render(createElement(PrivacyPage))
    const app = sectionText('Wat de server bewaart')
    expect(app).toContain('Tellers')
    expect(app).toMatch(/pseudoniem \(een code[^)]*\)\. De server maakt dat pseudoniem met een eigen geheim/)
    const docs = oneLine(docsSection('Wat de server bewaart'))
    for (const tabel of ['`tokengebruik`', '`rate_limit_hits`']) expect(docs).toContain(tabel)
    expect(docs).toMatch(/HMAC met een geheim van de server/)
  })

  // #666: the questions about the institution in the report feedback come only after the user's own choice.
  it('says that the questions about the institution are asked only after a choice, in the app and the docs', async () => {
    await render(createElement(PrivacyPage))
    for (const tekst of [sectionText('Wat de server bewaart'), oneLine(docsSection('Wat de server bewaart'))]) {
      expect(tekst).toContain('alleen na een eigen keuze')
      expect(tekst).toContain('Help ons verder')
      expect(tekst).toMatch(/zonder die vragen (te )?versturen/)
    }
  })
})

// #1139: de pagina is voor elke gebruiker, dus op B1: korte zinnen, geen onverklaard jargon, één datumnotatie, en elk
// kopje begint met één korte zin die zegt wat er gebeurt.
describe('de privacytekst op B1 (#1139)', () => {
  const woorden = zin => zin.split(/\s+/).filter(Boolean).length
  // De zinnen van een blok (alinea, opsommingspunt), gesplitst op . ! ? gevolgd door een spatie.
  const zinnen = tekst => oneLine(tekst).trim().split(/(?<=[.!?])\s+/).filter(Boolean)
  const blokken = () => [...container.querySelectorAll('p, li')].filter(el => !el.querySelector('p, li'))

  it('heeft geen zin van meer dan 25 woorden en een gemiddelde onder de 15', async () => {
    await render(createElement(PrivacyPage))
    const alle = blokken().flatMap(el => zinnen(el.textContent))
    const tekort = alle.filter(zin => woorden(zin) > 25)
    expect(tekort, tekort.join('\n')).toEqual([])
    const gemiddeld = alle.reduce((som, zin) => som + woorden(zin), 0) / alle.length
    expect(gemiddeld).toBeLessThan(15)
  })

  it('begint elk kopje met één korte zin', async () => {
    await render(createElement(PrivacyPage))
    for (const kop of PRIVACY_KOPJES) {
      const [eerste] = sectionElements(kop)
      expect(eerste.tagName, kop).toBe('P')
      expect(eerste.className, kop).toBe('privacy-kern')
      expect(zinnen(eerste.textContent), kop).toHaveLength(1)
      expect(woorden(eerste.textContent), kop).toBeLessThanOrEqual(15)
    }
  })

  it('noemt de bewaartermijn van gesprekken en rapporten in de eerste zin onder "Wat de server bewaart"', async () => {
    zetTermijnen({ bewaartermijn_gesprekken_dagen: 30, bewaartermijn_rapporten_dagen: 180 })
    try {
      await render(createElement(PrivacyPage))
      const [eerste] = sectionElements('Wat de server bewaart')
      expect(eerste.textContent).toContain('30 dagen')
      expect(eerste.textContent).toContain('180 dagen')
    } finally {
      zetTermijnen({})
    }
  })

  it('heeft geen vaktaal zonder uitleg', async () => {
    await render(createElement(PrivacyPage))
    const tekst = container.textContent
    // Weg: wat een gebruiker niet kent en wat de uitleg niet nodig heeft.
    expect(tekst).not.toMatch(/\bhash\b|OIDC|\bnonce\b|PKCE|verifier|toolstap|toolnaam|toolargument|datarecept|analytics|foutzoekniveau/i)
    // Blijft, met een uitleg in dezelfde zin of in de zin erna.
    expect(tekst).toMatch(/SRAM[^.]*inlogsysteem/)
    expect(tekst).toMatch(/DPIA[^.]*onderzoek naar de privacyrisico/)
    expect(tekst).toMatch(/verwerkingsverantwoordelijke \(/)
    expect(tekst).toMatch(/functionaris gegevensbescherming \(FG\)/)
    expect(tekst).toMatch(/pseudoniem \(een code/)
    expect(tekst).toMatch(/controlecode[^.]*niet uit terug te halen/)
  })

  it('schrijft elke datum op dezelfde manier uit, zonder streepjes', async () => {
    await render(createElement(PrivacyPage))
    const tekst = container.textContent
    expect(tekst).not.toMatch(/\d{1,2}-\d{1,2}-\d{4}/)
    expect(tekst).toContain('19 oktober 2026')
    expect(tekst).toContain('9 november 2026')
  })

  // #1119, #1139: wat de tekst over het logboek zegt klopt met de app: geen toegangslog (#1114).
  it('zegt dat de app geen toegangslog met IP-adressen schrijft', async () => {
    await render(createElement(PrivacyPage))
    expect(sectionText('Het logboek')).toMatch(/geen toegangslog/)
    expect(oneLine(docsSection('Het logboek'))).toMatch(/geen toegangslog/)
  })

  // De wijzigingen van #1112 en #1117: tellers onder een pseudoniem blijven na "Verwijder al mijn gegevens", want ze
  // hebben geen accountnaam om op te verwijderen (persistence/verwijderen.py). Dat moet de tekst zeggen.
  it('zegt dat de tellers na "Verwijder al mijn gegevens" blijven staan, in de app en in docs/privacy.md', async () => {
    await render(createElement(PrivacyPage))
    for (const tekst of [sectionText('Wat je zelf kunt doen'), oneLine(docsSection('Wat je zelf kunt doen'))]) {
      expect(tekst).toMatch(/tellers/)
      expect(tekst).toMatch(/tien minuten/)
    }
  })
})

// #1230: naam, organisatie en instelling uit SRAM staan sinds #984 in de database (`oidc_gebruikers`), niet meer in het
// geheugen van de server. #1209: ze zitten in de export en gaan mee met "Verwijder al mijn gegevens", in dezelfde
// transactie als de rest. App en docs/privacy.md noemen dezelfde plek, termijn en momenten van verwijderen.
describe('de SRAM-gegevens in de database (#1230, #1209)', () => {
  const inloggenInDeApp = () => sectionElements('Wat de server bewaart')
    .flatMap(el => [...el.querySelectorAll('li')]).map(li => oneLine(li.textContent))
    .find(li => li.startsWith('Inloggen'))
  const inloggenInDeDocs = () => oneLine(docsSection('Wat de server bewaart')).split('Inloggen:')[1].split('Bewaartermijn')[0]

  it('zegt in de app: in de database, ten hoogste de sessieduur, weg bij uitloggen en bij al je gegevens verwijderen', async () => {
    zetTermijnen({ sessie_max_uren: 12 })
    try {
      await render(createElement(PrivacyPage))
      const inloggen = inloggenInDeApp()
      expect(inloggen).toContain('naam, organisatie en instelling uit SRAM staan in de database van de server, ten hoogste 12 uur')
      expect(inloggen).toContain('weg als je uitlogt of al je gegevens verwijdert')
      expect(container.textContent).not.toContain('geheugen van de server')
      expect(container.textContent).not.toMatch(/SRAM[^.]*geheugen|geheugen[^.]*SRAM/)
    } finally {
      zetTermijnen({})
    }
  })

  it('docs/privacy.md noemt dezelfde plek, termijn en momenten van verwijderen', () => {
    const inloggen = inloggenInDeDocs()
    expect(inloggen).toMatch(/naam, organisatie en instelling[^.]*in de database \(`oidc_gebruikers`/)
    expect(inloggen).toContain('`SESSION_MAX_HOURS`')
    expect(inloggen).toMatch(/uitloggen/)
    expect(inloggen).toMatch(/al zijn gegevens verwijdert/)
    const rij = readDocs().split('\n').find(regel => regel.includes('| `oidc_gebruikers` |'))
    expect(rij).toMatch(/tot `SESSION_MAX_HOURS`/)
    expect(rij).toMatch(/eerder bij uitloggen of als de gebruiker al zijn gegevens verwijdert, en in de export/)
    expect(rij).not.toMatch(/stond tot #984 in het geheugen/)
    expect(readDocs()).not.toContain('geheugen van de server')
  })

  it('noemt de SRAM-gegevens bij exporteren en verwijderen, vóór wat blijft, in de app en de docs', async () => {
    await render(createElement(PrivacyPage))
    const appBullets = sectionElements('Wat je zelf kunt doen').flatMap(el => [...el.querySelectorAll('li')]).map(li => oneLine(li.textContent))
    const docsBullets = docsSection('Wat je zelf kunt doen').split(/^- /m).map(oneLine)
    for (const bullets of [appBullets, docsBullets]) {
      const exporteren = bullets.find(b => b.includes('Exporteer al mijn gegevens'))
      const verwijderen = bullets.find(b => b.includes('Verwijder al mijn gegevens'))
      expect(exporteren).toMatch(/naam, organisatie en instelling uit SRAM/)
      const [weg, blijft] = verwijderen.split('Wat blijft')
      expect(weg).toMatch(/naam, organisatie en instelling uit SRAM/)
      expect(blijft).not.toMatch(/SRAM/)
    }
    const docsExport = docsBullets.find(b => b.includes('Exporteer al mijn gegevens'))
    expect(docsExport).toMatch(/`oidc_gebruiker`/)
    const docsVerwijderen = docsBullets.find(b => b.includes('Verwijder al mijn gegevens'))
    expect(docsVerwijderen).not.toMatch(/direct daarna je SRAM-gegevens/)
  })
})

// #1140: de pagina en docs/privacy.md noemen wat er in de browser staat met de namen van de app. Een "werkboek" heet
// in de app een rapport, en de dashboardchat bestaat sinds #765 niet meer: de app schrijft haar niet meer, ze wist
// alleen wat een eerdere versie achterliet (SESSION_DATA_KEYS).
describe('de namen van de app in de privacytekst (#1140)', () => {
  it('noemt geen werkboek en geen dashboardchat, wel de rapporten in de browser', async () => {
    await render(createElement(PrivacyPage))
    for (const tekst of [container.textContent, readDocs()]) expect(tekst).not.toMatch(/werkboek|dashboardchat|dashboard-chat/i)
    expect(sectionText('Wat in je browser staat')).toMatch(/gesprekken en rapporten/)
    expect(oneLine(docsSection('Wat in je browser staat'))).toMatch(/de rapporten/)
  })
})

// #1144: JSX knipt een regelovergang weg, dus "na" en {gesprek} plakten aan elkaar ("na90 dagen"). Geen cijfer direct na
// een letter in de tekst van de pagina, en de termijn uit de configuratie staat er met een spatie.
describe('de spaties in de tekst (#1144)', () => {
  it('heeft nergens een cijfer direct achter een woord ("na90")', async () => {
    await render(createElement(PrivacyPage))
    expect(container.textContent).not.toMatch(/\p{L}\d/u)
  })

  it('zegt "na 90 dagen" bij het bewijs per antwoord, met de termijn uit de configuratie', async () => {
    await render(createElement(PrivacyPage))
    expect(sectionText('Wat de server bewaart')).toContain('of na 90 dagen als het gesprek er niet meer is')
    act(() => root.unmount())
    container.remove()
    zetTermijnen({ bewaartermijn_gesprekken_dagen: 45 })
    try {
      await render(createElement(PrivacyPage))
      expect(sectionText('Wat de server bewaart')).toContain('of na 45 dagen als het gesprek er niet meer is')
    } finally {
      zetTermijnen({})
    }
  })
})

// #1006: the privacy text names every party a lookup can go to in this environment (bronnenLijst.js, from /api/config
// `bronnen`), says only the lookup goes there, and that the Studiekeuzedatabase is licensed LCSK data, not open data.
describe('the sources a lookup goes to (#1006)', () => {
  const AI = 'Wat naar de AI-dienst gaat'
  const VAST = ['CBS', 'DUO', 'RIO', 'UWV', 'ROA', 'de Onderwijsinspectie']

  it('names the fixed sources, only the lookup, and nothing about the user', async () => {
    await render(createElement(PrivacyPage))
    const tekst = sectionText(AI)
    expect(tekst).toContain(`De cijfers zelf komen van ${VAST.slice(0, -1).join(', ')} en ${VAST.at(-1)}.`)
    expect(tekst).toContain('alleen de opvraag (welke tabel, welke selectie), niets over jou')
    expect(tekst).toContain('wetten.nl; daarheen gaat geen opvraag')
    expect(tekst).not.toMatch(/Studiekeuzedatabase|LCSK|UNL|WOPI/)
    expect(tekst).not.toMatch(/open bronnen/)
  })

  it('adds the Studiekeuzedatabase as licensed LCSK data where it is on', async () => {
    zetBronnenLijst({ studiekeuze: true })
    await render(createElement(PrivacyPage))
    const tekst = sectionText(AI)
    expect(tekst).toContain('ROA, de Onderwijsinspectie en de Studiekeuzedatabase (LCSK).')
    expect(tekst).toContain('De Studiekeuzedatabase is gelicentieerde data van LCSK, geen open data')
    expect(tekst).not.toMatch(/UNL|WOPI/)
  })

  it('adds UNL (WOPI) where it is on, without the licence note of the Studiekeuzedatabase', async () => {
    zetBronnenLijst({ wo_personeel: true })
    await render(createElement(PrivacyPage))
    const tekst = sectionText(AI)
    expect(tekst).toContain('de Onderwijsinspectie en UNL (WOPI).')
    expect(tekst).not.toMatch(/Studiekeuzedatabase|LCSK/)
  })

  it('docs/privacy.md names the same parties, with the environment rule and the licence', () => {
    const docs = oneLine(docsSection(AI))
    for (const naam of [...VAST, 'Studiekeuzedatabase', 'LCSK', 'UNL (WOPI)', 'wetten.nl']) expect(docs).toContain(naam)
    expect(docs).toContain('gelicentieerde data van LCSK, geen open data')
    expect(docs).toContain('alleen de opvraag (welke tabel, welke selectie), niets over de gebruiker')
    expect(docs).toContain('daarheen gaat geen opvraag')
    expect(docs).not.toMatch(/open bronnen/)
  })
})

describe('buttons for the privacy information', () => {
  it('the login page offers it below the form', async () => {
    await render(createElement(LoginPage, { onLogin: vi.fn(), oidcEnabled: false }))
    expect(privacyButtons()).toHaveLength(1)
    expect(privacyLinks()).toHaveLength(0)
    expect(container.textContent).toContain('externe AI-dienst')
  })

  it('the settings dialog says where the profile lives and offers it', async () => {
    await render(createElement(SettingsModal, { settings: {}, onSave: vi.fn(), onClose: vi.fn() }))
    expect(container.textContent).toContain('alleen in deze browser')
    expect(privacyButtons()).toHaveLength(1)
    expect(privacyLinks()).toHaveLength(0)
  })
})

describe('before login', () => {
  const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

  async function waitFor(check) {
    for (let i = 0; i < 300 && !check(); i++) {
      await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })
    }
    expect(check()).toBeTruthy()
  }

  it('/privacy shows the privacy page instead of the login page', { timeout: 20000 }, async () => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (url === '/api/auth/status') return response(200, { required: true, oidc_enabled: false })
      return response(200, {})
    }))
    window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
    window.history.replaceState({}, '', '/privacy')
    try {
      await render(createElement(App))
      await waitFor(() => container.querySelector('.privacy-page--standalone'))
      expect(container.querySelector('#login-username')).toBeNull()
      expect(container.querySelector('a[href="/"]').textContent).toBe('Naar het inloggen')
    } finally {
      delete window.matchMedia
      window.history.replaceState({}, '', '/')
    }
  })

  // #1177: de losse pagina stond buiten de shell, dus zonder <main> en zonder skiplink.
  it('/privacy before login has one main landmark and a skip-link to it', { timeout: 20000 }, async () => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (url === '/api/auth/status') return response(200, { required: true, oidc_enabled: false })
      return response(200, {})
    }))
    window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
    window.history.replaceState({}, '', '/privacy')
    try {
      await render(createElement(App))
      await waitFor(() => container.querySelector('.privacy-page--standalone'))
      const mains = container.querySelectorAll('main')
      expect(mains).toHaveLength(1)
      expect(mains[0].contains(container.querySelector('.privacy-page--standalone'))).toBe(true)
      expect(container.querySelector('a.skip-link').getAttribute('href')).toBe(`#${mains[0].id}`)
    } finally {
      delete window.matchMedia
      window.history.replaceState({}, '', '/')
    }
  })

  it('/privacy without login keeps the one main of the app shell', { timeout: 20000 }, async () => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (url === '/api/auth/status') return response(200, { required: false, oidc_enabled: false })
      return response(200, {})
    }))
    window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
    window.history.replaceState({}, '', '/privacy')
    try {
      await render(createElement(App))
      await waitFor(() => container.querySelector('.privacy-page'))
      expect(container.querySelectorAll('main')).toHaveLength(1)
      expect(container.querySelectorAll('a.skip-link')).toHaveLength(1)
    } finally {
      delete window.matchMedia
      window.history.replaceState({}, '', '/')
    }
  })

  // #1006: App reads /api/config before it decides on login, so the page before login names this environment's list.
  it('/privacy before login names the sources /api/config reports', { timeout: 20000 }, async () => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (url === '/api/auth/status') return response(200, { required: true, oidc_enabled: false })
      if (url === '/api/config') return response(200, { bronnen: { studiekeuze: true, wo_personeel: false } })
      return response(200, {})
    }))
    window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
    window.history.replaceState({}, '', '/privacy')
    try {
      await render(createElement(App))
      await waitFor(() => container.querySelector('.privacy-page--standalone'))
      const tekst = sectionText('Wat naar de AI-dienst gaat')
      expect(tekst).toContain('de Studiekeuzedatabase (LCSK)')
      expect(tekst).not.toContain('UNL')
    } finally {
      delete window.matchMedia
      window.history.replaceState({}, '', '/')
    }
  })
})
