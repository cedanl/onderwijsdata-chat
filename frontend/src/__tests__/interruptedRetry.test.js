// @vitest-environment jsdom
// #547: "Verbinding verbroken — antwoord onvolledig" gaf geen weg terug behalve de vraag
// opnieuw typen (WCAG 3.3.3). De melding krijgt één knop "Probeer opnieuw", die de vraag
// ervoor opnieuw stuurt via hetzelfde pad als de andere herhaalknoppen, zonder ander model.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

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
vi.mock('react-plotly.js', () => ({ default: () => null }))
vi.mock('react-markdown', () => ({ default: ({ children }) => children }))

const chat = vi.hoisted(() => ({ messages: [], busy: false, send: null, sendSettings: null }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chat.messages, busy: chat.busy, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false,
    reportProgress: { steps: 0, label: null }, reportSpec: null, send: chat.send, sendClarification: vi.fn(),
    sendSettings: chat.sendSettings, sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast: () => {},
  }),
}))

import ChatPage, { Message } from '../pages/ChatPage'
import { STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const MELDING = 'Verbinding verbroken — antwoord onvolledig'
const VRAAG = 'Hoeveel vacatures zijn er in de zorg?'
const ONDERBROKEN = { id: 2, role: 'assistant', content: 'Er zijn', done: true, interrupted: true }

let root
let container

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
})

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

const probeerOpnieuw = () => [...container.querySelectorAll('button')].filter(b => b.textContent === 'Probeer opnieuw')
const renderMessage = props => render(createElement(Message, { onSend: vi.fn(), busy: false, ...props }))

describe('Message: "Probeer opnieuw" bij een afgebroken antwoord (#547)', () => {
  it('toont de melding met precies één knop "Probeer opnieuw"', async () => {
    await renderMessage({ msg: ONDERBROKEN, herhaal: vi.fn() })
    expect(container.querySelector('.message-stopped').textContent).toContain(MELDING)
    expect(probeerOpnieuw()).toHaveLength(1)
  })

  it('stuurt de vraag opnieuw via herhaal en verder niets', async () => {
    const herhaal = vi.fn()
    const onSend = vi.fn()
    await renderMessage({ msg: ONDERBROKEN, herhaal, onSend })
    await act(async () => { probeerOpnieuw()[0].click() })
    expect(herhaal).toHaveBeenCalledTimes(1)
    expect(onSend).not.toHaveBeenCalled()
  })

  it('is een gewone knop: bereikbaar met Tab, te bedienen met Enter en Spatie', async () => {
    await renderMessage({ msg: ONDERBROKEN, herhaal: vi.fn() })
    const [knop] = probeerOpnieuw()
    expect(knop.tagName).toBe('BUTTON')
    expect(knop.type).toBe('button')
    expect(knop.tabIndex).not.toBe(-1)
    knop.focus()
    expect(document.activeElement).toBe(knop)
  })

  it('heeft de klasse met het tikdoel van de andere tekstknoppen', async () => {
    await renderMessage({ msg: ONDERBROKEN, herhaal: vi.fn() })
    expect(probeerOpnieuw()[0].classList.contains('message-continue')).toBe(true)
  })

  it('is dicht zolang er een antwoord loopt', async () => {
    await renderMessage({ msg: ONDERBROKEN, herhaal: vi.fn(), busy: true })
    expect(probeerOpnieuw()[0].disabled).toBe(true)
  })

  it('ontbreekt zonder vraag ervoor; de melding blijft', async () => {
    await renderMessage({ msg: ONDERBROKEN, herhaal: null })
    expect(container.textContent).toContain(MELDING)
    expect(probeerOpnieuw()).toEqual([])
  })

  it.each([
    ['een gewoon antwoord', { content: 'Het zijn er 12.345.' }],
    ['een gestopt antwoord', { content: 'Het zijn', stopped: true }],
    ['een afgekapt antwoord', { content: 'Het zijn', truncated: true }],
    ['een leeg antwoord', { empty: true }],
    ['een foutmelding', { content: 'Er ging iets mis.', isError: true }],
  ])('ontbreekt bij %s', async (_, velden) => {
    await renderMessage({ msg: { id: 2, role: 'assistant', done: true, ...velden }, herhaal: vi.fn() })
    expect(probeerOpnieuw()).toEqual([])
  })
})

describe('ChatPage: "Probeer opnieuw" stuurt de vraag ervoor (#547)', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem(STORAGE_TOKEN, 'tok')
    chat.messages = [{ id: 1, role: 'user', content: VRAAG, done: true }, ONDERBROKEN]
    chat.busy = false
    chat.send = vi.fn(() => true)
    chat.sendSettings = vi.fn()
  })

  it('stuurt de vraag van de gebruiker opnieuw, zonder ander model', async () => {
    await render(createElement(ChatPage, { user: 'tester' }))
    chat.sendSettings.mockClear()
    await act(async () => { probeerOpnieuw()[0].click() })
    expect(chat.send).toHaveBeenCalledTimes(1)
    expect(chat.send).toHaveBeenCalledWith(VRAAG)
    expect(chat.sendSettings).not.toHaveBeenCalled()
  })

  it('heeft geen knop als het gesprek met het afgebroken antwoord begint', async () => {
    chat.messages = [ONDERBROKEN]
    await render(createElement(ChatPage, { user: 'tester' }))
    expect(container.textContent).toContain(MELDING)
    expect(probeerOpnieuw()).toEqual([])
  })
})
