// @vitest-environment jsdom
// #594: tijdens het streamen verschoof de layout op een telefoon (CLS ≈ 0,09). De voortgang stond onder de
// berichten en zakte bij elke stap mee met de redeneerkaart en de grafiek; de actierij kwam pas na het antwoord
// terug en duwde het invoerveld 50 px omhoog. Nu delen voortgang en acties één statusrij boven het invoerveld.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

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

const chat = vi.hoisted(() => ({ messages: [], busy: false }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chat.messages, busy: chat.busy, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false,
    reportProgress: { steps: 0, label: null }, reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast: () => {},
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const beurt = (...tools) => [
  { id: 1, role: 'user', content: 'Hoeveel mbo-studenten zijn er in Utrecht?', done: true },
  { id: 2, role: 'assistant', content: '', done: false, tools },
]
const stap = { name: 'get_cbs_data', label: 'CBS data opgehaald', done: false }

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chat.busy = true
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
})

async function mountChat() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { user: 'tester' })) })
}

describe('ChatPage: één statusrij boven het invoerveld (#594)', () => {
  const rij = () => container.querySelector('.chat-input-area > .chat-statusrij')

  it('toont tijdens een antwoord de voortgang in de statusrij, niet tussen de berichten', async () => {
    chat.messages = beurt(stap)
    await mountChat()
    expect(rij().querySelector('.run-progress')).not.toBeNull()
    expect(container.querySelector('.chat-messages .run-progress')).toBeNull()
    expect(rij().querySelector('.chat-actions')).toBeNull()
  })

  it('toont na het antwoord de acties op dezelfde plek', async () => {
    chat.busy = false
    chat.messages = [beurt(stap)[0], { ...beurt(stap)[1], content: 'Er zijn 12.340 studenten.', done: true, tools: [{ ...stap, done: true }] }]
    await mountChat()
    expect(rij().querySelector('.chat-actions')).not.toBeNull()
    expect(rij().querySelector('.run-progress')).toBeNull()
  })

  it('ontbreekt zolang er geen bericht is', async () => {
    chat.busy = false
    chat.messages = []
    await mountChat()
    expect(container.querySelector('.chat-statusrij')).toBeNull()
  })
})

describe('statusrij in de stylesheet (#594)', () => {
  const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
  const regel = selector => css.match(new RegExp(`(?:^|})\\s*${selector.replace(/\./g, '\\.')}\\s*{([^}]*)}`))?.[1]

  // Zo hoog als de actierij (een 44px-knop plus 6px marge): de wissel tussen voortgang en acties verschuift niets.
  it('heeft een vaste minimumhoogte gelijk aan de actierij', () => {
    expect(regel('.chat-statusrij')).toContain('min-height: 50px')
    expect(regel('.chat-actions')).toContain('margin-bottom: 6px')
  })

  // Gecentreerd schoof elk langer staplabel de pil opzij.
  it('zet de voortgang links, over de volle breedte van de rij', () => {
    expect(regel('.chat-statusrij .run-progress-group')).toContain('align-self: stretch')
  })
})
