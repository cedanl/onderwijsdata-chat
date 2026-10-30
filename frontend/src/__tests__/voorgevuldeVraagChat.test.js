// @vitest-environment jsdom
// #709, door de hele chatpagina met de echte useChat: een vraag uit een link begint een nieuw gesprek en staat in de
// invoer. Er gaat niets over de socket tot de gebruiker zelf verstuurt; het gesprek dat open stond, gaat eerst naar de server.
// #806: ook als de app al open staat en de link alleen het fragment verandert.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { FakeWebSocket } from './fakeWebSocket'

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
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import ChatPage from '../pages/ChatPage'
import { STORAGE_CURRENT_CHAT, STORAGE_VOORGEVULDE_VRAAG } from '../constants'
import { luisterNaarVraagInUrl } from '../voorgevuldeVraag'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const VRAAG = 'Hoeveel eerstejaars had het hbo in 2024?'
const OUD = {
  id: 'oud-gesprek',
  messages: [
    { id: 1, role: 'user', content: 'Oude vraag over het mbo', done: true },
    { id: 2, role: 'assistant', content: 'Oud antwoord', done: true },
  ],
}

let root
let container
let stopLuisteren

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  window.history.replaceState({}, '', '/chat')
  stopLuisteren = luisterNaarVraagInUrl()
  api.putConversation.mockClear()
  FakeWebSocket.reset()
  globalThis.WebSocket = FakeWebSocket
})

afterEach(async () => {
  stopLuisteren()
  await act(async () => root.unmount())
  container.remove()
})

async function mount() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { settings: {}, user: 'gast' })) })
  const ws = FakeWebSocket.last
  await act(async () => { ws.open() })
  return ws
}

// Wat de browser doet als een link alleen het fragment van de open app verandert: geen herlaad, wel een hashchange.
async function linkInOpenApp(vraag) {
  await act(async () => {
    window.history.replaceState({}, '', `/chat#vraag=${encodeURIComponent(vraag)}`)
    window.dispatchEvent(new Event('hashchange'))
  })
}

const vragen = ws => ws.sent.filter(m => m.action === 'message').map(m => m.content)
// Wat in het gesprek staat; de gesprekslijst ernaast noemt het oude gesprek wel.
const berichten = () => container.querySelector('.chat-messages').querySelectorAll('.message')

describe('een vraag uit een link op de chatpagina', () => {
  it('staat in de invoer en gaat pas weg als de gebruiker verstuurt', async () => {
    sessionStorage.setItem(STORAGE_VOORGEVULDE_VRAAG, VRAAG)

    const ws = await mount()
    const textarea = container.querySelector('textarea.chat-input')

    expect(textarea.value).toBe(VRAAG)
    expect(vragen(ws)).toEqual([])
    expect(sessionStorage.getItem(STORAGE_VOORGEVULDE_VRAAG)).toBeNull()

    await act(async () => {
      textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    })
    expect(vragen(ws)).toEqual([VRAAG])
  })

  it('begint een nieuw gesprek en bewaart eerst het gesprek dat open stond', async () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify(OUD))
    sessionStorage.setItem(STORAGE_VOORGEVULDE_VRAAG, VRAAG)

    const ws = await mount()

    expect(berichten()).toHaveLength(0)
    expect(container.querySelector('textarea.chat-input').value).toBe(VRAAG)
    expect(api.putConversation).toHaveBeenCalledWith('oud-gesprek', expect.objectContaining({ messages: OUD.messages }))
    expect(ws.sent.some(m => m.action === 'history')).toBe(false)
  })

  it('laat zonder vraag het gesprek staan dat open stond', async () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify(OUD))

    await mount()

    expect(berichten()).toHaveLength(2)
    expect(container.querySelector('textarea.chat-input').value).toBe('')
  })
})

describe('een link die alleen het fragment verandert terwijl de app open staat (#806)', () => {
  it('zet de opgeschoonde vraag in de invoer van een nieuw gesprek, onverstuurd en met focus', async () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify(OUD))
    const ws = await mount()
    expect(berichten()).toHaveLength(2)

    await linkInOpenApp(`<b>${VRAAG}</b>\u200b`)

    const textarea = container.querySelector('textarea.chat-input')
    expect(textarea.value).toBe(`b${VRAAG}/b`)
    expect(document.activeElement).toBe(textarea)
    expect(berichten()).toHaveLength(0)
    expect(api.putConversation).toHaveBeenCalledWith('oud-gesprek', expect.objectContaining({ messages: OUD.messages }))
    expect(vragen(ws)).toEqual([])
    expect(window.location.hash).toBe('')
    expect(sessionStorage.getItem(STORAGE_VOORGEVULDE_VRAAG)).toBeNull()
  })

  it('breekt een lopend antwoord niet af: de vraag wacht tot het antwoord klaar is', async () => {
    const ws = await mount()
    const textarea = container.querySelector('textarea.chat-input')
    await act(async () => {
      const zet = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set
      zet.call(textarea, 'Eerste vraag')
      textarea.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => {
      textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    })
    await act(async () => { ws.emit({ type: 'message_start' }) })

    await linkInOpenApp(VRAAG)

    expect(berichten().length).toBeGreaterThan(0)
    expect(textarea.value).toBe('')
    expect(sessionStorage.getItem(STORAGE_VOORGEVULDE_VRAAG)).toBe(VRAAG)

    await act(async () => { ws.emit({ type: 'message_end', content: 'Antwoord', bronnen: [] }) })

    expect(container.querySelector('textarea.chat-input').value).toBe(VRAAG)
    expect(berichten()).toHaveLength(0)
    expect(vragen(ws)).toEqual(['Eerste vraag'])
  })

  it('doet niets bij een fragment zonder vraag', async () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify(OUD))
    await mount()

    await act(async () => {
      window.history.replaceState({}, '', '/chat#deel=2')
      window.dispatchEvent(new Event('hashchange'))
    })

    expect(berichten()).toHaveLength(2)
    expect(container.querySelector('textarea.chat-input').value).toBe('')
    expect(window.location.hash).toBe('#deel=2')
  })
})
