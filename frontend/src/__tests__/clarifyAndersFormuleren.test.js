// @vitest-environment jsdom
// #494, door de hele chatpagina met de echte useChat: "Anders formuleren" op een verduidelijkingskaart
// zet de oorspronkelijke vraag terug in het invoerveld. Er gaat niets over de socket tot de gebruiker
// zelf verstuurt; de keuze op de kaart blijft staan.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { FakeWebSocket } from './fakeWebSocket'
import { MAX_CHAT_TURNS } from '../constants'
import { persistCurrentChat } from '../conversationStore'

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

const VRAAG = 'Hoe gaat het met het onderwijs?'
const DEEL = { type: 'clarification', vraag: 'Welk deel van het onderwijs wil je bekijken?', opties: ['mbo', 'hbo', 'wo'] }
const JAAR = { type: 'clarification', vraag: 'Welk schooljaar?', opties: ['2023/24', 'Alle jaren'] }
const kaart = (id, event) => ({ id, role: 'assistant', content: event.vraag, clarification: event.opties, done: true })

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

async function openPage() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { settings: {}, user: 'gast' })) })
  const ws = FakeWebSocket.last
  await act(async () => { ws.open() })
  return { ws, textarea: container.querySelector('textarea.chat-input') }
}

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

async function klik(knop) {
  await act(async () => knop.click())
}

const andersKnoppen = () => [...container.querySelectorAll('button')].filter(b => b.getAttribute('aria-label')?.startsWith('Anders formuleren'))
const optie = label => [...container.querySelectorAll('button.clarification-btn')].find(b => b.textContent.endsWith(label))
// Wat de gebruiker de server laat doen: vragen en keuzes, niet de instellingen of de hartslag.
const verstuurd = ws => ws.sent.filter(m => m.action === 'message' || m.action === 'clarification_choice')

describe('"Anders formuleren" op de chatpagina', () => {
  it('zet na keuze en antwoord de vraag terug in het invoerveld en stuurt pas bij Enter', async () => {
    const { ws, textarea } = await openPage()
    await typ(textarea, VRAAG)
    await enter(textarea)
    await act(async () => { ws.emit(DEEL) })
    await klik(optie('hbo'))

    // Terwijl het antwoord op de keuze loopt, staan de opties dicht en is de weg terug er al.
    expect(optie('wo').disabled).toBe(true)
    expect(andersKnoppen()).toHaveLength(1)
    expect(andersKnoppen()[0].disabled).toBe(false)

    await act(async () => {
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'message_end', content: 'In het hbo …', bronnen: [] })
    })
    const voor = verstuurd(ws)
    expect(voor).toEqual([{ action: 'message', content: VRAAG }, { action: 'clarification_choice', choice: 'hbo' }])

    const [anders] = andersKnoppen()
    expect(anders.textContent).toBe('Anders formuleren')
    await klik(anders)

    expect(textarea.value).toBe(VRAAG)
    expect(document.activeElement).toBe(textarea)
    expect(verstuurd(ws)).toEqual(voor)

    // Nog eens: de oorspronkelijke vraag komt terug, ook over een aangepast concept heen.
    await typ(textarea, 'iets anders')
    await klik(anders)
    expect(textarea.value).toBe(VRAAG)
    expect(verstuurd(ws)).toEqual(voor)

    await enter(textarea)

    expect(verstuurd(ws)).toEqual([...voor, { action: 'message', content: VRAAG }])
    expect(textarea.value).toBe('')
    // De oude kaart houdt haar keuze.
    expect(optie('hbo').textContent).toBe('✓ hbo')
  })

  it('zet op de tweede kaart van een reeks de vraag terug, niet de keuze op de eerste', async () => {
    const { ws, textarea } = await openPage()
    await typ(textarea, VRAAG)
    await enter(textarea)
    await act(async () => { ws.emit(DEEL) })
    await klik(optie('hbo'))
    await act(async () => { ws.emit(JAAR) })

    const knoppen = andersKnoppen()
    expect(knoppen).toHaveLength(2)
    await klik(knoppen[1])

    expect(textarea.value).toBe(VRAAG)
    expect(verstuurd(ws).filter(m => m.action === 'message')).toHaveLength(1)
  })

  it('laat de knop weg bij een ingeladen gesprek dat met een kaart begint; de opties werken nog', async () => {
    persistCurrentChat('conv-a', [kaart(1, DEEL)])
    const { ws } = await openPage()

    expect(container.querySelectorAll('button.clarification-btn')).toHaveLength(3)
    expect(andersKnoppen()).toEqual([])

    await klik(optie('wo'))

    expect(verstuurd(ws)).toEqual([{ action: 'clarification_choice', choice: 'wo' }])
  })

  it('laat de knop weg als de chat vol is', async () => {
    const beurten = n => Array.from({ length: n }, (_, i) => [
      { id: 3 * i + 1, role: 'user', content: `Vraag ${i}`, done: true },
      kaart(3 * i + 2, DEEL),
    ]).flat()

    persistCurrentChat('conv-a', beurten(MAX_CHAT_TURNS - 1))
    await openPage()
    expect(andersKnoppen().length).toBeGreaterThan(0)
    act(() => root.unmount())
    container.remove()

    persistCurrentChat('conv-a', beurten(MAX_CHAT_TURNS))
    await openPage()
    expect(container.textContent).toContain('Chat is vol')
    expect(andersKnoppen()).toEqual([])
  })
})
