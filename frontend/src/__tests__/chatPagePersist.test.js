// @vitest-environment jsdom
// #511: niet bij elk tekstfragment het hele gesprek naar localStorage, en een volle
// opslag faalt niet langer stil.
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

const chatState = vi.hoisted(() => ({ messages: [], busy: false, addToast: null, buffered: '' }))
// Stabiele identiteit, zoals de echte addToast uit useChat (useCallback).
const stableToast = vi.hoisted(() => (...a) => chatState.addToast?.(...a))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: chatState.messages, busy: chatState.busy,
    // Zoals de echte: het lopende (laatste) antwoord plus wat nog in de deltabuffer zit (#520).
    withBufferedText: all => chatState.buffered
      ? all.with(-1, { ...all.at(-1), content: all.at(-1).content + chatState.buffered })
      : all, rejectedDraft: null, clearRejectedDraft: () => {},
    thinking: false, connected: true, resetting: false, historyDataKeys: 0, toasts: [], reportBusy: false,
    reportProgress: null, reportSpec: null, send: vi.fn(() => true), sendClarification: vi.fn(),
    sendSettings: vi.fn(), sendHistory: vi.fn(), stop: vi.fn(), generateReport: vi.fn(), cancelReport: vi.fn(),
    clearReport: vi.fn(), clear: vi.fn(), startNewConversation: vi.fn(), addToast: stableToast,
  }),
}))

import ChatPage from '../pages/ChatPage'
import { STORAGE_CONVERSATIONS, STORAGE_CURRENT_CHAT, STORAGE_TOKEN } from '../constants'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

let root
let container

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem(STORAGE_TOKEN, 'tok')
  chatState.messages = [{ id: 1, role: 'user', content: 'Hoeveel studenten?', done: true }]
  chatState.busy = false
  chatState.addToast = null
  chatState.buffered = ''
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  vi.restoreAllMocks()
})

async function render() {
  await act(async () => { root.render(createElement(ChatPage, { user: 'u' })) })
}

async function mountChat() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await render()
}

const chatSetItems = (spy) => spy.mock.calls.filter(([key]) => key === STORAGE_CURRENT_CHAT)

