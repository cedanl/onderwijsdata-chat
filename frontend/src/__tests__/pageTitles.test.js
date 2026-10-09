// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'

// Keep the pages off the network and away from heavy children: only the tab title matters here.
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))
vi.mock('../api', () => {
  const pending = () => new Promise(() => {})
  return {
    fetchCatalogCounts: pending,
    fetchConversations: pending,
    fetchSettingsConfig: pending,
    putConversation: pending,
    renameConversationApi: pending,
    deleteConversationApi: pending,
    fetchAnswerFeedback: pending,
    postAnswerFeedback: pending,
  }
})
vi.mock('../workbooks', () => ({
  BUILTIN_MIJN_INSTELLING: { id: 'b-1' },
  BUILTIN_ARBEIDSMARKT: { id: 'b-2' },
  BUILTIN_NATIONAAL: { id: 'b-3' },
  getWorkbooks: () => [],
  getWorkbookType: (wb) => wb.type,
  deleteWorkbook: vi.fn(),
  saveWorkbookWithSync: vi.fn(),
  migrateLocalWorkbooks: () => Promise.resolve(),
  loadWorkbooksFromServer: () => new Promise(() => {}),
}))
vi.mock('../components/DashboardGallery', () => ({ default: () => null }))
vi.mock('../components/DashboardCreator', () => ({ default: () => null }))
vi.mock('../components/WorkbookViewer', () => ({ default: () => null }))
vi.mock('../components/ScrollToBottom', () => ({ default: () => null }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], busy: false, rejectedDraft: null, clearRejectedDraft: vi.fn(), thinking: false, toasts: [],
    connected: true, resetting: false, historyDataKeys: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: vi.fn(), sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import HomePage from '../pages/HomePage'
import DashboardPage from '../pages/DashboardPage'
import ChatPage from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function render(page, props = {}) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(MemoryRouter, null, createElement(page, props))) })
}

beforeEach(() => { document.title = 'vorige' })

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

// #491: each route has its own tab title (WCAG 2.4.2).
describe('page titles', () => {
  it('the home page carries just the app name', async () => {
    await render(HomePage)
    expect(document.title).toBe('openEDUdata+')
  })

  it('the dashboards page says Dashboards', async () => {
    await render(DashboardPage, { settings: {} })
    expect(document.title).toBe('Dashboards — openEDUdata+')
  })

  it('the chat page says Chat, never the conversation title', async () => {
    await render(ChatPage, { settings: {}, user: 'gast' })
    expect(document.title).toBe('Chat — openEDUdata+')
  })
})
