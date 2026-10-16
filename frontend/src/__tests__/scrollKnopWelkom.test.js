// @vitest-environment jsdom
// #592 (mobiel B12): de knop "Scroll naar beneden" stond ook op het lege welkomstscherm en lag daar over
// een suggestie. Alleen een gevuld gesprek heeft hem nodig.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { STORAGE_CURRENT_CHAT } from '../constants'

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

const chat = vi.hoisted(() => ({ messages: [] }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chat.messages, busy: false, rejectedDraft: null, clearRejectedDraft: () => {}, thinking: false,
    connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

import ChatPage from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

// Een IntersectionObserver die de test bedient: meld() zegt elke actieve observer of de eindmarkering in beeld is.
let observers
class FakeObserver {
  constructor(callback) { this.callback = callback }
  observe() { observers.add(this) }
  unobserve() {}
  disconnect() { observers.delete(this) }
}

let root
let container

async function render() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { settings: {}, user: 'gast' })) })
}

async function meld(inBeeld) {
  await act(async () => { for (const o of [...observers]) o.callback([{ isIntersecting: inBeeld }]) })
}

const knop = () => container.querySelector('.scroll-to-bottom-btn')
const vraag = { id: 1, role: 'user', content: 'Hoeveel mbo-studenten?', done: true }
const antwoord = { id: 2, role: 'assistant', content: 'Er zijn er 518.940.', tools: [], done: true }

beforeEach(() => {
  localStorage.clear()
  chat.messages = []
  observers = new Set()
  globalThis.IntersectionObserver = FakeObserver
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('knop "Scroll naar beneden" (#592)', () => {
  it('staat niet op het lege welkomstscherm, ook niet als het einde van de lijst buiten beeld is', async () => {
    await render()
    expect(container.querySelector('.chat-welcome')).not.toBeNull()
    await meld(false)
    expect(knop()).toBeNull()
  })

  it('staat in een gevuld gesprek als het einde buiten beeld is, en gaat weg onderaan', async () => {
    chat.messages = [vraag, antwoord]
    await render()

    await meld(false)
    expect(knop()).not.toBeNull()
    await meld(true)
    expect(knop()).toBeNull()
  })

  it('werkt ook in een teruggezet gesprek, en verdwijnt bij een nieuw gesprek', async () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id: 'c1', messages: [vraag, antwoord] }))
    await render()

    await meld(false)
    expect(knop()).not.toBeNull()

    const nieuw = [...container.querySelectorAll('button')].find(b => b.textContent.trim() === 'Nieuw gesprek')
    await act(async () => nieuw.click())
    expect(container.querySelector('.chat-welcome')).not.toBeNull()
    expect(knop()).toBeNull()
    await meld(false)
    expect(knop()).toBeNull()
  })
})
