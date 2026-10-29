// @vitest-environment jsdom
// #801: een verwijdering die bij het sluiten van de tab mislukt, gaat bij het volgende laden van de chat opnieuw.
// Tot de server haar bevestigt (een 404 telt mee), staat alleen het id van het gesprek in een wachtrij. De API is hier
// echt (api.js); alleen fetch is nagebootst, zodat ook de 404 van api.js meeloopt.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: () => null }))
vi.mock('react-markdown', () => ({ default: ({ children }) => children }))

// De toasts van useChat nagebootst: addToast bewaart ze en de pagina rendert ze opnieuw.
const chat = vi.hoisted(() => ({ toasts: [], rerender: null }))
const addToast = vi.hoisted(() => (message, level = 'info', opties = {}) => {
  const id = Math.random()
  chat.toasts = [...chat.toasts, { id, message, level, actie: opties.actie || null }]
  chat.rerender?.()
  return () => { chat.toasts = chat.toasts.filter(t => t.id !== id); chat.rerender?.() }
})
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], withBufferedText: m => m, busy: false, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: chat.toasts, reportBusy: false,
    reportProgress: null, reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast,
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_TOKEN, STORAGE_TE_VERWIJDEREN } from '../constants'
import { UITSTEL_MS } from '../verwijderenMetUitstel'
import { inWachtrij, verwijderGesprek, zetInWachtrij } from '../verwijderWachtrij'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const antwoord = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })
const rijen = [
  { id: 'c1', title: 'Eerste gesprek', timestamp: 3 },
  { id: 'c2', title: 'Tweede gesprek', timestamp: 2 },
  { id: 'c3', title: 'Derde gesprek', timestamp: 1 },
]

let root
let container
let verwijderingen // de DELETE's die op een antwoord wachten, oudste eerst

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chat.toasts = []
  verwijderingen = []
  vi.stubGlobal('fetch', vi.fn((url, opties = {}) => {
    if (opties.method === 'DELETE') {
      return new Promise(resolve => { verwijderingen.push({ url, keepalive: opties.keepalive, antwoord: s => resolve(antwoord(s)) }) })
    }
    if (url.startsWith('/api/conversations') && !opties.method) return Promise.resolve(antwoord(200, rijen))
    return Promise.resolve(antwoord(200, {}))
  }))
})

