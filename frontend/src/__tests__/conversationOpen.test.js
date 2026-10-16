// @vitest-environment jsdom
// #509: de gesprekslijst draagt geen berichten; een gesprek openen haalt ze op.
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

const chat = vi.hoisted(() => ({ sendHistory: vi.fn(), addToast: vi.fn(), clear: vi.fn() }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], busy: false, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false,
    reportProgress: null, reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: chat.sendHistory, stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: chat.clear, startNewConversation: vi.fn(), addToast: chat.addToast,
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const rij = { id: 'c1', title: 'Studenten HU', timestamp: 1 }
const vraag = { role: 'user', content: 'Hoeveel studenten heeft de HU?' }
const antwoord = { role: 'assistant', content: '26.370' }

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  api.fetchConversations.mockResolvedValue([rij])
  api.fetchConversation.mockReset()
  chat.sendHistory.mockClear()
  chat.addToast.mockClear()
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

const gesprekKnop = () => container.querySelector('.history-btn')

// #602: een gesprek dat in het zoekpalet gekozen is, opent op de chatpagina, één keer.
describe('een gesprek uit het zoekpalet (#602)', () => {
  it('opent het gekozen gesprek en meldt dat het geopend is', async () => {
    api.fetchConversation.mockResolvedValue({ ...rij, messages: [vraag, antwoord] })
    const geopend = vi.fn()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root.render(createElement(ChatPage, { user: 'tester', teOpenenGesprek: 'c1', onGesprekGeopend: geopend }))
    })

    expect(geopend).toHaveBeenCalledTimes(1)
    expect(api.fetchConversation).toHaveBeenCalledWith('c1')
    expect(container.textContent).toContain('Hoeveel studenten heeft de HU?')
  })
})

describe('een gesprek openen (#509)', () => {
  it('haalt het gesprek op en toont zijn berichten', async () => {
    api.fetchConversation.mockResolvedValue({ ...rij, messages: [vraag, antwoord] })
    await mountChat()
    expect(gesprekKnop().textContent).toContain('Studenten HU')

    await act(async () => { gesprekKnop().click() })

    expect(api.fetchConversation).toHaveBeenCalledWith('c1')
    expect(container.textContent).toContain('Hoeveel studenten heeft de HU?')
    expect(chat.sendHistory).toHaveBeenCalledWith([vraag, antwoord], 'c1')
    expect(chat.addToast).not.toHaveBeenCalled()
  })

  it('toont "Openen…" zolang het gesprek wordt opgehaald en laat geen tweede klik toe', async () => {
    let geef
    api.fetchConversation.mockReturnValue(new Promise(r => { geef = r }))
    await mountChat()

    await act(async () => { gesprekKnop().click() })
    expect(gesprekKnop().textContent).toContain('Openen…')
    expect(gesprekKnop().disabled).toBe(true)
    await act(async () => { gesprekKnop().click() })
    expect(api.fetchConversation).toHaveBeenCalledTimes(1)

    await act(async () => { geef({ ...rij, messages: [vraag] }) })
    expect(gesprekKnop().textContent).not.toContain('Openen…')
    expect(gesprekKnop().disabled).toBe(false)
  })

  it('meldt het als ophalen mislukt en laat de chat met rust', async () => {
    api.fetchConversation.mockRejectedValue(new Error('API 500'))
    await mountChat()

    await act(async () => { gesprekKnop().click() })

    expect(chat.addToast).toHaveBeenCalledWith('Gesprek openen is mislukt. Probeer het opnieuw.', 'error')
    expect(chat.sendHistory).not.toHaveBeenCalled()
    expect(gesprekKnop().disabled).toBe(false)
  })
})
