// @vitest-environment jsdom
// #648: "Genereer rapport" zonder verbinding of tijdens een nieuw gesprek ziet er uit als niet beschikbaar
// (aria-disabled), maar een tik komt nog bij checkReportStart aan, dat zegt waarom het niet start. Alleen een lopend
// rapport zet de knop echt uit; tijdens een antwoord staat hij er niet.
// #751: kan het rapport starten, dan komt eerst een veld met de onderzoeksvraag, ingevuld en aan te passen.
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

// Een gesprek met een antwoord met data: daar hoort een rapportknop bij.
const MET_DATA = [
  { id: 1, role: 'user', content: 'Hoeveel mbo-studenten per provincie?', done: true },
  {
    id: 2, role: 'assistant', content: 'Op de kaart staat het aantal per provincie.', done: true,
    tools: [{ name: 'query_data', label: 'Data gefilterd', done: true, snippet: '41230' }],
  },
]

const chat = vi.hoisted(() => ({ staat: {}, generateReport: null, checkReportStart: null }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: MET_DATA, busy: false, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [],
    reportBusy: false, reportProgress: { steps: 0, label: null }, reportSpec: null, send: vi.fn(),
    sendClarification: vi.fn(), sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(),
    checkReportStart: chat.checkReportStart, generateReport: chat.generateReport, cancelReport: vi.fn(), clearReport: vi.fn(), clear: vi.fn(),
    startNewConversation: vi.fn(), addToast: () => {}, withBufferedText: m => m,
    ...chat.staat,
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chat.staat = {}
  chat.checkReportStart = vi.fn(() => true)
  chat.generateReport = vi.fn(() => true)
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
})

async function mountChat(staat) {
  chat.staat = staat
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(ChatPage, { user: 'tester' })) })
}

const knop = () => container.querySelector('.make-rapport-btn')
const dialoog = () => container.querySelector('.onderzoeksvraag-dialoog')
const veld = () => dialoog().querySelector('textarea')
const dialoogKnop = tekst => [...dialoog().querySelectorAll('button')].find(b => b.textContent === tekst)

describe('de rapportknop (#648)', () => {
  it('is gewoon beschikbaar met verbinding en zonder lopend werk', async () => {
    await mountChat({})
    expect(knop().hasAttribute('aria-disabled')).toBe(false)
    expect(knop().disabled).toBe(false)
    expect(knop().textContent).toBe('Genereer rapport')
  })

  it.each([
    ['zonder verbinding', { connected: false }],
    ['terwijl een nieuw gesprek start', { resetting: true }],
  ])('%s: aria-disabled, niet disabled, en een klik komt nog aan, zonder veld', async (_naam, staat) => {
    chat.checkReportStart = vi.fn(() => false)
    await mountChat(staat)
    expect(knop().getAttribute('aria-disabled')).toBe('true')
    expect(knop().hasAttribute('disabled')).toBe(false)

    await act(async () => { knop().click() })

    expect(chat.checkReportStart).toHaveBeenCalledTimes(1)
    expect(dialoog()).toBeNull()
    expect(chat.generateReport).not.toHaveBeenCalled()
  })

  it('is uit terwijl het rapport wordt gemaakt', async () => {
    await mountChat({ reportBusy: true })
    expect(knop().disabled).toBe(true)
    expect(knop().textContent).toBe('Rapport wordt gegenereerd…')
    await act(async () => { knop().click() })
    expect(chat.checkReportStart).not.toHaveBeenCalled()
    expect(chat.generateReport).not.toHaveBeenCalled()
  })

  it('staat er niet tijdens een antwoord', async () => {
    await mountChat({ busy: true })
    expect(knop()).toBeNull()
  })
})

