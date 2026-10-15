// @vitest-environment jsdom
// #547: bij een zware vraag (UWV, ROA) zegt de chat naast de voortgang wat de gebruiker
// kan verwachten, zodra zo'n stap in deze beurt is gestart.
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

const chat = vi.hoisted(() => ({ messages: [], busy: false }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chat.messages, busy: chat.busy, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false,
    reportProgress: { steps: 0, label: null }, reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast: () => {},
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const WACHTREGEL = 'Dit kan 2–3 minuten duren.'
const beurt = (...tools) => [
  { id: 1, role: 'user', content: 'Hoeveel vacatures zijn er in de zorg?', done: true },
  { id: 2, role: 'assistant', content: '', done: false, tools },
]

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chat.busy = true
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
})

async function mountChat() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { user: 'tester' })) })
}

describe('ChatPage: wachtregel bij een zware vraag (#547)', () => {
  it('staat naast de voortgang zodra de UWV-stap loopt', async () => {
    chat.messages = beurt({ name: 'search_catalog', label: 'Catalogus doorzoeken', done: true },
      { name: 'get_uwv_vacatures', label: 'Vacatures ophalen', done: false })
    await mountChat()
    expect(container.querySelector('.run-progress')).not.toBeNull()
    expect(container.querySelector('.run-progress-note').textContent).toBe(WACHTREGEL)
  })

  it('ontbreekt bij een beurt met alleen lichte stappen', async () => {
    chat.messages = beurt({ name: 'search_catalog', label: 'Catalogus doorzoeken', done: true },
      { name: 'get_cbs_data', label: 'CBS-data ophalen', done: false })
    await mountChat()
    expect(container.querySelector('.run-progress')).not.toBeNull()
    expect(container.textContent).not.toContain(WACHTREGEL)
  })

  it('ontbreekt als er niets loopt', async () => {
    chat.busy = false
    chat.messages = beurt({ name: 'get_roa_benchmark', label: 'ROA-benchmark ophalen', done: true })
    await mountChat()
    expect(container.textContent).not.toContain(WACHTREGEL)
  })
})