describe('opslaan per afgerond antwoord (#511)', () => {
  it('schrijft tijdens een stream niet per tekstfragment', async () => {
    await mountChat()
    const spy = vi.spyOn(Storage.prototype, 'setItem')

    chatState.busy = true
    const antwoord = { id: 2, role: 'assistant', content: '', tools: [], done: false }
    for (let i = 0; i < 25; i++) {
      antwoord.content += `fragment ${i} `
      chatState.messages = [chatState.messages[0], { ...antwoord }]
      await render()
    }
    expect(chatSetItems(spy)).toHaveLength(0)

    chatState.busy = false
    chatState.messages = [chatState.messages[0], { ...antwoord, done: true }]
    await render()

    const schrijfacties = chatSetItems(spy)
    expect(schrijfacties).toHaveLength(1)
    expect(schrijfacties[0][1]).toContain('fragment 24')
  })

  it('bewaart bij het verbergen van de tab ook een nog streamend antwoord', async () => {
    await mountChat()
    chatState.busy = true
    chatState.messages = [chatState.messages[0], { id: 2, role: 'assistant', content: 'half antw', tools: [], done: false }]
    await render()
    localStorage.removeItem(STORAGE_CURRENT_CHAT)

    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })

    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toContain('half antw')
  })

  it('bewaart bij het verbergen ook wat nog in de deltabuffer zit (#520)', async () => {
    await mountChat()
    chatState.busy = true
    chatState.messages = [chatState.messages[0], { id: 2, role: 'assistant', content: 'half', tools: [], done: false }]
    chatState.buffered = ' antwoord in de buffer'
    await render()
    localStorage.removeItem(STORAGE_CURRENT_CHAT)

    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })

    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toContain('half antwoord in de buffer')
  })

  it('bewaart bij pagehide ook als de tab nog zichtbaar heet (Safari/iOS)', async () => {
    await mountChat()
    chatState.busy = true
    chatState.messages = [chatState.messages[0], { id: 2, role: 'assistant', content: 'half', tools: [], done: false }]
    chatState.buffered = ' en de rest'
    await render()
    localStorage.removeItem(STORAGE_CURRENT_CHAT)

    expect(document.visibilityState).toBe('visible')
    await act(async () => { window.dispatchEvent(new Event('pagehide')) })

    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toContain('half en de rest')
  })

  it('bewaart niet bij visibilitychange naar zichtbaar', async () => {
    await mountChat()
    chatState.busy = true
    chatState.messages = [chatState.messages[0], { id: 2, role: 'assistant', content: 'half', tools: [], done: false }]
    await render()
    localStorage.removeItem(STORAGE_CURRENT_CHAT)

    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })

    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toBeNull()
  })

  it('meldt een volle opslag één keer in plaats van stil te falen', async () => {
    const meldingen = []
    chatState.addToast = (msg) => meldingen.push(msg)
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key) => {
      if (key === STORAGE_CURRENT_CHAT) throw new DOMException('kapot', 'QuotaExceededError')
    })
    await mountChat()

    chatState.messages = [...chatState.messages, { id: 2, role: 'assistant', content: 'antwoord', done: true }]
    await render()
    chatState.messages = [...chatState.messages, { id: 3, role: 'assistant', content: 'nog een', done: true }]
    await render()

    expect(meldingen).toEqual(['De lokale opslag is vol: dit gesprek wordt niet lokaal bewaard.'])
  })

  it('meldt op paginaniveau dat grafieken na verversen ontbreken (#521)', async () => {
    const meldingen = []
    chatState.addToast = (msg, level) => meldingen.push([msg, level])
    const echt = Storage.prototype.setItem
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (key, value) {
      if (key === STORAGE_CURRENT_CHAT && value.includes('"figures"')) throw new DOMException('vol', 'QuotaExceededError')
      return echt.call(this, key, value)
    })
    chatState.messages = [...chatState.messages, { id: 2, role: 'assistant', content: 'kijk', figures: ['{}'], done: true }]
    await mountChat()

    expect(meldingen).toEqual([[GRAFIEKEN_MELDING, 'warning']])
    expect(JSON.parse(localStorage.getItem(STORAGE_CURRENT_CHAT)).onvolledig).toBe(true)
  })
})

// #521: de gesprekslijst in localStorage faalde stil, en een herstel zonder grafieken leek compleet.
const LIJST_MELDING = 'De lokale opslag is vol: de gesprekslijst kan na verversen korter zijn.'
const GRAFIEKEN_MELDING = 'De lokale opslag is bijna vol: grafieken van dit gesprek komen na verversen niet terug.'
const ONVOLLEDIG_MELDING = 'Dit gesprek is niet volledig bewaard: grafieken ontbreken na verversen.'

function lijstVol() {
  const echt = Storage.prototype.setItem
  return vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (key, value) {
    if (key === STORAGE_CONVERSATIONS) throw new DOMException('vol', 'QuotaExceededError')
    return echt.call(this, key, value)
  })
}

