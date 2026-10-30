// @vitest-environment jsdom
// #772, door de hele app met de echte useChat: wie tijdens een antwoord of rapport naar een andere pagina gaat of een
// ander gesprek opent, krijgt eerst een bevestiging. Blijven laat de run doorlopen; weggaan stopt hem netjes, met een
// eigen markering in plaats van "Verbinding verbroken", en /chat opent bij terugkeer hetzelfde gesprek.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { FakeWebSocket } from './fakeWebSocket'

const OUD = {
  id: 'oud-gesprek', title: 'Oude vraag over het mbo', timestamp: 1,
  messages: [
    { id: 1, role: 'user', content: 'Oude vraag over het mbo', done: true },
    { id: 2, role: 'assistant', content: 'Oud antwoord', done: true },
  ],
}

const api = vi.hoisted(() => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  fetchConversations: vi.fn(),
  fetchConversation: vi.fn(),
  putConversation: vi.fn().mockResolvedValue({}),
  renameConversationApi: vi.fn().mockResolvedValue({}),
  deleteConversationApi: vi.fn().mockResolvedValue({}),
  fetchSettingsConfig: vi.fn().mockResolvedValue({}),
}))
vi.mock('../api', async importOriginal => ({ ...await importOriginal(), ...api }))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import App from '../App'
import { WEGGAAN_VRAAG } from '../runBewaking'
import { RAPPORT_WEGGEGAAN, WEGGEGAAN } from '../weggegaan'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

// Each App test renders the whole app; on a busy machine that nears the 5 s default.
const APP_TEST = { timeout: 20000 }
const VRAAG = 'Hoeveel eerstejaars had het hbo in 2024?'
const VERBROKEN = 'Verbinding verbroken'

const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

let root
let container

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  localStorage.setItem('openEDUdata_onboarded', '1')
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  window.matchMedia = q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })
  FakeWebSocket.reset()
  globalThis.WebSocket = FakeWebSocket
  api.putConversation.mockClear()
  api.fetchConversations.mockResolvedValue([])
  api.fetchConversation.mockResolvedValue(OUD)
  vi.stubGlobal('fetch', vi.fn(async url => {
    if (url === '/api/auth/status') return response(200, { required: false })
    if (url === '/api/instellingen') return response(200, [])
    return response(200, {})
  }))
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  delete window.matchMedia
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  window.history.replaceState({}, '', '/')
})

const invoer = () => container.querySelector('textarea.chat-input')
const dialoog = () => container.querySelector('[role="alertdialog"]')
const navLink = pad => container.querySelector(`.navbar-nav a[href="${pad}"]`)
const gesprek = () => container.querySelector('.chat-messages').textContent
const verzonden = (ws, actie) => ws.sent.filter(m => m.action === actie)
// De laatste versie van het gesprek die naar de server ging.
const laatstBewaard = () => api.putConversation.mock.calls.at(-1)?.[1].messages ?? []

async function opChat() {
  // De socket van deze chatpagina: een vorige is al dicht of gaat dicht.
  await vi.waitFor(() => {
    expect(invoer()).not.toBeNull()
    expect(FakeWebSocket.last?.readyState).toBe(FakeWebSocket.CONNECTING)
  }, { timeout: 10000 })
  const ws = FakeWebSocket.last
  await act(async () => { ws.open() })
  return ws
}

async function openApp() {
  window.history.replaceState({}, '', '/chat')
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(App)) })
  return opChat()
}

// Een vraag, en een antwoord dat nog geschreven wordt. De toolstap zet de tekst uit de deltabuffer in het bericht.
async function antwoordLoopt(ws) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(invoer(), VRAAG)
    invoer().dispatchEvent(new Event('input', { bubbles: true }))
  })
  await act(async () => { invoer().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })) })
  await act(async () => {
    ws.emit({ type: 'message_start' })
    ws.emit({ type: 'text_delta', content: 'Half antwoord' })
    ws.emit({ type: 'tool_start', name: 'zoek', label: 'Zoeken' })
  })
}

async function klik(el) {
  await act(async () => { el.click() })
}