afterEach(async () => {
  // Elke DELETE krijgt een antwoord: een belofte die blijft hangen, zou het volgende verzoek voor dat id overnemen.
  for (const v of verwijderingen) v.antwoord(200)
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  chat.rerender = null
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

async function mount() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  const render = () => root.render(createElement(ChatPage, { user: 'tester' }))
  chat.rerender = () => act(() => render())
  await act(async () => { render() })
}

async function unmount() {
  chat.rerender = null
  await act(async () => root.unmount())
  container.remove()
  root = null
}

// Het antwoord op de oudste DELETE die nog wacht; de keten erachter (api.js, de wachtrij, de pagina) loopt helemaal af.
async function beantwoordDelete(status) {
  const v = verwijderingen.shift()
  await act(async () => {
    v.antwoord(status)
    for (let i = 0; i < 20; i++) await Promise.resolve()
  })
  return v
}

const titels = () => [...container.querySelectorAll('.history-btn-title')].map(e => e.textContent)
const toast = () => container.querySelector('.toast')

async function verwijder(titel) {
  await act(async () => { container.querySelector(`[aria-label="Verwijder gesprek ${titel}"]`).click() })
  await act(async () => { container.querySelector('.confirm-destructive').click() })
}

describe('de verwijderwachtrij zelf (#801)', () => {
  it('bewaart alleen het id, één keer', () => {
    zetInWachtrij('c2')
    zetInWachtrij('c2')
    expect(localStorage.getItem(STORAGE_TE_VERWIJDEREN)).toBe('["c2"]')
  })

  it('haalt het id eruit na een 404: dan is het gesprek al weg', async () => {
    zetInWachtrij('c2')
    const klaar = verwijderGesprek('c2')
    expect(verwijderingen.map(v => [v.url, v.keepalive])).toEqual([['/api/conversations/c2', true]])
    await beantwoordDelete(404)
    await klaar
    expect(inWachtrij()).toEqual([])
    expect(localStorage.getItem(STORAGE_TE_VERWIJDEREN)).toBeNull()
  })

  it('laat het id staan na een 5xx', async () => {
    zetInWachtrij('c2')
    const klaar = verwijderGesprek('c2')
    await beantwoordDelete(503)
    await expect(klaar).rejects.toMatchObject({ status: 503 })
    expect(inWachtrij()).toEqual(['c2'])
  })

  it('stuurt een id dat al onderweg is niet nog een keer', async () => {
    zetInWachtrij('c2')
    const eerste = verwijderGesprek('c2')
    expect(verwijderGesprek('c2')).toBe(eerste)
    expect(verwijderingen).toHaveLength(1)
    await beantwoordDelete(200)
    await eerste
  })

  it('telt een onleesbare wachtrij als leeg', () => {
    localStorage.setItem(STORAGE_TE_VERWIJDEREN, '{kapot')
    expect(inWachtrij()).toEqual([])
  })
})

describe('verwijderen in de chat met de wachtrij (#801)', () => {
  it('zet het id bij het plannen in de wachtrij; ongedaan maken en een geslaagde DELETE halen het eruit', async () => {
    await mount()
    await verwijder('Tweede gesprek')
    expect(inWachtrij()).toEqual(['c2'])

    await act(async () => { toast().querySelector('.toast-actie').click() })
    expect(inWachtrij()).toEqual([])

    await verwijder('Derde gesprek')
    expect(inWachtrij()).toEqual(['c3'])
    await act(async () => { vi.advanceTimersByTime(UITSTEL_MS) })
    await beantwoordDelete(200)
    expect(inWachtrij()).toEqual([])
  })

  it('stuurt een pagehide-DELETE die mislukte bij de volgende mount opnieuw, en toont het gesprek niet', async () => {
    await mount()
    await verwijder('Tweede gesprek')
    await act(async () => { window.dispatchEvent(new Event('pagehide')) })
    // De tab is dicht; pas daarna faalt de DELETE.
    await unmount()
    expect((await beantwoordDelete(503)).url).toBe('/api/conversations/c2')
    expect(inWachtrij()).toEqual(['c2'])

    chat.toasts = []
    await mount()

    expect(verwijderingen.map(v => [v.url, v.keepalive])).toEqual([['/api/conversations/c2', true]])
    expect(titels()).toEqual(['Eerste gesprek', 'Derde gesprek'])
    await beantwoordDelete(200)
    expect(titels()).toEqual(['Eerste gesprek', 'Derde gesprek'])
    expect(inWachtrij()).toEqual([])
    expect(toast()).toBeNull()
  })

  it('haalt een gesprek dat de server niet meer kent (404) bij het laden uit de wachtrij, zonder melding', async () => {
    zetInWachtrij('c9')
    await mount()

    expect((await beantwoordDelete(404)).url).toBe('/api/conversations/c9')

    expect(inWachtrij()).toEqual([])
    expect(titels()).toEqual(['Eerste gesprek', 'Tweede gesprek', 'Derde gesprek'])
    expect(toast()).toBeNull()
  })

  it('zet het gesprek terug met de melding van #778 als het bij het laden weer mislukt; "Opnieuw proberen" verwijdert het', async () => {
    zetInWachtrij('c2')
    await mount()
    expect(titels()).toEqual(['Eerste gesprek', 'Derde gesprek'])

    await beantwoordDelete(503)

    expect(titels()).toEqual(['Eerste gesprek', 'Tweede gesprek', 'Derde gesprek'])
    expect(toast().classList.contains('error')).toBe(true)
    expect(toast().textContent).toContain('Gesprek verwijderen is niet gelukt. Het staat weer in de lijst.')
    expect(inWachtrij()).toEqual(['c2'])

    await act(async () => { toast().querySelector('.toast-actie').click() })
    expect(titels()).toEqual(['Eerste gesprek', 'Derde gesprek'])
    expect((await beantwoordDelete(200)).url).toBe('/api/conversations/c2')
    expect(inWachtrij()).toEqual([])
    expect(toast()).toBeNull()
  })
})
