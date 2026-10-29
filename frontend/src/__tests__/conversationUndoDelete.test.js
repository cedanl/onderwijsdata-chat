// @vitest-environment jsdom
// #493: een gesprek verwijderen is acht seconden ongedaan te maken; pas daarna gaat de DELETE.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

const api = vi.hoisted(() => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  fetchConversations: vi.fn().mockResolvedValue([]),
  fetchConversation: vi.fn(),
  putConversation: vi.fn().mockResolvedValue({}),
  renameConversationApi: vi.fn().mockResolvedValue({}),
  deleteConversationApi: vi.fn().mockResolvedValue({}),
  fetchSettingsConfig: vi.fn().mockResolvedValue({}),
}))
vi.mock('../api', async importOriginal => ({ ...await importOriginal(), ...api }))
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
import { STORAGE_TOKEN, STORAGE_CONVERSATIONS } from '../constants'
import { UITSTEL_MS } from '../verwijderenMetUitstel'
import { SEARCH_DELAY_MS } from '../hooks/useConversationSearch'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const rijen = [
  { id: 'c1', title: 'Eerste gesprek', timestamp: 3 },
  { id: 'c2', title: 'Tweede gesprek', timestamp: 2 },
  { id: 'c3', title: 'Derde gesprek', timestamp: 1 },
]

let root
let container

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chat.toasts = []
  api.fetchConversations.mockResolvedValue(rijen)
  api.deleteConversationApi.mockClear()
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  vi.useRealTimers()
})

async function mount() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  const render = () => root.render(createElement(ChatPage, { user: 'tester' }))
  chat.rerender = () => act(() => render())
  await act(async () => { render() })
}

const titels = () => [...container.querySelectorAll('.history-btn-title')].map(e => e.textContent)
const toast = () => container.querySelector('.toast')

async function verwijder(titel) {
  const knop = container.querySelector(`[aria-label="Verwijder gesprek ${titel}"]`)
  await act(async () => { knop.click() })
  await act(async () => { container.querySelector('.confirm-destructive').click() })
}

async function zoek(tekst) {
  const veld = container.querySelector('[aria-label="Zoek in gesprekken"]')
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(veld, tekst)
    veld.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await act(async () => { vi.advanceTimersByTime(SEARCH_DELAY_MS) })
}

describe('gesprek verwijderen ongedaan maken (#493)', () => {
  it('haalt het gesprek meteen uit de lijst en stuurt de DELETE pas na de bedenktijd', async () => {
    await mount()
    expect(titels()).toEqual(['Eerste gesprek', 'Tweede gesprek', 'Derde gesprek'])

    await verwijder('Tweede gesprek')

    expect(titels()).toEqual(['Eerste gesprek', 'Derde gesprek'])
    expect(JSON.parse(localStorage.getItem(STORAGE_CONVERSATIONS)).map(c => c.id)).toEqual(['c1', 'c3'])
    expect(api.deleteConversationApi).not.toHaveBeenCalled()
    expect(toast().textContent).toContain('Gesprek verwijderd')
    expect(toast().querySelector('.toast-actie').textContent).toBe('Ongedaan maken')

    await act(async () => { vi.advanceTimersByTime(UITSTEL_MS) })
    expect(api.deleteConversationApi).toHaveBeenCalledWith('c2', { keepalive: true })
    expect(toast()).toBeNull()
  })

  it('zet het gesprek op zijn plaats terug en laat de server met rust', async () => {
    await mount()
    await verwijder('Tweede gesprek')

    await act(async () => { toast().querySelector('.toast-actie').click() })

    expect(titels()).toEqual(['Eerste gesprek', 'Tweede gesprek', 'Derde gesprek'])
    expect(JSON.parse(localStorage.getItem(STORAGE_CONVERSATIONS)).map(c => c.id)).toEqual(['c1', 'c2', 'c3'])
    expect(toast()).toBeNull()
    await act(async () => { vi.advanceTimersByTime(UITSTEL_MS * 2) })
    expect(api.deleteConversationApi).not.toHaveBeenCalled()
  })

  it('voert een lopende verwijdering direct uit als de tab verborgen wordt', async () => {
    await mount()
    await verwijder('Derde gesprek')
    await act(async () => { window.dispatchEvent(new Event('pagehide')) })
    expect(api.deleteConversationApi).toHaveBeenCalledWith('c3', { keepalive: true })
  })
})

