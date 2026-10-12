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