describe('volle opslag van de gesprekslijst (#521)', () => {
  let meldingen
  beforeEach(() => {
    meldingen = []
    chatState.addToast = (msg, level) => meldingen.push([msg, level])
  })

  it('meldt het wanneer de lijst niet past', async () => {
    lijstVol()
    await mountChat()
    expect(meldingen).toEqual([[LIJST_MELDING, 'warning']])
  })

  it('meldt het ook bij de lijst die de server bij het openen stuurt', async () => {
    chatState.messages = []
    api.fetchConversations.mockResolvedValueOnce([{ id: 's1', title: 'Van de server', timestamp: 1 }])
    lijstVol()
    await mountChat()
    expect(meldingen).toEqual([[LIJST_MELDING, 'warning']])
  })

  it('meldt twee mislukte schrijfacties één keer', async () => {
    const spy = lijstVol()
    await mountChat()
    // Een tweede afgerond antwoord: de opslag na elk antwoord loopt pas weer als busy terugvalt.
    chatState.busy = true
    chatState.messages = [...chatState.messages, { id: 2, role: 'assistant', content: 'antwoord', done: false }]
    await render()
    chatState.busy = false
    chatState.messages = chatState.messages.with(-1, { ...chatState.messages.at(-1), done: true })
    await render()

    expect(spy.mock.calls.filter(([key]) => key === STORAGE_CONVERSATIONS).length).toBeGreaterThanOrEqual(2)
    expect(meldingen.filter(([m]) => m === LIJST_MELDING)).toHaveLength(1)
  })

  it('meldt het ook bij het verwijderen van een gesprek', async () => {
    chatState.messages = []
    api.fetchConversations.mockResolvedValueOnce([{ id: 's1', title: 'Weg ermee', timestamp: 1 }])
    await mountChat()
    lijstVol()

    await act(async () => { container.querySelector('[aria-label="Verwijder gesprek Weg ermee"]').click() })
    await act(async () => { document.querySelector('.confirm-destructive').click() })

    expect(meldingen).toEqual([[LIJST_MELDING, 'warning']])
  })

  it('meldt de lijst los van het open gesprek', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('vol', 'QuotaExceededError') })
    await mountChat()
    expect(meldingen.map(([m]) => m).sort()).toEqual(
      [LIJST_MELDING, 'De lokale opslag is vol: dit gesprek wordt niet lokaal bewaard.'].sort())
  })
})

describe('herstel na verversen (#521)', () => {
  let meldingen
  beforeEach(() => {
    meldingen = []
    chatState.addToast = (msg, level) => meldingen.push([msg, level])
    chatState.messages = []
  })

  it('zegt het wanneer het herstelde gesprek zonder grafieken is bewaard', async () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({
      id: 'c1', messages: [{ id: 1, role: 'user', content: 'vraag', done: true }], onvolledig: true,
    }))
    await mountChat()
    await render()
    expect(meldingen).toEqual([[ONVOLLEDIG_MELDING, 'warning']])
  })

  it('zegt niets bij een volledig bewaard gesprek', async () => {
    localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify({
      id: 'c1', messages: [{ id: 1, role: 'user', content: 'vraag', done: true }],
    }))
    await mountChat()
    expect(meldingen).toEqual([])
  })
})

describe('opslaan bij unmount (#521)', () => {
  let meldingen
  beforeEach(() => {
    meldingen = []
    chatState.addToast = (msg, level) => meldingen.push([msg, level])
  })

  async function nieuwAntwoordNietOpgeslagen() {
    await mountChat()
    // Tijdens het streamen wordt niet opgeslagen; pas de unmount bewaart dit antwoord.
    chatState.busy = true
    chatState.messages = [...chatState.messages, { id: 2, role: 'assistant', content: 'laatste woord', done: false }]
    await render()
  }

  it('schrijft de lijst, wist het open gesprek en meldt niets', async () => {
    await nieuwAntwoordNietOpgeslagen()
    const fout = vi.spyOn(console, 'error')

    await act(async () => root.unmount())
    root = null

    expect(JSON.parse(localStorage.getItem(STORAGE_CONVERSATIONS))).toHaveLength(1)
    expect(api.putConversation).toHaveBeenLastCalledWith(expect.any(String), expect.objectContaining({
      messages: expect.arrayContaining([expect.objectContaining({ content: 'laatste woord' })]),
    }))
    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toBeNull()
    expect(meldingen).toEqual([])
    expect(fout).not.toHaveBeenCalled()
  })

  it('meldt ook bij een volle opslag niets meer na unmount', async () => {
    await nieuwAntwoordNietOpgeslagen()
    lijstVol()
    const fout = vi.spyOn(console, 'error')

    await act(async () => root.unmount())
    root = null

    expect(localStorage.getItem(STORAGE_CURRENT_CHAT)).toBeNull()
    expect(meldingen).toEqual([])
    expect(fout).not.toHaveBeenCalled()
  })
})
