// @vitest-environment jsdom
// #600: één Feedback-link naast de privacylink opent een kort algemeen formulier: een idee, probleem of
// compliment los van een antwoord of rapport.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import FeedbackLink from '../components/FeedbackLink'
import { paginaVan } from '../components/AlgemeneFeedbackModal'
import HomePage from '../pages/HomePage'
import ChatPage from '../pages/ChatPage'
import RapportenPage from '../pages/RapportenPage'
import SettingsModal from '../components/SettingsModal'

const api = vi.hoisted(() => ({ postAlgemeneFeedback: vi.fn() }))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))
vi.mock('../api', () => {
  const pending = () => new Promise(() => {})
  return {
    fetchCatalogCounts: pending,
    fetchConversations: pending,
    fetchSettingsConfig: pending,
    fetchWorkbooks: pending,
    putConversation: pending,
    renameConversationApi: pending,
    deleteConversationApi: pending,
    fetchAnswerFeedback: pending,
    postAnswerFeedback: pending,
    postAlgemeneFeedback: api.postAlgemeneFeedback,
  }
})
vi.mock('../components/ScrollToBottom', () => ({ default: () => null }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [], busy: false, rejectedDraft: null, clearRejectedDraft: vi.fn(), thinking: false, toasts: [],
    connected: true, resetting: false, historyDataKeys: [], reportBusy: false, reportProgress: null,
    reportSpec: null, send: vi.fn(), sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(),
    stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: vi.fn(),
  }),
}))

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver ??= class { observe() {} unobserve() {} disconnect() {} }
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
  api.postAlgemeneFeedback.mockReset()
  window.history.pushState({}, '', '/chat')
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

const dialog = () => document.querySelector('[role="dialog"][aria-labelledby]')
const knop = (tekst, binnen = container) => [...binnen.querySelectorAll('button')].find(b => b.textContent === tekst)
const veld = () => dialog().querySelector('textarea')
const verstuur = () => knop('Versturen', dialog())

async function typ(tekst) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
  await act(async () => {
    setter.call(veld(), tekst)
    veld().dispatchEvent(new Event('input', { bubbles: true }))
  })
}

async function open() {
  await render(createElement(FeedbackLink))
  await act(async () => { knop('Feedback').click() })
}

describe('het algemene feedbackformulier', () => {
  it('opent vanuit de link, met de bewaartekst en zonder verplichte soort', async () => {
    await open()
    expect(dialog().getAttribute('aria-modal')).toBe('true')
    expect(dialog().textContent).toContain('Het team krijgt je bericht')
    expect([...dialog().querySelectorAll('input[type="radio"]')].map(r => r.value)).toEqual(['idee', 'probleem', 'compliment'])
    expect(verstuur().disabled).toBe(true)
  })

  it('verstuurt tekst, soort en de pagina, en bedankt in een statusregio', async () => {
    api.postAlgemeneFeedback.mockResolvedValue({ ok: true })
    await open()
    await act(async () => { dialog().querySelector('input[value="probleem"]').click() })
    await typ('De grafiek laadt niet op mijn telefoon')
    await act(async () => { verstuur().click() })

    expect(api.postAlgemeneFeedback).toHaveBeenCalledWith({ tekst: 'De grafiek laadt niet op mijn telefoon', soort: 'probleem', pagina: '/chat' })
    expect(dialog().querySelector('[role="status"]').textContent).toContain('Bedankt voor je feedback!')
    expect(veld()).toBeNull()
  })

  it('stuurt geen soort mee als er geen gekozen is', async () => {
    api.postAlgemeneFeedback.mockResolvedValue({ ok: true })
    await open()
    await typ('Fijne tool')
    await act(async () => { verstuur().click() })
    expect(api.postAlgemeneFeedback).toHaveBeenCalledWith({ tekst: 'Fijne tool', soort: null, pagina: '/chat' })
  })

  it('houdt de tekst en meldt de fout als versturen mislukt', async () => {
    api.postAlgemeneFeedback.mockRejectedValue(new Error('HTTP 429'))
    await open()
    await typ('Een idee')
    await act(async () => { verstuur().click() })
    expect(dialog().querySelector('[role="alert"]').textContent).toContain('HTTP 429')
    expect(veld().value).toBe('Een idee')
  })

  it('verstuurt niets met alleen spaties', async () => {
    await open()
    await typ('   ')
    expect(verstuur().disabled).toBe(true)
  })
})

describe('paginaVan', () => {
  it('geeft de route, nooit een query of een onbekend pad', () => {
    expect(paginaVan('/chat')).toBe('/chat')
    expect(paginaVan('/rapporten')).toBe('/rapporten')
    expect(paginaVan('/')).toBe('/')
    expect(paginaVan('/a/b')).toBe('/')
    expect(paginaVan('/Chat')).toBe('/')
  })
})

const PLEKKEN = [
  ['de footer van de startpagina', aan => createElement(MemoryRouter, null, createElement(HomePage, { feedbackEnabled: aan }))],
  ['de disclaimer van de chat', aan => createElement(MemoryRouter, null, createElement(ChatPage, { settings: {}, user: 'gast', feedbackEnabled: aan }))],
  ['de rapportenpagina', aan => createElement(MemoryRouter, null, createElement(RapportenPage, { settings: {}, feedbackEnabled: aan }))],
  ['de instellingen', aan => createElement(SettingsModal, { settings: {}, onSave: vi.fn(), onClose: vi.fn(), feedbackEnabled: aan })],
]

describe.each(PLEKKEN)('de Feedback-link in %s', (_, element) => {
  it('opent het formulier', async () => {
    await render(element(true))
    const link = knop('Feedback') ?? knop('Geef feedback')
    expect(link.getAttribute('type')).toBe('button')
    await act(async () => { link.click() })
    expect(dialog()).not.toBeNull()
  })

  it('ontbreekt als feedback uit staat', async () => {
    await render(element(false))
    expect(knop('Feedback') ?? knop('Geef feedback')).toBeUndefined()
  })
})