const VRAAG = 'Hoe is de trend van instroom in B Computing Science, B Informatica en B Computer Science?'
const WO = 'Hoe ontwikkelt de instroom in de wo-bachelors B Computing Science, B Informatica en B Computer Science zich?'
const BIJGESTUURD = [
  { id: 1, role: 'user', content: VRAAG, done: true },
  { id: 2, role: 'assistant', content: 'De instroom daalt.', done: true, tools: MET_DATA[1].tools },
  { id: 3, role: 'user', content: "Ik wil het alleen zien voor universitaire bachelor's.", done: true },
  { id: 4, role: 'assistant', content: `**Onderzoeksvraag:** ${WO}\n\nOok in het wo daalt de instroom.`, done: true, tools: MET_DATA[1].tools },
]

async function typ(tekst) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
  await act(async () => {
    setter.call(veld(), tekst)
    veld().dispatchEvent(new Event('input', { bubbles: true }))
  })
}

const toets = (key, extra = {}) => act(async () => {
  veld().dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...extra }))
})

describe('het veld met de onderzoeksvraag (#751)', () => {
  it('staat ingevuld met de onderzoeksvraag zoals die in het gesprek groeide, met de focus erin', async () => {
    await mountChat({ messages: BIJGESTUURD })
    await act(async () => { knop().click() })

    expect(dialoog().getAttribute('role')).toBe('dialog')
    const label = dialoog().querySelector(`label[for="${veld().id}"]`)
    expect(label.textContent).toBe('Onderzoeksvraag van het rapport')
    expect(veld().value).toBe(WO)
    expect(document.activeElement).toBe(veld())
    expect(veld().selectionStart).toBe(WO.length)
    // Nog geen rapport: dat start pas met Genereer.
    expect(chat.generateReport).not.toHaveBeenCalled()
  })

  it('zonder regel Onderzoeksvraag de eerste vraag', async () => {
    await mountChat({})
    await act(async () => { knop().click() })
    expect(veld().value).toBe('Hoeveel mbo-studenten per provincie?')
  })

  it('Genereer stuurt de aangepaste tekst mee en sluit het veld', async () => {
    await mountChat({ messages: BIJGESTUURD })
    await act(async () => { knop().click() })
    await typ(`${WO} Alleen voltijd.`)

    await act(async () => { dialoogKnop('Genereer').click() })

    expect(chat.generateReport).toHaveBeenCalledExactlyOnceWith('tester', `${WO} Alleen voltijd.`)
    expect(dialoog()).toBeNull()
  })

  it('Enter genereert; Shift+Enter niet', async () => {
    await mountChat({ messages: BIJGESTUURD })
    await act(async () => { knop().click() })

    await toets('Enter', { shiftKey: true })
    expect(chat.generateReport).not.toHaveBeenCalled()

    await toets('Enter')
    expect(chat.generateReport).toHaveBeenCalledExactlyOnceWith('tester', WO)
  })

  it('een leeg veld stuurt een lege vraag: de server neemt dan de eerste', async () => {
    await mountChat({ messages: BIJGESTUURD })
    await act(async () => { knop().click() })
    await typ('   ')
    await act(async () => { dialoogKnop('Genereer').click() })
    expect(chat.generateReport).toHaveBeenCalledExactlyOnceWith('tester', '')
  })

  it.each([
    ['Escape', () => act(async () => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })) })],
    ['Annuleren', () => act(async () => { dialoogKnop('Annuleren').click() })],
  ])('%s sluit zonder rapport', async (_naam, sluit) => {
    await mountChat({ messages: BIJGESTUURD })
    await act(async () => { knop().click() })
    await sluit()
    expect(dialoog()).toBeNull()
    expect(chat.generateReport).not.toHaveBeenCalled()
  })

  it('start het rapport toch niet (verbinding net weg), dan blijft het veld open met de tekst', async () => {
    chat.generateReport = vi.fn(() => false)
    await mountChat({ messages: BIJGESTUURD })
    await act(async () => { knop().click() })
    await typ('Alleen voltijd')
    await act(async () => { dialoogKnop('Genereer').click() })
    expect(chat.generateReport).toHaveBeenCalledTimes(1)
    expect(veld().value).toBe('Alleen voltijd')
  })
})
