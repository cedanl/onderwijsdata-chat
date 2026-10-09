// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MAX_MESSAGE_CHARS } from '../constants'

vi.mock('../api', () => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  fetchConversations: vi.fn().mockResolvedValue([]),
  putConversation: vi.fn(),
  renameConversationApi: vi.fn(),
  deleteConversationApi: vi.fn(),
  fetchSettingsConfig: vi.fn().mockResolvedValue({}),
}))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

const chat = vi.hoisted(() => ({ rejectedDraft: null, send: null }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], busy: false, rejectedDraft: chat.rejectedDraft, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: chat.send, sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import ChatPage from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
// jsdom lacks these browser APIs that the chat page uses for scrolling and layout.
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container

async function renderWithDraft(draft) {
  chat.rejectedDraft = draft
  chat.send = vi.fn(() => true)
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { settings: {}, user: 'gast' })) })
}

async function pressEnter() {
  const textarea = container.querySelector('textarea.chat-input')
  await act(async () => {
    textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
  })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

// #481: the composer never sends more than the server accepts.
describe('composer message limit', () => {
  it('caps typing with maxLength', async () => {
    await renderWithDraft(null)
    expect(container.querySelector('textarea.chat-input').maxLength).toBe(MAX_MESSAGE_CHARS)
  })

  it('does not send a restored draft over the limit, and says it is too long', async () => {
    await renderWithDraft('x'.repeat(MAX_MESSAGE_CHARS + 1))
    expect(container.querySelector('.send-btn').getAttribute('aria-disabled')).toBe('true')
    expect(container.querySelector('.message-counter--over')).not.toBeNull()

    await pressEnter()
    expect(chat.send).not.toHaveBeenCalled()
    expect(container.querySelector('textarea.chat-input').value).toHaveLength(MAX_MESSAGE_CHARS + 1)
  })

  it('sends a draft of exactly the limit', async () => {
    await renderWithDraft('x'.repeat(MAX_MESSAGE_CHARS))
    expect(container.querySelector('.send-btn').getAttribute('aria-disabled')).toBe('false')

    await pressEnter()
    expect(chat.send).toHaveBeenCalledWith('x'.repeat(MAX_MESSAGE_CHARS))
  })
})
