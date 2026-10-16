// @vitest-environment jsdom
// #589 (mobiel B5, B7): de stopknop heeft een naam voor een schermlezer, en het klaar antwoord wordt als
// platte tekst aangekondigd; op het scherm blijft het opgemaakt.
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

const chat = vi.hoisted(() => ({ messages: [], busy: false }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chat.messages, busy: chat.busy, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import ChatPage from '../pages/ChatPage'
import ChatInputFooter from '../components/ChatInputFooter'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

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
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

// Toegankelijke naam zoals getByRole hem ziet: aria-label gaat voor de tekst.
const knopMetNaam = naam => [...container.querySelectorAll('button')]
  .find(b => (b.getAttribute('aria-label') ?? b.textContent.trim()) === naam)

describe('stopknop (#589, B5)', () => {
  const footer = busy => createElement(ChatInputFooter, {
    connected: true, busy, models: [], selectedModel: '', onModelChange: vi.fn(), onStop: vi.fn(),
    onSend: vi.fn(), canSend: true, max: MAX_MESSAGE_CHARS,
  })

  it('heeft tijdens genereren de naam "Stop genereren" en houdt zijn tooltip', async () => {
    await render(footer(true))
    const stop = knopMetNaam('Stop genereren')
    expect(stop).toBeDefined()
    expect(stop.getAttribute('title')).toBe('Stop genereren')
    expect(knopMetNaam('Verstuur bericht')).toBeUndefined()
  })

  it('is er niet als er niets loopt', async () => {
    await render(footer(false))
    expect(knopMetNaam('Stop genereren')).toBeUndefined()
    expect(knopMetNaam('Verstuur bericht')).toBeDefined()
  })
})

describe('aankondiging van het antwoord (#589, B7)', () => {
  const ANTWOORD = [
    '**Onderzoeksvraag:** hoeveel mbo-studenten zijn er?',
    '',
    '| Jaar | Aantal |',
    '| --- | --- |',
    '| 2023 | 518.940 |',
  ].join('\n')
  const vraag = { id: 1, role: 'user', content: 'Hoeveel mbo-studenten?', done: true }
  const antwoord = (extra = {}) => ({ id: 2, role: 'assistant', content: ANTWOORD, tools: [], done: true, ...extra })
  const aankondiging = () => container.querySelector('.sr-only[aria-live="polite"]').textContent

  it('leest een klaar antwoord voor zonder * en |, met alle woorden', async () => {
    chat.messages = [vraag, antwoord()]
    await render(createElement(ChatPage, { settings: {}, user: 'gast' }))

    const tekst = aankondiging()
    expect(tekst).not.toMatch(/[*|]/)
    for (const woord of ['Onderzoeksvraag', 'mbo-studenten', 'Jaar', 'Aantal', '2023', '518.940']) {
      expect(tekst).toContain(woord)
    }
  })

  it('laat het antwoord op het scherm opgemaakt', async () => {
    chat.messages = [vraag, antwoord()]
    await render(createElement(ChatPage, { settings: {}, user: 'gast' }))

    const bubbel = container.querySelector('.message.assistant .message-bubble')
    expect(bubbel.querySelector('strong').textContent).toBe('Onderzoeksvraag:')
    expect(bubbel.querySelector('table')).not.toBeNull()
  })

  it('blijft leeg terwijl er iets loopt', async () => {
    chat.messages = [vraag, antwoord()]
    chat.busy = true
    await render(createElement(ChatPage, { settings: {}, user: 'gast' }))
    expect(aankondiging()).toBe('')
  })

  it('blijft leeg bij een antwoord dat nog niet klaar is', async () => {
    chat.messages = [vraag, antwoord({ done: false })]
    await render(createElement(ChatPage, { settings: {}, user: 'gast' }))
    expect(aankondiging()).toBe('')
  })

  it('blijft leeg als het laatste bericht een vraag is', async () => {
    chat.messages = [vraag, antwoord(), { id: 3, role: 'user', content: 'Nog een vraag', done: true }]
    await render(createElement(ChatPage, { settings: {}, user: 'gast' }))
    expect(aankondiging()).toBe('')
  })
})
