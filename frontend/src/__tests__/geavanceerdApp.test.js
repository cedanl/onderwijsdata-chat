// @vitest-environment jsdom
// #1269: App houdt "Geavanceerd" bij. Met login komt de stand van de server (dus op elk apparaat dezelfde) en gaat een
// wissel daarheen, nooit in het profiel in localStorage; zonder login houdt deze browser haar, standaard uit. Zonder
// Geavanceerd gaat elke vraag met het standaardmodel, ook als deze browser een andere keuze onthield.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import App from '../App'
import { STORAGE_SETTINGS, STORAGE_ONBOARDED, STORAGE_MODEL, STORAGE_GEAVANCEERD } from '../constants'
import { FakeWebSocket } from './fakeWebSocket'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

const APP_TEST = { timeout: 20000 }
const SRAM_LANDING = '#token=tok-1&user_data=%7B%22name%22%3A%22Anna%22%7D'
const MODELLEN = [{ id: 'azure_ai/standaard', name: 'Standaard' }, { id: 'azure_ai/extra', name: 'Extra' }]

const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

let root
let container
let opgeslagen

function serve({ required = true, geavanceerd = false } = {}) {
  opgeslagen = []
  let stand = geavanceerd
  vi.stubGlobal('fetch', vi.fn(async (url, opties = {}) => {
    if (url === '/api/auth/status') return response(200, { required, oidc_enabled: true })
    if (url === '/api/auth/user') return response(200, { name: 'Anna' })
    if (url === '/api/mijn-gegevens/geavanceerd') {
      if (opties.method === 'PUT') {
        const body = JSON.parse(opties.body)
        opgeslagen.push(body)
        stand = body.geavanceerd
      }
      return response(200, { geavanceerd: stand })
    }
    if (url === '/api/settings/config') return response(200, { models: MODELLEN, default_model: MODELLEN[0].id })
    if (url === '/api/instellingen') return response(200, [])
    if (url.startsWith('/api/conversations')) return response(200, [])
    return response(200, {})
  }))
}

async function open(adres) {
  window.history.replaceState({}, '', adres)
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
}

// Het model dat de chat de server meldt zodra zijn socket open is.
async function chatModel() {
  await vi.waitFor(() => expect(FakeWebSocket.last).not.toBeNull(), { timeout: 10000 })
  await act(async () => { FakeWebSocket.last.open() })
  await vi.waitFor(() => expect(FakeWebSocket.last.sent.some(m => m.action === 'settings' && m.settings.model)).toBe(true))
  return FakeWebSocket.last.sent.filter(m => m.action === 'settings').at(-1).settings.model
}

const kiezer = () => container.querySelector('.model-picker')
const knop = tekst => [...container.querySelectorAll('button')].find(b => b.textContent.trim() === tekst)

async function zetGeavanceerd() {
  await act(async () => { container.querySelector('button[title="Instellingen"]').click() })
  await act(async () => { container.querySelector('[role="switch"]').click() })
  await act(async () => { knop('Opslaan').click() })
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  // Een profiel en een gesloten onboarding: dan opent geen welkomstdialoog boven de chat.
  localStorage.setItem(STORAGE_SETTINGS, JSON.stringify({ functie: 'Onderzoeker' }))
  localStorage.setItem(STORAGE_ONBOARDED, '1')
  // Deze browser onthield eerder een eigen modelkeuze.
  localStorage.setItem(STORAGE_MODEL, MODELLEN[1].id)
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  FakeWebSocket.reset()
  vi.stubGlobal('WebSocket', FakeWebSocket)
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  container = null
  delete window.matchMedia
  localStorage.clear()
  sessionStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('App: Geavanceerd met login (#1269)', APP_TEST, () => {
  it('uit op de server: geen modelkiezer en het standaardmodel, ook met een onthouden keuze', async () => {
    serve({ geavanceerd: false })
    await open(`/chat${SRAM_LANDING}`)
    expect(await chatModel()).toBe(MODELLEN[0].id)
    expect(kiezer()).toBeNull()
  })

  it('aan op de server (een ander apparaat): de modelkiezer en de eigen keuze', async () => {
    serve({ geavanceerd: true })
    await open(`/chat${SRAM_LANDING}`)
    expect(await chatModel()).toBe(MODELLEN[1].id)
    await vi.waitFor(() => expect(kiezer()).not.toBeNull())
  })

  it('een wissel in Instellingen gaat naar de server, niet in het profiel', async () => {
    serve({ geavanceerd: false })
    await open(`/chat${SRAM_LANDING}`)
    expect(await chatModel()).toBe(MODELLEN[0].id)

    await zetGeavanceerd()

    expect(opgeslagen).toEqual([{ geavanceerd: true }])
    await vi.waitFor(() => expect(kiezer()).not.toBeNull())
    expect(JSON.parse(localStorage.getItem(STORAGE_SETTINGS))).not.toHaveProperty('geavanceerd')
    expect(localStorage.getItem(STORAGE_GEAVANCEERD)).toBeNull()
  })
})

describe('App: Geavanceerd zonder login (#1269)', APP_TEST, () => {
  it('staat standaard uit en blijft in deze browser na een wissel', async () => {
    serve({ required: false })
    await open('/chat')
    expect(await chatModel()).toBe(MODELLEN[0].id)
    expect(kiezer()).toBeNull()

    await zetGeavanceerd()

    expect(opgeslagen).toEqual([])
    expect(localStorage.getItem(STORAGE_GEAVANCEERD)).toBe('1')
    await vi.waitFor(() => expect(kiezer()).not.toBeNull())
  })
})
