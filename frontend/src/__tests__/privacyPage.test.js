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

const privacyLinks = () => [...container.querySelectorAll('a[href="/privacy"]')]

describe('PrivacyPage', () => {
  it('names the page in the tab title and carries every section', async () => {
    await render(createElement(PrivacyPage))
    expect(document.title).toBe('Privacy — openEDUdata+')
    expect([...container.querySelectorAll('h2')].map(h => h.textContent)).toEqual(PRIVACY_KOPJES)
    expect(container.querySelector('a[href="/"]').textContent).toBe('Terug naar de startpagina')
  })

  it('has the same sections as docs/privacy.md', () => {
    const docs = readFileSync(join(__dirname, '..', '..', '..', 'docs', 'privacy.md'), 'utf8')
    const kopjes = [...docs.matchAll(/^## (.+)$/gm)].map(m => m[1])
    expect(kopjes).toEqual(PRIVACY_KOPJES)
  })

  it('does not present the open points as settled facts', async () => {
    await render(createElement(PrivacyPage))
    const open = [...container.querySelectorAll('h2')].at(-1).nextElementSibling.textContent
    expect(open).toContain('Verwerkingsverantwoordelijke')
    expect(open).toContain('Bewaartermijn')
    expect(container.textContent).not.toMatch(/geen persoonsgegevens worden verwerkt/i)
  })
})

describe('links to the privacy page', () => {
  it('the login page links to it below the form', async () => {
    await render(createElement(LoginPage, { onLogin: vi.fn(), oidcEnabled: false }))
    expect(privacyLinks()).toHaveLength(1)
    expect(container.textContent).toContain('externe AI-dienst')
  })

  it('the settings dialog says where the profile lives and links to it', async () => {
    await render(createElement(SettingsModal, { settings: {}, onSave: vi.fn(), onClose: vi.fn() }))
    expect(container.textContent).toContain('alleen in deze browser')
    expect(privacyLinks()).toHaveLength(1)
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
