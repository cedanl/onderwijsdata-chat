// @vitest-environment jsdom
// #776: na verwijderen, ongedaan maken, een gesprek openen en "Nieuw gesprek" staat de focus op een logische plek,
// en de bedenktijd van "Ongedaan maken" staat stil zolang de melding muis of toetsenbord heeft.
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

// De toasts van useChat nagebootst, met alle opties die de ToastStack gebruikt.
const chat = vi.hoisted(() => ({ toasts: [], rerender: null }))
const addToast = vi.hoisted(() => (message, level = 'info', opties = {}) => {
  const id = Math.random()
  const { actie = null, focus = false, pauzeer = null, hervat = null, verlaat = null } = opties
  chat.toasts = [...chat.toasts, { id, message, level, actie, focus, pauzeer, hervat, verlaat }]
  chat.rerender?.()
  return () => { chat.toasts = chat.toasts.filter(t => t.id !== id); chat.rerender?.() }
})
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], withBufferedText: m => m, busy: false, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: chat.toasts, reportBusy: false,
    reportProgress: null, reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), openConversation: vi.fn(), addToast,
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_TOKEN } from '../constants'
import { UITSTEL_MS } from '../verwijderenMetUitstel'

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
// jsdom noemt elke focus :focus-visible; een browser doet dat na een muisklik niet. Per test te kiezen.
let toetsenbord

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chat.toasts = []
  api.fetchConversations.mockResolvedValue(rijen)
  api.deleteConversationApi.mockClear()
  toetsenbord = true
  const matches = Element.prototype.matches
  vi.spyOn(Element.prototype, 'matches').mockImplementation(function (kiezer) {
    return kiezer === ':focus-visible' ? toetsenbord && this === document.activeElement : matches.call(this, kiezer)
  })
})

afterEach(async () => {
  // Unmounten voert een lopende verwijdering uit (pagehide-pad); die sluit dan zijn melding in een root die al weg is.
  chat.rerender = null
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  vi.restoreAllMocks()
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

const gespreksKnop = id => container.querySelector(`.history-btn[data-conv-id="${id}"]`)
const ongedaanKnop = () => container.querySelector('.toast-actie')
const toets = (el, key) => act(async () => { el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })) })
const wacht = ms => act(async () => { vi.advanceTimersByTime(ms) })

async function verwijder(titel) {
  const knop = container.querySelector(`[aria-label="Verwijder gesprek ${titel}"]`)
  await act(async () => { knop.focus(); knop.click() })
  await act(async () => { container.querySelector('.confirm-destructive').click() })
}

describe('focus na gesprek verwijderen (#776)', () => {
  it('gaat naar Ongedaan maken, en de bedenktijd staat stil zolang het toetsenbord daar is', async () => {
    await mount()
    await verwijder('Tweede gesprek')

    expect(document.activeElement).toBe(ongedaanKnop())
    await wacht(UITSTEL_MS * 3)
    expect(api.deleteConversationApi).not.toHaveBeenCalled()
  })

  it('Tab verlaat de melding naar het volgende gesprek; daarna loopt de bedenktijd verder', async () => {
    await mount()
    await verwijder('Tweede gesprek')
    await wacht(UITSTEL_MS)

    await toets(ongedaanKnop(), 'Tab')

    expect(document.activeElement).toBe(gespreksKnop('c3'))
    await wacht(UITSTEL_MS - 1)
    expect(api.deleteConversationApi).not.toHaveBeenCalled()
    await wacht(1)
    expect(api.deleteConversationApi).toHaveBeenCalledWith('c2', { keepalive: true })
    expect(document.activeElement).toBe(gespreksKnop('c3'))
  })

  it('Escape op het laatste gesprek zet de focus op het gesprek ervoor', async () => {
    await mount()
    await verwijder('Derde gesprek')
    await toets(ongedaanKnop(), 'Escape')
    expect(document.activeElement).toBe(gespreksKnop('c2'))
  })

  it('zonder gesprekken over gaat de focus naar "Nieuw gesprek"', async () => {
    api.fetchConversations.mockResolvedValue([rijen[0]])
    await mount()
    await verwijder('Eerste gesprek')
    await toets(ongedaanKnop(), 'Tab')
    expect(document.activeElement).toBe(container.querySelector('.new-chat-btn'))
  })

  it('na Ongedaan maken staat de focus op het teruggezette gesprek', async () => {
    await mount()
    await verwijder('Tweede gesprek')
    await act(async () => { ongedaanKnop().click() })
    expect(container.querySelector('.toast')).toBeNull()
    expect(document.activeElement).toBe(gespreksKnop('c2'))
  })

  it('met de muis loopt de tijd door, en na afloop valt de focus niet op <body>', async () => {
    toetsenbord = false
    await mount()
    await verwijder('Tweede gesprek')
    expect(document.activeElement).toBe(ongedaanKnop())

    await wacht(UITSTEL_MS)

    expect(api.deleteConversationApi).toHaveBeenCalledWith('c2', { keepalive: true })
    expect(container.querySelector('.toast')).toBeNull()
    expect(document.activeElement).toBe(gespreksKnop('c3'))
  })

  it('de muis op de melding houdt de tijd vast, eraf laat hem verder lopen', async () => {
    toetsenbord = false
    await mount()
    await verwijder('Tweede gesprek')
    const melding = container.querySelector('.toast')

    await act(async () => { melding.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, relatedTarget: document.body })) })
    await wacht(UITSTEL_MS * 2)
    expect(api.deleteConversationApi).not.toHaveBeenCalled()

    await act(async () => { melding.dispatchEvent(new MouseEvent('mouseout', { bubbles: true, relatedTarget: document.body })) })
    await wacht(UITSTEL_MS)
    expect(api.deleteConversationApi).toHaveBeenCalledOnce()
  })
})

describe('focus na een gesprek openen of "Nieuw gesprek" (#776)', () => {
  it('een geopend gesprek krijgt zelf de focus, niet het invoerveld', async () => {
    api.fetchConversation.mockResolvedValue({ ...rijen[0], messages: [{ role: 'user', content: 'Een vraag' }] })
    await mount()
    await act(async () => { gespreksKnop('c1').focus(); gespreksKnop('c1').click() })
    await act(async () => {})

    expect(document.activeElement).toBe(container.querySelector('.chat-messages'))
    expect(document.activeElement.getAttribute('aria-label')).toBe('Gesprek')
  })

  it('"Nieuw gesprek" zet de focus in het invoerveld', async () => {
    await mount()
    const knop = container.querySelector('.new-chat-btn')
    await act(async () => { knop.focus(); knop.click() })
    expect(document.activeElement).toBe(container.querySelector('.chat-input'))
  })
})
