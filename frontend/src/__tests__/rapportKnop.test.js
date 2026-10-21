// @vitest-environment jsdom
// #648: "Genereer rapport" zonder verbinding of tijdens een nieuw gesprek ziet er uit als niet beschikbaar
// (aria-disabled), maar een tik komt nog bij generateReport aan, dat zegt waarom het niet start. Alleen een lopend
// rapport zet de knop echt uit; tijdens een antwoord staat hij er niet.
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

// Een gesprek met een antwoord met data: daar hoort een rapportknop bij.
const MET_DATA = [
  { id: 1, role: 'user', content: 'Hoeveel mbo-studenten per provincie?', done: true },
  {
    id: 2, role: 'assistant', content: 'Op de kaart staat het aantal per provincie.', done: true,
    tools: [{ name: 'query_data', label: 'Data gefilterd', done: true, snippet: '41230' }],
  },
]

const chat = vi.hoisted(() => ({ staat: {}, generateReport: null }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: MET_DATA, busy: false, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [],
    reportBusy: false, reportProgress: { steps: 0, label: null }, reportSpec: null, send: vi.fn(),
    sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(),
    generateReport: chat.generateReport, cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: () => {}, withBufferedText: m => m,
    ...chat.staat,
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chat.staat = {}
  chat.generateReport = vi.fn(() => false)
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
})

async function mountChat(staat) {
  chat.staat = staat
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { user: 'tester' })) })
}

const knop = () => container.querySelector('.make-rapport-btn')

describe('de rapportknop (#648)', () => {
  it('is gewoon beschikbaar met verbinding en zonder lopend werk', async () => {
    await mountChat({})
    expect(knop().hasAttribute('aria-disabled')).toBe(false)
    expect(knop().disabled).toBe(false)
    expect(knop().textContent).toBe('Genereer rapport')
  })

  it.each([
    ['zonder verbinding', { connected: false }],
    ['terwijl een nieuw gesprek start', { resetting: true }],
  ])('%s: aria-disabled, niet disabled, en een klik komt nog aan', async (_naam, staat) => {
    await mountChat(staat)
    expect(knop().getAttribute('aria-disabled')).toBe('true')
    expect(knop().hasAttribute('disabled')).toBe(false)

    await act(async () => { knop().click() })

    expect(chat.generateReport).toHaveBeenCalledTimes(1)
    expect(chat.generateReport).toHaveBeenCalledWith('tester')
  })

  it('is uit terwijl het rapport wordt gemaakt', async () => {
    await mountChat({ reportBusy: true })
    expect(knop().disabled).toBe(true)
    expect(knop().textContent).toBe('Rapport wordt gegenereerd…')
    await act(async () => { knop().click() })
    expect(chat.generateReport).not.toHaveBeenCalled()
  })

  it('staat er niet tijdens een antwoord', async () => {
    await mountChat({ busy: true })
    expect(knop()).toBeNull()
  })
})
