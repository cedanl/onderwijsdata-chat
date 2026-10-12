// @vitest-environment jsdom
// #515: onder een geweigerd rapport maakt "Opnieuw proberen" het rapport opnieuw, zonder de vraag
// opnieuw te sturen; "Vraag opnieuw stellen" stuurt de vraag. Tijdens een antwoord of rapport: dicht.
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

const chat = vi.hoisted(() => ({
  messages: [], busy: false, reportBusy: false,
  send: null, generateReport: null,
}))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chat.messages, busy: chat.busy, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: chat.reportBusy,
    reportProgress: { steps: 0, label: null }, reportSpec: null, send: chat.send, sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: chat.generateReport, cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast: () => {},
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const VRAAG = 'Hoeveel studenten heeft de HU?'
const VRAAG_MSG = { id: 1, role: 'user', content: VRAAG, done: true }
// Een antwoord met opgehaalde data: daarmee kan er een rapport komen.
const ANTWOORD = {
  id: 2, role: 'assistant', content: 'Het zijn er 36.201.', done: true,
  tools: [{ name: 'query_data', label: 'Data opvragen', done: true, snippet: '36201' }],
}
const GEWEIGERD = {
  id: 3, role: 'assistant', done: true, isError: true, herstel: 'rapport',
  content: 'De cijfers in het rapport klopten niet met de laatste analyse, daarom heb ik het niet getoond.',
}

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chat.messages = [VRAAG_MSG, ANTWOORD, GEWEIGERD]
  chat.busy = false
  chat.reportBusy = false
  chat.send = vi.fn(() => true)
  chat.generateReport = vi.fn()
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

const herstelKnoppen = () => [...container.querySelectorAll('.message-retry button')]
const knop = tekst => herstelKnoppen().find(b => b.textContent === tekst)

describe('herstel na een geweigerd rapport (#515)', () => {
  it('toont "Opnieuw proberen" en "Vraag opnieuw stellen", geen ander model', async () => {
    await mountChat()
    expect(herstelKnoppen().map(b => b.textContent)).toEqual(['Opnieuw proberen', 'Vraag opnieuw stellen'])
  })

  it('maakt het rapport opnieuw en stuurt de vraag niet opnieuw', async () => {
    await mountChat()
    await act(async () => { knop('Opnieuw proberen').click() })
    expect(chat.generateReport).toHaveBeenCalledWith('tester')
    expect(chat.send).not.toHaveBeenCalled()
  })

  it('stelt de vraag opnieuw zonder een rapport te starten', async () => {
    await mountChat()
    await act(async () => { knop('Vraag opnieuw stellen').click() })
    expect(chat.send).toHaveBeenCalledWith(VRAAG)
    expect(chat.generateReport).not.toHaveBeenCalled()
  })

  it.each([
    ['een antwoord', { busy: true }],
    ['een rapport', { reportBusy: true }],
  ])('zet beide knoppen dicht zolang %s loopt', async (_, stand) => {
    Object.assign(chat, stand)
    await mountChat()
    expect(herstelKnoppen()).toHaveLength(2)
    expect(herstelKnoppen().every(b => b.disabled)).toBe(true)
  })

  // Zonder geladen data (bijv. een heropend gesprek zonder bewaarde keys) faalt een nieuw rapport ook.
  it('biedt geen rapport opnieuw aan als er nu geen rapport kan komen', async () => {
    chat.messages = [VRAAG_MSG, GEWEIGERD]
    await mountChat()
    expect(herstelKnoppen().map(b => b.textContent)).toEqual(['Vraag opnieuw stellen'])
  })

  it('houdt een andere foutmelding bij "Opnieuw"', async () => {
    chat.messages = [VRAAG_MSG, ANTWOORD, { ...GEWEIGERD, herstel: undefined, content: 'Rapport kon niet worden gemaakt.' }]
    await mountChat()
    expect(herstelKnoppen().map(b => b.textContent)[0]).toBe('Opnieuw')
    expect(knop('Opnieuw proberen')).toBeUndefined()
  })
})
