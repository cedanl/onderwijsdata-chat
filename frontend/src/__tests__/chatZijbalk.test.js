// @vitest-environment jsdom
// #1141 en #1176: de zijbalk van de chat heeft een naam en zijn sectietitels zijn koppen (WCAG 1.3.1), en ze heten
// zoals elders in de app: "Voorbeeldvragen" en "Eerdere gesprekken".
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../api', async importOriginal => ({
  ...await importOriginal(),
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  fetchConversations: vi.fn().mockResolvedValue([]),
  putConversation: vi.fn().mockResolvedValue({}),
  renameConversationApi: vi.fn().mockResolvedValue({}),
  deleteConversationApi: vi.fn().mockResolvedValue({}),
  fetchSettingsConfig: vi.fn().mockResolvedValue({}),
}))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], busy: false, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import ChatPage, { ConversationHistory } from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  localStorage.clear()
})

describe('zijbalk van de chat (#1176)', () => {
  it('is een landmark met een naam', async () => {
    await render(createElement(MemoryRouter, null, createElement(ChatPage, { user: 'tester' })))
    const zijbalk = container.querySelector('aside.chat-sidebar')
    expect(zijbalk.getAttribute('aria-label')).toBe('Gesprekken en suggesties')
  })

  it('geeft de voorbeeldvragen een h2 in de zijbalk', async () => {
    await render(createElement(MemoryRouter, null, createElement(ChatPage, { user: 'tester' })))
    const kop = container.querySelector('aside.chat-sidebar h2.sidebar-section-title')
    expect(kop.textContent).toBe('Voorbeeldvragen')
  })

  it('geeft de gesprekkenlijst een h2 met de eerdere gesprekken', async () => {
    await render(createElement(ConversationHistory, {
      history: [{ id: 'c1', title: 'Studenten HU', timestamp: Date.now() }],
      onLoad: vi.fn(), onDelete: vi.fn(), onRename: vi.fn(),
    }))
    const kop = container.querySelector('h2.sidebar-section-title')
    expect(kop.textContent).toBe('Eerdere gesprekken')
  })
})

describe('koppen in de zijbalk (#1141)', () => {
  it('gebruiken geen losse samenstellingen als "Suggestie vragen" of "Gesprek geschiedenis"', async () => {
    await render(createElement(MemoryRouter, null, createElement(ChatPage, { user: 'tester' })))
    expect(container.textContent).not.toMatch(/Suggestie vragen|Gesprek geschiedenis/)
  })
})
