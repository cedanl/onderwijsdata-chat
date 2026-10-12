// @vitest-environment jsdom
// #511: niet bij elk tekstfragment het hele gesprek naar localStorage, en een volle
// opslag faalt niet langer stil.
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

const chatState = vi.hoisted(() => ({ messages: [], busy: false, addToast: null, buffered: '' }))
// Stabiele identiteit, zoals de echte addToast uit useChat (useCallback).
const stableToast = vi.hoisted(() => (...a) => chatState.addToast?.(...a))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chatState.messages, busy: chatState.busy,
    // Zoals de echte: het lopende (laatste) antwoord plus wat nog in de deltabuffer zit (#520).
    withBufferedText: all => chatState.buffered
      ? all.with(-1, { ...all.at(-1), content: all.at(-1).content + chatState.buffered })
      : all, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false,
    reportProgress: null, reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast: stableToast,
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_CURRENT_CHAT, STORAGE_TOKEN } from '../constants'

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

const chatSetItems = (spy) => spy.mock.calls.filter(([key]) => key === STORAGE_CURRENT_CHAT)

describe('opslaan per afgerond antwoord (#511)', () => {
  it('schrijft tijdens een stream niet per tekstfragment', async () => {
    await mountChat()
    const spy = vi.spyOn(Storage.prototype, 'setItem')

    chatState.busy = true
    const antwoord = { id: 2, role: 'assistant', content: '', tools: [], done: false }
    for (let i = 0; i < 25; i++) {
      antwoord.content += `fragment ${i} `
      chatState.messages = [chatState.messages[0], { ...antwoord }]
      await render()
    }
    expect(chatSetItems(spy)).toHaveLength(0)

    chatState.busy = false
    chatState.messages = [chatState.messages[0], { ...antwoord, done: true }]
    await render()

    const schrijfacties = chatSetItems(spy)
    expect(schrijfacties).toHaveLength(1)
    expect(schrijfacties[0][1]).toContain('fragment 24')
  })

  it('bewaart bij het verbergen van de tab ook een nog streamend antwoord', async () => {
    await mountChat()
    chatState.busy = true
    chatState.messages = [chatState.messages[0], { id: 2, role: 'assistant', content: 'half antw', tools: [], done: false }]
    await render()
    localStorage.removeItem(STORAGE_CURRENT_CHAT)

    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })

    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toContain('half antw')
  })

  it('bewaart bij het verbergen ook wat nog in de deltabuffer zit (#520)', async () => {
    await mountChat()
    chatState.busy = true
    chatState.messages = [chatState.messages[0], { id: 2, role: 'assistant', content: 'half', tools: [], done: false }]
    chatState.buffered = ' antwoord in de buffer'
    await render()
    localStorage.removeItem(STORAGE_CURRENT_CHAT)

    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })

    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toContain('half antwoord in de buffer')
  })

  it('bewaart bij pagehide ook als de tab nog zichtbaar heet (Safari/iOS)', async () => {
    await mountChat()
    chatState.busy = true
    chatState.messages = [chatState.messages[0], { id: 2, role: 'assistant', content: 'half', tools: [], done: false }]
    chatState.buffered = ' en de rest'
    await render()
    localStorage.removeItem(STORAGE_CURRENT_CHAT)

    expect(document.visibilityState).toBe('visible')
    await act(async () => { window.dispatchEvent(new Event('pagehide')) })

    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toContain('half en de rest')
  })

  it('bewaart niet bij visibilitychange naar zichtbaar', async () => {
    await mountChat()
    chatState.busy = true
    chatState.messages = [chatState.messages[0], { id: 2, role: 'assistant', content: 'half', tools: [], done: false }]
    await render()
    localStorage.removeItem(STORAGE_CURRENT_CHAT)

    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })

    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toBeNull()
  })

  it('meldt een volle opslag één keer in plaats van stil te falen', async () => {
    const meldingen = []
    chatState.addToast = (msg) => meldingen.push(msg)
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key) => {
      if (key === STORAGE_CURRENT_CHAT) throw new DOMException('kapot', 'QuotaExceededError')
    })
    await mountChat()

    chatState.messages = [...chatState.messages, { id: 2, role: 'assistant', content: 'antwoord', done: true }]
    await render()
    chatState.messages = [...chatState.messages, { id: 3, role: 'assistant', content: 'nog een', done: true }]
    await render()

    expect(meldingen.filter(m => m.includes('opslag is vol'))).toHaveLength(1)
  })
})
