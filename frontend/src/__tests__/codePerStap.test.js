// @vitest-environment jsdom
// #595: op een telefoon vulde de code van alle stappen, in één blok onder de stappen van "Redenering", het scherm
// vóór het antwoord. Nu staat de code bij haar eigen stap, ingeklapt achter "Bekijk code"; desktop blijft gelijk.
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
import { NARROW_SCREEN } from '../hooks/useMediaQuery'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }

const beurt = (...tools) => [
  { id: 1, role: 'user', content: 'Hoeveel mbo-studenten zijn er in Utrecht?', done: true },
  { id: 2, role: 'assistant', content: '', done: false, tools },
]
const CODE = 'import cbsodata\nrijen = cbsodata.get_data("85353NED", filters="Perioden eq \'2024SJ00\' and RegioS eq \'PV26\'")'
const stappen = [
  { name: 'search_catalog', label: 'Catalogus doorzocht', done: true },
  { name: 'get_cbs_data', label: 'CBS data opgehaald', done: true, snippet: CODE },
  { name: 'query_data', label: 'Data gefilterd', done: false },
]
let smal = true

let root
let container

beforeEach(() => {
  window.matchMedia = q => ({ matches: smal && q === NARROW_SCREEN, media: q, addEventListener() {}, removeEventListener() {} })
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

describe('Redenering: code per stap op een telefoon (#595)', () => {
  beforeEach(() => { chat.messages = beurt(...stappen) })

  it('zet de code onder haar eigen stap, ingeklapt achter "Bekijk code"', async () => {
    smal = true
    await mountChat()
    const stap = [...container.querySelectorAll('.reasoning-step')].find(s => s.textContent.includes('CBS data opgehaald'))
    const code = stap.querySelector('details.reasoning-step-code')
    expect(code).not.toBeNull()
    expect(code.open).toBe(false)
    expect(code.querySelector('summary').textContent).toBe('Bekijk code')
    expect(code.textContent).toContain('cbsodata.get_data')
  })

  it('geeft een stap zonder code geen knop, en toont geen los codeblok onder de stappen', async () => {
    smal = true
    await mountChat()
    expect(container.querySelectorAll('.reasoning-step-code')).toHaveLength(1)
    expect(container.querySelector('.reasoning-snippets')).toBeNull()
    // De stapregels zelf blijven zichtbaar: de voortgang tijdens het wachten (#547).
    expect(container.querySelectorAll('.reasoning-step')).toHaveLength(3)
  })

  it('breekt lange regels af in plaats van opzij te scrollen', async () => {
    smal = true
    await mountChat()
    expect(container.querySelector('.reasoning-step-code code').style.whiteSpace).toBe('pre-wrap')
  })

  it('laat een breed scherm zoals het was: alle code in één blok onder de stappen', async () => {
    smal = false
    await mountChat()
    expect(container.querySelector('.reasoning-step-code')).toBeNull()
    expect(container.querySelector('.reasoning-snippets').textContent).toContain('cbsodata.get_data')
  })
})
