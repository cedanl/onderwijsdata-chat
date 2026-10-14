// @vitest-environment jsdom
// #364: onder het laatste antwoord staan tot drie vervolgvragen uit de catalogus. Een klik zet de
// vraag in het invoerveld; de gebruiker past haar aan of stuurt haar zelf. De "Verken …"-starters
// blijven hun vraag meteen sturen.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MAX_MESSAGE_CHARS } from '../constants'

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

// Eén mutabel chat-object: de test bepaalt wat useChat per render teruggeeft.
const chat = vi.hoisted(() => ({ messages: [], busy: false, send: null }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chat.messages, busy: chat.busy, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: chat.send, sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import ChatPage, { Message } from '../pages/ChatPage'
import Composer from '../components/Composer'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const VRAGEN = ['Welke instellingen trekken de meeste eerstejaars?', 'Hoe verdelen eerstejaars zich over de provincies?']
const antwoord = (id, extra = {}) => ({
  id, role: 'assistant', content: `Antwoord ${id}.`, tools: [], done: true, vervolgvragen: VRAGEN, ...extra,
})

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

beforeEach(() => {
  localStorage.clear()
  chat.messages = []
  chat.busy = false
  chat.send = vi.fn(() => true)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const groepen = () => [...container.querySelectorAll('[role="group"]')]
const groepNaam = groep => groep.getAttribute('aria-label') ??
  document.getElementById(groep.getAttribute('aria-labelledby'))?.textContent
const vervolgknoppen = () => groepen()
  .filter(g => groepNaam(g) === 'Vervolgvragen')
  .flatMap(g => [...g.querySelectorAll('button.suggested-btn')])

describe('Message: vervolgvragen onder het antwoord', () => {
  it('toont ze als knoppen in een groep met een naam; een klik geeft de vraag door en stuurt niets', async () => {
    const onVervolgvraag = vi.fn()
    const onSend = vi.fn()
    await render(createElement(Message, { msg: antwoord(1), onSend, onVervolgvraag, busy: false }))

    const knoppen = vervolgknoppen()
    expect(knoppen.map(b => b.textContent)).toEqual(VRAGEN)
    await act(async () => knoppen[1].click())

    expect(onVervolgvraag).toHaveBeenCalledWith(VRAGEN[1])
    expect(onSend).not.toHaveBeenCalled()
  })

  it('toont geen knoppen zonder handler (een ouder antwoord) of terwijl er iets loopt', async () => {
    await render(createElement(Message, { msg: antwoord(1), onSend: vi.fn(), busy: false }))
    expect(vervolgknoppen()).toEqual([])
    act(() => root.unmount())
    container.remove()

    await render(createElement(Message, { msg: antwoord(1), onSend: vi.fn(), onVervolgvraag: vi.fn(), busy: true }))
    expect(vervolgknoppen()).toEqual([])
  })
})

describe('Message: de "Verken …"-starters', () => {
  it('sturen hun vraag nog steeds meteen', async () => {
    const onSend = vi.fn()
    const msg = { id: 1, role: 'assistant', content: 'Hier zijn voorbeeldvragen over **instroom**:', done: true, starterQuestions: VRAGEN }
    await render(createElement(Message, { msg, onSend, busy: false }))

    const [groep] = groepen()
    expect(groepNaam(groep)).toBe('Voorbeeldvragen')
    await act(async () => groep.querySelector('button.suggested-btn').click())

    expect(onSend).toHaveBeenCalledWith(VRAGEN[0])
  })
})

describe('Composer: een gekozen vervolgvraag', () => {
  const props = {
    hasMessages: true, connected: true, busy: false, ready: true, models: [], selectedModel: '',
    onModelChange: () => {}, onStop: () => {}, max: MAX_MESSAGE_CHARS, rejectedDraft: null, clearRejectedDraft: () => {},
  }

  it('vervangt het concept, krijgt de focus en de hoogte van de tekst, en gaat niet uit', async () => {
    const hoogte = vi.spyOn(HTMLTextAreaElement.prototype, 'scrollHeight', 'get').mockReturnValue(72)
    const onSubmit = vi.fn(() => true)
    const clearPrefill = vi.fn()
    await render(createElement(Composer, { ...props, onSubmit }))
    const textarea = container.querySelector('textarea.chat-input')
    const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set
    await act(async () => {
      set.call(textarea, 'Een half concept')
      textarea.dispatchEvent(new Event('input', { bubbles: true }))
    })

    await act(async () => { root.render(createElement(Composer, { ...props, onSubmit, prefill: { tekst: VRAGEN[0] }, clearPrefill })) })

    expect(textarea.value).toBe(VRAGEN[0])
    expect(document.activeElement).toBe(textarea)
    expect(textarea.style.height).toBe('72px')
    expect(textarea.selectionStart).toBe(VRAGEN[0].length)
    expect(clearPrefill).toHaveBeenCalledTimes(1)
    expect(onSubmit).not.toHaveBeenCalled()
    hoogte.mockRestore()
  })
})

describe('ChatPage: alleen onder het laatste antwoord', () => {
  it('toont de vervolgvragen van het laatste antwoord, niet die van een ouder antwoord', async () => {
    chat.messages = [
      { id: 1, role: 'user', content: 'Vraag 1', done: true },
      antwoord(2),
      { id: 3, role: 'user', content: 'Vraag 2', done: true },
      antwoord(4),
      // Een grafiek komt als eigen bericht na het antwoord en neemt de vervolgvragen niet over.
      { id: 5, role: 'assistant', content: '', done: true, figures: [{ label: 'Instroom', json: '{"data":[],"layout":{}}' }] },
    ]
    await render(createElement(ChatPage, { settings: {}, user: 'gast' }))

    const laatste = [...container.querySelectorAll('.message.assistant')].find(m => m.textContent.includes('Antwoord 4.'))
    expect(vervolgknoppen()).toHaveLength(VRAGEN.length)
    expect(vervolgknoppen().every(b => laatste.contains(b))).toBe(true)
  })

  it('toont geen vervolgvragen terwijl er een vraag loopt', async () => {
    chat.messages = [{ id: 1, role: 'user', content: 'Vraag 1', done: true }, antwoord(2)]
    chat.busy = true
    await render(createElement(ChatPage, { settings: {}, user: 'gast' }))

    expect(vervolgknoppen()).toEqual([])
  })

  it('zet een gekozen vraag in het invoerveld zonder haar te sturen', async () => {
    chat.messages = [{ id: 1, role: 'user', content: 'Vraag 1', done: true }, antwoord(2)]
    await render(createElement(ChatPage, { settings: {}, user: 'gast' }))
    const textarea = container.querySelector('textarea.chat-input')

    await act(async () => vervolgknoppen()[0].click())

    expect(textarea.value).toBe(VRAGEN[0])
    expect(document.activeElement).toBe(textarea)
    expect(chat.send).not.toHaveBeenCalled()
  })
})
