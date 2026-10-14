// @vitest-environment jsdom
// #364, door de hele chatpagina met de echte useChat: een vervolgvraag onder het antwoord vult de
// invoer, en er gaat niets over de socket tot de gebruiker zelf op versturen drukt.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { FakeWebSocket } from './fakeWebSocket'

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

import ChatPage from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const VERVOLG = 'Welke instellingen trekken de meeste eerstejaars?'

let root
let container

beforeEach(() => {
  localStorage.clear()
  FakeWebSocket.reset()
  globalThis.WebSocket = FakeWebSocket
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

async function typ(textarea, waarde) {
  const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set
  await act(async () => {
    set.call(textarea, waarde)
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

async function enter(textarea) {
  await act(async () => {
    textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
  })
}

const vragen = ws => ws.sent.filter(m => m.action === 'message').map(m => m.content)

describe('een vervolgvraag kiezen op de chatpagina', () => {
  it('vult de invoer en stuurt pas als de gebruiker verstuurt', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => { root.render(createElement(ChatPage, { settings: {}, user: 'gast' })) })
    const ws = FakeWebSocket.last
    await act(async () => { ws.open() })
    const textarea = container.querySelector('textarea.chat-input')

    await typ(textarea, 'Hoeveel eerstejaars had het hbo in 2024?')
    await enter(textarea)
    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'Het hbo had veel eerstejaars.', bronnen: [], vervolgvragen: [VERVOLG] })
    })

    const groep = container.querySelector('[role="group"][aria-labelledby]')
    expect(document.getElementById(groep.getAttribute('aria-labelledby')).textContent).toBe('Vervolgvragen')
    await act(async () => groep.querySelector('button.suggested-btn').click())

    expect(textarea.value).toBe(VERVOLG)
    expect(document.activeElement).toBe(textarea)
    expect(vragen(ws)).toEqual(['Hoeveel eerstejaars had het hbo in 2024?'])

    await enter(textarea)

    expect(vragen(ws)).toEqual(['Hoeveel eerstejaars had het hbo in 2024?', VERVOLG])
    expect(textarea.value).toBe('')
  })
})
