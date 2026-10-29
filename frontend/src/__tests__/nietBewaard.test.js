// @vitest-environment jsdom
// #785: een mislukte opslag van gesprek of rapport was onzichtbaar. Het gesprek stond al in de zijbalk, en een
// rapport was na clearReport() weg. Nu staat er een melding tot het lukt, met een nieuwe poging; een rapport kan
// dan ook gedownload worden. Een 413 (te groot) is niet met opnieuw proberen op te lossen en zegt dat.
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

const chatState = vi.hoisted(() => ({ messages: [], reportSpec: null }))
const stableToast = vi.hoisted(() => () => () => {})
// Stabiel en met het effect van de echte: de spec is daarna weg.
const clearReport = vi.hoisted(() => () => { chatState.reportSpec = null })
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chatState.messages, busy: false, withBufferedText: all => all, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false,
    reportProgress: null, reportSpec: chatState.reportSpec, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport, clear: vi.fn(), startNewConversation: vi.fn(), addToast: stableToast,
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const vraag = { id: 1, role: 'user', content: 'Hoeveel studenten?', done: true }
const antwoord = { id: 2, role: 'assistant', content: 'In 2024 waren er 470.000.', done: true }
const fout = status => Object.assign(new Error(`API ${status}`), { status })

let root
let container
let openRapport

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chatState.messages = [vraag, antwoord]
  chatState.reportSpec = null
  openRapport = vi.fn()
  api.putConversation.mockReset().mockResolvedValue({})
  api.putWorkbook.mockReset().mockResolvedValue({})
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
})

async function mount() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { user: 'u', openRapport })) })
}

const melding = () => container.querySelector('.niet-bewaard')
const knop = tekst => [...container.querySelectorAll('.niet-bewaard button')].find(b => b.textContent === tekst)

describe('een gesprek dat de server niet kreeg (#785)', () => {
  it('meldt een netwerkfout tot een nieuwe poging lukt', async () => {
    api.putConversation.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await mount()

    expect(melding().getAttribute('role')).toBe('alert')
    expect(melding().textContent).toContain('Dit gesprek is niet bewaard op de server.')

    await act(async () => { knop('Opnieuw proberen').click() })

    expect(api.putConversation).toHaveBeenCalledTimes(2)
    expect(melding()).toBeNull()
  })

  it('zegt bij een 413 dat het gesprek te groot is, zonder knop die niets oplost', async () => {
    api.putConversation.mockRejectedValueOnce(fout(413))
    await mount()

    expect(melding().textContent).toContain('te groot om op de server te bewaren')
    expect(knop('Opnieuw proberen')).toBeUndefined()
  })

  it('zegt niets als de opslag lukt', async () => {
    await mount()
    expect(api.putConversation).toHaveBeenCalledOnce()
    expect(melding()).toBeNull()
  })

  it('zegt niets als de gebruiker intussen uitlogde', async () => {
    let faal
    api.putConversation.mockReturnValueOnce(new Promise((_, reject) => { faal = reject }))
    await mount()
    localStorage.removeItem(STORAGE_TOKEN)
    await act(async () => { faal(new TypeError('Failed to fetch')) })
    expect(melding()).toBeNull()
  })
})

describe('een rapport dat de server niet kreeg (#785)', () => {
  const spec = { title: 'Instroom hbo', auteur: 'u', datum: '29-10-2026', secties: [] }

  it('blijft staan met opnieuw proberen en downloaden; een geslaagde poging opent het rapport', async () => {
    api.putWorkbook.mockRejectedValueOnce(fout(503))
    chatState.reportSpec = spec
    await mount()

    expect(melding().textContent).toContain('Dit rapport is niet bewaard op de server.')
    expect(knop('Download als HTML')).toBeDefined()
    expect(openRapport).not.toHaveBeenCalled()

    await act(async () => { knop('Opnieuw proberen').click() })

    expect(api.putWorkbook).toHaveBeenCalledTimes(2)
    expect(api.putWorkbook.mock.calls[1][0]).toBe(api.putWorkbook.mock.calls[0][0])
    expect(openRapport).toHaveBeenCalledWith(expect.objectContaining({ title: 'Instroom hbo' }))
    expect(melding()).toBeNull()
  })

  it('biedt bij een 413 alleen downloaden', async () => {
    api.putWorkbook.mockRejectedValueOnce(fout(413))
    chatState.reportSpec = spec
    await mount()

    expect(melding().textContent).toContain('Dit rapport is te groot om op de server te bewaren.')
    expect(knop('Opnieuw proberen')).toBeUndefined()
    expect(knop('Download als HTML')).toBeDefined()
  })
})