describe('weggaan tijdens een antwoord (#772)', APP_TEST, () => {
  it('vraagt niets zonder lopende run', async () => {
    await openApp()
    await klik(navLink('/rapporten'))
    expect(dialoog()).toBeNull()
    expect(window.location.pathname).toBe('/rapporten')
  })

  it('vraagt eerst; blijven houdt de gebruiker op de chat en laat het antwoord doorlopen', async () => {
    const ws = await openApp()
    await antwoordLoopt(ws)

    await klik(navLink('/rapporten'))
    expect(dialoog().textContent).toContain(WEGGAAN_VRAAG.antwoord)
    expect(window.location.pathname).toBe('/chat')

    await klik(dialoog().querySelector('.confirm-cancel'))
    expect(dialoog()).toBeNull()
    expect(window.location.pathname).toBe('/chat')
    expect(verzonden(ws, 'stop')).toEqual([])
    await act(async () => { ws.emit({ type: 'message_end', content: 'Het volledige antwoord.' }) })
    expect(gesprek()).toContain('Het volledige antwoord.')
    expect(gesprek()).not.toContain(WEGGEGAAN)
  })

  it('weggaan stopt het antwoord netjes, markeert het eerlijk en opent het gesprek bij terugkeer weer', async () => {
    const ws = await openApp()
    await antwoordLoopt(ws)

    await klik(navLink('/rapporten'))
    await klik(dialoog().querySelector('.confirm-destructive'))

    expect(verzonden(ws, 'stop')).toHaveLength(1)
    await vi.waitFor(() => expect(window.location.pathname).toBe('/rapporten'))
    expect(laatstBewaard().at(-1)).toMatchObject({ role: 'assistant', content: 'Half antwoord', stopped: true, weggegaan: true })

    await klik(navLink('/chat'))
    await opChat()
    expect(gesprek()).toContain(VRAAG)
    expect(gesprek()).toContain('Half antwoord')
    expect(gesprek()).toContain(WEGGEGAAN)
    expect(gesprek()).not.toContain(VERBROKEN)
  })

  it('markeert ook bij de terugknop van de browser, die buiten de bevestiging om gaat', async () => {
    const ws = await openApp()
    await antwoordLoopt(ws)

    await act(async () => {
      window.history.pushState({}, '', '/rapporten')
      window.dispatchEvent(new window.PopStateEvent('popstate'))
    })
    await act(async () => { ws.finishClose() })
    expect(laatstBewaard().at(-1)).toMatchObject({ content: 'Half antwoord', weggegaan: true })

    await klik(navLink('/chat'))
    await opChat()
    expect(gesprek()).toContain(WEGGEGAAN)
    expect(gesprek()).not.toContain(VERBROKEN)
  })

  it('begint /chat na een gewoon bezoek elders leeg, zoals voorheen', async () => {
    const ws = await openApp()
    await antwoordLoopt(ws)
    await act(async () => { ws.emit({ type: 'message_end', content: 'Klaar.' }) })

    await klik(navLink('/rapporten'))
    expect(dialoog()).toBeNull()
    await klik(navLink('/chat'))
    await opChat()
    // Alleen de chip "Ga verder met …" noemt het gesprek nog (#603).
    expect(container.querySelectorAll('.chat-messages .message')).toHaveLength(0)
  })
})

describe('een ander of nieuw gesprek tijdens een antwoord (#772)', APP_TEST, () => {
  it('"Nieuw gesprek": blijven laat alles staan, bevestigen stopt en bewaart het gestopte antwoord', async () => {
    const ws = await openApp()
    await antwoordLoopt(ws)
    const nieuw = container.querySelector('.new-chat-btn')

    await klik(nieuw)
    await klik(dialoog().querySelector('.confirm-cancel'))
    expect(verzonden(ws, 'reset')).toEqual([])
    expect(gesprek()).toContain('Half antwoord')

    await klik(nieuw)
    await klik(dialoog().querySelector('.confirm-destructive'))
    expect(ws.sent.map(m => m.action).filter(a => a === 'stop' || a === 'reset')).toEqual(['stop', 'reset'])
    expect(gesprek()).not.toContain('Half antwoord')
    expect(laatstBewaard().at(-1)).toMatchObject({ content: 'Half antwoord', weggegaan: true })
  })

  it('een gesprek uit de lijst opent pas na de bevestiging', async () => {
    api.fetchConversations.mockResolvedValue([{ id: OUD.id, title: OUD.title, timestamp: OUD.timestamp }])
    const ws = await openApp()
    await vi.waitFor(() => expect(container.querySelector(`.history-btn[data-conv-id="${OUD.id}"]`)).not.toBeNull())
    await antwoordLoopt(ws)

    await klik(container.querySelector(`.history-btn[data-conv-id="${OUD.id}"]`))
    expect(dialoog().textContent).toContain(WEGGAAN_VRAAG.antwoord)
    expect(api.fetchConversation).not.toHaveBeenCalled()

    await klik(dialoog().querySelector('.confirm-destructive'))
    await vi.waitFor(() => expect(gesprek()).toContain('Oud antwoord'))
    expect(verzonden(ws, 'stop')).toHaveLength(1)
    expect(api.putConversation.mock.calls.some(([, { messages }]) => messages.at(-1).weggegaan)).toBe(true)
  })
})

describe('weggaan tijdens een rapport (#772)', APP_TEST, () => {
  it('noemt het rapport, stopt het en zegt bij terugkeer dat het stopte omdat je wegging', async () => {
    const ws = await openApp()
    await antwoordLoopt(ws)
    await act(async () => { ws.emit({ type: 'message_end', content: 'Een antwoord met data.' }) })
    await act(async () => { ws.emit({ type: 'report_generating' }) })

    await klik(navLink('/rapporten'))
    expect(dialoog().textContent).toContain(WEGGAAN_VRAAG.rapport)
    await klik(dialoog().querySelector('.confirm-destructive'))
    expect(verzonden(ws, 'stop')).toHaveLength(1)
    await vi.waitFor(() => expect(window.location.pathname).toBe('/rapporten'))

    await klik(navLink('/chat'))
    await opChat()
    expect(gesprek()).toContain('Een antwoord met data.')
    expect(gesprek()).toContain(RAPPORT_WEGGEGAAN)
    expect(gesprek()).not.toContain('De verbinding viel weg')
  })
})
