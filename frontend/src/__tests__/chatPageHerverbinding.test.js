// @vitest-environment jsdom
// #756: elke WebSocket is een nieuwe serversessie. Na een herverbinding kende de server het open gesprek niet meer:
// de historie ging maar één keer per pagina mee.
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

// Stabiele functies, zoals de useCallbacks van de echte useChat: anders draait elk effect dat ervan afhangt bij
// elke render opnieuw.
const chat = vi.hoisted(() => ({
  messages: [],
  connected: false,
  sendHistory: vi.fn(),
  sendSettings: vi.fn(),
  addToast: () => () => {},
  noop: () => {},
}))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chat.messages, busy: false, withBufferedText: all => all, rejectedDraft: null,
    clearRejectedDraft: chat.noop, thinking: false, connected: chat.connected, resetting: false, historyDataKeys: 0,
    toasts: [], reportBusy: false, reportProgress: null, reportSpec: null, send: chat.noop, sendClarification: chat.noop,
    sendSettings: chat.sendSettings, sendHistory: chat.sendHistory, stop: chat.noop, checkReportStart: chat.noop,
    generateReport: chat.noop, cancelReport: chat.noop, clearReport: chat.noop, clear: chat.noop,
    startNewConversation: chat.noop, addToast: chat.addToast,
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_CURRENT_CHAT, STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const VRAAG = { id: 1, role: 'user', content: 'Hoeveel studenten heeft de HU?', done: true }
const ANTWOORD = { id: 2, role: 'assistant', content: 'Zoveel.', done: true }

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chat.messages = []
  chat.connected = false
  chat.sendHistory.mockReset()
  chat.sendSettings.mockReset()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
})

async function render() {
  await act(async () => { root.render(createElement(ChatPage, { user: 'u' })) })
}

async function verbinding(aan) {
  chat.connected = aan
  await render()
}

describe('ChatPage na een herverbinding (#756)', () => {
  it('stuurt een hersteld gesprek bij de eerste verbinding, met zijn id', async () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id: 'conv-a', messages: [VRAAG, ANTWOORD] }))
    await render()
    expect(chat.sendHistory).not.toHaveBeenCalled()

    await verbinding(true)

    expect(chat.sendHistory).toHaveBeenCalledTimes(1)
    const [berichten, id] = chat.sendHistory.mock.calls[0]
    expect(id).toBe('conv-a')
    expect(berichten.map(m => m.content)).toEqual([VRAAG.content, ANTWOORD.content])
  })

  it('stuurt het open gesprek opnieuw na een herverbinding, met wat er sinds het laden bij kwam', async () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id: 'conv-a', messages: [VRAAG, ANTWOORD] }))
    await verbinding(true)
    chat.messages = [{ id: 3, role: 'user', content: 'En in 2022?', done: true }, { id: 4, role: 'assistant', content: 'Minder.', done: true }]
    await render()

    await verbinding(false)
    await verbinding(true)

    expect(chat.sendHistory).toHaveBeenCalledTimes(2)
    const [berichten, id] = chat.sendHistory.mock.calls[1]
    expect(id).toBe('conv-a')
    expect(berichten.map(m => m.content)).toEqual(['Hoeveel studenten heeft de HU?', 'Zoveel.', 'En in 2022?', 'Minder.'])
  })

  it('stuurt een gesprek dat pas na het laden begon ook na een herverbinding', async () => {
    await verbinding(true)
    expect(chat.sendHistory).not.toHaveBeenCalled()
    chat.messages = [VRAAG, ANTWOORD]
    await render()

    await verbinding(false)
    await verbinding(true)

    expect(chat.sendHistory).toHaveBeenCalledTimes(1)
    expect(chat.sendHistory.mock.calls[0][0].map(m => m.content)).toEqual([VRAAG.content, ANTWOORD.content])
  })

  it('stuurt na "Nieuw gesprek" en een herverbinding het oude gesprek niet', async () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id: 'conv-a', messages: [VRAAG, ANTWOORD] }))
    await verbinding(true)
    expect(chat.sendHistory).toHaveBeenCalledTimes(1)

    // De echte useChat leegt zijn berichten bij een nieuw gesprek (clear); de mock doet dat hier.
    await act(async () => { container.querySelector('.new-chat-btn').click() })
    chat.messages = []
    await render()
    await verbinding(false)
    await verbinding(true)

    expect(chat.sendHistory).toHaveBeenCalledTimes(1)
  })

  it('stuurt niets zonder open gesprek', async () => {
    await verbinding(true)
    await verbinding(false)
    await verbinding(true)
    expect(chat.sendHistory).not.toHaveBeenCalled()
  })
})
