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
      for (const tekst of ['kopie in deze browser', 'serverlogs', 'back-ups van de beheerder', 'tot zij verloopt', 'losgekoppeld', 'ander apparaat', 'gedeeld account']) {
        expect(zelf).toContain(tekst)
      }
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
})
