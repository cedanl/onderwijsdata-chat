// @vitest-environment jsdom
// #983 (besluit 09-11): onder een antwoord staan geen duimpjes meer, ook niet met feedback aan. De link Feedback
// (#600) en de vragenlijst op rapporten (#250) blijven; die hangen niet aan een antwoord.
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

async function mountMetAntwoord() {
  const vraag = { id: 1, role: 'user', content: 'Hoeveel studenten zitten in het hbo?', model: 'claude-sonnet', done: true }
  const antwoord = { id: 2, role: 'assistant', content: 'Er waren 1200 studenten.', done: true }
  localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({ id: 'c1', messages: [vraag, antwoord] }))
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { user: 'u', feedbackEnabled: true })) })
}

describe('geen duimpjes onder een antwoord (#983)', () => {
  it('toont geen duimknoppen, ook niet met feedback aan', async () => {
    await mountMetAntwoord()
    const labels = [...container.querySelectorAll('button')].map(b => b.getAttribute('aria-label'))
    expect(labels).not.toContain('Goed antwoord')
    expect(labels).not.toContain('Fout antwoord')
    expect(container.textContent).not.toMatch(/👍|👎/)
  })

  it('laat onder het antwoord geen leeg element staan: het modellabel sluit de kolom af', async () => {
    await mountMetAntwoord()
    const kolom = container.querySelector('.message.assistant .message-model').parentElement
    expect(kolom.lastElementChild.className).toBe('message-model')
  })

  it('heeft geen aanroep naar het verwijderde eindpunt', async () => {
    const api = await vi.importActual('../api')
    expect(Object.keys(api)).not.toContain('fetchAnswerFeedback')
    expect(Object.keys(api)).not.toContain('postAnswerFeedback')
  })
})
