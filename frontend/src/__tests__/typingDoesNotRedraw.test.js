// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

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

// What a keystroke must not repeat: parsing the markdown of the answers and redrawing their charts.
const renders = vi.hoisted(() => ({ plot: 0, markdown: 0 }))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { renders.plot += 1; return null } }))
vi.mock('react-markdown', () => ({ default: function MarkdownStub({ children }) { renders.markdown += 1; return children } }))

// One array for every render, like the state in the real hook.
const MESSAGES = vi.hoisted(() => [
  { id: 1, role: 'user', content: 'Hoeveel studenten?', done: true },
  { id: 2, role: 'assistant', content: 'Het zijn er 12.345.', tools: [], done: true },
  {
    id: 3, role: 'assistant', content: '', done: true,
    figures: [{ label: 'Studenten', json: JSON.stringify({ data: [{ type: 'bar', x: ['a', 'b'], y: [1, 2] }], layout: {} }) }],
  },
])

vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: MESSAGES, busy: false, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import ChatPage from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

async function type(textarea, value) {
  const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set
  await act(async () => {
    set.call(textarea, value)
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

describe('typing a follow-up question after an answer', () => {
  it('neither parses the answers again nor redraws their charts', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => { root.render(createElement(ChatPage, { settings: {}, user: 'gast' })) })

    const textarea = container.querySelector('textarea.chat-input')
    expect(renders.plot).toBeGreaterThan(0)
    expect(renders.markdown).toBeGreaterThan(0)
    const before = { ...renders }

    for (const draft of ['E', 'En', 'En hoe', 'En hoe zit het met het hbo?']) await type(textarea, draft)

    expect(textarea.value).toBe('En hoe zit het met het hbo?')
    expect(renders).toEqual(before)
  })
})
