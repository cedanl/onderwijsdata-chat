// @vitest-environment jsdom
// #778: wie een gesprek verwijdert en binnen de bedenktijd uitlogt, houdt het niet op de server. De DELETE gaat
// met het token van vóór het uitloggen, en het token wordt pas ingetrokken als die DELETE klaar is.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import App from '../App'
import { STORAGE_TOKEN, STORAGE_TE_VERWIJDEREN } from '../constants'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

const APP_TEST = { timeout: 20000 }
const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })
const rijen = [
  { id: 'c1', title: 'Eerste gesprek', timestamp: 2 },
  { id: 'c2', title: 'Tweede gesprek', timestamp: 1 },
]

class FakeWebSocket {
  static OPEN = 1
  constructor() { this.readyState = FakeWebSocket.OPEN }
  send() {}
  close() {}
}

let root
let container
let verzoeken
let deleteKlaar

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  verzoeken = []
  vi.stubGlobal('WebSocket', FakeWebSocket)
  vi.stubGlobal('fetch', vi.fn((url, opties = {}) => {
    verzoeken.push({ url, method: opties.method || 'GET', auth: opties.headers?.Authorization })
    if (opties.method === 'DELETE') return new Promise(resolve => { deleteKlaar = () => resolve(response(200, { ok: true })) })
    if (url === '/api/auth/status') return Promise.resolve(response(200, { required: true, oidc_enabled: false }))
    if (url === '/api/auth/user') return Promise.resolve(response(200, { name: 'Anna' }))
    if (url.startsWith('/api/conversations')) return Promise.resolve(response(200, rijen))
    if (url === '/api/instellingen' || url.startsWith('/api/workbooks')) return Promise.resolve(response(200, []))
    return Promise.resolve(response(200, {}))
  }))
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  Element.prototype.scrollIntoView = () => {}
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  delete window.matchMedia
  delete Element.prototype.scrollIntoView
  window.history.replaceState({}, '', '/')
  vi.unstubAllGlobals()
})

async function waitFor(check) {
  for (let i = 0; i < 300 && !check(); i++) {
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)) })
  }
  expect(check()).toBeTruthy()
}

const knop = label => [...container.querySelectorAll('button')].find(b => b.textContent.trim().startsWith(label))
const naar = pad => verzoeken.filter(v => v.url.startsWith(pad))

describe('uitloggen binnen de bedenktijd (#778)', APP_TEST, () => {
  it('stuurt de DELETE met het oude token en trekt het token pas daarna in', async () => {
    window.history.replaceState({}, '', '/chat')
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => { root.render(createElement(App)) })
    await waitFor(() => container.querySelector('[aria-label="Verwijder gesprek Tweede gesprek"]'))

    await act(async () => { container.querySelector('[aria-label="Verwijder gesprek Tweede gesprek"]').click() })
    await act(async () => { container.querySelector('.confirm-destructive').click() })
    expect(verzoeken.filter(v => v.method === 'DELETE')).toEqual([])

    await act(async () => { knop('Uitloggen').click() })

    expect(verzoeken.filter(v => v.method === 'DELETE')).toEqual([{ url: '/api/conversations/c2', method: 'DELETE', auth: 'Bearer tok' }])
    expect(naar('/api/auth/logout')).toEqual([])

    await act(async () => { deleteKlaar() })
    await waitFor(() => naar('/api/auth/logout').length === 1)
    expect(naar('/api/auth/logout')[0].auth).toBe('Bearer tok')
  })
})

// #801: wat een vorig bezoek niet bevestigd verwijderde, gaat bij het uitloggen eerst nog met het eigen token, ook
// buiten de chat; daarna is de wachtrij leeg en blijft ze dat.
describe('uitloggen met een verwijderwachtrij (#801)', APP_TEST, () => {
  it('stuurt de wachtrij met het oude token, wist haar en trekt het token pas daarna in', async () => {
    localStorage.setItem(STORAGE_TE_VERWIJDEREN, '["c9"]')
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => { root.render(createElement(App)) })
    await waitFor(() => knop('Uitloggen'))

    await act(async () => { knop('Uitloggen').click() })

    expect(verzoeken.filter(v => v.method === 'DELETE')).toEqual([{ url: '/api/conversations/c9', method: 'DELETE', auth: 'Bearer tok' }])
    expect(localStorage.getItem(STORAGE_TE_VERWIJDEREN)).toBeNull()
    expect(naar('/api/auth/logout')).toEqual([])

    await act(async () => { deleteKlaar() })
    await waitFor(() => naar('/api/auth/logout').length === 1)
    expect(naar('/api/auth/logout')[0].auth).toBe('Bearer tok')
    expect(localStorage.getItem(STORAGE_TE_VERWIJDEREN)).toBeNull()
  })
})