// #778: een DELETE die niet lukt, laat het gesprek niet stil verdwijnen.
describe('gesprek verwijderen dat op de server mislukt (#778)', () => {
  const fout = Object.assign(new Error('API 500'), { status: 500 })
  const opgeslagen = () => JSON.parse(localStorage.getItem(STORAGE_CONVERSATIONS)).map(c => c.id)

  it('zet het gesprek terug met een melding, en "Opnieuw proberen" verwijdert het alsnog', async () => {
    api.deleteConversationApi.mockRejectedValueOnce(fout)
    await mount()
    await verwijder('Tweede gesprek')
    await act(async () => { vi.advanceTimersByTime(UITSTEL_MS) })

    expect(titels()).toEqual(['Eerste gesprek', 'Tweede gesprek', 'Derde gesprek'])
    expect(opgeslagen()).toEqual(['c1', 'c2', 'c3'])
    expect(toast().classList.contains('error')).toBe(true)
    expect(toast().textContent).toContain('Gesprek verwijderen is niet gelukt. Het staat weer in de lijst.')

    await act(async () => { toast().querySelector('.toast-actie').click() })

    expect(api.deleteConversationApi).toHaveBeenCalledTimes(2)
    expect(api.deleteConversationApi).toHaveBeenLastCalledWith('c2', { keepalive: true })
    expect(titels()).toEqual(['Eerste gesprek', 'Derde gesprek'])
    expect(opgeslagen()).toEqual(['c1', 'c3'])
    expect(toast()).toBeNull()
  })

  it('zet niets terug in de browser als de gebruiker intussen uitlogde', async () => {
    let faal
    api.deleteConversationApi.mockReturnValueOnce(new Promise((_, reject) => { faal = reject }))
    await mount()
    await verwijder('Tweede gesprek')
    await act(async () => { vi.advanceTimersByTime(UITSTEL_MS) })
    localStorage.removeItem(STORAGE_TOKEN)

    await act(async () => { faal(fout) })

    expect(opgeslagen()).toEqual(['c1', 'c3'])
    expect(toast()).toBeNull()
  })
})

// #513: een rapport is een eigen kopie van het gesprek en blijft staan; de bevestiging zegt dat vooraf.
describe('rapporten bij gesprek verwijderen (#513)', () => {
  it('zegt in de bevestiging dat een rapport van het gesprek blijft en waar je het verwijdert', async () => {
    await mount()
    const knop = container.querySelector('[aria-label="Verwijder gesprek Tweede gesprek"]')
    await act(async () => { knop.click() })

    const melding = container.querySelector('.confirm-message').textContent
    expect(melding).toContain('Weet je zeker dat je dit gesprek wilt verwijderen?')
    expect(melding).toMatch(/rapport .*blijft bewaard/i)
    expect(melding).toContain('Rapporten')
  })
})

