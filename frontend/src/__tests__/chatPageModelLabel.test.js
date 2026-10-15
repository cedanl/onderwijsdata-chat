// @vitest-environment jsdom
// #565: onder een vast antwoord uit code (scope-uitleg, weigering, sentinelantwoord) staat geen
// "Antwoord van <model>": geen model schreef het. Onder een gewoon antwoord blijft het staan.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

const api = vi.hoisted(() => ({
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  fetchConversations: vi.fn().mockResolvedValue([]),
  putConversation: vi.fn().mockResolvedValue({}),
  fetchSettingsConfig: vi.fn().mockResolvedValue({
    models: [{ id: 'claude-sonnet', name: 'Sonnet' }], default_model: 'claude-sonnet',
  }),
}))
vi.mock('../api', async importOriginal => ({ ...await importOriginal(), ...api }))
vi.mock('react-plotly.js', () => ({ default: () => null }))
vi.mock('react-markdown', () => ({ default: ({ children }) => children }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], busy: false, withBufferedText: all => all, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false,
    reportProgress: null, reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast: () => () => {},
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_CURRENT_CHAT, STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
})

async function mountMet(antwoord) {
  const vraag = { id: 1, role: 'user', content: 'Hoeveel leerlingen zaten in groep 8?', model: 'claude-sonnet', done: true }
  localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id: 'c1', messages: [vraag, antwoord] }))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { user: 'u' })) })
}

describe('modellabel onder een antwoord (#565)', () => {
  it('noemt geen model onder een vast antwoord uit code', async () => {
    await mountMet({ id: 2, role: 'assistant', content: 'Deze chat beantwoordt alleen vragen over het mbo, hbo en wo.', done: true, vast: true })
    expect(container.textContent).toContain('Deze chat beantwoordt alleen vragen')
    expect(container.querySelector('.message-model')).toBeNull()
  })

  it('noemt het model onder een gewoon antwoord', async () => {
    await mountMet({ id: 2, role: 'assistant', content: 'Er waren 1200 studenten.', done: true })
    expect(container.querySelector('.message-model')?.textContent).toBe('Antwoord van Sonnet')
  })
})
