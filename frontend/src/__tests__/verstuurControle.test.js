// @vitest-environment jsdom
// #774, door de hele chatpagina met de echte useChat: knoppen die buiten de composer om een vraag of keuze
// versturen (suggesties, opnieuw sturen, een verduidelijking) houden zich aan dezelfde voorwaarden als de
// composer, en een weigering staat onder het invoerveld in plaats van stil niets te doen.
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
import { NavSlotContext } from '../navSlot'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const DEEL = { type: 'clarification', vraag: 'Welk deel van het onderwijs wil je bekijken?', opties: ['mbo', 'hbo', 'wo'] }
const VOL = 'Chat is vol: begin een nieuw gesprek'

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

// Met een plek in de navigatie, zoals in de app: daar staat op een telefoon de knop van de lade (#596).
async function openPage() {
  container = document.createElement('div')
  document.body.appendChild(container)
  const slot = document.createElement('div')
  container.appendChild(slot)
  root = createRoot(container.appendChild(document.createElement('div')))
  await act(async () => {
    root.render(createElement(NavSlotContext.Provider, { value: slot }, createElement(ChatPage, { settings: {}, user: 'gast' })))
  })
  const ws = FakeWebSocket.last
  await act(async () => { ws.open() })
  return { ws, textarea: container.querySelector('textarea.chat-input') }
}

async function vraag(textarea, tekst) {
  const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set
  await act(async () => {
    set.call(textarea, tekst)
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await act(async () => { textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })) })
}

const klik = knop => act(async () => knop.click())
const optie = label => [...container.querySelectorAll('button.clarification-btn')].find(b => b.textContent.endsWith(label))
const suggestie = () => container.querySelector('.suggested-btn')
// De suggesties in de zijbalk staan per categorie ingeklapt.
const openSuggesties = () => klik(container.querySelector('.suggested-category-btn'))
const opnieuwSturen = () => container.querySelector('.resend-btn')
const melding = () => container.querySelector('.send-notice')?.textContent ?? ''
const verstuurd = ws => ws.sent.filter(m => m.action === 'message' || m.action === 'clarification_choice')
// Gesprekken van n afgeronde vragen, met antwoord.
const beurten = n => Array.from({ length: n }, (_, i) => [
  { id: 2 * i + 1, role: 'user', content: `Vraag ${i}`, done: true },
  { id: 2 * i + 2, role: 'assistant', content: `Antwoord ${i}`, done: true },
]).flat()

describe('verstuurknoppen buiten de composer (#774)', () => {
  it('een verduidelijking zonder verbinding blijft open en zegt waarom er niets ging', async () => {
    const { ws, textarea } = await openPage()
    await vraag(textarea, 'Hoeveel studenten zijn er?')
    await act(async () => { ws.emit(DEEL) })
    await act(async () => { ws.finishClose() })

    await klik(optie('hbo'))

    expect(verstuurd(ws)).toEqual([{ action: 'message', content: 'Hoeveel studenten zijn er?' }])
    expect(optie('hbo').textContent).toBe('hbo')
    expect(optie('hbo').disabled).toBe(false)
    expect(melding()).toBe('Geen verbinding')
  })

  it('een verduidelijking met verbinding gaat weg en sluit de kaart', async () => {
    const { ws, textarea } = await openPage()
    await vraag(textarea, 'Hoeveel studenten zijn er?')
    await act(async () => { ws.emit(DEEL) })

    await klik(optie('hbo'))

    expect(verstuurd(ws).at(-1)).toEqual({ action: 'clarification_choice', choice: 'hbo' })
    expect(optie('hbo').textContent).toBe('✓ hbo')
    expect(optie('wo').disabled).toBe(true)
  })

  it('bij een volle chat versturen suggestie en opnieuw sturen niets en zeggen ze waarom', async () => {
    persistCurrentChat('conv-a', beurten(MAX_CHAT_TURNS))
    const { ws } = await openPage()
    await openSuggesties()

    await klik(suggestie())
    expect(verstuurd(ws)).toEqual([])
    expect(melding()).toBe(VOL)

    await klik(opnieuwSturen())
    expect(verstuurd(ws)).toEqual([])
    expect(melding()).toBe(VOL)
  })

  it('met ruimte gaat een suggestie gewoon weg', async () => {
    persistCurrentChat('conv-a', beurten(MAX_CHAT_TURNS - 1))
    const { ws } = await openPage()
    await openSuggesties()
    const tekst = suggestie().textContent

    await klik(suggestie())

    expect(verstuurd(ws)).toEqual([{ action: 'message', content: tekst }])
    expect(melding()).toBe('')
  })

  it('een verduidelijking op de laatste vraag gaat ook bij een volle chat: ze maakt die vraag af', async () => {
    persistCurrentChat('conv-a', beurten(MAX_CHAT_TURNS - 1))
    const { ws, textarea } = await openPage()
    await vraag(textarea, 'De laatste vraag')
    await act(async () => { ws.emit(DEEL) })
    expect(container.textContent).toContain('Chat is vol')

    await klik(optie('wo'))

    expect(verstuurd(ws).at(-1)).toEqual({ action: 'clarification_choice', choice: 'wo' })
  })
})

// Op een telefoon ligt de open lade over het invoerveld: een weigering vanuit de lade staat dan als melding erboven,
// niet onzichtbaar onder de lade (#774, gemeten op 390 px).
describe('weigering vanuit de lade op een telefoon (#774)', () => {
  const echteMatchMedia = window.matchMedia
  beforeEach(() => {
    window.matchMedia = q => ({ matches: true, media: q, addEventListener() {}, removeEventListener() {} })
  })
  afterEach(() => { window.matchMedia = echteMatchMedia })

  it('toont de reden als melding boven de lade, en niet nog eens onder het invoerveld', async () => {
    persistCurrentChat('conv-a', beurten(MAX_CHAT_TURNS))
    const { ws } = await openPage()
    await klik(container.querySelector('[aria-label="Gesprekken en suggesties"]'))
    await openSuggesties()

    await klik(container.querySelector('.chat-sidebar .suggested-btn'))

    expect(verstuurd(ws)).toEqual([])
    expect(container.querySelector('.toast')?.textContent).toBe(VOL)
    expect(melding()).toBe('')
  })
})