// #529: verwijderen vanuit de zoekresultaten gaat net als vanuit de lijst, ook voor een treffer die niet in de
// geladen eerste pagina staat (hier 'c9').
describe('gesprek verwijderen vanuit de zoekresultaten (#529)', () => {
  const treffers = [
    { id: 'c2', title: 'Tweede gesprek', timestamp: 2 },
    { id: 'c9', title: 'Oud gesprek', timestamp: 0 },
    { id: 'c3', title: 'Derde gesprek', timestamp: 1 },
  ]
  const opgeslagen = () => JSON.parse(localStorage.getItem(STORAGE_CONVERSATIONS)).map(c => c.id)

  beforeEach(() => {
    api.fetchConversations.mockImplementation(opties => Promise.resolve(opties?.q ? treffers : rijen))
  })

  it('haalt een treffer buiten de lijst meteen weg en stuurt de DELETE pas na de bedenktijd', async () => {
    await mount()
    await zoek('gesprek')
    expect(titels()).toEqual(['Tweede gesprek', 'Oud gesprek', 'Derde gesprek'])

    await verwijder('Oud gesprek')

    expect(titels()).toEqual(['Tweede gesprek', 'Derde gesprek'])
    expect(toast().textContent).toContain('Gesprek verwijderd.')
    expect(toast().querySelector('.toast-actie').textContent).toBe('Ongedaan maken')
    expect(opgeslagen()).toEqual(['c1', 'c2', 'c3'])

    await act(async () => { vi.advanceTimersByTime(UITSTEL_MS - 1) })
    expect(api.deleteConversationApi).not.toHaveBeenCalled()
    await act(async () => { vi.advanceTimersByTime(1) })
    expect(api.deleteConversationApi).toHaveBeenCalledOnce()
    expect(api.deleteConversationApi).toHaveBeenCalledWith('c9', { keepalive: true })
  })

  it('voert de verwijdering van een treffer direct uit als de tab verborgen wordt', async () => {
    await mount()
    await zoek('gesprek')
    await verwijder('Oud gesprek')
    await act(async () => { window.dispatchEvent(new Event('pagehide')) })
    expect(api.deleteConversationApi).toHaveBeenCalledWith('c9', { keepalive: true })
  })

  it('zet de treffer op zijn plaats terug en laat lijst en server met rust', async () => {
    await mount()
    await zoek('gesprek')
    await verwijder('Oud gesprek')

    await act(async () => { toast().querySelector('.toast-actie').click() })

    expect(titels()).toEqual(['Tweede gesprek', 'Oud gesprek', 'Derde gesprek'])
    expect(toast()).toBeNull()
    expect(opgeslagen()).toEqual(['c1', 'c2', 'c3'])
    await act(async () => { vi.advanceTimersByTime(UITSTEL_MS * 2) })
    expect(api.deleteConversationApi).not.toHaveBeenCalled()
  })

  it('haalt een treffer die ook in de lijst staat uit beide en zet hem in beide terug', async () => {
    await mount()
    await zoek('gesprek')
    await verwijder('Tweede gesprek')

    expect(titels()).toEqual(['Oud gesprek', 'Derde gesprek'])
    expect(opgeslagen()).toEqual(['c1', 'c3'])

    await act(async () => { toast().querySelector('.toast-actie').click() })
    expect(titels()).toEqual(['Tweede gesprek', 'Oud gesprek', 'Derde gesprek'])
    expect(opgeslagen()).toEqual(['c1', 'c2', 'c3'])

    await zoek('')
    expect(titels()).toEqual(['Eerste gesprek', 'Tweede gesprek', 'Derde gesprek'])
  })

  it('toont een treffer in zijn bedenktijd niet opnieuw als een nieuwe zoekopdracht hem nog vindt', async () => {
    await mount()
    await zoek('gesprek')
    await verwijder('Oud gesprek')

    await zoek('oud gesprek')

    expect(titels()).toEqual(['Tweede gesprek', 'Derde gesprek'])
    await act(async () => { vi.advanceTimersByTime(UITSTEL_MS) })
    expect(api.deleteConversationApi).toHaveBeenCalledOnce()
    expect(api.deleteConversationApi).toHaveBeenCalledWith('c9', { keepalive: true })
  })

  it('meldt een fout als het gesprek nergens meer staat, en plant geen DELETE', async () => {
    await mount()
    await zoek('gesprek')
    await act(async () => { container.querySelector('[aria-label="Verwijder gesprek Oud gesprek"]').click() })
    // De zoekresultaten verversen terwijl de bevestiging openstaat; 'c9' zit er niet meer in.
    api.fetchConversations.mockImplementation(() => Promise.resolve([treffers[0]]))
    await zoek('tweede')

    await act(async () => { container.querySelector('.confirm-destructive').click() })

    expect(container.querySelector('.confirm-destructive')).toBeNull()
    expect(toast().classList.contains('error')).toBe(true)
    expect(toast().textContent).toBe('Gesprek verwijderen is mislukt. Probeer het opnieuw.')
    await act(async () => { vi.advanceTimersByTime(UITSTEL_MS * 2) })
    expect(api.deleteConversationApi).not.toHaveBeenCalled()
  })
})
