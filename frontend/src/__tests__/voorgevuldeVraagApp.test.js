// @vitest-environment jsdom
// #709 in de hele app: een vraag uit een link overleeft de login. Met het wachtwoordformulier blijft de app op /chat;
// SRAM landt na de callback op / met het token in het fragment, en de app gaat dan door naar de chat met de vraag.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import App from '../App'
import { bewaarVraagUitUrl } from '../voorgevuldeVraag'
import { FakeWebSocket } from './fakeWebSocket'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

// Each App test renders the whole app; on a busy machine that nears the 5 s default.
const APP_TEST = { timeout: 20000 }
const VRAAG = 'Hoeveel eerstejaars had het hbo in 2024?'
const LINK = `/chat#vraag=${encodeURIComponent(VRAAG)}`

const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

let root
let container

function serve() {
  vi.stubGlobal('fetch', vi.fn(async url => {
    if (url === '/api/auth/status') return response(200, { required: true, oidc_enabled: true })
    if (url === '/api/auth/user') return response(200, { name: 'Anna', username: 'anna@example.nl' })
    if (url === '/api/auth/login') return response(200, { token: 'tok-1', user: 'anna' })
    if (url === '/api/instellingen') return response(200, [])
    if (url.startsWith('/api/conversations')) return response(200, [])
    return response(200, {})
  }))
}

// Zoals main.jsx: de link wordt gelezen vóór de router het adres leest.
async function open(adres) {
  window.history.replaceState({}, '', adres)
  bewaarVraagUitUrl()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
}

const invoer = () => container.querySelector('textarea.chat-input')

async function wachtOpInvoer() {
  await vi.waitFor(() => expect(invoer()).not.toBeNull(), { timeout: 10000 })
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  localStorage.setItem('openEDUdata_onboarded', '1')
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  FakeWebSocket.reset()
  globalThis.WebSocket = FakeWebSocket
  serve()
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  delete window.matchMedia
  localStorage.clear()
  sessionStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('App: een vraag uit een link en de login', APP_TEST, () => {
  it('haalt de vraag uit het adres, ook vóór het inloggen', async () => {
    await open(LINK)
    expect(container.textContent).toContain('Inloggen')
    expect(window.location.hash).toBe('')
  })

  it('zet de vraag na de terugkeer van SRAM op / in de invoer van de chat', async () => {
    await open(LINK)
    await act(async () => { root.unmount() })
    container.remove()

    // De browser ging naar SRAM en komt terug op /, met het token in het fragment.
    await open('/#token=tok-1&user_data=%7B%22name%22%3A%22Anna%22%7D')
    await wachtOpInvoer()

    expect(window.location.pathname).toBe('/chat')
    expect(invoer().value).toBe(VRAAG)
  })

  it('zet de vraag na het wachtwoordformulier in de invoer van de chat', async () => {
    await open(LINK)
    const [gebruiker, wachtwoord] = container.querySelectorAll('input')
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    await act(async () => {
      set.call(gebruiker, 'anna')
      gebruiker.dispatchEvent(new Event('input', { bubbles: true }))
      set.call(wachtwoord, 'geheim')
      wachtwoord.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => { container.querySelector('form').requestSubmit() })
    await wachtOpInvoer()

    expect(window.location.pathname).toBe('/chat')
    expect(invoer().value).toBe(VRAAG)
  })
})
