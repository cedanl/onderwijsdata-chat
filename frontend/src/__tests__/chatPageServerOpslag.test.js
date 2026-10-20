// @vitest-environment jsdom
// #635: een gesprek kwam na een verbindingsbreuk of herladen tijdens een vraag niet op de server. De mislukte
// PUT telde als opgeslagen, en een hersteld gesprek gold na herladen meteen als "al opgeslagen".
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

const api = vi.hoisted(() => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  fetchConversations: vi.fn().mockResolvedValue([]),
  putConversation: vi.fn().mockResolvedValue({}),
  renameConversationApi: vi.fn().mockResolvedValue({}),
  deleteConversationApi: vi.fn().mockResolvedValue({}),
  fetchSettingsConfig: vi.fn().mockResolvedValue({}),
}))
vi.mock('../api', async importOriginal => ({ ...await importOriginal(), ...api }))
vi.mock('react-plotly.js', () => ({ default: () => null }))
vi.mock('react-markdown', () => ({ default: ({ children }) => children }))

const chatState = vi.hoisted(() => ({ messages: [], busy: false, addToast: null, buffered: '', toasts: [], connected: true }))
// Stabiele identiteit, zoals de echte addToast uit useChat (useCallback); geeft net als
// de echte een functie terug die de toast weghaalt (#493).
const stableToast = vi.hoisted(() => (...a) => {
  chatState.addToast?.(...a)
  return () => {}
})
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chatState.messages, busy: chatState.busy,
    // Zoals de echte: het lopende (laatste) antwoord plus wat nog in de deltabuffer zit (#520).
    withBufferedText: all => chatState.buffered
      ? all.with(-1, { ...all.at(-1), content: all.at(-1).content + chatState.buffered })
      : all, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: chatState.connected, resetting: false, historyDataKeys: 0, toasts: chatState.toasts, reportBusy: false,
    reportProgress: null, reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast: stableToast,
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_CURRENT_CHAT, STORAGE_SAVED_CHAT, STORAGE_TOKEN } from '../constants'
import { noteerOpgeslagen } from '../gesprekOpslag'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chatState.messages = [{ id: 1, role: 'user', content: 'Hoeveel studenten?', done: true }]
  chatState.busy = false
  chatState.addToast = null
  chatState.buffered = ''
  chatState.toasts = []
  chatState.connected = true
  api.putConversation.mockReset().mockResolvedValue({})
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  vi.restoreAllMocks()
})

async function render() {
  await act(async () => { root.render(createElement(ChatPage, { user: 'u' })) })
}

async function mountChat() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await render()
}

const vraag = { id: 1, role: 'user', content: 'Hoeveel studenten?', done: true }
const antwoord = { id: 2, role: 'assistant', content: 'In 2024 waren er 470.000.', done: true }
const puts = () => api.putConversation.mock.calls

describe('een mislukte opslag telt niet als opgeslagen', () => {
  it('stuurt het gesprek opnieuw zodra de verbinding terug is', async () => {
    api.putConversation.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    chatState.messages = [vraag, antwoord]
    await mountChat()
    expect(puts()).toHaveLength(1)
    expect(localStorage.getItem(STORAGE_SAVED_CHAT)).toBeNull()

    chatState.connected = false
    await render()
    chatState.connected = true
    await render()
    expect(puts()).toHaveLength(2)
    expect(puts()[1][1].messages.map(m => m.content)).toEqual([vraag.content, antwoord.content])
    expect(JSON.parse(localStorage.getItem(STORAGE_SAVED_CHAT)).id).toBe(puts()[1][0])
  })

  it('bewaart een afgebroken antwoord met zijn deeltekst op de server', async () => {
    const half = { id: 2, role: 'assistant', content: '| Jaar | Studenten |\n| 2023 | 470.000 |', done: true, interrupted: true }
    chatState.messages = [vraag, half]
    await mountChat()
    expect(puts()[0][1].messages[1]).toMatchObject({ content: half.content, interrupted: true })
  })
})

describe('een hersteld gesprek na herladen', () => {
  const herstel = (messages) => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id: 'c-herladen', messages }))
    chatState.messages = []
  }

  it('gaat naar de server als de laatste opslag niet aankwam (herladen tijdens een vraag)', async () => {
    herstel([vraag, { id: 2, role: 'assistant', content: 'half antwoord', done: true, interrupted: true }])
    await mountChat()
    expect(puts()).toHaveLength(1)
    expect(puts()[0][0]).toBe('c-herladen')
    expect(puts()[0][1].messages[0].content).toBe(vraag.content)
  })

  it('gaat niet nog eens naar de server als die het al heeft', async () => {
    const messages = [vraag, antwoord]
    herstel(messages)
    noteerOpgeslagen('c-herladen', JSON.stringify(messages))
    await mountChat()
    expect(puts()).toHaveLength(0)
  })
})

describe('een gewoon gesprek', () => {
  it('stuurt elk afgerond antwoord één keer, ook na een verbindingswissel', async () => {
    chatState.messages = [vraag, antwoord]
    await mountChat()
    await render()
    chatState.connected = false
    await render()
    chatState.connected = true
    await render()
    expect(puts()).toHaveLength(1)

    chatState.busy = true
    chatState.messages = [vraag, antwoord, { id: 3, role: 'user', content: 'En in 2023?', done: true }, { id: 4, role: 'assistant', content: 'In 2023', done: false }]
    await render()
    chatState.busy = false
    chatState.messages = chatState.messages.with(3, { id: 4, role: 'assistant', content: 'In 2023 waren het er meer.', done: true })
    await render()
    expect(puts()).toHaveLength(2)
  })
})
