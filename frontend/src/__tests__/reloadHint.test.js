// @vitest-environment jsdom
// #551 (UX F04): een heropend gesprek zonder recept voor zijn data biedt één klik om de laatste
// datavraag opnieuw te stellen, in plaats van alleen de tekst dat de gebruiker eerst iets moet vragen.
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

const chat = vi.hoisted(() => ({ historyDataKeys: 0, send: null }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], busy: false, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: chat.historyDataKeys, toasts: [],
    reportBusy: false, reportProgress: { steps: 0, label: null }, reportSpec: null, send: chat.send,
    sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(),
    cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast: () => {},
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_CURRENT_CHAT, STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const VRAAG = 'Hoeveel studenten heeft de HU?'
// Een heropend gesprek met een antwoord met data, zoals de gespreksopslag het teruggeeft.
const HEROPEND = [
  { id: 1, role: 'user', content: VRAAG, done: true },
  {
    id: 2, role: 'assistant', content: 'Het zijn er 36.201.', done: true,
    tools: [{ name: 'query_data', label: 'Data opvragen', done: true, snippet: '36201' }],
  },
]

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id: 'c1', messages: HEROPEND }))
  chat.historyDataKeys = 0
  chat.send = vi.fn(() => true)
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

const hint = () => container.querySelector('.report-reload-hint')

describe('heropend gesprek zonder recept (#551)', () => {
  it('zegt dat de data niet meer geladen is en biedt de laatste vraag met één klik aan', async () => {
    await mountChat()
    expect(hint().textContent).toContain('De data van dit gesprek is niet meer geladen.')
    const knop = hint().querySelector('button')
    expect(knop.textContent).toBe('Stel de laatste vraag opnieuw')
    await act(async () => { knop.click() })
    expect(chat.send).toHaveBeenCalledWith(VRAAG)
    expect(container.querySelector('.make-rapport-btn')).toBeNull()
  })

  it('toont de rapportknop en geen hint zodra de server de data van het gesprek kent', async () => {
    chat.historyDataKeys = 1
    await mountChat()
    expect(hint()).toBeNull()
    expect(container.querySelector('.make-rapport-btn')).not.toBeNull()
  })
})
