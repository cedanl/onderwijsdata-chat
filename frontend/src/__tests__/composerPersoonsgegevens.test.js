// @vitest-environment jsdom
// #478: een concept met een BSN krijgt een waarschuwing onder het invoerveld; versturen blijft mogelijk.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('../api', () => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  fetchConversations: vi.fn().mockResolvedValue([]),
  fetchConversation: vi.fn(),
  putConversation: vi.fn(),
  renameConversationApi: vi.fn(),
  deleteConversationApi: vi.fn(),
  fetchSettingsConfig: vi.fn().mockResolvedValue({}),
}))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

const chat = vi.hoisted(() => ({ send: vi.fn(() => true) }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], busy: false, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: chat.send, sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import ChatPage from '../pages/ChatPage'
import { PERSOONSGEGEVENS_WAARSCHUWING } from '../persoonsgegevens'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container

async function mount() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { user: 'tester' })) })
}

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  chat.send.mockClear()
})

const typ = async (tekst) => {
  const textarea = container.querySelector('textarea.chat-input')
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(textarea, tekst)
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
  })
  return textarea
}

describe('persoonsgegevens in de invoer (#478)', () => {
  it('toont de vaste waarschuwing onder het invoerveld', async () => {
    await mount()
    expect(container.querySelector('.chat-disclaimer').textContent).toContain(PERSOONSGEGEVENS_WAARSCHUWING)
  })

  it('waarschuwt zodra het concept een BSN bevat, en laat versturen toe', async () => {
    await mount()
    expect(container.querySelector('.chat-input-wrap .context-limit-banner')).toBeNull()

    const textarea = await typ('Mijn BSN is 123456782, hoeveel studenten heeft de HU?')
    const melding = container.querySelector('.chat-input-wrap .context-limit-banner')
    expect(melding.textContent).toContain('een BSN')

    await act(async () => {
      textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    })
    expect(chat.send).toHaveBeenCalledOnce()
  })

  it('zwijgt bij een gewone vraag met codes en jaartallen', async () => {
    await mount()
    await typ('Hoeveel studenten had opleiding 36201 in 2024/25 bij 21PL?')
    expect(container.querySelector('.chat-input-wrap .context-limit-banner')).toBeNull()
  })
})
