// @vitest-environment jsdom
// #507 (vervolg op #498): een ChatPage die bij uitloggen nog gemount is, mag het
// gesprek van de vorige gebruiker niet terugschrijven — niet via het save-effect,
// niet via saveConversation en niet via een fetch-resultaat dat na de wipe landt.
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

// Eén mutabel chat-object: de test stuurt wat useChat teruggeeft per render.
const chatState = vi.hoisted(() => ({
  messages: [],
  busy: false,
  reportSpec: null,
}))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chatState.messages, busy: chatState.busy, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false,
    reportProgress: null, reportSpec: chatState.reportSpec, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import ChatPage from '../pages/ChatPage'
import { clearLocalSessionData } from '../sessionData'
import { clearToken } from '../auth'
import { STORAGE_CURRENT_CHAT, STORAGE_TOKEN, STORAGE_WORKBOOKS, MAX_CONVERSATIONS } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chatState.messages = [{ id: 1, role: 'user', content: 'vraag van de vorige gebruiker', done: true }]
  chatState.reportSpec = null
  api.putConversation.mockClear()
  api.putWorkbook.mockClear()
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
  await act(async () => { root.render(createElement(ChatPage, { user: 'vorige' })) })
}

function logout() {
  clearLocalSessionData()
  clearToken()
}

describe('ChatPage na de sessie-wipe (#507)', () => {
  it('schrijft het gesprek niet terug wanneer het save-effect na uitloggen nog draait', async () => {
    await mountChat()
    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).not.toBeNull()

    act(() => logout())
    // Een nieuw streamfragment laat React het persist-effect opnieuw uitvoeren.
    chatState.messages = [...chatState.messages, { id: 2, role: 'assistant', content: 'laat antwoord', done: true }]
    await act(async () => { root.render(createElement(ChatPage, { user: 'vorige' })) })

    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toBeNull()
  })

  it('stuurt na uitloggen geen gesprek meer naar de server', async () => {
    await mountChat()
    act(() => logout())
    // De save bij mount (vóór uitloggen) is legitiem; daarna mag er geen volgen.
    api.putConversation.mockClear()
    // Het antwoord komt pas na het uitloggen binnen: zonder guard wijkt het gesprek dan af
    // van savedJsonRef en wordt het wél weggeschreven.
    chatState.busy = true
    await act(async () => { root.render(createElement(ChatPage, { user: 'vorige' })) })
    chatState.messages = [...chatState.messages, { id: 2, role: 'assistant', content: 'laat antwoord', done: true }]
    chatState.busy = false
    await act(async () => { root.render(createElement(ChatPage, { user: 'vorige' })) })

    expect(api.putConversation).not.toHaveBeenCalled()
  })

  it('bewaart een laat fetch-resultaat met gesprekken van de vorige gebruiker niet', async () => {
    let geefRows
    api.fetchConversations.mockReturnValueOnce(new Promise(r => { geefRows = r }))
    await mountChat()

    act(() => logout())
    await act(async () => {
      geefRows([{ id: 9, title: 'oud gesprek', timestamp: 1, messages: [{ role: 'user', content: 'pii' }] }])
    })

    expect(localStorage.getItem('openEDUdata_conversations')).toBeNull()
  })

  it('toont een laat "meer laden"-resultaat van de vorige gebruiker niet', async () => {
    const rij = n => ({ id: n, title: `gesprek ${n}`, timestamp: 1000 - n, messages: [{ role: 'user', content: 'vraag' }] })
    // Een volle pagina plus één extra rij: er is meer te laden.
    api.fetchConversations.mockResolvedValueOnce(Array.from({ length: MAX_CONVERSATIONS + 1 }, (_, n) => rij(n + 1)))
    let geefRows
    api.fetchConversations.mockReturnValueOnce(new Promise(r => { geefRows = r }))
    await mountChat()

    await act(async () => { container.querySelector('.history-more-btn').click() })
    act(() => logout())
    await act(async () => { geefRows([rij(99)]) })

    expect(container.textContent).not.toContain('gesprek 99')
  })

  it('slaat na uitloggen geen rapport op wanneer de spec nog binnenkomt', async () => {
    await mountChat()
    act(() => logout())
    chatState.reportSpec = { title: 'Rapport van de vorige gebruiker', auteur: 'vorige' }
    await act(async () => { root.render(createElement(ChatPage, { user: 'vorige' })) })

    expect(api.putWorkbook).not.toHaveBeenCalled()
    expect(localStorage.getItem(STORAGE_WORKBOOKS)).toBeNull()
  })
})
