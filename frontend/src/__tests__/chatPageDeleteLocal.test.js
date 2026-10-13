// @vitest-environment jsdom
// #530 (privacy M7): een verwijderd open gesprek kwam na verversen terug, omdat pagehide en het
// save-effect het weer in localStorage schreven. Tot een nieuw gesprek of een nieuwe vraag blijft het weg.
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

// De test stuurt per render wat useChat teruggeeft; addToast bewaart de knop "Ongedaan maken".
const chatState = vi.hoisted(() => ({ messages: [], busy: false, buffered: '', ongedaan: null }))
const addToast = vi.hoisted(() => (msg, level, opties) => {
  if (opties?.actie) chatState.ongedaan = opties.actie.onClick
  return () => {}
})
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chatState.messages, busy: chatState.busy,
    withBufferedText: all => chatState.buffered
      ? all.with(-1, { ...all.at(-1), content: all.at(-1).content + chatState.buffered })
      : all, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false,
    reportProgress: null, reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast,
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_CURRENT_CHAT, STORAGE_TOKEN } from '../constants'
import { UITSTEL_MS } from '../verwijderenMetUitstel'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const vraag = { id: 1, role: 'user', content: 'Mijn BSN is 123456782, hoeveel studenten?', done: true }
const antwoord = { id: 2, role: 'assistant', content: 'Er zijn 1200 studenten.', done: true }
const rijen = [
  { id: 'c1', title: 'Open gesprek', timestamp: 2 },
  { id: 'c2', title: 'Ander gesprek', timestamp: 1 },
]

let root
let container

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id: 'c1', messages: [vraag, antwoord] }))
  chatState.messages = []
  chatState.busy = false
  chatState.buffered = ''
  chatState.ongedaan = null
  api.fetchConversations.mockResolvedValue(rijen)
  api.fetchConversation.mockReset()
  api.deleteConversationApi.mockClear()
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  vi.useRealTimers()
})

async function render() {
  await act(async () => { root.render(createElement(ChatPage, { user: 'u' })) })
}

async function mount() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await render()
}

async function verwijder(titel) {
  await act(async () => { container.querySelector(`[aria-label="Verwijder gesprek ${titel}"]`).click() })
  await act(async () => { document.querySelector('.confirm-destructive').click() })
}

const bedenktijdVoorbij = () => act(async () => { vi.advanceTimersByTime(UITSTEL_MS) })
const pagehide = () => act(async () => { window.dispatchEvent(new Event('pagehide')) })

async function tabVerborgen() {
  Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
  Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
}

const opgeslagen = () => localStorage.getItem(STORAGE_CURRENT_CHAT)

describe('verwijderd open gesprek blijft uit localStorage (#530)', () => {
  it('komt na de bedenktijd niet terug bij pagehide', async () => {
    await mount()
    await verwijder('Open gesprek')
    await bedenktijdVoorbij()
    expect(api.deleteConversationApi).toHaveBeenCalledWith('c1', { keepalive: true })
    expect(opgeslagen()).toBeNull()

    await pagehide()

    expect(opgeslagen()).toBeNull()
  })

  it('komt na de bedenktijd niet terug als de tab verborgen wordt', async () => {
    await mount()
    await verwijder('Open gesprek')
    await bedenktijdVoorbij()

    await tabVerborgen()

    expect(opgeslagen()).toBeNull()
  })

  it('voert bij pagehide binnen de bedenktijd de DELETE uit en laat de sleutel leeg', async () => {
    await mount()
    await verwijder('Open gesprek')

    await pagehide()

    expect(api.deleteConversationApi).toHaveBeenCalledWith('c1', { keepalive: true })
    expect(opgeslagen()).toBeNull()
  })

  it('schrijft binnen de bedenktijd niets, zodat de volgorde van de listeners niet uitmaakt', async () => {
    await mount()
    await verwijder('Open gesprek')
    // Alleen de opslaan-listener loopt bij visibilitychange; de DELETE wacht nog.
    localStorage.removeItem(STORAGE_CURRENT_CHAT)

    await tabVerborgen()

    expect(api.deleteConversationApi).not.toHaveBeenCalled()
    expect(opgeslagen()).toBeNull()
  })

  it('schrijft een antwoord dat na het verwijderen afrondt niet terug', async () => {
    chatState.busy = true
    chatState.messages = [{ id: 3, role: 'assistant', content: 'half', done: false }]
    await mount()
    await verwijder('Open gesprek')
    await bedenktijdVoorbij()

    chatState.busy = false
    chatState.messages = [{ id: 3, role: 'assistant', content: 'half en heel', done: true }]
    await render()
    await render()
    await pagehide()

    expect(opgeslagen()).toBeNull()
  })

  it('zet het gesprek bij ongedaan maken meteen terug en houdt het bij pagehide', async () => {
    await mount()
    await verwijder('Open gesprek')
    localStorage.removeItem(STORAGE_CURRENT_CHAT)

    await act(async () => { chatState.ongedaan() })

    expect(JSON.parse(opgeslagen())).toMatchObject({ id: 'c1', messages: [vraag, antwoord] })
    await act(async () => { vi.advanceTimersByTime(UITSTEL_MS * 2) })
    expect(api.deleteConversationApi).not.toHaveBeenCalled()
    await pagehide()
    expect(JSON.parse(opgeslagen()).id).toBe('c1')
  })

  it('bewaart weer zodra er in hetzelfde scherm een nieuwe vraag komt', async () => {
    await mount()
    await verwijder('Open gesprek')
    await bedenktijdVoorbij()

    chatState.messages = [{ id: 3, role: 'user', content: 'Nieuwe vraag', done: true }]
    await render()

    expect(opgeslagen()).toContain('Nieuwe vraag')
  })

  it('bewaart weer na "Nieuw gesprek"', async () => {
    await mount()
    await verwijder('Open gesprek')
    await bedenktijdVoorbij()

    await act(async () => { container.querySelector('.new-chat-btn').click() })
    chatState.messages = [{ id: 3, role: 'user', content: 'Eerste vraag', done: true }]
    await render()
    localStorage.removeItem(STORAGE_CURRENT_CHAT)
    await pagehide()

    expect(opgeslagen()).toContain('Eerste vraag')
  })

  it('bewaart weer na het openen van een ander gesprek', async () => {
    api.fetchConversation.mockResolvedValue({
      ...rijen[1], messages: [{ id: 5, role: 'user', content: 'Andere vraag', done: true }],
    })
    await mount()
    await verwijder('Open gesprek')
    await bedenktijdVoorbij()

    const ander = [...container.querySelectorAll('.history-btn')].find(b => b.textContent.includes('Ander gesprek'))
    await act(async () => { ander.click() })
    await pagehide()

    expect(JSON.parse(opgeslagen())).toMatchObject({ id: 'c2' })
  })

  it('blokkeert niets als een ander dan het open gesprek wordt verwijderd', async () => {
    await mount()
    await verwijder('Ander gesprek')
    await bedenktijdVoorbij()
    expect(api.deleteConversationApi).toHaveBeenCalledWith('c2', { keepalive: true })
    localStorage.removeItem(STORAGE_CURRENT_CHAT)

    await pagehide()

    expect(JSON.parse(opgeslagen())).toMatchObject({ id: 'c1', messages: [vraag, antwoord] })
  })
})
