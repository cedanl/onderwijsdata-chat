// @vitest-environment jsdom
// #775, door de hele chatpagina met de echte useChat: een vraag die op de tijdsgrens stopt, houdt de reden als
// blijvende regel bij het bericht en krijgt de knoppen om het opnieuw te proberen. De stopknop blijft "Genereren
// gestopt", zonder knoppen: dat was een keuze van de gebruiker.
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

const VRAAG = 'Hoeveel studenten volgen een hbo-opleiding, per opleiding en per jaar sinds 2010?'
const REDEN = 'De vraag is na 5 min gestopt. Maak hem kleiner of specifieker, of probeer een ander model.'

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

async function vraagEnStop(einde) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { settings: {}, user: 'gast' })) })
  const ws = FakeWebSocket.last
  await act(async () => { ws.open() })
  const textarea = container.querySelector('textarea.chat-input')
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(textarea, VRAAG)
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await act(async () => { textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })) })
  await act(async () => {
    ws.emit({ type: 'message_start' })
    ws.emit({ type: 'text_delta', content: 'Het eerste deel' })
    ws.emit({ type: 'message_end', ...einde })
  })
  return ws
}

const regels = () => [...container.querySelectorAll('.message-stopped')].map(e => e.textContent)
const knoppen = () => [...container.querySelectorAll('.message-retry button')].map(b => b.textContent)
const vragen = ws => ws.sent.filter(m => m.action === 'message').map(m => m.content)

describe('een vraag die op de tijdsgrens stopt (#775)', () => {
  it('houdt de reden bij het bericht, niet "Genereren gestopt", en biedt opnieuw aan', async () => {
    await vraagEnStop({ aborted: true, timeout: true, stopreden: REDEN })

    expect(regels()).toEqual([REDEN])
    expect(container.querySelector('.message-stopped').getAttribute('role')).toBe('status')
    expect(knoppen()).toEqual(['Opnieuw'])
    expect(container.querySelector('.toast')).toBeNull()
    expect(container.textContent).toContain('Het eerste deel')
  })

  it('"Opnieuw" stelt dezelfde vraag nog een keer', async () => {
    const ws = await vraagEnStop({ aborted: true, timeout: true, stopreden: REDEN })
    await act(async () => { container.querySelector('.message-retry button').click() })
    expect(vragen(ws)).toEqual([VRAAG, VRAAG])
  })

  it('na de stopknop blijft het "Genereren gestopt", zonder knoppen', async () => {
    await vraagEnStop({ aborted: true })
    expect(regels()).toEqual(['Genereren gestopt'])
    expect(knoppen()).toEqual([])
  })
})
